# Fact Table Selection: Advanced - Exercises

Lesson: [dm_pattern_fact_table_selection.md](../dm_pattern_fact_table_selection.md)

### Exercise 1 of 7

**● TASK**

A recruiting analytics team tracks every job application through the hiring pipeline: applied, screened, interviewed, offer, and decision. They want to measure how many days pass between consecutive stages and find where candidates stall. Design a fact table with one row per application, including stage-to-stage duration measures and dimensions for recruiter and job opening.

<details>
<summary><strong>Solution</strong></summary>

#### What this question is really asking

Beneath the recruiting language, this is a lifecycle-tracking table dressed up as pipeline analytics. The real question the interviewer is timing you on: is each row a discrete event that happens once, or the state of one thing as it changes over time? An application is not an event. It is one entity that marches through `applied`, `screened`, `interviewed`, `offer`, and `decision`, and the business wants to know how long it sat at each gate. That makes it an accumulating snapshot: **one row per application, revised in place as milestones land**. The trap is to log every stage change as its own row, which turns "how many days from screen to interview" into a self-join across rows and makes "where is this application right now" expensive. Model the wrong shape and every stalled-pipeline metric downstream is wrong.

#### Classify it in 60 seconds

1. **Ask: event or state?**

   A discrete thing that happens once and never changes is a transaction fact: a click, a payment, an order line. A thing whose state evolves is a snapshot. An application clearly evolves, so you are in snapshot territory. Say this out loud before you draw anything.

2. **Ask: milestones or periodic?**

   Snapshots split 2 ways. A periodic snapshot samples a state on a fixed cadence, like a daily account balance. An accumulating snapshot tracks an entity with a defined lifecycle of milestones. A hiring pipeline has named milestones with a beginning and an end, so it is accumulating, not periodic. You do not want a fresh row per application per day.

3. **State the grain**

   Say it precisely: one row per job application. That row is born when the application arrives and is updated in place as each milestone completes. Naming the grain first is what separates a senior answer from a junior one.

4. **Name the measures and their additivity**

   The useful measures are the day counts between consecutive stages, for example `days_applied_to_screen` and `days_screen_to_interview`. Those are additive: you can average them across recruiters and openings. The milestone dates themselves and the `current_stage` label are not summable. Calling out additivity unprompted signals you are thinking about how the table aggregates, not just how it loads.

#### The reference model

One fact table, one row per application, with a foreign key to a role-playing `dim_date` for each milestone and the stage durations pre-computed as measures. The dimensions are the candidate, the job opening, and the recruiter.

![Schema diagram](../_images/dm_pattern_fact_table_selection_exercise_1_schema.png)

*One row per application; each milestone is a role-playing `dim_date` FK; the stage durations are the additive measures.*

| Key insight: The row is the application |
| --- |
| The whole point of an accumulating snapshot is that the row IS the application. `WHERE current_stage = 'interview'` answers "what is in the pipeline right now" with no aggregation, and a stage lag is a plain subtraction on the same row instead of a self-join across event rows. |

| Interviewer: Classify out loud, then declare the grain |
| --- |
| A strong candidate classifies out loud (event vs state, then milestones vs periodic), declares the grain as one row per application, and names which measures are additive without being asked. Fumbling any of those 3 reads as someone who has only loaded fact tables, never designed one. |

| Pitfall: One row per stage change |
| --- |
| Logging one row every time an application changes stage (a transaction fact) because "everything is an event" feels natural and is wrong here: every lag metric becomes a self-join, and finding an application's current state means scanning all of its rows. That milestone-per-row shape answers a different question than the one asked. |

| ✕ Accumulating snapshot (correct here) | ✓ One row per stage event |
| --- | --- |
| One row per application, milestone date FKs filled in over time, durations as measures.<br><br>* Current state is a single column read<br>* Stage lag is a subtraction on one row<br>* Row count equals application count | One row every time an application changes stage.<br><br>* Current state needs the latest row per application<br>* Stage lag needs a self-join across rows<br>* Row count balloons with pipeline activity |

**Follow-up questions**

1. The business now wants the count of applications sitting in each stage at the end of every week. Does that change your fact table?\
   *Tests whether they reach for a periodic snapshot for a point-in-time count, complementing the accumulating snapshot rather than replacing it.*
