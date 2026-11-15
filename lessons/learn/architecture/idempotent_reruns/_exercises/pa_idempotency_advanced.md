# Idempotent Reruns: Advanced - Exercises

Lesson: [pa_idempotency_advanced.md](../pa_idempotency_advanced.md)

### Exercise 1 of 11

**● TASK**

Two aggregators read the same at-least-once event log. The daily revenue sum feeds a regulatory report, where a replayed duplicate misstates revenue: route it through a checkpointed exactly-once engine that commits into a warehouse revenue table, and validate that table with a quality gate before the report reads it. The real-time page-view counter tolerates duplicates, so give it its own cheaper path to the dashboard. Show each aggregator's freshness tier.

**Starting canvas** (already placed for you):

- Event log: payment and page-view events (30-day retention, replay-capable, at-least-once delivery) (source, Kafka)
- Regulatory revenue report (finance files this with the SEC; needs exactly-once-correct daily revenue) (consumer, API)
- Real-time engagement dashboard (page-view counts; tolerates at-least-once noise) (consumer, Grafana)

<details>
<summary><strong>Solution</strong></summary>

#### One log, two guarantees

Streaming idempotency is harder than the batch kind because there is no partition to swap out. A batch rerun overwrites a whole slice of the destination and lands on the same answer, but a stream never closes a slice you can replace. The `Kafka` log here delivers at-least-once, so after a crash or a rebalance it replays events the consumer already applied. Whether that replay hurts depends on the pattern. A **running sum is not naturally idempotent**: every replayed payment adds to revenue again, so the financial close has to be engineered against it. A live page-view count can absorb the same noise, so it stays cheap.

```mermaid
flowchart LR
    n0[("Event log<br/>(Kafka)")]
    n1["Exactly-once engine<br/>(Flink)"]
    n2[("Revenue table<br/>(warehouse)<br/>SLA: #60; 24h")]
    n3["Data-quality gate<br/>(quality_gate)"]
    n4(["Regulatory revenue report<br/>(API)"])
    n5["Page-view counter<br/>(transform)<br/>SLA: real-time"]
    n6(["Engagement dashboard<br/>(Grafana)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n0 --> n5
    n5 --> n6
```

*One retained log fans out to two aggregators; only the daily revenue path carries the engineered exactly-once chain.*

Exactly-once is not something the log hands you; it is built across 3 links. The engine keeps its running total in checkpointed state, and it commits that state together with the consumed offsets into the revenue table in one transaction. When the log replays a range after a restart, the same offsets re-commit atomically instead of being summed twice, and that is what makes a rerun leave revenue unchanged.

| ✕ Revenue sum, engineered | ✓ Page-view count, tolerant |
| --- | --- |
| Every duplicate inflates a filed number, so the path runs on a checkpointed engine with a transactional commit into the warehouse revenue table, and a quality gate validates that table before the report reads it. Correctness first, cost second. | A replayed view nudges a live chart by a rounding error, so the path skips checkpointing, the transactional sink and the gate, and runs as a separate, cheaper reader off the same `Kafka` log. Freshness first. |

| Pitfall: Not every stream needs the expensive guarantee |
| --- |
| The tempting design is one aggregator for both, either deduping downstream or holding the dashboard to the same exactly-once machinery. That drags the cheap path up to the cost of the financial close and couples two readers with opposite needs, so a stall on one blocks the other. Decide per pattern which one needs engineering, and give each its own reader. |

| Real world: Replay is only safe on the engineered path |
| --- |
| Because the log is retained, a bug in the revenue math is fixed by correcting the engine and replaying the affected days into the `Revenue table` from the same offsets. That replay is only safe because this path was engineered to be idempotent; replaying into the page-view counter would simply count twice. |

**Follow-up questions**

1. The revenue bug is found after the report was filed. How do you correct the numbers using only the retained log?\
   *Replay into an idempotent sink as the recovery mechanism, rather than a batch partition rerun.*
2. What does the data-quality gate actually check before the regulatory report reads the revenue table?\
   *Concrete validations: row counts, no missing days, totals within expected bounds.*
3. If the engagement team later wanted page views that are exact for billing advertisers, which path changes and why?\
   *Whether a tolerant pattern becomes one that needs explicit engineering once a duplicate costs money.*

</details>


<br>

### Exercise 2 of 11

**● TASK**

Audit the claim. The vendor diagram says the Flink job delivers exactly-once via 2PC, but the revenue dashboard's numbers double after every checkpoint recovery. Apply the section's across-which-boundary audit: name the boundary where the engine's guarantee ends and pick a repair so the new sink actually carries the property its name claims.

**Starting canvas** (already placed for you):

- Kafka events topic (source, Kafka)
- Flink streaming job (vendor diagram label: exactly-once via 2PC) (transform, Flink)
- Plain Postgres revenue_events: INSERT INTO append (no PK constraint, no UPSERT, no transaction integration with Flink) (storage, PostgreSQL)
- Revenue dashboard (numbers double after every Flink checkpoint recovery) (consumer, Metabase)

<details>
<summary><strong>Solution</strong></summary>

#### Where the guarantee stops being true

