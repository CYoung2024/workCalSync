#!/usr/bin/env python3
"""
Sync .ics calendar attachments from a Fastmail inbox into a Fastmail calendar.

How it works:
  1. Connect to Fastmail over IMAP, search for unread mail matching a subject filter.
  2. Pull any .ics / text-calendar attachment from each matching message.
  3. Repair and escape the attachment's text (see sanitize_ics_text()), since
     the Power Automate flow writes SUMMARY/LOCATION unescaped, then parse
     every VEVENT in it.
  4. For each VEVENT, look up its UID in the target CalDAV calendar:
       - if found  -> overwrite the existing event (update)
       - if absent -> create a new event
  5. Delete synced events the attachment says are gone (see delete_stale_events()).
     Each export declares which events it covers:
       X-WORKCAL-SCOPE:SNAPSHOT  every event in the window (weekly flow)
       X-WORKCAL-SCOPE:ID        one event or recurring series (change flow),
                                 named by X-WORKCAL-SCOPE-ID
     Synced events in that scope that aren't in the attachment are deleted.
     Only events carrying X-WORKCAL-ID (i.e. written by this sync) are touched.
  6. Mark the source email as read (\\Seen) so it isn't reprocessed next run.

Calendar writes use CalDAV because Fastmail has not yet opened up JMAP access
for calendars (JMAP mail/contacts are available, but calendar access is
CalDAV-only per Fastmail's own developer docs as of 2026).

Required environment variables (set these as GitHub Actions secrets):
  FASTMAIL_EMAIL          Full Fastmail address, e.g. you@fastmail.com
  FASTMAIL_APP_PASSWORD   An app password with Mail + DAV (CalDAV) scopes enabled
                           (Settings -> Privacy & Security -> App Passwords)

Optional environment variables:
  IMAP_SUBJECT_FILTER     Only process mail whose subject contains this (default: "WorkCalendar",
                           which matches both "WorkCalendarExport" and "WorkCalendarChange")
  CALENDAR_NAME           Name of the target Fastmail calendar (default: first/primary calendar)
  IMAP_HOST               Default: imap.fastmail.com
  CALDAV_URL              Default: https://caldav.fastmail.com/dav/ (trailing slash matters)
"""

import email
import imaplib
import os
import sys
from datetime import date, datetime, timedelta, timezone
from email.header import decode_header

import caldav
from icalendar import Calendar as ICalCalendar

IMAP_HOST = os.environ.get("IMAP_HOST", "imap.fastmail.com")
CALDAV_URL = os.environ.get("CALDAV_URL", "https://caldav.fastmail.com/dav/")
SUBJECT_FILTER = os.environ.get("IMAP_SUBJECT_FILTER", "WorkCalendar")
CALENDAR_NAME = os.environ.get("CALENDAR_NAME")  # None = use first calendar found

FASTMAIL_EMAIL = os.environ["FASTMAIL_EMAIL"]
FASTMAIL_APP_PASSWORD = os.environ["FASTMAIL_APP_PASSWORD"]


def log(msg):
    print(msg, flush=True)


def decode_mime_words(s):
    parts = decode_header(s)
    return "".join(
        (t.decode(enc or "utf-8") if isinstance(t, bytes) else t) for t, enc in parts
    )


def get_ics_attachments(msg):
    """Yield raw bytes for every .ics / text-calendar attachment in an email.message.Message."""
    for part in msg.walk():
        content_type = part.get_content_type()
        filename = part.get_filename()
        is_ics = (
            content_type in ("text/calendar", "application/ics")
            or (filename and filename.lower().endswith(".ics"))
        )
        if is_ics:
            payload = part.get_payload(decode=True)
            if payload:
                yield payload


# Property lines the Power Automate flow's Compose steps can produce, in the
# order they appear. Used by sanitize_ics_text() to tell a genuine property
# line apart from a stray continuation line (see below).
_KNOWN_ICS_PREFIXES = (
    "BEGIN:",
    "END:",
    "VERSION:",
    "PRODID:",
    "METHOD:",
    "UID:",
    "DTSTAMP:",
    "DTSTART",  # also matches "DTSTART;VALUE=DATE:" for all-day events
    "DTEND",
    "SUMMARY:",
    "LOCATION:",
    "TRANSP:",
    "STATUS:",
    "X-WORKCAL-",
)