2. A candidate is rejected at one stage and re-enters later after a referral. How do you model that?\
   *Tests grain discipline: a genuine re-entry on the same row versus a separate application.*
3. Which of your measures would you refuse to SUM in a BI tool, and why?\
   *Tests additivity understanding beyond just naming it: milestone dates and current stage are not summable.*

</details>


<br>

### Exercise 2 of 7

**● TASK**

A digital wallet product records every money movement on a user's balance: top-ups, purchases, refunds, and peer transfers. Design a fact table for this event stream where each transaction is one immutable row, use a signed amount (positive for inflows, negative for outflows) so totals by user, merchant, and day stay additive across dimensions, and model corrections as new events rather than updates to the original.

<details>
<summary><strong>Solution</strong></summary>

#### What this problem is really testing

This is an append-only transaction fact wearing a fintech costume. The skill: model one immutable row per money-movement event, with a **signed, additive** amount, so any total by user, merchant, or day is a plain `SUM`. The trap arrives as the follow-up. The interviewer asks for each wallet's current balance, and a shaky candidate bolts a mutable `current_balance` column onto the fact and updates it on every transaction. Do that and you throw away the one property a transaction fact exists to guarantee: the row you wrote yesterday still says exactly what happened yesterday.

#### Break down the requirements

1. **Declare the grain**

   One row equals one discrete money-movement event: a single top-up, purchase, refund, or transfer. Not one row per wallet, not one row per day. Carry `transaction_id` as a degenerate dimension and `occurred_at` as the event timestamp so the stream is fully ordered.

2. **Make the measure signed and additive**

   Store one `signed_amount`: positive for top-ups and refunds, negative for purchases and outbound transfers. A single `SUM(signed_amount)` then works across every type and every dimension. Separate `debit_amount` / `credit_amount` columns force CASE logic on every query and quietly invite double counting.

3. **Keep it append-only**

   A refund, chargeback, or correction is a NEW row with its own `occurred_at` and its own signed amount, never an `UPDATE` to the original event. Immutability is what makes the ledger auditable and safe to reprocess from raw events.

4. **Wire the dimensions**

   Foreign keys to `dim_wallets`, `dim_users`, `dim_merchants`, `dim_transaction_type`, and `dim_date`. These are the exact axes the analysts asked to slice money flow by.

#### The reference model

One transaction fact surrounded by conformed dimensions. Every measure on `fact_wallet_transactions` is additive at the event grain, and nothing on the row is ever overwritten.

![Schema diagram](../_images/dm_pattern_fact_table_selection_exercise_2_schema.png)

*`fact_wallet_transactions` is append-only at one-row-per-event grain; there is no stored balance column.*

| Trick: Balance is a query, not a column |
| --- |
| A wallet's balance at any moment is the running `SUM(signed_amount)` for that wallet ordered by `occurred_at`. Because it is derivable from the events, it never belongs on the fact row. Storing it there is the fast path to a number that silently disagrees with the events that produced it. |

| Interviewer: The current-state question is bait |
| --- |
| A strong candidate answers 'what is the current balance?' by aggregating the events, and notes that if state reads dominate traffic you later add a derived snapshot alongside the transaction fact. What they never do is mutate the event rows to hold state. |

| Pitfall: The mutable-balance trap |
| --- |
| Adding `current_balance` to the fact and updating it in place on every transaction. It turns an immutable event log into mutable state, so a failed reprocess or an out-of-order write corrupts a number you can no longer reconstruct, and the audit trail is gone. |

#### Trade-offs

| ✕ One signed measure | ✓ Separate debit/credit columns |
| --- | --- |
| `signed_amount` positive for inflow, negative for outflow.<br><br>* Totals are a plain `SUM` across every type and dimension<br>* Reversals are just another negative row<br>* Reads never branch on transaction type | `debit_amount` and `credit_amount` side by side.<br><br>* Every total needs `SUM(credit) - SUM(debit)`<br>* Easy to sum the wrong column and double count<br>* Type logic leaks into every downstream query |

**Follow-up questions**

1. The interviewer wants every wallet's balance as of the end of last month. How do you answer it with no stored balance?\
   *Tests deriving state as a running `SUM(signed_amount)` per wallet up to a cutoff, straight from the event fact.*
2. A purchase is reversed 3 days after it settled. Which rows change?\
   *Tests immutability: a new negative row is appended with its own `occurred_at`, and zero existing rows are updated or deleted.*
