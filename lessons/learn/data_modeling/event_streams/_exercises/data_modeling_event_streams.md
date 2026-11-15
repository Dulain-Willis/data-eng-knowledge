# Event Streams - Exercises

Lesson: [data_modeling_event_streams.md](../data_modeling_event_streams.md)

### Exercise 1 of 12

**● TASK**

Design an append-only events table for an event-driven system. Each event should be immutable once written.

<details>
<summary><strong>Solution</strong></summary>

#### Event sourcing: store what happened, not the current state

The technique this challenge asked you to apply is **event sourcing**: instead of a table whose rows you overwrite as things change, you keep an append-only log where every row is a fact that already happened. The `events` table never sees an `UPDATE` or a `DELETE`; the only write is an `INSERT`. Current state is something you derive by replaying the log, not something you store and mutate in place. That single shift is what makes the design immutable, auditable, and replayable.

![Schema diagram](../_images/data_modeling_event_streams_exercise_1_schema.png)

*One immutable row per fact. Rows are only ever inserted, never changed.*

Each column earns its place. `event_id` is the primary key and the log's order: a monotonic identity so you can read events back in the exact sequence they were written. `event_type` names what happened ('OrderPlaced', 'PaymentCaptured') so one table can hold many kinds of fact. `aggregate_id` groups every event about the same entity, the order or the user, so you can replay just that entity's history. `payload` carries the event-specific detail, kept flexible because different `event_type` values describe different things. `occurred_at` records when the fact happened, and `source_service` says who emitted it, which is priceless when many services write to the same log.

| Pitfall: The mutable-status column |
| --- |
| The most common miss is adding a `status` column you plan to flip from 'pending' to 'shipped'. The moment you `UPDATE` that column you've thrown away the fact that it was ever pending, and the log stops being append-only. In event sourcing a status change is a NEW row, a `StatusChanged` event, not an edit to an old one. If you find yourself wanting to overwrite anything on `events`, model it as another event instead. |

| ✕ State table (mutable) | ✓ Event log (append-only) |
| --- | --- |
| One row per order; `status` is overwritten on each change. You always know the current value, but the history is gone and an `UPDATE` bug is unrecoverable. | One row per thing that happened, keyed by `event_id` and grouped by `aggregate_id`. Current status is derived by replaying events; every prior state is still on disk, so you can audit or rebuild at any point. |

| Real world: Where this shows up |
| --- |
| This is the shape behind bank ledgers, order pipelines, and audit trails. Because the log is immutable you can build several read models from the same `events` stream, replay it into a fresh projection after a bug, or hand it to another team's service by `event_type`. Enforcing immutability at the boundary, a table that only accepts `INSERT`s, is often done with a database trigger or a write-only role so nothing can quietly mutate a past fact. |

**Follow-up questions**

1. How would you reconstruct an order's current status from this table?\
   *Tests that they understand state is derived by replaying events filtered by `aggregate_id`, ordered by `event_id`.*
2. What would you add if 2 services could emit events for the same aggregate at the same time?\
   *Pushes toward an ordering or version column per `aggregate_id` to detect concurrent writes.*
3. The `payload` shape differs per `event_type`. How do you keep readers from breaking when it evolves?\
   *Tests schema-versioning of events and why `payload` is kept flexible rather than split into typed columns.*

</details>


<br>

### Exercise 2 of 12

**● TASK**

Create an audit log table that tracks all changes across the system with enough detail to reconstruct what happened.

<details>
<summary><strong>Solution</strong></summary>

#### One append-only log for every change

The concept this challenge asks you to apply is the **immutable audit log**: a single append-only table where every insert, update, and delete anywhere in the system writes one row, and no row is ever changed again. Instead of scattering `updated_by` and `updated_at` columns across every business table, you record each change as its own event. That is event sourcing in miniature, the log of what happened becomes the source of truth you can replay to reconstruct any record's history.

![Schema diagram](../_images/data_modeling_event_streams_exercise_2_schema.png)

*One row per change. `table_name` + `record_id` point back at the row that changed; `old_values` and `new_values` carry the before/after snapshot.*

