# Fastmail calendar sync

Syncs `.ics` calendar attachments arriving by email into a Fastmail calendar,
creating or updating events by their iCal `UID` so nothing gets duplicated.

## Setup

1. **Create a Fastmail app password**
   Settings → Privacy & Security → App Passwords → New App Password.
   Give it access to **Mail** and **DAV (CardDAV, CalDAV, WebDAV)**.

2. **Create this repo on GitHub** (can be private) and add these two files
   at the paths shown: `sync_calendar.py` and
   `.github/workflows/sync-calendar.yml`.

3. **Add repo secrets**
   Repo → Settings → Secrets and variables → Actions → New repository secret:
   - `FASTMAIL_EMAIL` — your full Fastmail address
   - `FASTMAIL_APP_PASSWORD` — the app password from step 1

4. **(Optional) Adjust the filters**
   In `sync-calendar.yml`, uncomment and set:
   - `IMAP_SUBJECT_FILTER` — only process mail with this subject
     (defaults to `"WorkCalendarExport"`, matching the Power Automate flow's
     subject line)
   - `CALENDAR_NAME` — which Fastmail calendar to write to
     (defaults to your first/primary calendar if unset)

5. **Test it**
   Go to the Actions tab → "Sync Fastmail calendar from email" → Run workflow,
   to trigger it manually instead of waiting for the schedule. Check the logs
   to confirm it found and processed the email, then check your calendar.

## Notes

- The workflow runs every 15 minutes via cron. GitHub may delay scheduled
  runs by a few minutes under load — not an issue for this use case.
- GitHub disables scheduled workflows automatically after 60 days of repo
  inactivity (no commits). If that happens, just re-enable it from the
  Actions tab, or push a trivial commit occasionally.
- The script only processes **unread** mail matching the subject filter, and
  marks messages read only after a successful sync — so a transient failure
  just gets retried on the next run rather than silently dropping events.
- No changes to the Power Automate flow are needed; the script parses
  `METHOD:PUBLISH` exports as-is.