3. Balance reads are now 80 percent of traffic and the running sum is too slow at 40M events a day. What do you add?\
   *Tests knowing that a derived periodic snapshot complements the transaction fact for state reads rather than replacing it or mutating it.*

</details>


<br>

### Exercise 3 of 7

**● TASK**

A grocery distributor's supply team keeps getting asked how many units of each product were sitting in each warehouse at the end of any given past day, and today the only way to answer is to replay the whole stream of receipts and shipments from the beginning. Design the fact table and its dimensions so that a single day's end-of-day on-hand quantities read straight off one day's rows, and set the grain so the level for a product at a warehouse is captured once per day.

<details>
<summary><strong>Solution</strong></summary>

#### What you just built

This is the **periodic snapshot** pattern in a grocery costume. Receipts and shipments are a flow, but the supply team keeps asking for a level: units on the shelf at close of business. Reading a level off a flow means replaying every movement, so you store the level itself, once per day. The trap: on-hand quantity is semi-additive, add it across products and warehouses on one day, but `SUM` it across dates and you multiply the same standing stock by the day count.

The grain is the whole design: one row per product per warehouse per close of one calendar day. Each grain column is a foreign key into a conformed dimension (`dim_date`, `dim_product`, `dim_warehouse`), never free text on the fact. Carry the level forward on days a product did not move, so any past day reads off one day's rows.

![Schema diagram](../_images/dm_pattern_fact_table_selection_exercise_3_schema.png)

*Grain: one closing level per product per warehouse per day. The three keys on `fact_inventory_snapshot` are foreign keys into conformed dimensions; `inventory_snapshot_key` is the surrogate.*

| Key insight: State, not flow |
| --- |
| Ask any measure: does it HAPPEN (a shipment, a sale) or simply exist (a balance on hand)? A happening is a transaction fact you sum freely over time; a standing level is a snapshot you sum only within a single day. |

| Pitfall: Summed across dates, it's fiction |
| --- |
| `SUM(quantity_on_hand)` from Jan 1 to Mar 31 adds every day's standing stock, so a warehouse holding 10,000 units all quarter reports 900,000. For a range, pick one day or average the daily levels. |

**On-hand by warehouse as of a chosen day**

```sql
SELECT
    w.warehouse_code,
    SUM(f.quantity_on_hand) AS units_on_hand
FROM fact_inventory_snapshot f
JOIN dim_date d ON d.date_key = f.snapshot_date_key
JOIN dim_warehouse w ON w.warehouse_key = f.warehouse_key
WHERE d.full_date = DATE '2024-03-31'
GROUP BY w.warehouse_code
ORDER BY units_on_hand DESC
```

*One day's rows summed across products; the `SUM` is safe because it never crosses a date.*

| ✕ Periodic snapshot (this model) | ✓ Transaction/movement fact |
| --- | --- |
| One closing `quantity_on_hand` per product per warehouse per day. Point-in-time questions read one day's rows. Additive across products and warehouses within a day, never across dates. | One row per receipt or shipment with a signed `quantity_change`. Flow questions sum over the range, but on-hand as of a date needs scanning all history, wrong for a level. |

**Follow-up questions**

1. The buyer wants total units SHIPPED in March. Does this fact answer it?\
   *A flow question needs the movement fact, where the measure IS additive over time.*
2. Finance wants average inventory over the quarter, which aggregate is valid on `quantity_on_hand`?\
   *AVG across daily snapshots is valid for a semi-additive level; SUM is not.*

</details>


<br>

### Exercise 4 of 7

**● TASK**

A consumer-lending platform moves every loan application through the same checkpoints in order: submitted, documents verified, underwriting decision, and funds disbursed. The analytics team keeps getting asked how long applications sit at each stage and which ones have been approved but are not yet funded, broken down by loan product. Design the fact table and the dimensions it needs so analysts answer these without stitching separate events back together or subtracting dates by hand.

<details>
<summary><strong>Solution</strong></summary>

#### Why this problem exists in real interviews

Beneath the lending story this is an **accumulating snapshot**, the one fact type where a row is born incomplete and updated as it grows up. The trap is modeling each checkpoint as its own event row, a transaction fact. Do that and 'which applications are approved but not funded' becomes a self-join across event rows, and every stage-duration number forces analysts to pair events and subtract dates by hand. The accumulating snapshot collapses the whole lifecycle into one updatable row with a date column per checkpoint, so the same questions are a `WHERE` clause and a plain `AVG`.

