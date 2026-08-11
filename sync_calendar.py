#!/usr/bin/env python3
"""
Sync .ics calendar attachments from a Fastmail inbox into a Fastmail calendar.

How it works:
  1. Connect to Fastmail over IMAP, search for unread mail matching a subject filter.
  2. Pull any .ics / text-calendar attachment from each matching message.
  3. Parse every VEVENT in the attachment.
  4. For each VEVENT, look up its UID in the target CalDAV calendar:
       - if found  -> overwrite the existing event (update)
       - if absent -> create a new event
  5. Mark the source email as read (\\Seen) so it isn't reprocessed next run.

Calendar writes use CalDAV because Fastmail has not yet opened up JMAP access
for calendars (JMAP mail/contacts are available, but calendar access is
CalDAV-only per Fastmail's own developer docs as of 2026).

Required environment variables (set these as GitHub Actions secrets):
  FASTMAIL_EMAIL          Full Fastmail address, e.g. you@fastmail.com
  FASTMAIL_APP_PASSWORD   An app password with Mail + DAV (CalDAV) scopes enabled
                           (Settings -> Privacy & Security -> App Passwords)

Optional environment variables:
  IMAP_SUBJECT_FILTER     Only process mail with this subject (default: "WorkCalendarExport")
  CALENDAR_NAME           Name of the target Fastmail calendar (default: first/primary calendar)
  IMAP_HOST               Default: imap.fastmail.com
  CALDAV_URL              Default: https://caldav.fastmail.com/dav/ (trailing slash matters)
"""

import email
import imaplib
import os
import sys
from email.header import decode_header

import caldav
from icalendar import Calendar as ICalCalendar

IMAP_HOST = os.environ.get("IMAP_HOST", "imap.fastmail.com")
CALDAV_URL = os.environ.get("CALDAV_URL", "https://caldav.fastmail.com/dav/")
SUBJECT_FILTER = os.environ.get("IMAP_SUBJECT_FILTER", "WorkCalendarExport")
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


def main():
    imap = imaplib.IMAP4_SSL(IMAP_HOST)
    imap.login(FASTMAIL_EMAIL, FASTMAIL_APP_PASSWORD)
    imap.select("INBOX")

    search_criteria = f'(UNSEEN SUBJECT "{SUBJECT_FILTER}")'
    status, data = imap.search(None, search_criteria)
    if status != "OK":
        log("IMAP search failed.")
        sys.exit(1)

    msg_ids = data[0].split()
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
        try:
            for ics_bytes in get_ics_attachments(msg):
                cal = ICalCalendar.from_ical(ics_bytes)
                for component in cal.walk("VEVENT"):
                    upsert_event(calendar, component)
                    event_count += 1
        except Exception as e:
            log(f"  ERROR processing message {msg_id!r}: {e}")
            continue  # leave unread so it's retried next run

        log(f"  synced {event_count} event(s)")
        imap.store(msg_id, "+FLAGS", "\\Seen")

    imap.logout()


if __name__ == "__main__":
    main()
