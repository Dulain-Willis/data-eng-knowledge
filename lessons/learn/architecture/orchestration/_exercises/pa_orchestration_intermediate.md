# Orchestration: Intermediate - Exercises

Lesson: [pa_orchestration_intermediate.md](../pa_orchestration_intermediate.md)

### Exercise 1 of 11

**● TASK**

Design the pipeline that builds mart.daily_revenue_by_account, ready by 6am Pacific, from three distinct feeds each on its own cadence: a continuous Kafka clickstream, a Stripe payments API pulled hourly, and a Salesforce account file that lands once a day. Start the daily table only once every feed it needs has actually landed, triggered by upstream arrival rather than a fixed clock offset.

**Starting canvas** (already placed for you):

- Clickstream events (never stops) (source, Kafka)
- Stripe payments (refreshes hourly) (source, API)
- Salesforce account export (one file a day) (source, S3)

<details>
<summary><strong>Solution</strong></summary>

#### One clock was never going to fit three rhythms

This design comes down to picking a schedule for each feed **from how its data arrives**. A stream that never stops needs no schedule at all. An API that refreshes hourly fits an interval. A file that lands once a day at an unpredictable minute fits an event trigger. Forcing all three onto one nightly cron is how `mart.daily_revenue_by_account` ends up serving yesterday's numbers behind a fresh timestamp.

```mermaid
flowchart LR
    n0[("Clickstream events<br/>(Kafka)")]
    n1["Continuous clickstream rollup<br/>(transform)<br/>SLA: real-time"]
    n2[("Stripe payments<br/>(API)")]
    n3["Hourly payments pull<br/>(Airflow)<br/>SLA: #60; 1h"]
    n4[("Salesforce account file<br/>(object storage)")]
    n5["Daily account load<br/>(Airflow)<br/>SLA: #60; 24h"]
    n6["Build daily revenue<br/>(Airflow)"]
    n7[("mart.daily_revenue_by_account<br/>(warehouse)")]
    n8(["Revenue dashboard<br/>(consumer)"])
    n0 --> n1
    n2 --> n3
    n4 --> n5
    n1 --> n6
    n3 --> n6
    n5 --> n6
    n6 --> n7
    n7 --> n8
```

*Each feed runs on the schedule its arrival pattern calls for. The daily build starts when the account file lands and its upstream loads finish, never at a fixed time.*

The clickstream rollup runs continuously, so it is already current whenever the daily build reads it. The Stripe pull uses an interval schedule, `@hourly`, because only the gap between pulls matters, not the wall-clock minute. The Salesforce file gets an event trigger: its arrival starts the daily run. The account load runs first, then the build, in dependency order, with the latest completed hourly pull and the stream rollup as the other 2 inputs.

| Pitfall: Moving the cron later is not the fix |
| --- |
| The tempting patch is a cron like `0 5 * * *`: run at 5am and hope every feed is in. That is still a wall clock guessing when data arrives. The morning the Salesforce file lands 40 minutes late, 5am comes anyway, the build reads stale accounts, and the dashboard is wrong at 6am with nothing flagged. |

| Trick: Let the arrival pattern pick the schedule |
| --- |
| Ask one question of each source: does it arrive at a fixed time, at a fixed gap, or whenever something upstream happens? A fixed gap means an interval, and an unpredictable arrival means an event trigger. Only a truly time-anchored source earns a cron. The daily file is the slowest and least predictable input, so triggering on it lets the build start early on a good morning and correctly on a bad one. |

| Real world: A cron deadline needs its timezone |
| --- |
| The 6am Pacific deadline is the one genuinely wall-clock fact in this design. If you ever schedule against it, write the timezone and a comment next to the cron. Read in UTC, `0 6 * * *` fires at 10pm Pacific in winter and 11pm in summer, both on the night before. |

**Follow-up questions**

1. If the Salesforce file has not landed by 6am, should the build ship with yesterday's accounts joined to today's payments, or wait for the file?\
   *Forces a late-data policy: partial but timely versus complete but late.*
2. Salesforce switches to delivering a fresh file every 4 hours. Does the account feed keep its event trigger or move to an interval?\
   *Re-picks the schedule when the arrival pattern changes.*
3. The clickstream job restarts and replays 2 hours of events. What keeps the daily table from double-counting them?\
   *Tests idempotency in the rollup the daily build reads.*
4. Stripe posts a refund against a payment from three days ago. Does an hourly incremental pull catch it?\
   *Tests full versus incremental loads and late-arriving corrections.*

</details>


<br>

### Exercise 2 of 11

**● TASK**

Replace the monolithic Python task that extracts, cleans and aggregates orders with three separate task nodes (extract_orders, clean_orders, aggregate_orders), so a failure retries only its own task instance instead of re-running the whole DAG. Keep the orchestrator in the production path to own the per-task retry policy, alongside the source, storage and consumer.

**Starting canvas** (already placed for you):