| Trick: One row that fills in over time |
| --- |
| The moment you hear 'the same fixed set of milestones, in order, and we want to know where things sit and how long each stage takes,' reach for `fact_loan_application_lifecycle` at one row per application. Give each milestone its own `*_date_sk`, let `NULL` mean 'not there yet,' and precompute the gaps. |

#### Break down the requirements

1. **Declare the grain: one application, not one event**

   The lifecycle instance is the loan application, so `fact_loan_application_lifecycle` holds exactly one row per application. Every dimension (`dim_applicant`, `dim_loan_product`, `dim_loan_officer`) attaches at that grain. This is the choice that separates candidates: pick per-event and everything downstream becomes a self-join.

2. **Give each milestone its own date key**

   `submitted_date_sk`, `verified_date_sk`, `decisioned_date_sk`, `funded_date_sk` all live on the one row and all point at the same `dim_date`. A `NULL` means the checkpoint has not been reached, so 'approved but not funded' is `decisioned_date_sk IS NOT NULL AND funded_date_sk IS NULL`.

3. **Precompute the lags and denormalize the status**

   Store `days_to_verify`, `days_to_decision`, and `days_to_fund` so 'average time to decision per product' is `AVG(days_to_decision)` with no date math. Add a `current_status` column ('`in_review`', 'approved', 'funded', 'denied', 'withdrawn') so dashboards filter state without decoding which date columns are populated.

4. **Accept that rows are updated in place**

   The row is inserted at submission with only `submitted_date_sk` set, then UPDATEd as each later checkpoint lands, backfilling its date and the corresponding lag. This is the only fact type where in-place UPDATE is the correct pattern, and saying so out loud is the tell an interviewer listens for.

#### The reference model

Below is one sound design. The anchor is that `fact_loan_application_lifecycle` is a single wide, updatable row per application, with a date key per milestone and precomputed lags, hanging off conformed dimensions.

![Schema diagram](../_images/dm_pattern_fact_table_selection_exercise_4_schema.png)

*One row per application; each milestone key points at the shared `dim_date`, and NULL means not yet reached.*

| Performance: The pipeline query stays a single scan |
| --- |
| At 40,000 applications a month the fact table stays small because the row count is applications, not events. 'Approved but not funded' is one indexed predicate on `decisioned_date_sk` and `funded_date_sk`; 'average days to decision by product' is one `GROUP BY` on `loan_product_key`. No self-join, no window function, no per-row date arithmetic. |

| Interviewer: Say the row gets updated |
| --- |
| A strong candidate names the grain first, then volunteers that this is the one fact type that is UPDATEd in place and that `NULL` milestone dates encode progress. Naming those 2 things unprompted is what signals they have actually built one, not just read about it. |

| Pitfall: Do not model milestones as event rows |
| --- |
| The common miss is four rows per application, one per checkpoint, treating this like a transaction fact. Then every stage-duration metric needs a self-join to pair the 'submitted' row with the 'funded' row, and 'stuck at underwriting' needs an anti-join. The second miss is a single mutable `status_date` column that overwrites history: you lose the per-milestone timestamps the lags depend on. |

#### Trade-offs and alternatives

| ✕ Accumulating snapshot | ✓ Transaction fact per milestone |
| --- | --- |
| One updatable row per application with a `*_date_sk` per milestone and precomputed lags.<br><br>* 'Approved but not funded' is one predicate<br>* Stage durations are direct aggregations<br>* Requires in-place UPDATE as milestones land | One immutable row per checkpoint event.<br><br>* Clean append-only load<br>* Preserves a raw event log<br>* Every lag and 'stuck at stage X' becomes a self-join or anti-join, and current state must be reconstructed per query |

**Follow-up questions**

1. The business adds an appraisal checkpoint between verification and decision. How does the model change?\
   *Tests whether the candidate adds one `appraised_date_sk` plus its lag to the same row, and understands schema evolution on a fixed-milestone snapshot.*
2. An applicant can reopen a withdrawn application months later. How do you keep both attempts?\
   *Tests whether the candidate keeps the grain honest by treating a reopen as a new application row rather than resurrecting and overwriting the old one.*