The property under audit has a name: **end-to-end exactly-once**, a claim about the whole path from `Kafka` to the dashboard, not something any single box owns. Flink's 2PC checkpointing earns exactly-once for its own state and any sink that enrolls in the checkpoint barrier. The across-which-boundary audit asks how far that enrollment reaches: only to the last hop that participates. Here that hop is a plain `INSERT INTO revenue_events` with no `PK`, no `ON CONFLICT`, and no transaction shared with Flink, so the guarantee ends one box short of the dashboard.

| Pitfall: A checkpoint rewind replays, and a bare append never forgets |
| --- |
| On a task failure Flink restores the last checkpoint and reprocesses every event consumed since. That is fine for state that rolls back with it, but the earlier `INSERT` already committed those rows, and the replay appends them again. Nothing collapses the duplicates, so the totals double on exactly the recovery the diagram promised was safe. The '2PC' label describes Flink's internal protocol, not the sink write. |

```mermaid
flowchart LR
    n0[("Kafka events topic<br/>(Kafka)")]
    n1["Flink streaming job (exactly-once checkpoints)<br/>(Flink)"]
    n2[("revenue_events, UNIQUE(event_id), INSERT ... ON CONFLICT DO NOTHING<br/>(PostgreSQL)")]
    n3(["Revenue dashboard (stable across recovery)<br/>(Metabase)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
```

*The repair lives entirely at the sink: `revenue_events` gains `UNIQUE(event_id)`, so a replay lands the same keys and dedupes.*

| ✕ Enroll the sink in the transaction | ✓ Make the write idempotent |
| --- | --- |
| Swap the plain insert for Flink's `TwoPhaseCommitSinkFunction`. Writes stage in a DB transaction that pre-commits on the checkpoint barrier and commits only once the checkpoint is confirmed; a rewind aborts the unconfirmed transaction, so replayed rows never survive. This is what '2PC' should have meant past Flink's own boundary. | Give `revenue_events` a `UNIQUE(event_id)` constraint on a deterministic key and write `INSERT ... ON CONFLICT (event_id) DO NOTHING`. A replay re-sends the same keys and the clause drops them, no distributed transaction needed, only an id that comes from the event itself, never `now()` or a serial. |

**Follow-up questions**

1. What do you use for `event_id` when the upstream events carry no natural unique key?\
   *Probes deterministic key construction, e.g. a hash of stable payload fields or a Kafka `(partition, offset)` pair, and why a generated `now()` or serial breaks the dedup.*
2. When would you reach for the transactional 2PC sink over the idempotent upsert?\
   *Checks the tradeoff: 2PC handles non-idempotent side effects and multi-row atomic writes, at the cost of commit latency tied to the checkpoint interval.*

</details>


<br>

### Exercise 3 of 11

**● TASK**

The order service commits to Postgres orders and publishes to Kafka order_events in one handler, with no shared transaction. Downstream, order_analytics is a plain Postgres append with no key on event_id, so each Kafka redelivery double-counts on the dashboard. Fix each boundary with its idempotency building block: feed Kafka by change data capture from Postgres instead of from the handler, make the analytics write idempotent, and use no custom two-phase commit.

**Starting canvas** (already placed for you):