Read the columns as answers to who-what-when. `table_name` and `record_id` say WHICH row changed, kept as loose text (not a foreign key) so the log can cover every table without one FK per target. `operation` says WHAT kind of change ('INSERT', 'UPDATE', 'DELETE'). `changed_by` and `changed_at` are the WHO and WHEN. The pair that actually lets you reconstruct history is `old_values` and `new_values`: store the row's before and after state as `jsonb`, and any table's shape fits the same 2 columns. An UPDATE fills both, an INSERT leaves `old_values` null, a DELETE leaves `new_values` null.

| Key insight: Why jsonb instead of a column per field |
| --- |
| The log has to describe changes to tables you haven't designed yet. A flat `old_email` / `new_email` pair only works for one table; `old_values` and `new_values` as `jsonb` snapshots let one schema audit the whole system. You trade strict typing for universality, which is the right trade for a cross-cutting log. |

| Pitfall: Common pitfall: mutable columns on the business table |
| --- |
| The tempting wrong answer is to bolt `last_modified_by` and `last_modified_at` onto each table and call it auditing. That only ever remembers the MOST RECENT change, the previous values are overwritten and gone. You cannot reconstruct what happened, only what the row looks like now. Auditing needs a separate row per change, never an updated cell. |

| ✕ Mutable columns on each table | ✓ Append-only `audit_log` |
| --- | --- |
| Add `modified_by` / `modified_at` in place. Each write overwrites the last. History depth is exactly one; a DELETE erases the row and its trail together. No way to answer 'what was the price last Tuesday'. | Append one row per change with `old_values` / `new_values`. History is unbounded and ordered by `changed_at`. A DELETE is just another logged event, so the record survives its own deletion. |

The defining property is that the log is immutable, rows are only ever inserted, never updated or deleted. That is what makes it trustworthy: to replay a record's life you filter by `table_name` and `record_id`, order by `changed_at`, and walk the `new_values` forward. In production this same shape shows up as change-data-capture streams, database triggers writing to a history table, and event-sourced systems where the event log, not the current-state table, is canonical.

**Follow-up questions**

1. How would you enforce that `audit_log` is truly append-only, so even an admin can't edit history?\
   *Tests whether the learner knows immutability is enforced (revoke UPDATE/DELETE grants, INSERT-only triggers), not just intended.*
2. The log grows forever. How do you keep it queryable, by partitioning on `changed_at`, archiving cold ranges, or both?\
   *Tests awareness that an unbounded append-only table needs a retention and partitioning story.*
3. If `record_id` values collide across tables (2 tables both have id 100), does storing `table_name` alongside it fully disambiguate the target?\
   *Tests understanding of why the polymorphic pointer needs both columns to identify a row.*

</details>


<br>

### Exercise 3 of 12

**● TASK**

Design a clickstream log table that is strictly INSERT-only. No updates or deletes are allowed.

<details>
<summary><strong>Solution</strong></summary>

#### An immutable log is just an append-only table

The concept the section named is the **immutable log**: a table you only ever `INSERT` into, never `UPDATE` or `DELETE`. Each row records that a thing happened at a moment in time, and once written it is frozen. A click is an event, not a piece of state, so there is nothing to edit later. When you designed `page_clicks`, every column describes the click as it occurred: who (`user_id`), in which visit (`session_id`), where (`page_url`), on what (`clicked_element`), and when (`occurred_at`). Nothing in that row will ever be corrected, because the click already happened exactly as recorded.

![Schema diagram](../_images/data_modeling_event_streams_exercise_3_schema.png)

*One flat event table. A surrogate PK, the dimensions that describe the click, and the moment it happened.*

| Key insight: Why the key is a surrogate, not the data |
| --- |
| `click_id` is a **surrogate key**: a system-generated id (a `bigint` sequence or a uuid) whose only job is to name the row uniquely. You reach for one here because there is no natural key that safely identifies a click. It is tempting to use `(user_id, occurred_at)`, but the same user can fire 2 clicks in the same millisecond, and a timestamp is a value you might want to trust rather than a guaranteed-unique identifier. The surrogate sidesteps all of that: it is unique by construction and never has to change. |

| Pitfall: The columns an immutable log must NOT have |
| --- |
| The most common mistake on this shape is bringing state-table habits: adding an `updated_at`, an `is_deleted` flag, or a `status` column you plan to flip later. In an append-only log none of those make sense, because a row is never revisited. If a click was later found to be a bot, you do not update the row, you record a new observation elsewhere. One timestamp, `occurred_at`, the event time, is all a log row needs. |

