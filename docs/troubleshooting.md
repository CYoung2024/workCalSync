# Troubleshooting

## Power Automate

**"The template language function 'items' ... 'Apply_to_each_1' ... not found"**
(or similar for `Compose` / `Compose_1`)
: A step name doesn't match what the expression expects. Rename the loop to
  exactly `Apply to each 1` and the Compose steps to `Compose` and `Compose 1`,
  then paste the expressions again. See the step-name note in
  [Step 1](1-power-automate.md).

**Send an email fails with a policy / DLP / "blocked" error**
: Your organisation doesn't allow flows to email external addresses. There's
  no workaround within this setup. Ask IT, or don't use this setup.

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
  contains `WorkCalendarExport`. Check that:
  - the email arrived and hasn't been opened. Mark it unread and run the
    workflow again.
  - a Fastmail rule or filter isn't moving it out of the Inbox or into spam.
  - the flow's subject matches `IMAP_SUBJECT_FILTER`.

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

**Cancelled meetings are still in Fastmail**
: Known gap (TODO, planned for a separate PR). The sync only adds and updates events; it never
  deletes them. Delete cancelled meetings in Fastmail by hand.

**Events show at the wrong time**
: The flow writes all timed events in UTC (with a trailing `Z`), and Fastmail
  shows them in your own time zone. If they're off by whole hours, check the
  time zone in Fastmail's settings.