3. Leadership wants a daily count of how many applications sat in each stage, historically, not just today. Does this table answer it?\
   *Tests the boundary between an accumulating snapshot (current state) and a periodic snapshot needed for a day-by-day historical stage census.*

</details>


<br>

### Exercise 5 of 7

**● TASK**

A video-streaming service licenses each title for specific regions, and those licensing windows shift day to day as deals start and expire. The catalog team needs a model that captures which titles were available to stream in which regions on each day, and that can surface the titles a region was paying to license but that nobody streamed. Design the schema. The availability table should contain only the three foreign keys (title_id, region_id, date_id) as a composite primary key, with no measure or flag columns.

<details>
<summary><strong>Solution</strong></summary>

#### Why this problem exists in real interviews

This is a **factless coverage fact** wearing a licensing-analytics costume. The question everyone gets wrong is the one that isn't asked out loud: what is the measure? There isn't one. A title being streamable in a region on a day is a relationship that existed, not a number that was produced. Candidates who assume every fact table holds numbers reach for a play count on the availability row, and the moment they do, they can no longer answer the question the catalog team actually cares about: which licensed titles got zero plays. You cannot count rows that were never written.

| Trick: The row's existence is the fact |
| --- |
| The tell is 'which titles were available in which regions on which days' with no quantity attached. That is a factless fact: grain `(title_sk, region_sk, date_sk)`, zero measure columns. Coverage is `COUNT(*)`. To find what did NOT happen, anti-join this coverage fact against the actual `fact_title_play` events. |

#### Break down the requirements

1. **Name the grain, then look for the measure**

   One row per title, per region, per day of availability. Now ask what number lives on that row. Nothing does: the row asserts eligibility to stream, not an event with a magnitude. That absence is the signal, not a mistake to fix.

2. **Model `fact_title_availability` with keys only**

   It holds `title_sk`, `region_sk`, and `date_sk`, and those three together are the primary key. No `play_count`, no `is_available` flag: a flag on a coverage fact is redundant, because the row would not exist if the title were dark.

3. **Keep actual plays in their own fact**

   Real streams are transactional events, so `fact_title_play` records them at `(title_sk, region_sk, date_sk)` too. 2 facts, one asserting what COULD happen and one recording what DID. The gap between them is the whole point of the design.

#### The reference model

2 facts share the same conformed dimensions. `fact_title_availability` is the coverage table (factless); `fact_title_play` is the event table. Because both are keyed on the same three surrogate keys, the anti-join that finds wasted licensing spend is a clean join, not a fuzzy match.

![Schema diagram](../_images/dm_pattern_fact_table_selection_exercise_5_schema.png)

*`fact_title_availability` carries no measures; its composite key of `title_sk`, `region_sk` and `date_sk` IS the record.*

| Key insight: 2 facts, one asks CAN, one asks DID |
| --- |
| `fact_title_availability` answers what was possible; `fact_title_play` answers what occurred. Blending them into one table with a nullable `watch_seconds` looks tidier but destroys the coverage semantics: a null play does not prove the title was licensed that day. |

| Interviewer: Saying the word factless unprompted |
| --- |
| Strong candidates state 'this is a factless fact, the count of rows is the metric' before drawing anything, and they immediately explain what the coverage table is FOR: gap analysis. That framing is the seniority tell here. |

| Pitfall: A play count on the coverage row cannot find zeros |
| --- |
| Putting `play_count` on `fact_title_availability` and deriving coverage from `SUM` feels natural and is a trap. To find titles that were licensed but never streamed, you need rows that exist for availability and are absent for plays. A single blended fact with a zero count only exists if someone thought to write the zero, which nobody does. |

#### The power query: what did NOT happen

**Licensed but never streamed**

```sql
SELECT a.title_sk, a.region_sk, a.date_sk
FROM fact_title_availability a
LEFT JOIN fact_title_play p
  ON p.title_sk = a.title_sk
 AND p.region_sk = a.region_sk
 AND p.date_sk  = a.date_sk
WHERE p.play_id IS NULL
```

*The unmatched coverage rows are the wasted licensing spend: available, but zero plays.*