| ✕ Mutable state table | ✓ Immutable log |
| --- | --- |
| A `carts` or `user_profile` row is the current truth. You `UPDATE` it in place, keep an `updated_at`, and the past is overwritten. You store WHAT IS. | A `page_clicks` row is a fact that already happened. You only `INSERT`, keep `occurred_at`, and the past is preserved forever. You store WHAT HAPPENED. |

| Real world: In production... |
| --- |
| Append-only logs are the backbone of analytics and event sourcing. Because rows never change, the table partitions cleanly by `occurred_at`, replicates without update conflicts, and can be replayed to rebuild any downstream aggregate. Teams often enforce the rule at the boundary too, granting the ingestion role `INSERT` only, so an accidental `UPDATE` fails as a permission error rather than corrupting history. |

**Follow-up questions**

1. If GDPR forces you to erase a user, how do you honor that without breaking the append-only rule?\
   *Tests whether they reach for tombstone events or crypto-shredding a per-user key instead of a raw DELETE.*
2. The same click could arrive twice from a retrying client. How do you dedupe an append-only log?\
   *Pushes toward an idempotency key from the producer rather than an UPDATE-on-conflict.*

</details>


<br>

### Exercise 4 of 12

**● TASK**

Create an order status events table that tracks each order's lifecycle immutably, using new rows instead of updates.

<details>
<summary><strong>Solution</strong></summary>

#### An append-only event log

Event sourcing changes one habit: an order's status is no longer a column you overwrite. Each change becomes its own row in `order_events`. The newest row is the current status, and every earlier row is the history. Nothing is updated in place and nothing is deleted, so the table is an **immutable log**.

![Schema diagram](../_images/data_modeling_event_streams_exercise_4_schema.png)

*One row per status change. `order_id` groups an order's events and `created_at` orders them in time.*

| Pitfall: An `UPDATE` erases the history you need |
| --- |
| The instinctive design is an `orders` table with a `status` column that you `UPDATE` from 'pending' to 'shipped' to 'delivered'. That table can tell you the current status and nothing else. When someone asks when the order shipped or how long it sat in 'pending', the answer is gone, because each `UPDATE` overwrote the previous state. |

Each column has one job. `event_id` is a surrogate key, so 2 events with the same `order_id` and status stay distinct. `created_at` defines "latest", and that makes the current state a query: run `ROW_NUMBER()` partitioned by `order_id` and ordered by `created_at DESC`, then keep rank 1.

**`order_events` schema and current-status read**

```sql
CREATE TABLE order_events (
    event_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id   BIGINT      NOT NULL REFERENCES orders (order_id),
    status     TEXT        NOT NULL,
    notes      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

/* Group events per order so latest-per-order queries stay cheap. */
CREATE INDEX idx_order_events_order_time
    ON order_events (order_id, created_at DESC);

/* Current status = the newest event for each order. */
WITH ranked AS (
    SELECT
        order_id,
        status,
        created_at,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY created_at DESC
        ) AS rn
    FROM order_events
)
SELECT order_id, status, created_at
FROM ranked
WHERE rn = 1;
```

*The table only ever gets appends. The current view is derived from the log, never stored.*

| Real world: The log is truth, the projection is a cache |
| --- |
| The same shape shows up in shipment tracking, payment state machines, subscription lifecycles and audit trails. Teams often keep both: `order_events` as the source of truth, and a small `orders` projection that holds the current `status` for fast reads and is rebuilt from the log. If a customer disputes a ship date, the log still has the row. |

**Follow-up questions**

1. How would you guarantee that a row in `order_events` can never be changed once it is written?\
   *Immutability has to be enforced, for example by revoking `UPDATE` and `DELETE` grants or adding a trigger that raises an error.*
2. 2 events for one order share the same `created_at`. How do you pick the latest deterministically?\
   *Add the monotonic `event_id` as a secondary sort key.*
3. The log reaches a billion rows. How do you keep current-status reads fast?\
   *Options include a projection table, a materialized view, or partitioning by time.*

</details>


<br>

### Exercise 5 of 12

**● TASK**

Design event sourcing tables for a bank account: an immutable events log and a derived current-state view.

<details>
<summary><strong>Solution</strong></summary>

#### Event sourcing: the log is the truth