- Order service application (handler currently writes to Postgres orders AND publishes to Kafka order_events with no atomicity) (source, Custom)
- Postgres orders (the application's primary state) (storage, Postgres)
- Order analytics transform (subscribes to Kafka order_events) (transform, Python)
- Kafka order_events topic (storage, Kafka)
- Plain Postgres order_analytics: INSERT INTO append (no PK on event_id, no UPSERT, double-counts on Kafka redelivery) (storage, Postgres)
- Order analytics dashboard (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

#### Two boundaries, two named building blocks

Both fixes have names the section gave you. The first boundary is a **dual write**: the handler commits to `orders` and publishes to `order_events` in the same block, with no shared transaction. If the publish fails after the commit (or the commit fails after the publish), the two stores disagree. The building block is the transactional outbox plus change data capture: write the event as a row in an `outbox` table inside the SAME transaction as the order, then let CDC tail the Postgres log and publish each outbox row to Kafka. One atomic commit, no lost or phantom events.

```mermaid
flowchart LR
    n0[("Order service<br/>(source)")]
    n1[("Postgres orders and outbox<br/>(PostgreSQL)")]
    n2["Outbox CDC tailer<br/>(transform)"]
    n3[/"Kafka order events<br/>(Kafka)"/]
    n4["Order analytics consumer<br/>(transform)"]
    n5[("Order analytics keyed on event id<br/>(PostgreSQL)<br/>Idempotency: upsert")]
    n6(["Order analytics dashboard<br/>(consumer)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n4 --> n5
    n5 --> n6
```

*The handler writes only the order and its `outbox` row in one transaction; CDC owns the publish, and the analytics store upserts on `event_id`.*

The second boundary duplicates for a different reason. Kafka is at-least-once, so `order_analytics` will see some `event_id` values twice after a redelivery or a consumer restart. A plain `INSERT INTO` append counts each arrival, and the dashboard inflates. The fix is an **idempotent consumer**: put a primary key on `event_id` and write with `INSERT ... ON CONFLICT (event_id) DO UPDATE`, an upsert. A redelivered event lands on the same key and changes nothing.

| Pitfall: CDC replaces the second write, it never adds a third |
| --- |
| Do not keep the in-handler publish AND add an `outbox`: that is still a dual write. The handler writes only the `outbox` row and CDC does the publishing. Rolling your own two-phase commit across Postgres and Kafka is the tempting wrong turn the prompt rules out. |

| Key insight: The event carries its own dedupe key |
| --- |
| Idempotency needs a stable identity per event. An `event_id` minted at the source and preserved through Kafka is what makes `ON CONFLICT` safe. If analytics invented a fresh surrogate id per row, every redelivery would look brand new again. |

**Follow-up questions**

1. What if two `outbox` rows for the same order arrive at `order_analytics` out of order?\
   *Tests whether an idempotency key alone handles ordering, or whether you also need a version or sequence column.*
2. Does the outbox plus CDC give you exactly-once end to end?\
   *Checks whether you see it as at-least-once delivery that the consumer's `event_id` upsert makes effectively-once.*

</details>


<br>

### Exercise 4 of 11

**● TASK**

Prepare this pipeline to replay the 14 days a consumer-logic bug corrupted through the corrected Flink job. Rename the existing nodes in place so the replay works: the Kafka source needs retention covering all 14 days (its default is 7), the Flink job needs a named start position at the window start (an offset, a timestamp, or a consumer group reset to it), and the Snowflake sink needs an idempotent write so replayed rows are not counted twice.

**Starting canvas** (already placed for you):

- Kafka events topic (default 7-day retention, too short to cover the 14-day cycle) (source, Kafka)
- Flink streaming job (consumer logic was wrong for the last 14 days; it was restarted but only resumed from the newest events, so the corrupted period was never reprocessed) (transform, Flink)
- Plain Snowflake event_stats: append-only INSERT, so any reprocessing double-counts (storage, Snowflake)
- Event analytics consumer (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

#### Why the replay was blocked in 3 places

Fixing a bad output window the Kappa way means replaying the same event log through the corrected job, not standing up a side batch job. That only works when 3 properties hold along the path at once: the log still holds the start of the window, the job can rewind to an addressable position, and the sink absorbs re-emitted rows without double-counting. This canvas broke all three, which is why every node needed a rename.

```mermaid
flowchart LR
    n0[("Kafka topic, retention #62;= 14d so the window start is still on the log<br/>(Kafka)")]
    n1["Flink job rewinds to a committed start offset / start timestamp at the window start<br/>(Flink)"]
    n2[("Snowflake event_stats via idempotent MERGE keyed on event id<br/>(Snowflake)")]
    n3(["Event analytics dashboard<br/>(consumer)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
```

*Each rename restores one property the replay depends on; drop any one and the replay still fails.*

| ✕ What the job did | ✓ What the replay needs |
| --- | --- |
| Restarting `from-latest` seeks to the newest events, so the 14 corrupted days are never re-read. The offset the corrected code needs to start at is not addressable. | A named start position (a committed or start offset, a start timestamp, or a fresh consumer group reset to the window start), so the job rewinds to exactly the first corrupted event. |

| Pitfall: Append plus replay counts every row twice |
| --- |
| The original sink only ran `INSERT`, so replaying 14 days adds a second copy of every event on top of the wrong numbers. Idempotency is what makes a replay safe to run (and re-run): a `MERGE` keyed on event id updates the existing row instead of appending, so the re-emitted rows land exactly once. |

| Real world: The log is your only backfill source |
| --- |
| Kappa reprocessing has no separate history to fall back on, so retention is a hard dependency: if the topic keeps 7 days you can never replay a 14-day window, no matter how the job is configured. Set retention to cover your longest plausible correction window before you need it. |

**Follow-up questions**

1. Rows outside the 14-day window are correct already. How do you keep the rewind from re-touching them?\
   *Bounding the replay: stop offset / end timestamp, or a `MERGE` that no-ops when the value is unchanged.*
2. What breaks if 2 events share the same key you `MERGE` on?\
   *Tests whether the idempotency key is truly unique per event, not just per user or per minute.*

</details>


<br>

### Exercise 5 of 11

**● TASK**

2 streaming aggregators were built with their destinations crossed. The financial-close job, whose daily revenue feeds an SEC filing and must produce identical numbers across every replay, lands in a Redis counter; the page-view counter behind a five-second engagement dashboard, which tolerates the odd duplicate, runs two-phase commit into a lakehouse table. Rehome each so its destination gives exactly the guarantee its use case is willing to pay for.

**Starting canvas** (already placed for you):

- Kafka payments topic (financial close source) (source, Kafka)
- Kafka pageviews topic (page view source) (source, Kafka)
- Aggregator A: financial close, currently lands in Redis (WRONG) (transform, Flink)
- Aggregator B: page view, currently 2PC into lakehouse (OVER-ENGINEERED) (transform, Flink)
- Redis daily_revenue counter (non-ACID, wrong for financial close) (storage, Redis)
- Iceberg page_views_2pc table (over-engineered for a dashboard) (storage, Iceberg)
- Financial regulatory report consumer (SEC) (consumer, API)
- Engagement dashboard consumer (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

#### Match the guarantee to the bill

Picking a **delivery guarantee** is a spending decision: you buy exactly the correctness the reader of the data needs and no more. Exactly-once is expensive. It needs a transactional sink that commits the aggregate and its input offsets atomically, so a replay lands the same number, and that takes a two-phase commit, coordinated checkpoints and a store that supports atomic commits. At-least-once is cheap and fast: write the counter, retry on failure, and tolerate the occasional double-count. Neither is 'better'; the skill is spending the coordination only where the reader demands it. Here the wires were crossed. The job that needs exactly-once wrote to a store that cannot give it, and the job that is happy with at-least-once paid for a two-phase commit it will never notice.

```mermaid
flowchart LR
    n0[("Kafka payments topic<br/>(Kafka)")]
    n1[("Kafka pageviews topic<br/>(Kafka)")]
    n2["Aggregator A: financial close<br/>(Flink)"]
    n3["Aggregator B: page views<br/>(Flink)"]
    n4[("Iceberg daily revenue table<br/>(Iceberg)")]
    n5[("Redis page views counter<br/>(Redis)")]
    n6(["SEC regulatory report<br/>(API)"])
    n7(["Engagement dashboard<br/>(dashboard)"])
    n0 --> n2
    n2 --> n4
    n4 --> n6
    n1 --> n3
    n3 --> n5
    n5 --> n7
```

*The corrected wiring: the financial close commits exactly-once into the ACID Iceberg table through a two-phase-commit sink, and page views land at-least-once in the cheap Redis counter. Each job now pays exactly the coordination its reader requires.*

| ✕ Financial close | ✓ Page views |
| --- | --- |
| Feeds an SEC filing, so every replay must produce identical numbers. That is a demand for exactly-once, which needs a store that commits the aggregate and the consumed Kafka offsets in one atomic step. `Iceberg` gives you that: the 2PC sink writes a new snapshot only when the checkpoint commits, so a crash-and-replay re-reads the same offsets and rewrites the same snapshot. `Redis` `INCR` cannot: it is a non-transactional counter, and a retried batch double-counts revenue with no way to undo it. | Feeds a five-second dashboard that can absorb a stray duplicate. That is at-least-once territory, and a `Redis` counter is the right tool: one `INCRBY` per batch, sub-millisecond reads, no coordinator. Running two-phase commit into a lakehouse table here is over-engineering. You pay checkpoint latency and commit overhead to protect a number nobody audits, and you still refresh a real-time panel from a batch-committed table. |

| Pitfall: Non-atomic counter for money |
| --- |
| The tempting shortcut for a revenue aggregate is a fast counter: `INCRBY daily_revenue :amount`. It works until the job restarts mid-batch. On replay the aggregator re-emits the batch, the `INCRBY` fires again, and the SEC number is now wrong by whatever the batch held, with no snapshot to roll back to. A counter has no notion of 'I already applied this offset', and that is exactly the property a financial close needs. |

| Key insight: Exactly-once is really idempotent replay |
| --- |
| The lakehouse sink is not magic; it is idempotency plus atomic commit. The aggregate and the input offsets move together, so replaying a committed checkpoint is a no-op and replaying an uncommitted one reproduces the same snapshot. When you cannot get a transactional commit, you recover the same guarantee by making writes idempotent on a key: an upsert keyed by (day, `source_offset`) instead of a blind increment, so a re-applied batch overwrites rather than adds. |

| Real world: In production, cost hides in the guarantee |
| --- |
| Teams reach for exactly-once everywhere because it feels safe, then wonder why their streaming bill and their p99 latency are high. Most pipelines are a mix: the finance and billing paths genuinely need transactional sinks, while metrics, engagement and telemetry are fine on at-least-once. Sorting each stream by what its consumer will tolerate is one of the largest cost levers in a streaming platform. |

**Follow-up questions**

1. The page-view dashboard starts driving usage-based billing. What has to change about the Redis path?\
   *Once a number is billed on, it inherits the financial-close guarantee and needs an idempotent or transactional sink.*
2. You cannot use a 2PC sink for the financial close, only a plain object store. How do you still get identical numbers across replays?\
   *Points toward idempotent upserts keyed by input offset rather than blind increments.*

</details>


<br>

### Exercise 6 of 11

**● TASK**

Make every boundary of the financial-close pipeline effectively-once: replace the handler's dual write to Postgres and Kafka with CDC tailing a Postgres outbox into Kafka. Swap the plain Snowflake sink behind the Flink aggregator for a lakehouse table that upserts on event id and keeps time-travel snapshots for reproducible quarter-close reports. Add an orchestrator that owns the daily schedule, automatic retries, and on-demand replay from historical Kafka offsets. Validate daily revenue totals (completeness, non-null amounts) before the CFO consumer reads them, from the lakehouse only.

**Starting canvas** (already placed for you):

- Order service application (DUAL-WRITE ANTIPATTERN: writes Postgres + Kafka in same handler) (source, API)
- Kafka merchant_balance_events (at-least-once; rebalance produced last week's duplicates) (source, Kafka)
- Postgres orders + outbox table (atomic; outbox row in same transaction as business row) (storage, PostgreSQL)
- Flink streaming aggregator (engine-level 2PC; does not extend to plain Snowflake sink) (transform, Flink)
- Plain Snowflake fct_merchant_balance_hourly (last week's reissue source; no ACID; no time travel) (storage, Snowflake)
- CFO quarter-close reconciliation consumer (against bank settlement file) (consumer, Tableau)

<details>
<summary><strong>Solution</strong></summary>

#### Effectively-once is a chain, not a switch

No single setting turns on **effectively-once** delivery. Every hop where a record moves between systems can duplicate or drop it, so each hop has to be either atomic or idempotent. Last week's incident came from one hop that was neither: a `Kafka` rebalance re-delivered events, and the plain `Snowflake` table counted the money twice.

```mermaid
flowchart LR
    subgraph L0["Ingest"]
        n0[("Order service<br/>(API)")]
        n1[("Postgres orders + outbox (one transaction)<br/>(PostgreSQL)")]
        n2[("Outbox CDC tail<br/>(CDC)")]
    end
    subgraph L1["Stream"]
        n3[/"merchant balance events<br/>(Kafka)"/]
        n4["Keyed dedup aggregator<br/>(Flink)"]
    end
    subgraph L2["Serve"]
        n5[("Lakehouse merchant balance hourly<br/>(Iceberg)")]
        n6["Revenue totals validation<br/>(Great Expectations)"]
        n7(["CFO quarter-close reconciliation<br/>(dashboard)"])
    end
    subgraph L3["Control"]
        n8["Orchestrator: schedule, retries, offset replay<br/>(Airflow)"]
    end
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n4 --> n5
    n5 --> n6
    n6 --> n7
    n8 --> n4
    n8 --> n6
```

*Each hop is atomic (the outbox) or idempotent (the `event_id` dedup and the `MERGE` sink). The CFO reads only validated lakehouse totals.*

1. **Collapse the dual-write into an outbox**

   A Postgres commit and a `Kafka` produce cannot succeed or fail together, so a crash between them leaves the 2 disagreeing. The handler now writes the `orders` row and an outbox row in one transaction, and a CDC tail of the log publishes the outbox row. The `Kafka` event follows from a committed row instead of being a second write that can half-happen.

2. **Accept repeats, then make them harmless**

   A rebalance re-delivers uncommitted offsets, so `Flink` keys its state on a stable `event_id` and drops events it has already seen. Its two-phase commit stops at its own boundary, so the sink must be idempotent too: an Iceberg `MERGE` on the aggregation key overwrites a re-run hour instead of appending a second copy. Time travel lets the CFO reopen the exact snapshot behind any past report.

3. **Give the pipeline an owner and a gate**

   `Airflow` owns the daily schedule, retries failed tasks, and launches replays from historical offsets. Because the sink is idempotent, a replay reissues a corrected report rather than double-counting. A Great Expectations check on completeness and non-null amounts sits between the lakehouse and the CFO, so the close runs on enforced checks.

| Pitfall: Engine exactly-once ends at the engine |
| --- |
| Trusting `Flink`'s exactly-once to cover the whole path is the mistake behind the incident. The guarantee covers the engine's operators, not a plain insert into an external table. Effectively-once is at-least-once delivery plus an idempotent write at every hop that leaves the engine. |

**Follow-up questions**

1. What should happen if the same `event_id` arrives with a different amount?\
   *Last-write-wins on the key versus rejecting conflicting payloads.*
2. How far back must `Kafka` retention reach to replay an old quarter?\
   *Ties the replay promise to retention or tiered storage.*

</details>


<br>

### Exercise 7 of 11

**● TASK**

Parcel scan events arrive in Kafka at 40,000 per second, and a Flink job counts scans per depot per minute for an operations API that needs them within a minute. The counts land in a key-value store outside Flink's transaction boundary, and after a restart Kafka redelivers every event since the last checkpoint. Design the pipeline so the stored counts are effectively-once: a replay must leave every count unchanged.

<details>
<summary><strong>Solution</strong></summary>

#### Exactly-once stops where the transaction stops

Flink's exactly-once guarantee is honest, but its boundary is narrow: it covers the Kafka offsets, the checkpointed state, and any sink that joins the checkpoint's transaction. A key-value store that commits each write the moment it lands sits outside that boundary, so when the job restarts from its last checkpoint, Kafka redelivers events whose effects the store has already seen. What the store receives is at-least-once. **Effectively-once** is what you build on top of it: make the write idempotent, so a second delivery changes nothing.

```mermaid
flowchart LR
    n0[("scan_events<br/>(Kafka)")]
    n1["depot_minute_counter<br/>(Flink)"]
    n2[("depot_minute_counts<br/>(Redis)<br/>Idempotency: upsert")]
    n3(["operations_api<br/>(API)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
```

*Exactly-once inside `depot_minute_counter`; an upsert into `depot_minute_counts` makes the outside hop effectively-once.*

1. **Find where the closed system ends**

   Trace each hop and ask who commits it. Kafka into Flink is inside: the consumed offset is part of the checkpoint. Flink into the store is not: the store has nothing to roll back. That second hop is where duplicates can appear, so it is where the deduplication work has to live.

2. **Write the value, not the delta**

   Key each entry by depot and minute and write that minute's full count as an upsert. After a restart Flink's restored state rebuilds the same count from the replayed events, so rewriting it lands the identical entry. Setting `idempotencyStrategy` to upsert on the store is how the canvas records that decision.

| Pitfall: An increment turns a replay into a double count |
| --- |
| If the sink write is `count = count + n`, every event redelivered since the last checkpoint is added again, and the depot's minute jumps. The Flink job did nothing wrong; the store simply accepted the same effect twice. Overwriting with the full count is what makes the replay harmless. |

| Real world: Kafka to Kafka is the closed case |
| --- |
| Swap the store for a Kafka output topic and the picture changes: Kafka Streams, or Flink with a transactional Kafka sink, commits the output records and the input offsets together, and readers that see only committed records get each result once. Add any hop outside that system, a database, an HTTP call, an email, and you are back to at-least-once plus an idempotent receiver. |

**Follow-up questions**

1. What changes if the API also needs a running daily total per depot?\
   *Whether the daily figure stays replay-safe when built from per-minute entries rather than an incremented counter.*
2. The store is replaced by a Kafka topic that a second Flink job reads. Where does exactly-once now hold, and where does it stop?\
   *Placing the closed-system boundary when both ends are Kafka.*

</details>


<br>

### Exercise 8 of 11

**● TASK**

Order status events arrive in Kafka at 15,000 per second; a Flink job enriches them into a second Kafka topic, and a notifier sends each update through a push API that has no prepare step and cannot recall a push. A Flink restart must never publish an enriched event twice, and a notifier retry must never notify a customer twice. Use two-phase commit where both sides can take part, and an idempotent consumer with a durable store of sent event ids where one cannot.

<details>
<summary><strong>Solution</strong></summary>

#### Match the pattern to what each boundary can promise

Two-phase commit and the idempotent consumer stop different duplicates, and the boundary decides which one you can use. Between Flink and Kafka both sides can prepare and commit, so Flink's sink stages each enriched event in a Kafka transaction and commits it only when the checkpoint completes: a restart aborts the staged batch instead of publishing it again. The push API cannot prepare and cannot recall a message, so no coordinator can make it abort. There the duplicate is stopped on the consumer side, by checking the event id against a durable record of what was already sent.

```mermaid
flowchart LR
    n0[("order_status_events<br/>(Kafka)")]
    n1["enrich_job_two_phase_commit<br/>(Flink)"]
    n2[/"transactional_enriched_topic<br/>(Kafka)"/]
    n3["dedup_notifier<br/>(transform)"]
    n4[("sent_event_ids<br/>(PostgreSQL)")]
    n5(["push_api<br/>(API)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n3 --> n5
```

*`enrich_job_two_phase_commit` commits into `transactional_enriched_topic` through Flink's two-phase commit; `dedup_notifier` checks `sent_event_ids` before every call to `push_api`.*

1. **Let the Flink sink commit with the checkpoint**

   Flink is the coordinator and the Kafka topic is a participant. The pre-commit happens at the checkpoint barrier and the commit once every operator has acknowledged it. Readers of the topic see only committed records, so the replay after a restart never surfaces a second copy.

2. **Key the notifier on the event id**

   The id the order service stamped on the event is the one thing that is identical on the first delivery and on the retry. The notifier looks it up, skips an id it has seen, and otherwise sends and records it. The record has to outlive a notifier restart, which is why it sits in a database table and not in memory.

| Pitfall: A transactional topic does not protect the push |
| --- |
| Flink's exactly-once ends at the topic. Once the notifier reads a committed record, a crash before it commits its own offset redelivers that record, and without the id check the customer gets the push again. Two-phase commit fixed the producer side; the consumer side is still at-least-once until you add the check. |

| Real world: Every outbound call needs the same check |
| --- |
| Payment providers, email services and partner webhooks are almost never two-phase commit participants. Wherever a pipeline calls out to one, expect an idempotent consumer in front of it, keyed on an id the upstream event already carries. |

**Follow-up questions**

1. The notifier crashes after the push API returns but before the event id is recorded. What happens on retry, and what changes if you record the id first?\
   *The residual window an idempotent consumer leaves at a sink that cannot roll back, and the trade toward at-most-once.*
2. The push API adds an idempotency key header. Which part of this design could you remove?\
   *Moving deduplication into the sink itself.*

</details>


<br>

### Exercise 9 of 11

**● TASK**

Ad clicks reach Kafka at 20,000 a second, up to an hour out of order, and Kafka keeps 7 days. A live stream job keeps per-campaign state in hourly windows of click time, open for clicks up to an hour late, so advertisers see spend within seconds. Finance replays any hours of the last 180 days through a second windowed stream job whose watermark follows click time, resuming where a failed run stopped. A replayed click counts once.

<details>
<summary><strong>Solution</strong></summary>

#### Replay is a second stream job over old events

Stream processing is what makes this replay hard. The live job keeps state keyed by campaign in hourly windows of event time, meaning when the click happened rather than when it arrived, and a watermark decides when an hour is complete. It updates its campaign's hour as each click arrives and re-emits that hour's total, late clicks included. It closes the hour once clicks are more than an hour late. A replayed click from months ago sits far behind that watermark, so the live job would either drop it or hold every window open for half a year. A batch recompute is ruled out too: corrected hours must come from the same windowed stream logic that produced the live totals. Replay therefore needs a second stream job with the same keyed window state and its own watermark. That job reads a replay topic in click-time order, so its watermark advances hour by hour. Both jobs write into a sink that can take the same hour twice without changing the answer.

| ✕ Windows by arrival time | ✓ Windows by event time |
| --- | --- |
| Each click lands in whatever hour the job happens to see it. A click 40 minutes late inflates the next hour, and a replayed months-old click inflates today's hour. There is no watermark, because nothing ever waits. | Each click lands in the hour it happened, and the watermark sets how long an hour's state stays open. A late click updates its own hour. A replayed click updates its own old hour inside the replay job. |

```mermaid
flowchart LR
    n0[("click_events<br/>(Kafka)")]
    n1["live_stream_job_keyed_hour_windows_1h_watermark<br/>(Flink)<br/>SLA: real-time"]
    n2[("click_archive_180_days<br/>(object storage)")]
    n3[/"replay_topic_ordered_by_click_time<br/>(Kafka)"/]
    n4["replay_stream_job_keyed_hour_windows_own_watermark<br/>(Flink)"]
    n5[("campaign_spend_store<br/>(Redis)<br/>Idempotency: upsert")]
    n0 --> n1
    n1 --> n5
    n0 --> n2
    n2 --> n3
    n3 --> n4
    n4 --> n5
```

*Live path: Kafka streams the unbounded click log into `live_stream_job_keyed_hour_windows_1h_watermark`, a real-time job holding keyed state per campaign. It assigns each click to the hour it happened, keeps that hour's window open behind a one-hour watermark, and re-emits the hour's total to `campaign_spend_store` within seconds. Replay path: `click_archive_180_days` re-publishes the chosen hours into `replay_topic_ordered_by_click_time`, keyed by campaign and sorted by click time. `replay_stream_job_keyed_hour_windows_own_watermark` reads it from a committed offset with its own window state and watermark, and upserts into the same store.*

1. **Key the window state by campaign and event hour**

   Clicks arrive up to an hour out of order, so each click updates the state for its campaign and the hour it happened in, not the hour it arrived. Keying by campaign keeps all of a campaign's clicks on one task, so its window state is updated in one place. The one-hour watermark keeps each hour open until its stragglers are in, and every straggler re-emits that hour's new total. Both stream jobs hold exactly this keyed event-time window state. What separates them is where each watermark sits.

2. **Copy the log into a store that outlives it**

   Kafka stays the live source, but its 7-day retention is the hard limit on how far a replay can reach. A continuous copy of every event into object storage, `click_archive_180_days`, keeps 180 days of clicks. That moves the limit without touching the shared cluster.

3. **Give replay an addressable stream and its own watermark**

   Fixes are scoped by when a click happened, so the archive is partitioned by click hour, and a replay of one bad week reads exactly those hours. Those hours are re-published into `replay_topic_ordered_by_click_time`, keyed by campaign and in click-time order. Every event in that topic has an offset, and the replay job commits the last one it finished, so a failed replay resumes from that stored position instead of starting over. The replay job's watermark starts at the first replayed hour and advances with the ordered clicks, so each old hour fills, closes in turn and emits its total. Shuffled replay clicks would force the job to keep weeks of windows open. Ordered clicks keep only an hour or 2 open at a time, while the live watermark stays at now.

4. **Let the sink absorb re-emitted hours**

   The same hour reaches `campaign_spend_store` more than once. A late click re-emits an hour the live job already wrote, and a replay re-emits hours that were already counted. If the store adds each emitted total to a running sum, both inflate spend. With an upsert keyed on campaign and click hour, the recomputed window total replaces the old one. A late click, one replay or 5 replays all land on the same number.

| Pitfall: Replaying through the live watermark drops every old click |
| --- |
| Wiring the archive straight back into `live_stream_job_keyed_hour_windows_1h_watermark` looks like the shortest replay path. But that job's watermark sits at now, so every replayed click arrives as late data and is discarded. The replay finishes without changing a single total. |

| Performance: Retention cost is throughput times days |
| --- |
| At 20,000 clicks per second and about 500 bytes each, the stream produces close to 860 GB a day, so 180 days is roughly 155 TB raw. Compressed columnar files in object storage shrink that several times over, and they cost far less per terabyte than keeping the data on Kafka brokers. The replay topic only ever holds the hours being replayed, so the shared cluster's 7 days is plenty for it. |

**Follow-up questions**

1. What changes if replays must reach 2 years back?\
   *Whether the retained store and its cost scale with the new window while both windowed stream jobs stay the same.*
2. How would you replay one campaign without recomputing every other campaign?\
   *Whether the archive can also be addressed by key, for example partitioned by campaign as well as click hour, so only that campaign's window state is rebuilt.*

</details>


<br>

### Exercise 10 of 11

**● TASK**

Smart-meter readings arrive in Kafka at 50,000 per second. A billing aggregator sums daily kWh per meter for invoices, and its totals must be identical across every replay and recovery. A dashboard counter tallies readings per substation per minute for a grid-load dashboard that must refresh within a minute and tolerates a few double counts. Exactly-once sink commits surface only at each 2-minute checkpoint, so the dashboard counter must not wait on them.

<details>
<summary><strong>Solution</strong></summary>

#### Pay for exactly-once only where a duplicate costs money

Idempotency has a price, and these two aggregators sit at opposite ends of it. A duplicated reading on the billing path is an overcharge on a customer's invoice, so that path is built for exactly-once from the topic to the table. A duplicated reading on the grid-load path is a blip operators never notice, so that path runs at-least-once and skips the commit protocol. Same topic, same engine, two guarantees chosen by what a duplicate costs the reader.

```mermaid
flowchart LR
    n0[("meter_readings<br/>(Kafka)")]
    n1["billing_aggregator<br/>(Flink)"]
    n2[("billing_ledger<br/>(Delta Lake)")]
    n3(["invoicing<br/>(consumer)"])
    n4["at_least_once_counter<br/>(Flink)"]
    n5[("substation_counts<br/>(Redis)<br/>SLA: #60; 1min")]
    n6(["grid_load_dashboard<br/>(Grafana)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n0 --> n4
    n4 --> n5
    n5 --> n6
```

*Two paths off one readings topic: billing totals commit into Delta Lake only at checkpoint, while the at-least-once counter writes substation counts to Redis as it goes.*

1. **Bind the billing commit to the checkpoint**

   The billing aggregator uses Flink's two-phase commit: per-meter daily sums are pre-committed to the Delta Lake table and become visible only when the checkpoint covering those Kafka offsets completes. A crash rolls output and offsets back together, so a replay re-derives the same totals rather than adding to them.

2. **Let the dashboard counter write as it goes**

   The counter writes each minute's substation count to Redis immediately, with no transactional sink. After a restart it resumes from the last checkpoint and may count some readings twice; the dashboard absorbs that, and it shows load within seconds instead of waiting up to 2 minutes for a commit.

| Pitfall: Exactly-once on both paths costs the dashboard its freshness |
| --- |
| Routing the counter through the same transactional sink looks safer but holds every count until the 2-minute checkpoint, which breaks the one-minute refresh. The opposite mistake is worse: a billing path with a plain append double-bills every meter whose readings were replayed. |

| Performance: The commit cost lands only where it buys correctness |
| --- |
| At 50,000 readings a second, the billing job collapses traffic into one row per meter per day, so its checkpoint commits stay small. The counter carries the same input but never pays for a commit, so its latency is set by the one-minute window, not the checkpoint interval. |

**Follow-up questions**

1. Finance also wants hourly kWh per meter. Does that path inherit the billing guarantee?\
   *Whether the cost of a duplicate to the reader, not the data source, decides the guarantee.*
2. What if the billing table had to live in a store with no transactions?\
   *Falling back to a keyed upsert on meter and day to reach effectively-once.*

</details>


<br>

### Exercise 11 of 11

**● TASK**

A hotel-booking service writes each reservation to PostgreSQL and publishes a booking event to Kafka as 2 separate calls; a stream job reads the topic and credits loyalty points into a PostgreSQL ledger. 2 duplicate symptoms appear: events for bookings that never committed, and points credited twice after the job restarts from a checkpoint. Neither database can join a distributed transaction. Fix the producer side and the consumer side with the right pattern each, so a 30-day replay of the topic after a points-rule fix overwrites credits instead of adding to them.

<details>
<summary><strong>Solution</strong></summary>

#### Name the side of the duplicate before naming the pattern

Every duplicate has a side, and its fix lives on that side. This pipeline leaks on both. The 2 separate calls in the booking service can publish an event for a reservation that never committed: a **producer-side** duplicate. The stream job restarting from a checkpoint re-delivers events the ledger already credited: a consumer-side duplicate. Neither database can join a distributed transaction, so 2PC is ruled out, and that leaves exactly one pattern per side.

1. **Move the publish inside the reservation transaction**

   Write the reservation row and an outbox row in the same PostgreSQL transaction, and let CDC on the outbox table publish to Kafka. A rolled-back booking leaves no outbox row, so no event. A committed booking always has its row, so no event goes missing. The relay can still re-send after a crash, which is fine, because the consumer side is about to absorb that.

2. **Key the ledger write on the booking**

   The ledger holds one row per `booking_id` and writes it with an upsert (`INSERT ... ON CONFLICT (booking_id) DO UPDATE`). A redelivered event lands on the row it already wrote, so the credit is set, not added. The same key also absorbs the outbox relay's own re-sends: one idempotent consumer covers every at-least-once hop above it.

3. **Let replay ride on the same key**

   Rewinding the job 30 days re-reads every booking under the fixed rule, and each upsert overwrites the old credit with the corrected one. An additive ledger (`points = points + n`) would make that replay double every balance. The keyed overwrite turns it into a correction.

```mermaid
flowchart LR
    n0[("reservation_outbox<br/>(CDC)")]
    n1[/"booking_events<br/>(Kafka)"/]
    n2["points_job<br/>(Flink)"]
    n3[("points_ledger<br/>(PostgreSQL)<br/>Idempotency: upsert")]
    n0 --> n1
    n1 --> n2
    n2 --> n3
```

*Outbox rows captured by CDC feed `booking_events`; the Flink job upserts one credit per `booking_id` into `points_ledger`.*

| Pitfall: An idempotent ledger cannot catch a phantom event |
| --- |
| The tempting fix is to upsert at the ledger and stop there. That ends the double credits, but an event for a rolled-back reservation still carries a real `booking_id`, so the ledger credits points for a stay that does not exist. Deduplication removes repeats of true events. It cannot tell a phantom from a real one. Only the outbox stops phantoms, at the source. |

| Key insight: 2PC needs every endpoint to vote |
| --- |
| Two-phase commit would make the write and the publish atomic, but only if PostgreSQL and Kafka both take part in one coordinator's prepare and commit. When an endpoint cannot vote, the outbox gets the same atomicity from a single local transaction, and the idempotent consumer replaces a sink-side 2PC with a key. |

**Follow-up questions**

1. A cancellation event must now revoke a booking's points. How do you keep revocation correct under replay?\
   *Whether the revocation overwrites state keyed by `booking_id` instead of appending a negative credit that double-applies.*
2. The app now wants a running total per member. Where does that total come from so a replay cannot inflate it?\
   *Deriving the aggregate from the keyed ledger rows instead of incrementing a counter on every event.*

</details>