| ✕ Factless coverage fact | ✓ Blended fact with a measure |
| --- | --- |
| `fact_title_availability` holds only `(title_sk, region_sk, date_sk)`.<br><br>* Coverage is `COUNT(*)`<br>* 'Never streamed' is a clean anti-join<br>* No zero rows to fabricate | One table with `watch_seconds` nullable.<br><br>* A missing stream is indistinguishable from a missing license<br>* Gap analysis needs rows that were never inserted<br>* Coverage becomes a fragile `COUNT(DISTINCT ...)` over event data |

**Follow-up questions**

1. The team now wants total watch time per available title-region. Does that change your factless fact?\
   *Tests whether the candidate keeps the coverage fact factless and adds the measure to `fact_title_play`, rather than corrupting the coverage grain.*
2. Licensing windows are contiguous ranges, sometimes months long. Would you still write one row per day?\
   *Tests the daily-grain versus range-row tradeoff: daily rows keep the date anti-join trivial but explode volume; a range fact is compact but complicates coverage counting.*
3. How would you answer 'which titles were available in every region for the whole month'?\
   *Tests reasoning over the factless fact with COUNT and completeness checks against `dim_region` and `dim_date`.*

</details>


<br>

### Exercise 6 of 7

**● TASK**

A hotel group's warehouse tracks four reporting needs, each requiring a different fact table shape: Finance needs every folio charge and payment linked to a reservation with signed amounts; Revenue needs nightly snapshot counts (total, sold, unsold) per property and type; Operations needs each reservation with date keys for booking, check-in, check-out, and settlement, plus calculated inter-milestone days; Marketing needs rate-plan offerings (which rates per room type per night) with no measures. Design the fact tables and conformed dimensions.

<details>
<summary><strong>Solution</strong></summary>

#### What this problem is really testing

Four business questions, one hotel, and the whole test is whether you can hear the fact table TYPE inside each request. The trap is treating them as four flavours of the same wide table, or worse, picking a type that quietly breaks the math: model the nightly unsold-rooms count as a transaction fact and someone will `SUM(rooms_available)` across March to get a number 30 times too big, and nobody will notice until revenue management builds a forecast on it. The skill being probed is fast, correct classification: event, level, lifecycle, or coverage.

| Trick: Classify each request before you draw anything |
| --- |
| Each of the four needs maps to one canonical shape. Folio charges are discrete events, so a transaction fact. Unsold rooms is a level captured at a cadence, so a periodic snapshot. A reservation crawling through ordered milestones is an accumulating snapshot. A rate plan that was merely on offer is a factless coverage table. Name the four before you touch a column. |

#### Walk the four decisions

1. **Folio: one row per posted event, linked to the reservation**

   Finance wants the single spa charge and the single card settlement, so the grain is one row per line, inserted and never updated. Keep `amount` signed (payments and refunds negative) and it stays fully additive: a stay total, a daily total, and a property total are all just `SUM(amount)`. Add a `reservation_key` foreign key so Finance can answer 'what did this stay cost?' and 'which guest incurred this charge?'

2. **Inventory: one row per property, room type, night**

   Revenue management asks a level question: how many rooms stood unsold at close of night. That is a periodic snapshot. Store `rooms_total`, `rooms_sold`, `rooms_available` per hotel per room type per night. The `rooms_available` measure is semi-additive: sum it across properties on one night, never across nights.

3. **Reservation: one row, updated as milestones arrive, with a date key per milestone**

   Operations wants the whole journey and the lag between legs. That is an accumulating snapshot: one row per reservation, a separate date foreign key for each milestone (`booked_date_key`, `checkin_date_key`, `checkout_date_key`, `invoice_settled_date_key`), and pre-computed lags like `booking_to_checkin_days`. The row is revisited as milestones land; a cancelled reservation simply leaves later milestones empty. The per-milestone date keys are what make the lags queryable and the lifecycle trackable.

4. **Rate availability: record the offer, not a number**

   Marketing wants rate plans that were bookable but never booked. There is nothing to measure, only a relationship that existed. That is a factless fact: one row per date, hotel, room type, and rate plan offered. Carry only the foreign keys, no numeric column. Zero-booking rates fall out of a left join from this table to the reservations that reference the same rate plan.

#### The reference model