Event sourcing means you never store just the current answer. You store every fact that changed it, in order, and treat the sequence of facts as the system of record. Here that split into 2 tables you drew: `account_events`, the append-only log of what happened, and `accounts`, the derived current-state you keep so a balance read is one row lookup instead of a re-sum of history. The log is authoritative; `accounts` is a convenience you could throw away and rebuild by replaying the log.

![Schema diagram](../_images/data_modeling_event_streams_exercise_5_schema.png)

*The immutable log (`account_events`) points at the derived state (accounts) via `account_id`. One row per account in accounts; many events per account in the log.*

Notice which way the foreign key points. Each row in `account_events` carries an `account_id` that references the one row in `accounts` for that account. That is the many-to-one shape of a log: an account has many events, an event belongs to exactly one account. The `event_id` is the log's own primary key so every fact is individually addressable and the natural ordering key; `occurred_at` records when the fact happened, which is what you fold over to rebuild `balance`.

| Trick: 2 tables, 2 jobs |
| --- |
| The insight that cracks this shape is refusing to fold the 2 roles into one table. A single `accounts` table with a mutable `balance` loses history the moment you `UPDATE`. A single `account_events` table with no `accounts` makes every balance read a full re-aggregation. You need both: the log for truth and audit, `accounts` for cheap reads. `accounts` is a materialized fold of the log keyed by `account_id`. |

| Pitfall: Common pitfall: a mutable balance and no log |
| --- |
| The version most people reach for is one `accounts` table where a deposit does `UPDATE accounts SET balance = balance + 100`. It answers 'what is the balance' fine, but it cannot answer 'why', 'when', or 'what was it last Tuesday', and a buggy update silently corrupts the only copy of the number. Event sourcing exists precisely to make those questions answerable and to make corruption recoverable by replay. |

| Key insight: Immutable means enforced, not just intended |
| --- |
| 'Append-only' is a property you protect, not a comment. In production you revoke `UPDATE` and `DELETE` on `account_events` and only grant `INSERT`, so a corrected mistake is a new compensating event (a reversal), never an edited past. That is what makes the log trustworthy as an audit trail and what lets you rebuild `accounts` bit-identically by replaying from the beginning. |

| ✕ Mutable state only | ✓ Event-sourced (log + derived state) |
| --- | --- |
| One `accounts` row per account; every transaction is an in-place `UPDATE balance`. Reads are cheap, but history, audit, and 'balance as of date X' are impossible, and a bad write overwrites truth. | `account_events` holds every deposit and withdrawal as an immutable row; `accounts.balance` is a fold you maintain on each insert. Reads stay cheap AND you can audit, time-travel, and rebuild state from the log after any bug. |

| Real world: In production this is the ledger pattern |
| --- |
| Banks, payment processors, and inventory systems almost never store a mutable balance alone. They keep an immutable ledger like `account_events` and a projection like `accounts` (often several projections for different read patterns). When the projection and the log disagree, the log wins and the projection is rebuilt, never the other way around. |

**Follow-up questions**

1. How would you get an account's balance as of a past date without a stored snapshot?\
   *Tests whether they understand `accounts.balance` is a fold: sum `amount` over `account_events` where `occurred_at <= :date`.*
2. If replaying the whole log on every rebuild gets slow, what would you add?\
   *Looks for periodic snapshot rows so replay starts from the latest snapshot plus later events, not from the beginning.*
3. A customer disputes a withdrawal that was recorded in error. How do you fix it?\
   *Checks that they append a compensating reversal event rather than `DELETE`-ing the row, preserving immutability.*

</details>


<br>

### Exercise 6 of 12

**● TASK**

Create an event-sourced inventory system with an events log and a projection table showing current stock levels.

<details>
<summary><strong>Solution</strong></summary>

#### Event sourcing: the log is the truth

Event sourcing means you never overwrite a stock number in place. Each change is appended to a log as an immutable fact, and the current quantity is derived by replaying those facts. Your 2 tables split that job: `inventory_events` is the append-only ledger of what happened, and `current_inventory` is a **projection**, a precomputed answer to 'how many do we have right now?' so a read never re-sums the whole log.

![Schema diagram](../_images/data_modeling_event_streams_exercise_6_schema.png)

*Many events per product fold into one stock row: `inventory_events.product_id` is the FK to the projection's `product_id` PK.*

