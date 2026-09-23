# Step 2: Build the change flow

This second flow runs whenever your work calendar changes: an invite arrives,
you accept or decline it, the organizer moves it, you edit or delete an
event. Each time, it emails a small `.ics` with just the changed event, or
every upcoming occurrence if it's a recurring meeting.

That `.ics` is marked `X-WORKCAL-SCOPE:ID` and names the Outlook event it's
about. The sync adds or updates what's in it, then deletes any synced event
for that Outlook ID that's no longer listed. So:

| What happened in Outlook | What the email contains | What the sync does |
| --- | --- | --- |
| Invite arrives, or you accept it | The event | Adds or updates it |
| Event edited or moved (by you or the organizer) | The updated event | Updates it |
| Recurring series changed | Every upcoming occurrence | Updates them, and deletes occurrences that were dropped |
| Event deleted, cancelled, or declined | Nothing | Deletes it |

It follows the same pattern as the [weekly flow](1-weekly-flow.md). The
only differences are the trigger, a **Filter array** step, and the last
Compose and email subject.

> [!TIP]
> The quickest way to build it: open the weekly flow's details page and
> choose **Save As** to make a copy. Then change the trigger, add
> Filter array, and update steps 6–8 as below.

| # | Step | Connector |
| --- | --- | --- |
| 1 | When an event is added, updated or deleted (V3) | Office 365 Outlook |
| 2 | Window start | Data Operations (Compose) |
| 3 | Get calendar view of events (V3) | Office 365 Outlook |
| 4 | Filter array | Data Operations |
| 5 | Initialize variable | Variables |
| 6 | Apply to each 1 | Control |
| 6a | ↳ Compose | Data Operations |
| 6b | ↳ Append to array variable | Variables |
| 7 | Compose 1 | Data Operations |
| 8 | Send an email (V2) | Office 365 Outlook |

The same step-name rule applies: `Window start`, `Apply to each 1`,
`Compose`, `Compose 1`, and `Filter array` must keep those exact names.

---

## 1. When an event is added, updated or deleted (V3) (trigger)

Add **Office 365 Outlook → When an event is added, updated or deleted (V3)**.

| Field | Value |
| --- | --- |
| Calendar Id | Choose **Calendar** from the dropdown |

Then open the trigger's **Settings** tab and turn on **Concurrency control**
with **Degree of Parallelism** set to `1`. This makes changes run one at a
time, so their emails arrive in the order the changes happened.

## 2. Window start

Same as the weekly flow: **Data Operations → Compose**, renamed `Window
start`, with Inputs = [`window-start.txt`](../power-automate/expressions/window-start.txt).

## 3. Get calendar view of events (V3)

Same as the weekly flow: Calendar Id **Calendar**, Start Time
[`start-time.txt`](../power-automate/expressions/start-time.txt), End Time
[`end-time.txt`](../power-automate/expressions/end-time.txt).

The trigger only gives the one changed item, which for a recurring meeting is
the series itself, not its individual occurrences. Reading the calendar view
and filtering it (next step) gives the same per-occurrence events the weekly
flow sends.

## 4. Filter array

Add **Data Operations → Filter array**.

| Field | Value |
| --- | --- |
| From | Dynamic content → **Get calendar view of events (V3)** → `body/value` |
| Filter query | Click **Edit in advanced mode** and paste [`filter-array-changes.txt`](../power-automate/expressions/filter-array-changes.txt) |

```text
@or(equals(item()?['id'], triggerOutputs()?['body/id']), equals(item()?['seriesMasterId'], triggerOutputs()?['body/id']))
```

This one *does* start with `@`, because advanced mode expects it.

It keeps the changed event itself, plus every occurrence if the changed item
is a recurring series. If the event was deleted, nothing matches and the
array is empty, which is what tells the sync to delete it.

## 5. Initialize variable

Same as the weekly flow: Name `VEventList`, Type `Array`, Value empty.

## 6. Apply to each 1

Same as the weekly flow, **except the loop input**:

| Field | Value |
| --- | --- |
| Select an output from previous steps | Dynamic content → **Filter array** → `Body` |

Inside it, **Compose** ([`compose-vevent.txt`](../power-automate/expressions/compose-vevent.txt))
and **Append to array variable** (`VEventList`, Compose `Outputs`) are
identical to the weekly flow.

## 7. Compose 1

| Field | Value |
| --- | --- |
| Inputs | expression: [`compose-1-changes.txt`](../power-automate/expressions/compose-1-changes.txt) |

This is the weekly version with `X-WORKCAL-SCOPE:ID` and the changed event's
Outlook ID in place of `SNAPSHOT`.

## 8. Send an email (V2)

Same as the weekly flow, **except the subject**:

| Field | Value |
| --- | --- |
| To | Your personal **Fastmail** address (mine is `mail@charles-young.com`) |
| Subject | `WorkCalendarChange` |
| Body | `WorkCalendarChange` |
| Attachments Name - 1 | `calendar.ics` |
| Attachments Content - 1 | expression: [`attachment-content-bytes.txt`](../power-automate/expressions/attachment-content-bytes.txt) |

---

## Save and test

1. **Save** the flow.
2. In Outlook, create a test event in the next few days.
3. Within a few minutes, the flow's run history should show a successful
   run, and a `WorkCalendarChange` email should arrive in Fastmail. Its
   `calendar.ics` should contain one `VEVENT` for your test event.
4. Delete the test event in Outlook. The next run's email should contain
   no `VEVENT` at all. After the GitHub Action runs, the event is gone from
   Fastmail.

If the Filter array step returns nothing for an event that exists, open the
trigger's output in the run history and check that it has an `id` field.
The filter expression depends on it.

## Reference: full flow definition

[`power-automate/flow-changes.json`](../power-automate/flow-changes.json)
has the whole flow as Power Automate stores it, for reference.

Next: **[Step 3: Set up Fastmail and GitHub Actions](3-fastmail-and-github.md)**