Four facts, 5 conformed dimensions. Every fact points at the same `dim_date`, `dim_hotel`, and `dim_room_type`, so the same slicing works everywhere. The shapes differ on purpose: `fact_folio_transactions` grows by insert and links to `fact_reservation_lifecycle` via `reservation_key`, `fact_room_inventory_snapshot` grows one batch per night, `fact_reservation_lifecycle` is updated in place, and `fact_rate_availability` carries no measure at all.

![Schema diagram](../_images/dm_pattern_fact_table_selection_exercise_6_schema.png)

*`fact_folio_transactions` links to `fact_reservation_lifecycle` via `reservation_key` (BIGINT); `fact_room_inventory_snapshot` has a composite grain of (`snapshot_date_key`, `hotel_key`, `room_type_key`); `fact_rate_availability` is factless with a composite key over all four foreign keys and no numeric columns.*

| Interviewer: The strongest candidates name the semi-additive trap unprompted |
| --- |
| A senior answer says out loud that `rooms_available` sums across properties on a night but never across nights, and that a period-over-period view uses an average or a period-end pick, not a `SUM`. Saying it before being asked is the single clearest seniority tell on this problem. |

| Pitfall: One wide events table for all four |
| --- |
| The most common failure is folding every request into a single fact keyed by event time. Reservation lifecycle needs an in-place update the insert-only design cannot express, the inventory level becomes wrongly additive, and the offered-but-unbooked rate has no event to hang on at all. Four shapes exist because one shape cannot answer all four questions correctly. |

| ✕ Accumulating snapshot for reservations | ✓ Transaction fact of milestone events |
| --- | --- |
| One row per reservation, updated as milestones land. Lags like `booking_to_checkin_days` are a single subtraction, and `WHERE checkin_date_key IS NULL` finds no-shows instantly. | One row per milestone reached. Correct, but every lag becomes a self-join across rows of the same reservation, and pipeline funnel counts need conditional aggregation. Slower to query and easier to get wrong. |

**Follow-up questions**

1. Revenue management wants average nightly occupancy per property for a quarter. Why can't that be `SUM(rooms_sold)` over the quarter, and what do you write instead?\
   *Tests whether the candidate truly internalised semi-additivity: the level must be averaged across time or picked at period end, never summed.*
2. A reservation is cancelled after check-in but before check-out. How does that look in `fact_reservation_lifecycle`?\
   *Tests handling of partial and non-linear lifecycles in an accumulating snapshot (empty later milestones, and whether cancellation needs its own milestone or status).*
3. Marketing wants, per room type, the count of rate plans offered in a month that produced zero bookings. Which tables do you touch?\
   *Tests use of the factless coverage table as the left side of an anti-join against reservations on the conformed rate-plan and room-type keys.*
4. The inventory snapshot is now hundreds of millions of rows a year. How do you keep the nightly-level queries cheap?\
   *Tests scale reasoning: partitioning the snapshot by date and pruning on `snapshot_date_key`, and whether a rolling window needs a coarser monthly grain.*

</details>


<br>

### Exercise 7 of 7

**● TASK**

A property insurer's claims director needs cycle-time reporting on every claim as it moves through a fixed lifecycle: submitted, then adjudicated, then paid. Design the analytical model that stores the days between each milestone pair (submit to adjudicate, adjudicate to pay, and submit to pay) as measures on each claim row and enables listing the claims currently sitting between two milestones with no further movement. Every claim reaches the milestones in that order, and the model must reflect a claim's progress even before it is fully paid.

<details>
<summary><strong>Solution</strong></summary>

#### What this problem really is

Strip the insurance costume and this is a lifecycle-tracking model: one business object (`a claim`) that passes through a fixed, ordered set of milestones, and reporting that lives on the gaps between those milestones. This is the **accumulating snapshot** shape, and the interview separation is entirely in the grain. Reach for one row per milestone event and cycle time becomes a self-join every time someone opens the dashboard. Reach for one row per claim per day and you multiply two thousand claims a month by their age in days for numbers that never change. The right answer is one row per claim that you keep updating as the claim moves.

| Trick: One row that grows up |
| --- |
| The whole trick: the row is born when the claim is `submitted`, with `adjudicated_date` and `paid_date` still null, and you UPDATE those columns in place as each milestone arrives. The claim's entire life is one row. That is what makes cycle time a subtraction and 'stuck between milestones' a null check. |

#### Break down the requirements

