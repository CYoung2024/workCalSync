# workCalSync

Mirror a work Outlook / Microsoft 365 calendar into a personal Fastmail
calendar, without any admin access or third-party sync service.

```
┌──────────────────────┐ Sundays, and  ┌───────────────┐  every 15 min    ┌────────────────────┐
│ Power Automate flows │ on each change│ Fastmail inbox│ ◀── IMAP ─────── │ GitHub Actions     │
│ (work M365 account)  │ ── email ───▶ │               │                  │ sync_calendar.py   │
└──────────────────────┘  calendar.ics └───────────────┘                  └─────────┬──────────┘
                                                                                    │ CalDAV
                                                                                    ▼
                                                                          ┌────────────────────┐
                                                                          │ Fastmail calendar  │
                                                                          └────────────────────┘
```

1. Two **Power Automate** flows run inside your work tenant and email `.ics`
   files to your personal Fastmail address:
   - the **weekly flow** sends a full snapshot of the next 90 days every
     Sunday at 6 PM (subject `WorkCalendarExport`).
   - the **change flow** sends just the affected event whenever your calendar
     changes: an invite arrives, you accept or decline, a meeting is moved or
     edited, or an event is deleted (subject `WorkCalendarChange`).
2. **GitHub Actions** runs `sync_calendar.py` every 15 minutes. It logs in to
   Fastmail over IMAP, picks up any unread emails from either flow, and writes
   the events into a Fastmail calendar over CalDAV, matching on each event's
   `UID`. It updates existing events in place and deletes events that are
   gone from Outlook.
3. After a successful sync the email is moved to Trash. If the sync fails, the
   email stays unread in the Inbox and is retried next time.

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

Takes about 30 minutes. Do the steps in this order:

1. **[Build the weekly flow](docs/1-weekly-flow.md)**: the Sunday snapshot.
2. **[Build the change flow](docs/2-change-flow.md)**: sends each change as
   it happens.
3. **[Set up Fastmail and GitHub Actions](docs/3-fastmail-and-github.md)**:
   copy this repo, add two secrets, and run the sync.

If something doesn't work, see **[Troubleshooting](docs/troubleshooting.md)**.

## Repo layout

| Path | What it is |
| --- | --- |
| `sync_calendar.py` | The sync script (IMAP → parse `.ics` → CalDAV upsert). |
| `.github/workflows/sync-calendar.yml` | Scheduled GitHub Actions workflow that runs the script. |
| `power-automate/expressions/` | Copy-paste-ready expressions for each flow step. |
| `power-automate/flow-weekly.json`, `flow-changes.json` | The complete flow definitions, for reference and diffing. |
| `docs/` | Setup guides, troubleshooting, and screenshots. |

## Things to know before you rely on it

- **Only future events are synced** (now → 90 days out). Past events already
  in Fastmail are left alone, and never deleted.
- **Changes take up to about 15 minutes** to reach Fastmail, plus however
  long Power Automate takes to notice the change.
- **Private repos need a slower schedule.** Every 15 minutes is free on a
  public repo, but on a private one it uses more than the free plan's 2,000
  Actions minutes a month. See
  [Changing the schedule](docs/3-fastmail-and-github.md#changing-the-schedule).
- **The sync only deletes events it created.** It marks them with an
  `X-WORKCAL-ID` property, so anything you add to the calendar by hand is
  left alone.
- **Your work calendar data leaves the tenant.** Event titles and locations
  are emailed to a personal address. Check that this is allowed by your
  employer's policy before you set it up. Your work tenant must allow flows to
  email external addresses; some tenants block this with
  data loss prevention (DLP) policies, and the flow will fail if yours does.
- Use a **dedicated Fastmail calendar** (for example, one called "Work") so
  synced events stay separate from your personal ones.