# The two fields the flow fills from free-text Outlook data (event subject
# and location), which is why they're the only ones that can contain a raw
# comma, semicolon, backslash, or newline.
_ESCAPED_ICS_FIELDS = ("SUMMARY:", "LOCATION:")


def _escape_ics_text(value):
    """Escape a raw TEXT value the way RFC 5545 (iCalendar) requires.

    Order matters: backslashes must be doubled first, so the backslashes
    this adds for ';', ',' and newlines aren't themselves re-escaped.
    """
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def sanitize_ics_text(text):
    """Repair and escape the .ics text the Power Automate flow sends.

    The flow's Compose steps (see power-automate/expressions/compose-vevent.txt)
    write SUMMARY and LOCATION straight from the event's subject and location,
    with no escaping. RFC 5545 requires backslash, semicolon, comma, and any
    line break in a TEXT value to be backslash-escaped. An unescaped line
    break is the more serious of the two: it splits the value across
    "content lines" that this parser can no longer tell apart from a genuine
    property, so it's repaired first, then every TEXT value is escaped.

    NOTE: this assumes the incoming text has no escaping of its own, which
    matches the flow as documented. If the flow is ever changed to escape
    these fields itself (see docs/1-weekly-flow.md), this function should
    be removed rather than left in place, or it will double-escape.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    # Merge lines that aren't a recognized property back into the previous
    # line -- these are subject/location text that happened to contain a
    # raw newline, which the flow writes as an actual line break.
    merged = []
    for line in lines:
        if not merged or line.startswith(_KNOWN_ICS_PREFIXES):
            merged.append(line)
        else:
            merged[-1] += "\n" + line

    repaired = []
    for line in merged:
        for prefix in _ESCAPED_ICS_FIELDS:
            if line.startswith(prefix):
                line = prefix + _escape_ics_text(line[len(prefix):])
                break
        repaired.append(line)

    return "\r\n".join(repaired)


def find_calendar(client, name):
    # Fastmail's server doesn't answer the current-user-principal discovery
    # PROPFIND that client.principal() tries by default, so point it at the
    # known principal URL directly instead.
    principal_url = f"https://caldav.fastmail.com/dav/principals/user/{FASTMAIL_EMAIL}/"
    principal = client.principal(url=principal_url)
    calendars = principal.calendars()
    if not calendars:
        raise RuntimeError("No calendars found on this Fastmail account.")
    if name:
        for cal in calendars:
            if cal.name == name:
                return cal
        available = ", ".join(c.name for c in calendars)
        raise RuntimeError(f"Calendar '{name}' not found. Available calendars: {available}")
    return calendars[0]


def upsert_event(calendar, component):
    """Create or update a single VEVENT (an icalendar component) in the given CalDAV calendar."""
    uid = str(component.get("uid"))
    summary = str(component.get("summary", "(no title)"))

    wrapped = ICalCalendar()
    wrapped.add("prodid", "-//fastmail-calendar-sync//EN")
    wrapped.add("version", "2.0")
    wrapped.add_component(component)
    ics_text = wrapped.to_ical().decode("utf-8")

    try:
        existing = calendar.event_by_uid(uid)
    except caldav.lib.error.NotFoundError:
        existing = None
    except AttributeError:
        # Fallback for older/newer caldav versions with a different exception path
        existing = None
        for ev in calendar.events():
            try:
                if str(ev.icalendar_component.get("uid")) == uid:
                    existing = ev
                    break
            except Exception:
                continue

    if existing:
        existing.data = ics_text
        existing.save()
        log(f"  updated: {summary} ({uid})")
    else:
        calendar.save_event(ics_text)
        log(f"  created: {summary} ({uid})")


def _as_utc(value):
    """Turn an icalendar DTSTART/DTEND value into an aware UTC datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    return None