The primary keys carry the one-to-many. The log is keyed by a surrogate `event_id` because it holds many rows per product. The projection is keyed by `product_id` because it holds exactly one. The log stores a signed `quantity_delta` (+50 on a receipt, -3 on a sale), not an absolute count, so no row ever needs editing.

| Pitfall: One mutable table loses the history |
| --- |
| The tempting design is a single table updated with `SET quantity_on_hand = quantity_on_hand - 3` on every sale. It works until someone asks why a product sits at 12. The history was overwritten, so you cannot audit it, replay it, or repair a bad write. |

| Key insight: The projection is a disposable cache |
| --- |
| Since `quantity_on_hand` is just `SUM(quantity_delta)` per `product_id`, you can drop `current_inventory` and rebuild it from the log at any time. Ledgers and bank balances work the same way. Let only the process that folds new events forward write to the projection, or the 2 drift apart. |

**Follow-up questions**

1. How would you report stock as of last Tuesday when the projection holds only today's number?\
   *Replaying `inventory_events` up to an `occurred_at` cutoff gives time travel.*
2. If products move between warehouses, how do the keys change?\
   *The projection's grain becomes (`product_id`, `warehouse_id`), a composite PK.*

</details>


<br>

### Exercise 7 of 12

**● TASK**

Design a website clickstream schema where each page view is an immutable event recording the user, page URL, referrer and view time. Page views arrive with no session id; sessions are derived from them by grouping a user's views with no gap over 30 minutes. Store each session's user, start, end and page count so sessions can be rebuilt from the page view log, and record which session each page view was assigned to.

<details>
<summary><strong>Solution</strong></summary>

#### The log is the truth, sessions are a reading of it

Clickstream modeling is **event sourcing** at its most common: the page view log is the source of truth, and a session is state you derive from it, never state you edit. Raw views carry no session id, because a session only exists once you look at the gaps between one user's views. The trap is a `sessions` row you keep updating while the user browses. It works until the 30-minute rule changes or a view is corrected, and then there is nothing to rebuild the sessions from.

![Schema diagram](../_images/data_modeling_event_streams_exercise_7_schema.png)

*`page_view_events` is insert-only; `sessions` and `session_page_views` are derived from it and can be dropped and rebuilt.*

1. **Keep `page_view_events` append-only**

   Each row is one view, as it happened: `user_id`, `page_url`, `referrer_url`, `viewed_at`. There is no session column, because the event cannot know its session when it is written. Nothing here is ever updated.

2. **Derive `sessions` by sessionization**

   Per user, ordered by `viewed_at`, take the gap to the previous view with `LAG`, flag a new session when it exceeds 30 minutes, and number sessions with a running `SUM` of the flags. `started_at`, `ended_at` and `page_view_count` are the `MIN`, `MAX` and `COUNT` of each group.

3. **Record the assignment beside the log, not in it**

   `session_page_views` maps each `view_id` to its `session_id`. The assignment is derived output, so it lives in its own table and the raw event stays untouched. Deriving `session_id` deterministically (from `user_id` plus the session start) means a rebuild produces the same ids.

| Pitfall: A session row you keep patching cannot be replayed |
| --- |
| Opening a `sessions` row on the first view and bumping `ended_at` and the count on every later view stores only the latest state. Once the threshold or a view changes, the old answer is baked in and nothing is left to recompute it. |

| Real world: Changing the threshold is a replay, not a migration |
| --- |
| When product decides that mobile sessions end after 10 minutes instead of 30, teams drop the derived tables and re-run sessionization over the log. The same split shows up in order lines derived from cart events and in trips derived from GPS pings. |

The shape to remember: one insert-only table of facts, and every grouping of those facts (sessions, the view-to-session map) is a projection you can throw away and regenerate.

**Follow-up questions**

1. How would you add click and search events with different properties to the same log?\
   *Extends the log to several event types: a shared envelope plus a `properties` payload.*
2. How would you keep `sessions` current without rebuilding the whole history every hour?\
   *Incremental sessionization: only users with new views need their recent sessions recomputed.*
3. What would you add so a session can be tied to the page it was entered from?\
   *An entry page is derived too: the `page_url` of the earliest view in each session.*

</details>


<br>

### Exercise 8 of 12

**● TASK**

Create a funnel events table to track user progression through conversion stages.

<details>
<summary><strong>Solution</strong></summary>

#### Model the funnel as events, not columns

