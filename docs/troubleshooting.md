# Troubleshooting

## Power Automate

**"The template language function 'items' ... 'Apply_to_each_1' ... not found"**
(or similar for `Compose` or `Compose_1`)
: A step name doesn't match what the expression expects. Rename the loop to
  exactly `Apply to each 1` and the Compose steps to `Compose` and
  `Compose 1`, then paste the expressions again. An error naming
  `WindowStart` means the Window start variable is missing or named
  differently. See the step-name note in
  [Step 1](1-weekly-flow.md).

**Send an email fails with a policy / DLP / "blocked" error**
: Your organisation doesn't allow flows to email external addresses. There's
  no workaround within this setup. Ask IT, or don't use this setup.

**The change flow runs but its email has no events for an event that exists**
: Open the trigger's output in the run history and check it has an `id`
  field, and that the Filter array step uses
  [`filter-array-changes.txt`](../power-automate/expressions/filter-array-changes.txt)
  in advanced mode.

**The `.ics` is all on one line, or Fastmail says it's invalid**
: The multi-line Compose expressions were flattened when you pasted them. Copy
  them again from the `.txt` files, keeping the line breaks.

**The flow succeeds but the attachment has no events**
: Check the output of *Get calendar view of events (V3)* in the run history.
  If `value` is empty, check that **Calendar Id** is set to your main
  calendar and that you have meetings in the next 90 days.

## GitHub Actions

**`KeyError: 'FASTMAIL_EMAIL'`**
: The repo secrets are missing or misnamed. Names are case-sensitive:
  `FASTMAIL_EMAIL` and `FASTMAIL_APP_PASSWORD`.

**`imaplib.IMAP4.error: [AUTHENTICATIONFAILED]`**
: Wrong app password, or the app password doesn't have Mail access. Make a
  new one.

**`No new matching mail found.`**
: The workflow found no **unread** email in the **Inbox** whose subject
  contains `WorkCalendar`. Check that:
  - the email arrived and hasn't been opened. Mark it unread and run the
    workflow again. Emails that already synced are moved to **Trash**; move
    one back to the Inbox and mark it unread to sync it again.
  - a Fastmail rule or filter isn't moving it out of the Inbox or into spam.
  - both flows' subjects contain `IMAP_SUBJECT_FILTER`.

**`Calendar 'Work' not found. Available calendars: ...`**
: `CALENDAR_NAME` must exactly match one of the names listed, including
  capitalisation.

**401 / 403 errors from CalDAV**
: The app password doesn't have DAV access, or `FASTMAIL_EMAIL` is an alias
  rather than your login address.

**`ERROR processing message ...`**
: The email stays unread and is retried on the next run. The line after
  `ERROR` says what went wrong. If it keeps failing on the same email, you
  can open that email in Fastmail and save the attachment to take a look.

**The scheduled workflow stopped running**
: On a **public** repo, GitHub turns off scheduled workflows after 60 days
  with no commits. Turn it back on from the Actions tab, or push any small
  commit.

## Calendar contents

**A deleted or declined meeting is still in Fastmail**
: It's removed when the sync processes the change flow's email for it, or at
  the latest after the Sunday snapshot. If it's still there after that,
  check that the event has an `X-WORKCAL-ID` line in Fastmail. Events synced
  before the flows added that line are never deleted automatically, so delete
  those by hand.

**Events show at the wrong time**
: The flow writes all timed events in UTC (with a trailing `Z`), and Fastmail
  shows them in your own time zone. If they're off by whole hours, check the
  time zone in Fastmail's settings.