- Postgres orders source (source, Postgres)
- Airflow orchestrator (transform, Airflow)
- Monolithic ETL: extract+clean+aggregate (one task) (transform, Python)
- Snowflake mart_orders (storage, Snowflake)
- Morning dashboard (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

#### Task, DAG, run: where a retry actually lives

The section gave you three precise words, and the whole answer turns on keeping them apart. A **DAG** is the graph of work: the boxes and the arrows. A run is one execution of that graph for a given schedule interval (today's 6am run, yesterday's). A task instance is one single box inside one single run, for example `clean_orders` in today's run. A `retries` policy attaches to that smallest unit, the task instance. When `clean_orders` fails, the orchestrator re-runs `clean_orders` for that one run, and nothing else.

```mermaid
flowchart LR
    n0[("Postgres orders source<br/>(Postgres)")]
    n1["Airflow orchestrator<br/>(Airflow)"]
    n2["extract_orders<br/>(Python)"]
    n3["clean_orders<br/>(Python)"]
    n4["aggregate_orders<br/>(Python)"]
    n5[("orders mart<br/>(warehouse)")]
    n6(["Morning dashboard<br/>(dashboard)"])
    n0 --> n2
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n4 --> n5
    n5 --> n6
```

*The monolith split into three retryable task instances. Airflow owns the schedule and the per-task `retries` policy; the arrows are the dependency edges that let a downstream task wait for a healthy upstream.*

| Pitfall: A DAG-level retry re-runs the successful work too |
| --- |
| The tempting shortcut is one `retries` on the whole DAG: on any failure, re-run everything. But retries do not operate on DAGs, they operate on task instances. If `aggregate_orders` fails, a DAG-level retry drags `extract_orders` and `clean_orders` back through the source and the cleaning pass a second time, even though they already succeeded. That is wasted compute, a longer time-to-recover, and re-reading Postgres for rows you already pulled. With the monolith it is worse still: extract, clean, and aggregate are one box, so there is no seam to retry at all, and a fail in aggregate forces a full re-extract by construction. |

| ✕ One DAG-level retry on the monolith | ✓ Per-task retries on the split |
| --- | --- |
| A single `retries` re-runs the entire graph. `extract_orders` and `clean_orders` repeat their successful work on every failure. Recovery cost scales with the whole pipeline, not the broken step, and a transient hiccup in aggregate pays the full extract bill again. | Each of `extract_orders`, `clean_orders`, `aggregate_orders` carries its own `retries`. A fail retries only that task instance; the completed upstream stays completed and the dependency edge holds the downstream until it is healthy. Recovery cost scales with the broken step alone. |

Notice the division of labor the diagram makes explicit: the orchestrator was already on the canvas, and it stays. It owns the schedule and the per-task `retries` policy. What you added is purely structural, the split into three nodes joined by dependency edges. That structural split is what makes per-task retry meaningful, because there is now a boundary for a retry to act on. Orchestration and retry handling are 2 concepts doing one job together: the graph defines the units, the policy decides how each unit recovers.

| Real world: The seams are where you fight fires |
| --- |
| Real ETL fails unevenly. The source database times out during extract, an upstream schema change breaks cleaning, a warehouse credit runs dry mid-aggregate. When each stage is its own task instance you re-run just the one that broke, often with a task-specific backoff, and your morning dashboard is still on time. A monolith with one blunt retry turns every one of those small failures into a full, expensive replay, which is exactly what pages people at 6am. |

**Follow-up questions**

1. If `extract_orders` writes to a staging table, what makes its retry safe to run twice?\
   *Tests whether the learner sees idempotency as the property that makes per-task retry trustworthy.*
2. Where would you set a different `retries` count or backoff for `aggregate_orders` than for `extract_orders`, and why might they differ?\
   *Checks that retry policy is understood as per-task-instance, not one global knob.*
3. The 6am run fails at clean but you fix the bug at 9am. How do you re-run just the failed and downstream tasks for that one run without touching other runs?\
   *Tests the task-instance-within-a-run mental model against clear-and-rerun semantics.*

</details>


<br>

### Exercise 3 of 11

**● TASK**

The orders DAG starts at 2am and usually finishes by 2:45am, so the marketing DAG is scheduled at 3am; on a slow night orders finishes at 3:15am and marketing reads stale data. Replace this time offset with a real cross-DAG dependency. Swap the plain Snowflake mart for a lakehouse-format table (Iceberg, Delta, or Hudi) whose snapshot commits an asset-aware orchestrator can observe, and have the marketing DAG fire when that asset is fresh instead of at a clock time.

**Starting canvas** (already placed for you):

- Orders source (source, PostgreSQL)
- Orders Airflow DAG (cron 0 2 * * *) (transform, Airflow)
- aggregate_orders task (transform, Pandas)
- Plain Snowflake mart.orders_by_region (no snapshot) (storage, Snowflake)
- Marketing Airflow DAG (cron 0 3 * * *, BRITTLE time-offset) (transform, Airflow)
- compute_attribution task (transform, Pandas)
- Marketing dashboard (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

#### Wire DAGs to data, not to the clock

Swapping a clock for an asset trigger is **data-aware scheduling**: the producing task declares that it wrote an asset, and the downstream DAG's schedule becomes that asset. Airflow calls these Datasets (Assets in newer releases); Dagster calls them asset materializations. The marketing run no longer starts at a wall-clock time it hopes is late enough. It starts the moment `mart.orders_by_region` has a fresh commit, and never before.

| Pitfall: A time offset is a guess, not a dependency |
| --- |
| The starter wires the two DAGs with `cron 0 3 * * *`, an offset chosen because orders 'usually' finishes by 2:45. But `compute_attribution` has no idea whether the data is fresh; it reads whatever `mart.orders_by_region` holds at 3am. On a slow night orders is still running at 3:15, so attribution reads yesterday's numbers and nothing errors. The failure is silent, which is the worst kind: the dashboard is confidently wrong. |

1. **Give the mart snapshot semantics**

   Swap the plain Snowflake `mart.orders_by_region` for a lakehouse-format table (Iceberg, Delta, or Hudi). The point isn't the storage engine: every write from `aggregate_orders` becomes a new immutable, atomically committed snapshot. A plain table is just its current contents, so 'is it fresh?' is unanswerable. A snapshot table carries a commit the orchestrator can observe.

2. **Emit the asset only when the commit lands**

   Mark the `aggregate_orders` task with an outlet, e.g. `outlets=[Dataset("iceberg://mart.orders_by_region")]`. The orchestrator records an asset update only after the snapshot commit succeeds, so the freshness signal is tied to the data being durably written, not to the task merely starting. If the run fails or is still running, no asset update fires.

3. **Schedule marketing on the asset, not the clock**

   Change the marketing DAG from `schedule="0 3 * * *"` to `schedule=[Dataset("iceberg://mart.orders_by_region")]`. Now it triggers whenever the mart is refreshed, whether that's 2:45 on a fast night or 3:15 on a slow one. The brittle 15-minute race is gone because there is no assumed gap left to lose.

```mermaid
flowchart LR
    n0[("Orders source<br/>(PostgreSQL)")]
    n1["Orders Airflow DAG<br/>(Airflow)"]
    n2["aggregate_orders (emits asset on commit)<br/>(Pandas)"]
    n3[("mart.orders_by_region<br/>(Iceberg)")]
    n4["Marketing DAG (schedule=[asset])<br/>(Airflow)"]
    n5["compute_attribution<br/>(Pandas)"]
    n6(["Marketing dashboard<br/>(dashboard)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n4 --> n5
    n5 --> n6
```

*The snapshot commit on the Iceberg mart is the event the marketing DAG subscribes to. The clock coupling is replaced by a real data edge.*

| ✕ Time offset (brittle) | ✓ Asset trigger (fresh) |
| --- | --- |
| Marketing runs at `0 3 * * *` and reads `mart.orders_by_region` blind. Correctness depends on orders always finishing before 3am. Any slowdown, a bigger day, or a retry breaks it silently. | Marketing runs on `schedule=[Dataset(...)]`, fired by the snapshot commit. Correctness depends only on the data existing. The run self-adjusts to whenever `aggregate_orders` actually finishes. |

| Real world: Why the table format is load-bearing |
| --- |
| A plain warehouse table can't tell you 'a new version just landed', so you fall back to timing. Lakehouse formats give you an atomic, observable commit per write, exactly the event an asset-aware orchestrator subscribes to. In production this is how you kill the whole family of 'DAG B assumes DAG A is done by X' bugs across teams that don't share a schedule. |

**Follow-up questions**

1. What if `aggregate_orders` writes several partitions and marketing only needs one region refreshed?\
   *Tests whether the learner scopes the asset to a partition-level dataset rather than the whole table.*
2. How would you backfill a week of history without the asset trigger firing the marketing DAG 7 times mid-backfill?\
   *Tests decoupling manual or backfill runs from data-driven scheduling.*
3. If the orders DAG commits a snapshot but the data is empty or partial, should the asset still fire?\
   *Tests data-quality gating on the emit step, not just commit success.*

</details>


<br>

### Exercise 4 of 11

**● TASK**

A vendor drops a daily file on SFTP at any time between 01:00 and 05:00, so the Spark transform that loads the warehouse behind the daily dashboard must not start on a fixed clock. Add a sensor task, run by the orchestrator, that waits for the file without holding a worker slot and times out and pages on-call if nothing has landed by 08:00. Once it succeeds, a non-empty check on the file must pass before the Spark transform runs.

**Starting canvas** (already placed for you):

- Vendor SFTP file drop (source)
- Daily Spark transform (transform, Spark)
- Reporting warehouse (storage, warehouse)
- Daily dashboard (consumer, dashboard)

<details>
<summary><strong>Solution</strong></summary>

#### Wait for the world, then run

A **sensor** turns something outside your control into a task the DAG can depend on. Here the outside event is the vendor's file. The orchestrator runs a file sensor at the head of the daily DAG, and everything after it depends on that task, so the Spark load starts when the file lands rather than when the clock says. The non-empty check comes right after the sensor, because a sensor only proves that a file exists, not that it holds data.

```mermaid
flowchart LR
    n0[("Vendor SFTP file drop<br/>(source)")]
    n1["Deferrable file sensor<br/>(Airflow)<br/>Alert: page if no file by 08:00"]
    n2["Non-empty file check<br/>(quality_gate)"]
    n3["Daily Spark transform<br/>(Spark)"]
    n4[("Reporting warehouse<br/>(warehouse)")]
    n5(["Daily dashboard<br/>(dashboard)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n4 --> n5
```

*The sensor and the check sit on the one edge the orchestrator cannot see past: the hand-off from the vendor.*

| Pitfall: A poking sensor holds a slot for hours |
| --- |
| In poke mode the sensor keeps its worker slot for the whole wait. A file that lands at 05:00 means 4 hours of a slot doing nothing, and a handful of such sensors can starve the pool. Reschedule mode, or a deferrable sensor (`deferrable=True` in Airflow), gives the slot back between checks. |

| Key insight: A timeout turns a silent wait into a page |
| --- |
| Without a `timeout`, a sensor waiting on a vendor that never delivers just sits in the running state. The dashboard goes stale and nothing errors. Bounding the wait at 08:00 makes the sensor fail, and that failure pages on-call while there is still time to chase the vendor. |

Notice where the sensor does not go. There is none between Spark and the warehouse: inside the DAG, the orchestrator already knows whether the upstream task succeeded, and an ordinary dependency covers it. Sensors belong only at the boundary, where the condition lives in a system the orchestrator does not run.

**Follow-up questions**

1. The file lands but holds only a header row. Should the check pass?\
   *Whether non-empty means bytes or data rows.*
2. The vendor starts calling a webhook when the file is ready. Do you still need the sensor?\
   *An external trigger can start the DAG directly, so nothing has to poll.*
3. The vendor is sometimes a day late. Should the 08:00 timeout fail the run, or should a later run pick the file up?\
   *Timeout semantics versus catching up on the next schedule.*

</details>


<br>

### Exercise 5 of 11

**● TASK**

Split the daily mega-DAG into three upstream DAGs, each on its source's natural cadence (Kafka events every 5 minutes, Stripe payments hourly, Salesforce CRM daily), plus one downstream daily DAG that joins their three raw outputs into the table the 6am dashboard reads. Give the upstream cadences and the daily join separate orchestrated DAGs. Set each source's freshness to its own tier: < 15min for Kafka, < 1h for Stripe, < 24h for Salesforce.

**Starting canvas** (already placed for you):

- Mobile events Kafka (continuous) (source, Kafka)
- Stripe payments REST API (source, Stripe)
- Salesforce CRM REST API (source, Salesforce)
- One mega-DAG (daily, forces all cadences to daily) (transform, Airflow)
- Executive daily revenue dashboard (6am SLA) (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

#### One DAG per cadence

Multi-cadence ingestion gives each source a DAG on the schedule it naturally arrives on, and lets a separate downstream DAG assemble whatever those DAGs land. The starter's mega-DAG did the opposite. Its single daily trigger pinned the five-minute event feed and the hourly payments pull to the pace of the slowest source, so events sat unread for most of a day before the dashboard saw them.

```mermaid
flowchart LR
    n0[("Mobile events<br/>(Kafka)<br/>SLA: #60; 15min")]
    n1[("Stripe payments API<br/>(API)<br/>SLA: #60; 1h")]
    n2[("Salesforce CRM API<br/>(API)<br/>SLA: #60; 24h")]
    n3["Events 5-minute DAG<br/>(Airflow)"]
    n4["Payments hourly DAG<br/>(Airflow)"]
    n5["CRM daily DAG<br/>(Airflow)"]
    n6[("Raw events<br/>(Delta Lake)")]
    n7[("Raw payments<br/>(Delta Lake)")]
    n8[("Raw CRM accounts<br/>(Delta Lake)")]
    n9["Daily join DAG<br/>(Airflow)"]
    n10[("Daily revenue by account<br/>(warehouse)")]
    n11(["Executive dashboard<br/>(dashboard)"])
    n0 --> n3
    n1 --> n4
    n2 --> n5
    n3 --> n6
    n4 --> n7
    n5 --> n8
    n6 --> n9
    n7 --> n9
    n8 --> n9
    n9 --> n10
    n10 --> n11
```

*Three cadence-specific DAGs each land a raw table; one daily DAG joins those tables into the table the 6am dashboard reads.*

1. **Land each source on its own schedule**

   The events DAG runs every 5 minutes, the payments DAG hourly and the CRM DAG once a day, and each one writes its own raw table. The three no longer share a trigger, so a slow CRM pull can never hold back the event feed. Each source's freshness chip (< 15min, < 1h, < 24h) now describes one real feed instead of a single global number.

2. **Join on data, not on clock offsets**

   The daily join DAG never assumes the upstreams finished by a fixed hour. It reads the three raw tables once the day's data is in them and builds the account-level revenue table before the 6am read. The raw tables are the handoff: no producer calls the join, and the join waits on data being present, not on another DAG's run.

| Pitfall: A faster trigger does not rescue one DAG |
| --- |
| Running the mega-DAG every 5 minutes helps the events, but it also re-pulls the CRM 288 times a day for nothing and hammers its API. The cadences are incompatible, so they belong in separate graphs. |

**Follow-up questions**

1. The CRM pull has not landed when the daily join is due. Should the join block, or run against yesterday's CRM accounts?\
   *Weighs a missed dashboard deadline against serving slightly stale account metadata.*
2. Stakeholders now want an intraday revenue view. What would you add without touching the daily join?\
   *The raw events table can feed a second, faster path on its own schedule.*

</details>


<br>

### Exercise 6 of 11

**● TASK**

A logistics company feeds a daily Looker dashboard from three sources on different cadences: shipments hourly, inventory every 6 hours, and a Kafka event stream. Today the upstream pipelines and the analytics pipeline are glued together by wall-clock offsets, and on Black Friday a slow upstream run left the dashboard reading stale data. Redesign it so each cadence runs under its own orchestration and the analytics pipeline starts from the freshness of a lakehouse-format table (Iceberg or Delta Lake) instead of a fixed clock time, and so that a missed freshness target on the analytics output is detected and paged to on-call.

**Starting canvas** (already placed for you):

- Postgres shipments (source, PostgreSQL)
- Postgres inventory (source, PostgreSQL)
- Kafka events (source, Kafka)
- Looker analytics dashboard (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

#### Trigger on data, not on the clock

**Data-aware triggering** replaces a clock with a fact. The analytics run starts when the upstream tables actually hold new data, not when a cron offset guesses they probably do. Each cadence keeps its own orchestration: shipments hourly, inventory every 6 hours, and the Kafka stream continuously. All three land in `Iceberg` tables, and those tables' committed snapshots become the readiness signal the analytics DAG waits on.

| Pitfall: A clock offset is a dependency nobody enforces |
| --- |
| Scheduling analytics at 02:00 because shipments usually finish by 01:30 works until the upstream slips. When it does, the downstream runs anyway, reads a partition that was never written, and finishes green. Time is only a proxy for readiness. A committed snapshot is readiness itself. |

```mermaid
flowchart LR
    subgraph L0["Sources"]
        n0[("Postgres shipments<br/>(PostgreSQL)")]
        n1[("Postgres inventory<br/>(PostgreSQL)")]
        n2[("Kafka events<br/>(Kafka)")]
    end
    subgraph L1["Ingestion"]
        n3["shipments DAG<br/>(Airflow)"]
        n4["inventory DAG<br/>(Airflow)"]
        n5["events stream job<br/>(Flink)"]
    end
    subgraph L2["Lakehouse"]
        n6[("shipments table<br/>(Iceberg)")]
        n7[("inventory table<br/>(Iceberg)")]
        n8[("events table<br/>(Iceberg)")]
    end
    subgraph L3["Analytics"]
        n9["analytics DAG<br/>(Airflow)"]
        n10[("gold analytics table<br/>(Iceberg)")]
    end
    subgraph L4["Serving and monitoring"]
        n11(["Looker analytics dashboard<br/>(Looker)"])
        n12["freshness monitor<br/>(Great Expectations)"]
        n13(["on-call<br/>(alerting)"])
    end
    n0 --> n3
    n1 --> n4
    n2 --> n5
    n3 --> n6
    n4 --> n7
    n5 --> n8
    n6 --> n9
    n7 --> n9
    n8 --> n9
    n9 --> n10
    n10 --> n11
    n10 --> n12
    n12 --> n13
```

*Each cadence runs under its own orchestration and lands in an Iceberg table. The analytics DAG starts from those snapshots, and a freshness monitor on the gold output pages on-call.*

| Key insight: The table format is the readiness signal |
| --- |
| `Iceberg` and `Delta Lake` commit atomically and timestamp every snapshot. That lets the analytics DAG open with a sensor task that proceeds only once all three tables have committed data newer than its last build. A folder of plain Parquet files gives you neither the atomic commit nor a timestamp to wait on. |

| Trick: Waiting fixes stale, the monitor fixes silent |
| --- |
| On its own, a sensor turns stale-and-silent into late-and-silent. The freshness monitor compares the gold table's snapshot age against its freshness target and routes any miss to the on-call alert. A stuck upstream now pages someone instead of waiting for a user to notice old numbers. |

**Follow-up questions**

1. Inventory is down for a full day. Should the sensor block the analytics run indefinitely, or publish partial output?\
   *Sensor timeouts: blocking keeps the output correct but breaches freshness; publishing partial output needs a visible staleness flag.*
2. A Kafka event lands inside a day partition of the `events` table that analytics already read. How does it reach the dashboard?\
   *Late data: an idempotent partition overwrite and a recompute of the touched day.*

</details>


<br>

### Exercise 7 of 11

**● TASK**

A card processor's API publishes the previous day's settlement file only after 3am UTC, and finance reviews the settled totals in the warehouse at 7am UTC. A fraud dashboard reads authorization counts from that warehouse, pulled from the processor's auth API every 15 minutes, at no particular clock time. Give each feed its own orchestrated DAG with a cron or interval schedule that fits its source, and write that schedule into the DAG's name.

<details>
<summary><strong>Solution</strong></summary>

#### Let the source pick the schedule

Picking between cron and interval is a question about the source, not about taste. The settlement file comes with a wall-clock fact: it exists only after 3am UTC and has to be in the warehouse by 7am. A cron expression is exactly the tool that names a recurring clock time. The auth API carries no such fact: any 15-minute window is as good as another, so only the gap between runs matters, and that is what an interval expresses.

```mermaid
flowchart LR
    n0[("settlement_api<br/>(API)")]
    n1["settlement_dag_cron_4am_utc<br/>(Airflow)<br/>SLA: #60; 24h"]
    n2[("auth_api<br/>(API)")]
    n3["auth_dag_every_15min<br/>(Airflow)<br/>SLA: #60; 15min"]
    n4[("warehouse<br/>(storage)")]
    n5(["fraud_dashboard<br/>(consumer)"])
    n0 --> n1
    n1 --> n4
    n2 --> n3
    n3 --> n4
    n4 --> n5
```

*2 DAGs, 2 schedules: a cron at 4am UTC for settlements and a 15-minute interval for authorizations, both landing in one warehouse.*

1. **Anchor the settlement load with cron**

   `0 4 * * *` reads minute zero, hour four, every day: 4am UTC. That clears the file's latest arrival of 3:15am with margin and lets a 40-minute load finish long before the 7am review. Cron is easy to misread, so state its meaning where people look: on the canvas, that is the DAG's name.

2. **Put the auth pull on a 15-minute interval**

   The first run starts when the DAG is deployed, and each later run starts 15 minutes after the previous one. Nothing downstream cares whether a run lands at :00 or :07, so pinning it to the clock adds a constraint nobody asked for. One DAG holds one schedule, which is why each feed gets its own.

| Pitfall: A 24-hour interval drifts with the deploy |
| --- |
| Scheduling the settlement load as every 24 hours looks like a nightly cron, but an interval's first run happens at deploy time. Ship it at 1pm and the load runs at 1pm every day, hours after finance's 7am review. Redeploy and the time moves again. When the clock matters, the schedule must name the clock. |

**Follow-up questions**

1. Finance adds a month-end reconciliation on the first of every month at 5am UTC. Which schedule, and what expression?\
   *Reading the day-of-month field: `0 5 1 * *` fires only on day 1.*
2. If fraud ops later need each refresh to land on the quarter hour, does the authorization schedule change?\
   *Once the absolute time matters, the interval becomes a cron such as `*/15 * * * *`.*

</details>


<br>

### Exercise 8 of 11

**● TASK**

A daily DAG extracts orders from PostgreSQL, fetches exchange rates from a currency API that times out a few nights a week, converts the orders to USD and loads them into a warehouse table. Set a retry policy on the rates task instance alone: exponential backoff and at most 3 retries, never re-running the whole DAG run. When the retries run out, alert the on-call engineer. Make the warehouse load overwrite its date partition so a retried load writes the same rows.

<details>
<summary><strong>Solution</strong></summary>

#### Retry the task instance, not the run

A retry is aimed at one task instance: this task, in this run, for this date, with these inputs. When the rates call times out at 1:20am, the orders extract in the same run has already finished, so only `fetch_fx_rates` for that date should go again. Because the retry sees the same inputs as the failed attempt, a correct task produces the same output, and the rest of the run carries on as if nothing happened.

```mermaid
flowchart LR
    n0[("orders_db<br/>(PostgreSQL)")]
    n1[("currency_api<br/>(API)")]
    n2["extract_orders<br/>(SQL)"]
    n3["fetch_fx_rates<br/>(transform)<br/>Alert: page on-call when retries are exhausted · Retries: 3 · Backoff: exponential"]
    n4["convert_to_usd<br/>(Spark)"]
    n5[("usd_revenue<br/>(warehouse)<br/>Idempotency: delete_write")]
    n0 --> n2
    n1 --> n3
    n2 --> n4
    n3 --> n4
    n4 --> n5
```

*Retries, backoff and the exhaustion alert live on `fetch_fx_rates`; the write to `usd_revenue` deletes and rewrites its date partition.*

1. **Put the retry policy on the flaky task**

   Set the retry count and an exponential backoff on `fetch_fx_rates` alone. The API recovers within minutes, so growing the wait between attempts gives it room, and three retries bound how long a dead API can hold the run before anyone hears about it.

2. **Decide what exhaustion means**

   Once the last retry fails, the task instance is failed and `convert_to_usd` never starts. That failure has to reach a person, which is why the alert hangs off the same task: missing rates must not quietly become wrong revenue.

3. **Make the write safe to repeat**

   Any task instance can be retried, including the one that writes. Overwriting the run's date partition means a load that died halfway and ran again leaves exactly one copy of the day's rows. Retry semantics and idempotent writes are one decision, not two: a bounded retry in front of an append is still a duplicate generator.

| Pitfall: Re-running the run repeats work that already succeeded |
| --- |
| Clearing the whole DAG run after a rates timeout re-extracts 40 minutes of orders that were fine, and if the load appends, a run that had already written part of the day doubles it. The run is the unit you inspect; the task instance is the unit you retry. |

**Follow-up questions**

1. What should change if the currency API starts returning a `400` for an unknown currency code?\
   *Separating transient failures, which retries fix, from permanent ones, which retries only delay.*
2. The orders extract starts timing out on some nights too. Where does its retry policy go, and does anything else in the run change?\
   *Applying task-level retries to a second task without touching the rest of the run.*

</details>


<br>

### Exercise 9 of 11

**● TASK**

An events DAG owned by the platform team writes the day's sessionized events table, usually done by 1:30am but sometimes past 4am. Two DAGs owned by other teams read that table: the ML team's feature DAG and the product team's analytics DAG, each currently cron-scheduled at 2am. Draw the design so each downstream DAG starts only once the events DAG has finished that day's table, modeled as a cross-DAG dependency rather than a time offset.

<details>
<summary><strong>Solution</strong></summary>

#### Encode the dependency, not the clock

A cross-DAG dependency makes a downstream DAG wait on an event, the upstream DAG finishing its table, instead of a wall-clock guess about when that usually happens. Here the events DAG is upstream of two teams, so it carries two such edges: one into the feature DAG, one into the analytics DAG. When the events run finishes at 1:30am both consumers start at 1:30am; when it drags past 4am they start past 4am, and neither one ever reads a half-written table.

```mermaid
flowchart LR
    n0["events_dag<br/>(Airflow)"]
    n1[("sessionized_events<br/>(storage)")]
    n2["feature_dag<br/>(Airflow)"]
    n3["analytics_dag<br/>(Airflow)"]
    n0 --> n1
    n1 --> n2
    n1 --> n3
    n0 --> n2
    n0 --> n3
```

*`events_dag` writes `sessionized_events`; two `cross_dag` edges start `feature_dag` and `analytics_dag` when it completes, with no clock offset.*

| Pitfall: A later cron time is still a guess |
| --- |
| Moving both 2am schedules to 5am feels safe until the night the events run finishes at 5:20am. It also wastes every early night: features that could start at 1:30am sit idle for hours. Worse, the dependency now lives only in two schedules that two different teams can edit without telling the platform team. |

| Key insight: One edge per consumer scales across teams |
| --- |
| Each reader of the table gets its own cross-DAG edge, so a third team joining means one new edge and no schedule negotiation. The events DAG keeps its own cadence untouched; the consumers simply follow it, and a failed upstream run holds them back instead of letting them build on a partial day. |

**Follow-up questions**

1. What changes if the analytics DAG must also wait for an orders DAG owned by a fourth team?\
   *A downstream with two upstream cross-DAG edges, which should start only when both have finished the same day.*
2. If the events DAG is rerun for last Tuesday, should the feature DAG rerun for last Tuesday too?\
   *Whether the dependency is tied to the logical date, so an upstream backfill reaches the consumers it fed.*

</details>


<br>

### Exercise 10 of 11

**● TASK**

A clickstream Kafka topic receives about 20 million events a day, and a Spark batch job should load them into the warehouse each time 2 million new messages accumulate, not on a fixed clock. Design the DAG with a sensor that watches the topic's offset and triggers the batch job once the threshold is crossed. If the threshold is not reached within 6 hours, the sensor must time out and page on-call.

<details>
<summary><strong>Solution</strong></summary>

#### Let the offset, not the clock, start the load

A sensor turns an outside condition into a task the DAG can wait on. Here the condition is a Kafka offset: the topic gains about 20 million events a day, and the Spark load should start each time 2 million new messages have landed. The sensor sits between the topic and the batch job, checks the offset on an interval, and succeeds once it has advanced 2 million past the last load. Only then does the orchestrator release the job downstream.

```mermaid
flowchart LR
    n0[/"clickstream_topic<br/>(Kafka)"/]
    n1["offset_sensor<br/>(Airflow)<br/>Alert: page on-call if threshold not met in 6h"]
    n2["spark_batch_load<br/>(Spark)"]
    n3[("warehouse<br/>(warehouse)")]
    n0 --> n1
    n1 --> n2
    n2 --> n3
```

*The Kafka topic feeds an Airflow offset sensor with a 6-hour timeout that pages on-call; the Spark load runs only after the sensor succeeds.*

1. **Put the sensor in the dependency line**

   The batch job's only upstream is the sensor. That ordering is the whole point: the load cannot start until the condition is true, and it starts as soon as it is, whether that happens at 3am or 9pm.

2. **Give the wait an end**

   A sensor with no timeout can wait forever on a stalled producer, and nobody notices until the warehouse is stale. At 20 million a day, 2 million messages normally arrive in about 2 and a half hours, so a 6-hour timeout marks a real stall and pages on-call.

| Pitfall: A cron time is a guess about the data |
| --- |
| Scheduling the load every 2 hours looks equivalent, but traffic is uneven: a quiet night loads a sliver, a busy evening loads far more than 2 million, and the run never knows which. The sensor makes the threshold itself the trigger. |

| Performance: Deferrable mode frees the slot while waiting |
| --- |
| A poking sensor holds a worker slot for the whole wait, up to 6 hours here. In deferrable mode the check is handed off and the slot goes back to the pool until the offset crosses the line. |

**Follow-up questions**

1. What changes if the load must also run at least once every 6 hours, even when fewer than 2 million messages arrived?\
   *Combining a sensor condition with a time-based fallback instead of a hard failure.*
2. How does the sensor know where the last load stopped?\
   *Recording the committed offset so each run's threshold is measured from the previous load.*

</details>


<br>

### Exercise 11 of 11

**● TASK**

A grocery chain's replenishment DAG runs at 4am because the inventory snapshot DAG, owned by another team, usually finishes by 3:30am; on late nights it reads a half-written snapshot. Replace the time offset with an encoded cross-DAG dependency, a sensor or an event trigger, so the replenishment run starts only once the day's snapshot is complete. The run also calls a supplier lead-time API that times out a few nights a week: retry that task with backoff, and alert on-call when retries run out. Land the forecast in a warehouse that feeds the buyers' dashboard by 7am.

<details>
<summary><strong>Solution</strong></summary>

#### Encode the wait instead of guessing it

A time offset is a cross-DAG dependency written in invisible ink: the 4am start only works because someone once watched the snapshot finish by 3:30am. Encoding the dependency makes the wait explicit. A sensor, or an event the upstream DAG emits when it succeeds, holds the replenishment run until the day's snapshot is marked complete, so a slow night delays the forecast instead of corrupting it. The capstone stacks that on the lesson's other two habits: a schedule that states the business deadline, and retries scoped to the one task that actually fails.

```mermaid
flowchart LR
    n0[("inventory_snapshot<br/>(PostgreSQL)")]
    n1["snapshot_ready_sensor<br/>(custom)"]
    n2[("supplier_lead_time_api<br/>(API)")]
    n3["fetch_lead_times<br/>(transform)<br/>Retries: 3 · Backoff: exponential"]
    n4["replenishment_forecast_run<br/>(Airflow)"]
    n5[("forecast_warehouse<br/>(warehouse)")]
    n6(["buyers_dashboard<br/>(dashboard)"])
    n7(["on_call_alerts<br/>(Email)"])
    n0 --> n1
    n1 --> n4
    n1 --> n3
    n2 --> n3
    n3 --> n4
    n3 --> n7
    n4 --> n5
    n5 --> n6
```

*`snapshot_ready_sensor` releases the whole run, `fetch_lead_times` and `replenishment_forecast_run` alike; only `fetch_lead_times` retries, and its exhausted retries reach `on_call_alerts`.*

1. **Wait on completion, not on 4am**

   The sensor checks the upstream team's done marker for the day's snapshot. The run keeps its daily schedule as the earliest possible start, but both the lead-time fetch and `replenishment_forecast_run` wait behind `snapshot_ready_sensor`, so a 5am finish simply means a 5am start.

2. **Retry the task that times out**

   Retries belong on `fetch_lead_times` with exponential backoff, because the timeout lives in one HTTP call. Retrying the whole run would reread the snapshot and rebuild the forecast to recover from a failure that never touched them.

3. **Make exhausted retries loud**

   When the backoff runs out, the failure path to `on_call_alerts` turns a silent miss into a page hours before 7am, instead of buyers ordering from yesterday's numbers.

| Pitfall: A wider offset only moves the bad night |
| --- |
| Pushing the start to 5:30am adds margin on most nights, still reads a half-written snapshot on the worst one, and delays every good night for nothing. Only a dependency on the completion signal is right on both. |

**Follow-up questions**

1. The snapshot still has not landed by 6:30am. What should the sensor do so buyers are not left guessing?\
   *Sensor timeouts and failing loudly against a business deadline.*
2. A markdown-pricing DAG also needs the same snapshot. How do you avoid encoding its dependency a second, different way?\
   *Reusing one completion signal across several downstream DAGs.*

</details>
