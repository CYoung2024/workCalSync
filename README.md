# workCalSync

Mirror a work Outlook / Microsoft 365 calendar into a personal Fastmail
calendar, without any admin access or third-party sync service.

```
┌──────────────────────┐   every 6h    ┌───────────────┐   every 2 hours  ┌────────────────────┐
│ Power Automate flow  │ ── email ───▶ │ Fastmail inbox│ ◀── IMAP ─────── │ GitHub Actions     │
│ (work M365 account)  │  calendar.ics │               │                  │ sync_calendar.py   │
└──────────────────────┘               └───────────────┘                  └─────────┬──────────┘
  reads the next 90 days                                                            │ CalDAV
  of your work calendar                                                             ▼
                                                                          ┌────────────────────┐
                                                                          │ Fastmail calendar  │
                                                                          └────────────────────┘
```

1. **Power Automate** (runs inside your work tenant) reads the next 90 days of
   your work calendar four times a day, builds a `.ics` file, and emails it to
   your personal Fastmail address with the subject `WorkCalendarExport`.
2. **GitHub Actions** runs `sync_calendar.py` every 2 hours. It logs in to
   Fastmail over IMAP, picks up any unread `WorkCalendarExport` emails, and
   writes each event into a Fastmail calendar over CalDAV, matching on the
   event's `UID`. Existing events are updated in place, so nothing gets duplicated.
3. The email is marked read only after a successful sync, so a failed run is
   retried automatically next time.

## What you need

- A work Microsoft 365 account that can use **Power Automate** with the
  standard **Office 365 Outlook** connector (most licences include this).
- A **Fastmail** account. The sync script uses Fastmail's IMAP (mail) and
  CalDAV (calendar) servers.
  - *Other providers:* the mail service must allow IMAP logins from outside
    apps (here, GitHub's servers) using an app password, and the calendar
    service must support CalDAV with an app password. Fastmail does both.
- A **GitHub** account (free is fine).

The guides and flow files use my own settings (`mail@charles-young.com` and
`-//Charles//`). Swap in your own where the guides say so.

## Setup

Takes about 20 minutes. Do the steps in this order:

1. **[Build the Power Automate flow](docs/1-power-automate.md)**: builds the
   `.ics` export and emails it to you.
2. **[Set up Fastmail and GitHub Actions](docs/2-fastmail-and-github.md)**:
   copy this repo, add two secrets, and run the sync.

If something doesn't work, see **[Troubleshooting](docs/troubleshooting.md)**.

## Repo layout

| Path | What it is |
| --- | --- |
| `sync_calendar.py` | The sync script (IMAP → parse `.ics` → CalDAV upsert). |
| `.github/workflows/sync-calendar.yml` | Scheduled GitHub Actions workflow that runs the script. |
| `power-automate/expressions/` | Copy-paste-ready expressions for each flow step. |
| `power-automate/flow-definition.json` | The complete flow definition, for reference and diffing. |
| `docs/` | Setup guides, troubleshooting, and screenshots. |

## Things to know before you rely on it

- **TODO (separate PR): cancelled meetings aren't removed.** Edits and time
  changes in Outlook are carried over, but meetings that are **cancelled or
  deleted** in Outlook stay in Fastmail. For now, delete them by hand.
- **Only future events are sent** (now → 90 days out). Past events already in
  Fastmail are left alone.
- **Your work calendar data leaves the tenant.** Event titles and locations
  are emailed to a personal address. Check that this is allowed by your
  employer's policy before you set it up. Your work tenant must allow flows to
  email external addresses; some tenants block this with
  data loss prevention (DLP) policies, and the flow will fail if yours does.
- **TODO (separate PR): special characters aren't escaped.** The flow writes
  event titles and locations into the `.ics` file as they are. The iCalendar
  format expects commas, semicolons, backslashes and line breaks in those
  fields to be escaped. Fastmail handles most titles fine, but an unusual one
  could show up garbled.
- Use a **dedicated Fastmail calendar** (for example, one called "Work") so
  synced events stay separate from your personal ones.