A funnel is a sequence of stages a user moves through, and the clean way to store it is **event sourcing**: one row every time a user enters a stage, rather than one wide row per user with a column for each stage. Each row records who moved (`user_id`), which funnel and stage (`funnel_name`, `stage`), and when they entered and left (`entered_at`, `exited_at`). That is exactly the shape you built, and it is the shape that survives contact with a product team that keeps changing the funnel.

![Schema diagram](../_images/data_modeling_event_streams_exercise_8_schema.png)

*One row per (user, funnel, stage) entry. The grain is the stage transition, not the user.*

| Pitfall: The wide table that seems simpler |
| --- |
| The tempting wrong answer is one row per user with a timestamp column per stage: `signup_at`, `activated_at`, `purchased_at`. It reads well for one fixed funnel, but it breaks the moment marketing adds a stage (now it is a schema migration and a backfill), it cannot represent a user who enters the same stage twice, and it has no place to put a checkout funnel that is nothing like the onboarding one. The event table absorbs all 3 changes with zero DDL: a new stage is just a new value in `stage`. |

| Key insight: Grain is the whole design |
| --- |
| Every column here earns its place by answering "what does one row mean?" A row means: this user entered this stage of this funnel at this time. That is the **grain**. Because a user can pass through many stages, and the same stage across different funnels, none of `user_id`, `stage`, or `funnel_name` is unique on its own. The natural key is the composite of user, funnel, stage, and `entered_at` together, which is why a surrogate `event_id` primary key is the pragmatic choice: it is a single stable handle for a row whose real identity is a four-column combination. |

Note the 2 timestamps do different jobs. `entered_at` is mandatory and is set the instant the event happens; `exited_at` stays `NULL` while the user is still sitting in that stage and gets filled in when they move on. That `NULL` is meaningful, not missing data: it is how you find everyone currently stuck at a stage. Storing only a single event timestamp would throw away dwell time, which is usually the first thing anyone asks a funnel.

**Follow-up questions**

1. How would you compute the conversion rate from `stage` 'cart' to `stage` 'purchase' from this table?\
   *Tests whether the event grain actually supports funnel analysis: a self-join or a window over `user_id` ordered by `entered_at`.*
2. What changes if a funnel's stages have a defined order and you must stop a user from skipping one?\
   *Pushes on whether ordering lives in the data (a `stage_number`) or is enforced by the application.*
3. At a billion events, how would you partition this table?\
   *Checks that they reach for time-range partitioning on `entered_at`, since funnel queries are almost always windowed by date.*

</details>


<br>

### Exercise 9 of 12

**● TASK**

Design a schema for ride events in which each ride references a driver. A ride can arrive before its driver's profile reaches the warehouse, and some rides arrive hours after they happened. Store every ride the moment it arrives, linked to a placeholder driver row that is filled in once the profile lands, and keep both when each ride occurred and when it was recorded.

<details>
<summary><strong>Solution</strong></summary>

#### Rides that beat their driver

A late-arriving dimension member is the mirror image of a late event: the fact shows up first, and the thing it references shows up later. Here a ride lands before its driver's profile does. Rejecting the ride loses data, and parking it in a holding area delays every report. The standard move is a **placeholder member**: insert a row in `drivers` that carries only the `driver_id` the ride brought, flag it with `is_placeholder`, and let the ride reference it right away.

![Schema diagram](../_images/data_modeling_event_streams_exercise_9_schema.png)

*`ride_events` always points at a `drivers` row. An early ride creates that row as a placeholder, and the real profile later fills it in place.*

1. **Insert the placeholder on first sight**

   When a ride arrives with a `driver_id` that `drivers` has never seen, insert that id with `is_placeholder` set to true and the descriptive columns left empty. The ride is then written as usual, with both `event_time` and `recorded_at`, and joins cleanly from its first second.

2. **Fill the same row when the profile lands**

   The profile feed updates the existing row by `driver_id`: it sets the name and city, flips `is_placeholder` to false, and stamps `profile_received_at`. No ride is touched, because the key the rides reference never changed. The event log stays append-only, and only the dimension row matures.

| Pitfall: A missing driver should never mean a missing ride |
| --- |
| If rides are inner-joined to `drivers` at load time, an early ride is silently dropped. If the ride is stored with a null `driver_id` instead, someone must later find and patch every such ride. Both choices leak rides out of the reports. The placeholder keeps every ride linked from the start. |