1. **Declare the grain: one row per claim**

   Say it out loud before drawing anything: the grain of `fact_claim_lifecycle` is one row per claim, the lifecycle instance. Not one row per milestone (that is a transaction fact) and not one row per claim per period (that is a periodic snapshot). Everything below only works because the grain is the claim.

2. **Give every milestone its own date column**

   `submitted_date_key`, `adjudicated_date_key`, and `paid_date_key` all sit on the same row, each a foreign key into `dim_date`. The later two are nullable and start empty. As the claim advances you fill them in with an UPDATE. A claim adjudicated but not paid has `adjudicated_date_key` populated and `paid_date_key` null, which is exactly the 'stuck' filter the director wants.

3. **Store the durations as measures**

   The headline metric is time between milestones, read all day. Pre-compute `days_submit_to_adjudicate`, `days_adjudicate_to_pay`, and `days_submit_to_pay` as columns on the row, filled in when the closing milestone lands. Now the dashboard averages a stored number instead of self-joining a heap of event rows to reconstruct each duration.

4. **Attach the conformed dimensions**

   Hang the claim on `dim_policyholders`, `dim_adjusters`, and `dim_claim_type`, and point all three milestone date keys at a shared `dim_date`. Reusing one date dimension for all three milestones is what lets you slice cycle time by submission month, adjudication quarter, or payment week from the same row.

#### The reference model

One accumulating-snapshot fact at claim grain, three date foreign keys into a shared calendar, the pre-computed lag measures, and the conformed dimensions around it. The row is created at submission and updated twice more over the claim's life.

![Schema diagram](../_images/dm_pattern_fact_table_selection_exercise_7_schema.png)

*`fact_claim_lifecycle` is one row per claim; `adjudicated_date_key` and `paid_date_key` are null until reached, and the days_* measures fill in as milestones close.*

| Interviewer: Grain named before tables drawn |
| --- |
| A strong candidate says 'one row per claim, updated in place' inside the first 30 seconds and then explains why the milestone dates are nullable. Watch for whether they volunteer that `days_*` durations are non-additive across claims: you average them, you never SUM them across the fact. |

| Pitfall: The event-row grain that looks right |
| --- |
| The common miss is one row per milestone event (`claim_id`, `milestone`, `event_date`). It inserts cleanly and feels like a tidy transaction fact, but every cycle-time number now needs a self-join to pair a claim's submit row with its adjudicate row, and 'stuck between milestones' becomes a NOT EXISTS. At dashboard read rates that is the wrong grain. |

| Performance: Small table, cheap reads |
| --- |
| One row per claim means the fact stays tiny (roughly the count of claims ever filed), and cycle time is a stored subtraction rather than an aggregation. Updates touch a single row when a milestone lands. Contrast the periodic-snapshot alternative, which would append a row per open claim every day and balloon for numbers that do not change until the next milestone. |

#### Why not the other fact shapes

| ✕ Transaction fact (one row per milestone) | ✓ Accumulating snapshot (one row per claim) |
| --- | --- |
| Insert-only, never updated. Great for counting events. But cycle time forces you to pivot a claim's `submitted` and `adjudicated` rows back together with a self-join, and listing claims stuck mid-lifecycle means proving a row's absence. Wrong tool for gap reporting. | Row created at `submitted`, UPDATEd at `adjudicated` and `paid`. Cycle time is `paid_date_key` minus `submitted_date_key`, precomputed. Stuck claims are `adjudicated_date_key IS NOT NULL AND paid_date_key IS NULL`. The lifecycle question and the model shape line up exactly. |

**Follow-up questions**

1. A claim can be denied at adjudication and never paid. How does the model represent that without looking like missing data?\
   *Tests whether they use `claim_status` plus a permanently-null `paid_date_key` as a valid end state rather than an incomplete row.*
2. The director now wants the average time in each milestone by submission month. Why can't you SUM the days_* columns to get there?\
   *Tests additivity awareness: durations are non-additive across claims and must be averaged.*
3. Compliance adds a fourth checkpoint, 'reviewed', between submitted and adjudicated. What changes in the model?\
   *Tests whether they extend the same row with another date key and lag measure rather than reaching for a new fact table.*
4. How would you also answer 'how many claims were open on the last day of each month'?\
   *Tests whether they recognize that count-open-over-time is a periodic-snapshot question that complements, not replaces, the accumulating snapshot.*

</details>
