# Step 2: Set up Fastmail and GitHub Actions

GitHub Actions runs [`sync_calendar.py`](../sync_calendar.py) on a schedule.
Each run it:

1. Logs in to Fastmail over IMAP and searches the **Inbox** for **unread**
   emails whose subject contains `WorkCalendarExport`.
2. Reads every `VEVENT` from each `.ics` attachment.
3. Looks up each event's `UID` in your Fastmail calendar over CalDAV, then
   **updates** the event if it's already there or **creates** it if it isn't.
4. Marks the email as read, but only if every event synced. If anything
   failed, the email stays unread and is retried on the next run.

## 1. Create a Fastmail app password

Fastmail → **Settings → Privacy & Security → App passwords → New app password**.

- Access: give it **Mail** and **DAV (CardDAV, CalDAV, WebDAV)**.
- Copy the password now. Fastmail won't show it again.

> *Other providers:* your mail service must allow IMAP logins from outside
> apps. Here that means GitHub's servers, which change IP address every run,
> so IP allow-lists won't work. Its calendar must support CalDAV. Both need
> to accept an app password, because the script can't complete a 2FA prompt
> or a browser sign-in. Fastmail meets all of these.

## 2. (Recommended) Create a dedicated calendar

Fastmail → **Settings → Calendars → New calendar**, and name it
something like `Work`. This keeps synced events separate from your own,
and lets you hide or delete them all at once.

If you skip this, events go into your first (default) calendar.

## 3. Make your own copy of this repo

Click **Fork** at the top of this repo.

Your fork is public, like this repo. Your secrets stay private, but anyone
can read your Actions run logs, and those list your event titles. If you'd
rather keep them hidden, go to <https://github.com/new/import> instead, paste
this repo's URL, and choose **Private**. The 2-hour schedule (about 360 runs
a month) fits within the free plan's 2,000 Actions minutes a month for
private repos.

## 4. Add the secrets

In your copy: **Settings → Secrets and variables → Actions → New repository
secret**. Add both:

| Secret | Value |
| --- | --- |
| `FASTMAIL_EMAIL` | Your full Fastmail address, e.g. `you@fastmail.com` |
| `FASTMAIL_APP_PASSWORD` | The app password from step 1 |

`FASTMAIL_EMAIL` has to be the **login** address of the Fastmail account.
An alias won't work, because it's also used to build your CalDAV URL.

> *Other providers:* the script builds a Fastmail-specific CalDAV principal URL
> in `find_calendar()`. For another provider you'd also need to change that
> URL, plus `IMAP_HOST` and `CALDAV_URL`.

## 5. Point it at your calendar (if you made one)

Edit [`.github/workflows/sync-calendar.yml`](../.github/workflows/sync-calendar.yml)
and uncomment `CALENDAR_NAME`:

```yaml
        env:
          FASTMAIL_EMAIL: ${{ secrets.FASTMAIL_EMAIL }}
          FASTMAIL_APP_PASSWORD: ${{ secrets.FASTMAIL_APP_PASSWORD }}
          # IMAP_SUBJECT_FILTER: "WorkCalendarExport"
          CALENDAR_NAME: "Work"
```

All settings:

| Variable | Default | Purpose |
| --- | --- | --- |
| `FASTMAIL_EMAIL` | *(required)* | Fastmail login address |
| `FASTMAIL_APP_PASSWORD` | *(required)* | App password with Mail + CalDAV access |
| `CALENDAR_NAME` | first calendar | Name of the Fastmail calendar to write to (exact match) |
| `IMAP_SUBJECT_FILTER` | `WorkCalendarExport` | Only process emails with this subject. Must match the flow's email subject. |
| `IMAP_HOST` | `imap.fastmail.com` | IMAP server |
| `CALDAV_URL` | `https://caldav.fastmail.com/dav/` | CalDAV server (keep the trailing slash) |

## 6. Enable Actions and run it

1. Open the **Actions** tab. On a fork, click **"I understand my workflows,
   go ahead and enable them"**.
2. Select **Sync Fastmail calendar from email → Run workflow**.
3. Open the run and expand **Run sync**. You should see something like:

   ```text
   Found 1 matching message(s).
   Target calendar: Work
   Processing: WorkCalendarExport
     created: Team standup (040000008200E00074C5B7101A82E008...)
     created: 1:1 with Sam (040000008200E00074C5B7101A82E008...)
     synced 42 event(s)
   ```

4. Check your Fastmail calendar.

After that, the Power Automate flow sends a new export every 6 hours, and the
workflow picks it up at its next run (within 2 hours).

## Changing the schedule

The schedule is the `cron` line in `.github/workflows/sync-calendar.yml` and
uses **UTC**:

```yaml
    - cron: "0 */2 * * *"    # every 2 hours (default)
    - cron: "0 * * * *"      # every hour
```

GitHub sometimes starts scheduled runs several minutes late. That's fine for
this job.

Next: **[Troubleshooting](troubleshooting.md)** if anything went wrong.