| Key insight: The ride still needs both clocks |
| --- |
| Rides from a phone that was offline arrive hours late. Bucketing by `event_time` puts each one in the hour it happened, and `recorded_at - event_time` measures how late it was. With `profile_received_at` on the driver side, you can also see how long each placeholder waited for its profile. |

**Follow-up questions**

1. How would you list placeholder drivers that are still waiting a day after their first ride?\
   *Compare `is_placeholder` rows against the earliest `recorded_at` of their rides.*
2. What changes if a driver's `home_city` must be reported as it was at the time of each ride?\
   *Filling in place loses older values, so the dimension needs dated versions and a back-dated first version.*
3. What if the profile feed sends a driver whose id was mistyped on the rides?\
   *The placeholder never resolves, so you need a rule for merging or retiring orphaned placeholders.*

</details>


<br>

### Exercise 10 of 12

**● TASK**

Create a watermark tracking table alongside an events table to track processing progress and detect late-arriving data.

<details>
<summary><strong>Solution</strong></summary>

#### A watermark is a per-source high-water mark

A **watermark** is the answer to one question: for each source, what is the latest event time we have already processed? You store it once per source, and every time a batch finishes you push it forward to the newest `event_time` you saw. Anything that arrives later carrying an `event_time` below that mark is late-arriving data. The whole design is those 2 ideas, a grain of one row per source, and a stored maximum you compare new events against.

![Schema diagram](../_images/data_modeling_event_streams_exercise_10_schema.png)

*events is the fact stream at grain one-row-per-event; watermarks is progress state at grain one-row-per-source.*

The grain choice is the crux. The `events` table is at the grain of a single event, so its key is `event_id`. The `watermarks` table is at the grain of a single source, so its key is `source_id`, exactly one row per source, holding that source's `max_event_time` and an `updated_at` bookkeeping stamp. That grain is why `watermarks.source_id` can be the primary key and why `events.source_id` points at it as a foreign key.

| Pitfall: Don't collapse the watermark to one global row |
| --- |
| The tempting shortcut is a single-row table holding one `max_event_time` for the whole pipeline. It works until a second source lags: one slow source drags the global mark backward and either blocks fast sources or floods you with false late-arrivals. Keying `watermarks` on `source_id` lets each source advance independently, that is what makes the grain per-source, not per-pipeline. |

| Key insight: `event_time` and `ingestion_time` are 2 different clocks |
| --- |
| The watermark tracks `event_time` (when the thing happened at the source), never `ingestion_time` (when we received it). Late data is precisely the case where these diverge: a row lands now with an `ingestion_time` of today but an `event_time` from last week. You detect it by comparing the incoming `event_time` against the source's stored `max_event_time`, if it is lower, it is late. Keeping both columns on `events` is what lets you measure that lag. |

**Follow-up questions**

1. Where would you record how late a late-arriving event was, rather than just flagging it?\
   *Extends the grain: a per-event `is_late` flag or a `lateness = max_event_time - event_time` column on events versus a separate late-arrivals audit table.*
2. What changes if a single source can be processed by several workers at once?\
   *Tests concurrency on the watermark row: advancing `max_event_time` with a GREATEST(...) upsert so out-of-order commits never move the mark backward.*

</details>


<br>

### Exercise 11 of 12

**● TASK**

Design a complete event-sourced order management system with an immutable log of order events (placed, paid, shipped, cancelled) as the source of truth and a materialized current-state view of each order rebuilt from it. Each order belongs to a customer. Warehouse scanners queue shipping events offline and send them hours later, so every event keeps when it happened apart from when it was received. A mistaken event is never edited: a correcting event is appended that names the event it corrects.

<details>
<summary><strong>Solution</strong></summary>

#### One log, everything else derived

This capstone puts event sourcing, append-only corrections and late-arriving events into one model. The key decision is which table is the truth. Here it is `order_events`, one row per thing that happened to an order. The `orders` table is a **projection you can throw away and rebuild** by replaying the log for each `order_id`. If you get that backwards and treat `orders` as the record, every other requirement in the statement has nowhere to live.

![Schema diagram](../_images/data_modeling_event_streams_exercise_11_schema.png)

*Many `order_events` per order; `corrects_event_id` points a correction at the event it fixes, and `orders` is the projection replayed from the log.*