def _parse_window(cal):
    start = datetime.strptime(str(cal.get("X-WORKCAL-WINDOW-START")), "%Y%m%dT%H%M%SZ")
    end = datetime.strptime(str(cal.get("X-WORKCAL-WINDOW-END")), "%Y%m%dT%H%M%SZ")
    return start.replace(tzinfo=timezone.utc), end.replace(tzinfo=timezone.utc)


def delete_stale_events(calendar, cal, kept_uids):
    """Delete synced events in this export's scope that the export no longer lists.

    Only events that start inside the export's window are considered, minus a
    one-day margin at the far end, so edge cases around the window boundary
    are left alone rather than deleted by mistake. The next export catches them.
    """
    scope = str(cal.get("X-WORKCAL-SCOPE", "")).upper()
    if scope not in ("SNAPSHOT", "ID"):
        return 0  # older export without scope information: add/update only
    scope_id = str(cal.get("X-WORKCAL-SCOPE-ID", ""))
    if scope == "ID" and not scope_id:
        raise RuntimeError("X-WORKCAL-SCOPE:ID export is missing X-WORKCAL-SCOPE-ID")

    window_start, window_end = _parse_window(cal)
    window_end -= timedelta(days=1)

    deleted = 0
    for ev in calendar.events():
        try:
            comp = ev.icalendar_component
        except Exception:
            continue
        outlook_id = str(comp.get("X-WORKCAL-ID", ""))
        if not outlook_id:
            continue  # not written by this sync
        if str(comp.get("uid")) in kept_uids:
            continue
        if scope == "ID" and scope_id not in (outlook_id, str(comp.get("X-WORKCAL-SERIES-ID", ""))):
            continue
        dtstart = comp.get("dtstart")
        start = _as_utc(dtstart.dt) if dtstart is not None else None
        if start is None or not (window_start <= start < window_end):
            continue
        ev.delete()
        deleted += 1
        log(f"  deleted: {comp.get('summary', '(no title)')} ({comp.get('uid')})")
    return deleted


def main():
    imap = imaplib.IMAP4_SSL(IMAP_HOST)
    imap.login(FASTMAIL_EMAIL, FASTMAIL_APP_PASSWORD)
    imap.select("INBOX")

    search_criteria = f'(UNSEEN SUBJECT "{SUBJECT_FILTER}")'
    status, data = imap.search(None, search_criteria)
    if status != "OK":
        log("IMAP search failed.")
        sys.exit(1)

    # Oldest first, so a later change always wins over an earlier one.
    msg_ids = sorted(data[0].split(), key=int)
    if not msg_ids:
        log("No new matching mail found.")
        imap.logout()
        return

    log(f"Found {len(msg_ids)} matching message(s).")

    dav_client = caldav.DAVClient(
        url=CALDAV_URL, username=FASTMAIL_EMAIL, password=FASTMAIL_APP_PASSWORD
    )
    calendar = find_calendar(dav_client, CALENDAR_NAME)
    log(f"Target calendar: {calendar.name}")

    for msg_id in msg_ids:
        # BODY.PEEK avoids marking the message \Seen until we confirm success below
        status, msg_data = imap.fetch(msg_id, "(BODY.PEEK[])")
        if status != "OK":
            log(f"Failed to fetch message {msg_id!r}, skipping.")
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)
        subject = decode_mime_words(msg.get("Subject", ""))
        log(f"Processing: {subject}")

        event_count = 0
        deleted_count = 0
        try:
            for ics_bytes in get_ics_attachments(msg):
                ics_text = sanitize_ics_text(ics_bytes.decode("utf-8", errors="replace"))
                cal = ICalCalendar.from_ical(ics_text)
                kept_uids = set()
                for component in cal.walk("VEVENT"):
                    upsert_event(calendar, component)
                    kept_uids.add(str(component.get("uid")))
                    event_count += 1
                deleted_count += delete_stale_events(calendar, cal, kept_uids)
        except Exception as e:
            log(f"  ERROR processing message {msg_id!r}: {e}")
            continue  # leave unread so it's retried next run

        log(f"  synced {event_count} event(s), deleted {deleted_count}")
        imap.store(msg_id, "+FLAGS", "\\Seen")

    imap.logout()


if __name__ == "__main__":
    main()
