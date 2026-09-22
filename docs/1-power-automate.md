# Step 1: Build the Power Automate flow

This flow runs in your **work** Microsoft 365 account. Every 6 hours it reads
the next 90 days of your calendar, turns each event into an iCalendar
`VEVENT`, wraps them in a `.ics` file, and emails that file to your personal
Fastmail address.

![Finished flow](images/flow-overview.png)

The finished flow has 7 steps:

| # | Step | Connector |
| --- | --- | --- |
| 1 | Recurrence | Schedule |
| 2 | Get calendar view of events (V3) | Office 365 Outlook |
| 3 | Initialize variable | Variables |
| 4 | Apply to each 1 | Control |
| 4a | ↳ Compose | Data Operations |
| 4b | ↳ Append to array variable | Variables |
| 5 | Compose 1 | Data Operations |
| 6 | Send an email (V2) | Office 365 Outlook |

> [!IMPORTANT]
> **Step names matter.** The expressions refer to other steps by name:
> `Apply_to_each_1`, `Compose`, `Compose_1`, and `Get_calendar_view_of_events_(V3)`.
> Power Automate turns spaces into underscores, so the loop must be called
> exactly **Apply to each 1**, and so on. If the designer gives a step a
> different name (for example, just "Apply to each"), rename it with the
> step's `⋮` menu → **Rename** *before* you paste the expressions.

## Pasting expressions

Every expression you need is in [`power-automate/expressions/`](../power-automate/expressions).
To use one:

1. Click in the field, then click the **fx** button (or type `/` and choose
   **Insert expression**).
2. Open the matching `.txt` file, copy **all** of it, and paste it into the
   expression box. Leave out any leading `@`; the files already omit it.
3. Click **Add**.

The two Compose expressions span several lines on purpose. The line breaks
inside the quoted strings become the line breaks in the `.ics` file, so paste
them as they are. Don't reformat them onto one line.

---

## 1. Recurrence (trigger)

Create a new **Scheduled cloud flow**, or start from a blank automated flow
and add the **Schedule → Recurrence** trigger.

![Recurrence settings](images/01-recurrence.png)

| Field | Value |
| --- | --- |
| Interval | `6` |
| Frequency | `Hour` |
| Time zone | Your local time zone |
| Start time | Any time in the past, e.g. `2026-07-31T10:00:00.000Z` |

This runs the flow 4 times a day. The start time only sets which hours it
runs at (here 06:00, 12:00, 18:00 and 00:00 Eastern).

## 2. Get calendar view of events (V3)

Add **Office 365 Outlook → Get calendar view of events (V3)**.

![Get calendar view settings](images/02-get-calendar-view.png)

| Field | Value |
| --- | --- |
| Calendar Id | Choose **Calendar** from the dropdown (your main calendar) |
| Start Time | expression: [`start-time.txt`](../power-automate/expressions/start-time.txt) |
| End Time | expression: [`end-time.txt`](../power-automate/expressions/end-time.txt) |

```text
formatDateTime(utcNow(), 'yyyy-MM-ddTHH:mm:ssZ')
formatDateTime(addDays(utcNow(), 90), 'yyyy-MM-ddTHH:mm:ssZ')
```

To sync further ahead, change `90` to a larger number of days.

Leave the advanced parameters empty. Use this action rather than "Get events":
the *calendar view* expands recurring meetings into individual occurrences,
and each occurrence gets its own `iCalUId`.

## 3. Initialize variable

Add **Variables → Initialize variable**.

![Initialize variable settings](images/03-initialize-variable.png)

| Field | Value |
| --- | --- |
| Name | `VEventList` |
| Type | `Array` |
| Value | *(leave empty)* |

## 4. Apply to each 1

Add **Control → Apply to each** and **rename it to `Apply to each 1`**.

![Apply to each settings](images/04-apply-to-each.png)

| Field | Value |
| --- | --- |
| Select an output from previous steps | Dynamic content → **Get calendar view of events (V3)** → `body/value` (may be labelled **value**) |

### 4a. Compose (inside the loop)

Inside the loop, add **Data Operations → Compose**. Keep the name `Compose`.

![Compose settings](images/05-compose.png)

| Field | Value |
| --- | --- |
| Inputs | expression: [`compose-vevent.txt`](../power-automate/expressions/compose-vevent.txt) |

This builds one `VEVENT` block per calendar event:

| iCal field | Comes from |
| --- | --- |
| `UID` | the event's `iCalUId`. It stays the same when the event changes, which lets the sync update the event instead of duplicating it. |
| `DTSTART` / `DTEND` | `start` / `end` in UTC. All-day events use date-only values. |
| `SUMMARY` | `subject` |
| `LOCATION` | `location` |
| `TRANSP` | `TRANSPARENT` when shown as *Free*, otherwise `OPAQUE` |
| `STATUS` | `TENTATIVE` when shown as *Tentative*, otherwise `CONFIRMED` |

### 4b. Append to array variable (inside the loop, after Compose)

Add **Variables → Append to array variable**.

![Append to array variable settings](images/06-append-to-array.png)

| Field | Value |
| --- | --- |
| Name | `VEventList` |
| Value | Dynamic content → **Compose** → `Outputs` |

## 5. Compose 1 (after the loop)

Add **Data Operations → Compose** *below and outside* the loop. It should be
named `Compose 1`.

![Compose 1 settings](images/07-compose-1.png)

| Field | Value |
| --- | --- |
| Inputs | expression: [`compose-1-vcalendar.txt`](../power-automate/expressions/compose-1-vcalendar.txt) |

This wraps all the `VEVENT`s in a `VCALENDAR`. Change `Charles` in the
`PRODID` line to your own name. It's only a label, so anything works.

## 6. Send an email (V2)

Add **Office 365 Outlook → Send an email (V2)**.

![Send an email settings](images/08-send-email.png)

| Field | Value |
| --- | --- |
| To | Your personal **Fastmail** address (mine is `mail@charles-young.com`) |
| Subject | `WorkCalendarExport` |
| Body | `WorkCalendarExport` (any text works) |
| Attachments Name - 1 | `calendar.ics` |
| Attachments Content - 1 | expression: [`attachment-content-bytes.txt`](../power-automate/expressions/attachment-content-bytes.txt) |
| Importance | Normal |

```text
base64(outputs('Compose_1'))
```

Attachment fields are under **Advanced parameters → Attachments**.

The designer shows this field as an **Outputs** chip, as in the screenshot,
even though it's the `base64(...)` expression underneath. To check it, open
the step's **Code view**. `ContentBytes` should read
`@base64(outputs('Compose_1'))`.

The subject has to match the sync script's `IMAP_SUBJECT_FILTER`, which
defaults to `WorkCalendarExport`. If you change one, change the other.

---

## Save and test

1. **Save** the flow.
2. Click **Test → Manually → Test**.
3. Check that every step shows a green tick, and that an email with
   `calendar.ics` attached arrives in your Fastmail inbox.
4. Optional: open `calendar.ics` in a text editor. It should start with
   `BEGIN:VCALENDAR` and have one `BEGIN:VEVENT … END:VEVENT` block per
   meeting.

> [!TIP]
> Leave the test email **unread**. The GitHub Action in step 2 only picks up
> unread emails, so this one will be your first real sync.

## Reference: full flow definition

[`power-automate/flow-definition.json`](../power-automate/flow-definition.json)
contains the whole flow as Power Automate stores it (each step's **Code
view**), except for the calendar ID, which is unique to each mailbox. You can't import it
directly, but you can use it to check your build step by step.

Next: **[Step 2: Set up Fastmail and GitHub Actions](2-fastmail-and-github.md)**