| Pitfall: An in-place status update erases the lifecycle |
| --- |
| The tempting design is a single `orders` table where 'placed' is overwritten with 'shipped'. That table cannot tell you when the order shipped or what it looked like before a cancellation. It also cannot absorb a late scan or a fix without destroying the row it replaces. In the event-sourced design, `orders` stays, but only as a projection. |

1. **Append corrections, never edit**

   A wrong 'shipped' event stays in the log. A new event is appended whose `corrects_event_id` points at it, and the projection skips any event that has been corrected. The self-reference keeps the audit trail intact, and a replay reproduces exactly what the system believed at any point.

| Key insight: 2 timestamps keep late scans in their real place |
| --- |
| An offline scanner's event arrives hours after it happened. `occurred_at` records when it happened, and the projection replays in that order, so status lands correctly. `received_at` records when the event arrived, which is what tells you an event was late. |

**Follow-up questions**

1. How would you rebuild `orders` from scratch if the projection were corrupted?\
   *Treats `orders` as a fold over `order_events` sorted by `occurred_at`, skipping corrected events.*
2. Replaying years of events per order gets slow: what would you add so the projection stays cheap to rebuild?\
   *Points at periodic snapshots, which section 2 warns you will eventually need.*

</details>


<br>

### Exercise 12 of 12

**● TASK**

Design a mobile app's clickstream schema with an append-only hit log as the source of truth, a sessions table, and a per-user-per-day summary rebuilt by replaying the log. Offline phones upload queued hits hours late, so each hit records when it happened and when it arrived, and the summary counts it toward the day it happened. A hit may arrive before its session's start event and must still link to that session. A mislogged hit is never edited: a correction arrives as a new event pointing at the hit it reverses.

<details>
<summary><strong>Solution</strong></summary>

#### One log, everything else replayed

This capstone puts **event sourcing** at the center of a clickstream. The hit log is the only table that records truth. `sessions` and `daily_user_summary` are things you can throw away and rebuild by replaying it, and that one choice settles everything else. The trap is treating the summary as the source of truth. A late offline hit then has nowhere to go except an in-place bump to yesterday's row. A mislogged hit gets edited, and the log can no longer explain the numbers.

![Schema diagram](../_images/data_modeling_event_streams_exercise_12_schema.png)

*`page_view_events` is the insert-only source of truth; `daily_user_summary` is rebuilt from it by replay.*

1. **Keep the hit log append-only, corrections included**

   `page_view_events` only ever receives inserts. A wrong hit stays where it is. A new row with `event_type` 'correction' and `corrects_event_id` pointing back at it cancels the wrong hit on replay. The self-referencing edge is the whole mechanism: an audit sees both rows, and a replay that skips reversed hits gets the right totals.

2. **Store event time and arrival time**

   `occurred_at` is when the tap happened on the phone, and `received_at` is when the upload landed. The summary buckets by the date of `occurred_at`, so a hit queued offline on Monday and uploaded Tuesday counts toward Monday. `received_at` tells the rebuild job which closed days a late batch touched, so it replays only those days.

3. **Let a hit point at a session you have not met yet**

   When a hit arrives before its session start event, insert a placeholder `sessions` row with `is_inferred` set to true and only `session_id` known. The foreign key holds. When the start event lands, it fills in `user_id`, `device` and `started_at` and clears the flag, and the next replay attributes those hits to the right user.

| Pitfall: Bucketing by arrival puts offline hits on the wrong day |
| --- |
| Grouping the summary by `received_at` is the easy mistake: every hit uploaded after a night offline lands in the next day. The totals still look plausible, so nobody notices until a day with a big upload spike. |

| Key insight: A rebuild replaces rows, it never adds deltas |
| --- |
| `daily_user_summary` is keyed by `(activity_date, user_id)`: one row per user per day. A rebuild overwrites a day's rows from the log instead of incrementing them, so replaying the same day twice gives the same answer. |

**Follow-up questions**

1. A session spans midnight. Which `activity_date` do its hits count toward, and does `sessions` need to change?\
   *Grain edge case: each hit is bucketed by its own `occurred_at`, not by the session start.*
2. Phones sometimes upload the same hit twice. What in `page_view_events` lets a replay drop the duplicate?\
   *An idempotent append: a client-generated `event_id` as the key.*
3. How would you treat a placeholder session whose start event never arrives?\
   *Late-arriving dimension members that stay inferred.*

</details>
