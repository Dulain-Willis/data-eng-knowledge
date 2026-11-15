# Orchestration: Advanced - Exercises

Lesson: [pa_orchestration_advanced.md](../pa_orchestration_advanced.md)

### Exercise 1 of 11

**● TASK**

Airflow runs compute_fct_orders, which loads Postgres orders into fct_orders, then compute_mart_revenue, which reads fct_orders and writes the Snowflake mart_revenue for the executive dashboard. Wire the task dependency graph so Airflow runs them in that order, with a retry policy on each task. Go asset-aware: store both tables in a lakehouse format such as Iceberg, and add a lineage catalog such as OpenLineage that records which asset each task reads and writes.

**Starting canvas** (already placed for you):

- Postgres orders source (source, PostgreSQL)
- Airflow orchestrator (transform, Airflow)
- compute_fct_orders (lineage implicit) (transform, Spark)
- compute_mart_revenue (reads fct_orders, lineage implicit) (transform, Spark)
- Plain Snowflake mart_revenue (storage, Snowflake)
- Executive dashboard (consumer, dashboard)

<details>
<summary><strong>Solution</strong></summary>

#### Tasks run the work; assets are the data

Task-based orchestration makes the work the object. Airflow schedules `compute_fct_orders` and `compute_mart_revenue`, runs them along the edges you draw, and retries each one under its own policy. What it never learns is why the order matters: `compute_mart_revenue` reads the `fct_orders` table the first task wrote. Asset-based orchestration makes that table the object. Here you keep the task graph and add the asset view beside it.

| Pitfall: Task order is not lineage |
| --- |
| A `compute_fct_orders >> compute_mart_revenue` edge encodes execution order, not data flow. Rename a table, split a task, or add a third reader of `fct_orders`, and the ordering still looks right while the lineage rots. Nothing fails loudly: the dashboard just goes stale and no one can trace which upstream produced the numbers. |

1. **Wire the task graph and its retries**

   Draw the orchestrator into each task it schedules, and put an ordering edge from `compute_fct_orders` to `compute_mart_revenue`. Set the retry policy on each task, not on the whole run. A flaky write to `fct_orders` then retries that task alone, and the downstream task waits instead of reading half a table.

```mermaid
flowchart LR
    n0[("Postgres orders source<br/>(PostgreSQL)")]
    n1["Airflow orchestrator<br/>(Airflow)"]
    n2["compute_fct_orders<br/>(Spark)<br/>On error: retry"]
    n3[("fct_orders<br/>(Iceberg)")]
    n4["compute_mart_revenue<br/>(Spark)<br/>On error: retry"]
    n5[("mart_revenue<br/>(Iceberg)")]
    n6(["Lineage catalog<br/>(OpenLineage)"])
    n7(["Executive dashboard<br/>(dashboard)"])
    n1 --> n2
    n1 --> n4
    n2 --> n4
    n0 --> n2
    n2 --> n3
    n3 --> n4
    n4 --> n5
    n5 --> n7
    n2 --> n6
    n4 --> n6
```

*Airflow schedules both tasks in order with task-level retries. Each run reports its reads and writes to the catalog, and `fct_orders` and `mart_revenue` are `Iceberg` tables the catalog pins lineage to.*

2. **Register each task's assets in a catalog**

   Add a lineage catalog such as `OpenLineage` and connect both tasks to it. Each run reports what it read and wrote: `compute_fct_orders` produces `fct_orders`; `compute_mart_revenue` consumes it and produces `mart_revenue`. The dependency that lived in the code becomes metadata anyone can query.

3. **Move the tables to a lakehouse format**

   Store `fct_orders` and `mart_revenue` as `Iceberg` tables instead of the plain Snowflake mart. Each write becomes a versioned snapshot, so the catalog pins lineage to the exact version a run produced, and 'which run made these numbers' has an answer.

| Key insight: Hybrid keeps the task graph and adds the asset view |
| --- |
| Airflow still decides when work runs and what retries. The catalog and the lakehouse tables say what data exists and where it came from. You made the dependency Airflow already relied on visible without ripping out the task graph. |

**Follow-up questions**

1. A third task starts reading `fct_orders`. What does the catalog show that the `>>` edge never could?\
   *Lineage as a queryable graph of consumers, not a hand-kept ordering.*
2. `compute_mart_revenue` reruns on corrected input. How does snapshot identity on the `Iceberg` table let you name exactly which dashboard reads are affected?\
   *Connects snapshot versioning to impact analysis across a rerun.*

</details>


<br>

### Exercise 2 of 11

**● TASK**

The daily aggregation hardcodes CURRENT_DATE, and history is filled by a custom Python loop firing 365 append queries at once into plain Snowflake. Make it backfillable: replace the loop with an orchestrator (Airflow, Dagster, or Prefect) that runs the task once per logical date as a scheduled backfill job. Replace Snowflake with an ACID lakehouse format (Iceberg, Delta, or Hudi) so each day's run overwrites only its own partition.

**Starting canvas** (already placed for you):

- Postgres orders source (source, Postgres)
- Daily aggregation: CURRENT_DATE hardcoded, INSERT INTO (transform, Python)
- Custom Python backfill loop (no orchestrator) (transform, Python)
- Plain Snowflake mart.daily_orders (storage, Snowflake)
- Morning dashboard (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

#### Making the pipeline backfillable by design

Backfilling is treating the re-computation of any past day as a normal, repeatable operation rather than a one-off rescue script. 2 structural pieces make that true here: an orchestrator that owns each run keyed to a logical date, and a table format whose ACID writes let a run replace only its own day's partition.

```mermaid
flowchart LR
    n0[("Postgres orders source<br/>(Postgres)")]
    n1["Orchestrated daily job (execution_date param)<br/>(Airflow)"]
    n2["Aggregation: INSERT OVERWRITE partition<br/>(Python)"]
    n3[("mart.daily_orders partitioned by day<br/>(Iceberg)")]
    n4(["Morning dashboard<br/>(dashboard)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
```

*The orchestrator passes the run's date in; the aggregation overwrites that day's partition in `mart.daily_orders`.*

| Pitfall: A hardcoded date can only ever run today |
| --- |
| The daily task pinned `CURRENT_DATE` inside its SQL, so it only knew about the wall-clock day. To fill history the author bolted on a custom loop that fired 365 `INSERT INTO` appends at once: no retries, no per-day isolation, and any re-run double-appends rows. The date a run computes must be a parameter the orchestrator passes in, never read from the clock. |

| Trick: Idempotency comes from overwriting a partition |
| --- |
| Partition the target by day and have each run do a partition overwrite (`INSERT OVERWRITE` scoped to its date) instead of an append. Iceberg, Delta and Hudi make that write atomic, so re-running any historical day replaces exactly that day's rows and nothing else. Backfilling a year becomes 365 independent, idempotent tasks the orchestrator schedules and retries. |

| Real world: Backfills are routine, not emergencies |
| --- |
| In production you re-run history constantly: a bug in the aggregation, a late-arriving source, a new column. When the orchestrator owns backfill as a scheduled job over a date range and each day overwrites its own partition, a backfill is one command over a window, safe to interrupt and resume. |

**Follow-up questions**

1. What breaks if 2 backfill runs for the same day overlap on a plain append destination?\
   *Tests why partition-level atomicity, not just parameterization, is what makes re-runs safe.*
2. How would you backfill after adding a column to the aggregation?\
   *Tests table-format schema evolution alongside partition overwrite.*

</details>


<br>

### Exercise 3 of 11

**● TASK**

The daily revenue DAG promises that mart.daily_revenue is fresh for the previous day by 6am Pacific, but that SLA lives only in a runbook, so on-call learns of a miss when an executive opens a stale dashboard. Declare the SLA on the asset: add a monitor that watches mart.daily_revenue's freshness against the 6am deadline, and an alert destination that routes each miss to on-call.

**Starting canvas** (already placed for you):

- Postgres orders source (source, PostgreSQL)
- Airflow daily DAG (transform, Airflow)
- aggregate_revenue task (transform, SQL)
- mart.daily_revenue (storage, warehouse)
- Executive dashboard (6am Pacific read) (consumer, dashboard)

<details>
<summary><strong>Solution</strong></summary>

#### Moving the SLA out of the runbook

An orchestrator-level SLA is a promise about one asset: `mart.daily_revenue` is fresh for the previous day by 6am Pacific. Declaring it turns that promise into a live check on the asset instead of a line a human must remember. It takes 2 stages. A freshness monitor owns the 6am threshold and decides when a miss has happened. An alert destination carries that miss to on-call with the asset and the deadline attached.

```mermaid
flowchart LR
    n0[("Postgres orders<br/>(PostgreSQL)")]
    n1["Airflow daily DAG<br/>(Airflow)"]
    n2["aggregate_revenue task<br/>(SQL)"]
    n3[("mart.daily_revenue<br/>(warehouse)")]
    n4(["Executive dashboard<br/>(dashboard)"])
    n5(["Freshness monitoring<br/>(consumer)"])
    n6(["On-call alerting<br/>(consumer)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n3 --> n5
    n5 --> n6
```

*The monitor reads `mart.daily_revenue`, the same asset the dashboard reads, so a miss pages on-call before the 6am read.*

| Pitfall: A runbook that says 6am checks nothing |
| --- |
| The old pipeline had an SLA only because someone wrote 6am in a runbook. Nothing measured it, so the first sign of a miss was an executive opening a stale dashboard. A commitment that nothing monitors is a hope, not an SLA. |

| ✕ Freshness monitor | ✓ Alert destination |
| --- | --- |
| Watches `mart.daily_revenue` and owns the threshold: fresh by 6am Pacific. It decides that a miss happened, so tuning the deadline against past run times happens here. | Receives the miss and wakes on-call with the asset name and the deadline attached. It owns routing and escalation, not the definition, so changing who gets paged never changes what counts as late. |

| Key insight: Watch the asset, not the task exit code |
| --- |
| Watching the freshness of `mart.daily_revenue` catches every way the pipeline can fail: the DAG never ran, `aggregate_revenue` silently wrote zero rows, or the upstream orders were empty. It asks whether the data is fresh, not whether a task exited 0, and a green Airflow run can still breach the SLA. |

**Follow-up questions**

1. The DAG usually lands at 4:30am but ran past 5:50am twice last month. Where do you set the warning threshold so that it fires early without paging every night?\
   *Tuning an SLA threshold against the historical runtime distribution.*
2. A finance export also reads `mart.daily_revenue`, but its deadline is noon. How do you express both deadlines?\
   *Whether the SLA lives on the asset or on each consumer's expectation of it.*

</details>


<br>

### Exercise 4 of 11

**● TASK**

A 6am-SLA customer dashboard DAG, a 365-day backfill DAG and an experimental ML feature DAG share one Snowflake XL warehouse and collide on Mondays. Draw the dashboard DAG as tasks in dependency order, each retrying on failure, on its own high-priority orchestrator, and put the backfill and ML DAGs on a separate lower-priority orchestrator. Give the lower-priority path its own warehouse so it cannot starve the dashboard, and monitor the dashboard's 6am SLA.

**Starting canvas** (already placed for you):

- Customer-facing daily dashboard DAG (SLA 6am) (transform, Airflow)
- Backfill DAG (365-day reload) (transform, Airflow)
- ML experimental feature build DAG (transform, Airflow)
- Snowflake XL warehouse (shared) (storage, Snowflake)
- Executive dashboard (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

Priority isolation starts with the DAG itself. The orchestrator runs **tasks in dependency order** and retries each task on its own, so a failed aggregate reruns without reloading the tables before it. Pools and `priority_weight` then decide which task starts next, but neither takes compute back from a query already running. On one shared Snowflake XL warehouse, a 365-day backfill query mid-flight keeps its compute while the dashboard waits, and on Monday that wait pushes it past 6am. The fix is structural: separate orchestrators and separate warehouses.

```mermaid
flowchart LR
    subgraph L0["Customer-facing path (high priority)"]
        n0["High-priority orchestrator<br/>(Airflow)"]
        n1["Load dashboard tables<br/>(SQL)<br/>On error: retry"]
        n2["Build dashboard aggregates<br/>(SQL)<br/>On error: retry"]
        n3[("Dedicated dashboard warehouse<br/>(Snowflake)")]
        n4(["Executive dashboard<br/>(dashboard)"])
        n5(["SLA monitoring<br/>(Grafana)"])
    end
    subgraph L1["Batch and experimental path (low priority)"]
        n6["Low-priority orchestrator<br/>(Airflow)"]
        n7["Backfill DAG<br/>(Airflow)"]
        n8["ML feature build DAG<br/>(Airflow)"]
        n9[("Isolated batch warehouse<br/>(Snowflake)")]
    end
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n0 --> n5
    n6 --> n7
    n6 --> n8
    n7 --> n9
    n8 --> n9
```

*The dashboard DAG runs as ordered, retrying tasks on its own orchestrator and warehouse; the backfill and ML DAGs share a lower-priority orchestrator and warehouse, and SLA monitoring watches the 6am target.*

| Pitfall: Raising `priority_weight` only reorders the queue |
| --- |
| Keeping one warehouse and bumping the dashboard's `priority_weight` wins the scheduler race, but the backfill query already running holds its compute until it finishes. Priority orders the next slot. It never preempts running work, so the collision moves instead of disappearing. |

1. **Split orchestration by criticality**

   One orchestrator runs only the customer-facing dashboard DAG at high priority. A second runs the backfill and ML experimental DAGs at lower priority. A runaway experiment can no longer take a slot the dashboard depends on.

2. **Draw the dashboard DAG as ordered tasks**

   Load the dashboard tables, then build the aggregates. The edge between them is the dependency the orchestrator enforces. Each task has its own retry, so a transient warehouse error on the aggregate step reruns only that step and the 6am window survives.

3. **Give each path its own compute**

   Each path writes to its own Snowflake warehouse. The backfill and the feature build can saturate the batch warehouse for hours while the dashboard's warehouse stays idle and ready at 6am. Priority alone could not buy this.

4. **Alert on lateness, not only failure**

   A run that succeeds at 6:40am is green and still a missed SLA. The monitor watches completion time against the target, so you can prove the isolation actually holds.

**Follow-up questions**

1. The backfill runs only a few days a month. Should its warehouse stay on, or start on demand?\
   *Isolation as a cost lever: auto-suspend for bursty batch compute.*
2. If the aggregate task exhausts its retries at 5:50am, what should the dashboard show?\
   *Task-level retries versus the SLA they are meant to protect.*
3. How do you stop 2 orchestrators from becoming 5 as new low-priority DAGs arrive?\
   *Criticality tiers as the rule, not one orchestrator per workload.*

</details>


<br>

### Exercise 5 of 11

**● TASK**

Redesign the seam between stripe_to_raw (now every 5 minutes) and daily_finance_close (6am SLA) so it no longer relies on a time offset. Replace Snowflake raw.payments with an Iceberg, Delta, or Hudi asset and trigger finance close on its snapshot freshness, not the clock. Add an observability_tool on that asset's freshness with an alert_destination paging on-call, and use two orchestrators to isolate finance close from backfills.

**Starting canvas** (already placed for you):

- stripe_to_raw DAG (every 5 min) (transform, Airflow)
- Plain Snowflake raw.payments (mid-batch writes) (storage, Snowflake)
- daily_finance_close DAG (cron 0 5 * * *, BRITTLE) (transform, Airflow)
- Snowflake mart.daily_close (SLA 6am, missing 2x/week) (storage, Snowflake)
- Executive finance dashboard (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

#### The seam was a clock, not a contract

This postmortem is a case for **data-aware scheduling**: a downstream job fires when the asset it depends on is actually fresh, not at a wall-clock time you hope is late enough. Here `daily_finance_close` ran on `0 5 * * *` and just assumed `stripe_to_raw` had finished the previous day's writes by then. That assumption was a hidden time offset. When `stripe_to_raw` moved from a 30-minute cadence to 5 minutes, the write pattern shifted and the 5am read started landing mid-batch, so the close missed its 6am SLA about twice a week. Nobody changed `daily_finance_close`; the implicit contract just quietly broke.

| Pitfall: The fix that breaks again next quarter |
| --- |
| The tempting patch is to push the cron to `0 6 * * *` or drop a `sleep` in front of the close. That is still a time offset, just a bigger one. It papers over this cadence change and re-breaks the moment `stripe_to_raw` retimes again, gets slower, or backfills. You have not removed the fragile coupling, you have re-tuned it. The postmortem framing says redesign the seam structurally, not re-guess the delay. |

```mermaid
flowchart LR
    subgraph L0["ingest (backfill-competing)"]
        n0["stripe_to_raw DAG (every 5 min)<br/>(Airflow)"]
    end
    subgraph L1["asset"]
        n1[("raw payments Iceberg table<br/>(Iceberg)")]
        n2["snapshot freshness check<br/>(custom)"]
    end
    subgraph L2["finance priority path"]
        n3["daily_finance_close DAG<br/>(Airflow)"]
        n4[("daily close mart<br/>(warehouse)")]
        n5(["Executive finance dashboard<br/>(dashboard)"])
    end
    subgraph L3["observability"]
        n6(["freshness monitor<br/>(monitoring)"])
        n7(["on-call alerts<br/>(alerting)"])
    end
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n4 --> n5
    n1 --> n6
    n6 --> n7
```

*The seam is now the asset's snapshot, not a shared clock: the close waits on freshness, a monitor watches the same asset, and finance runs on its own orchestrator.*

1. **Give the asset snapshot semantics, then trigger on freshness**

   Swap plain `raw.payments` for a lakehouse table format (Iceberg here, Delta or Hudi work too). A plain table has no notion of "the batch is complete", so a reader can only guess with a clock. An Iceberg table commits atomic snapshots, so `raw.payments` can answer "what is my newest committed snapshot and when did it land". Now `daily_finance_close` fires on that snapshot freshness instead of `0 5 * * *`: it waits for the day's data to actually be committed, whether that is 4:50 or 5:20, and it never reads mid-batch.

2. **Watch the asset, not the job**

   Point a monitoring tool at the freshness of `raw.payments` and route breaches to on-call through an alerting destination. The signal you care about is "the asset the close depends on has gone stale", which is upstream of the close ever starting. That catches a stalled `stripe_to_raw` before the SLA burns, instead of finding out at 6am when the executive dashboard is blank. The alert is about the contract's freshness guarantee, so it fires on the cause, not the symptom.

3. **Isolate finance-close onto its own priority path**

   Split into two orchestrators so `daily_finance_close` no longer shares scheduling and warehouse contention with the backfill and ingest workloads. Even with a correct freshness trigger, a heavy backfill hammering the same warehouse can starve the close and blow the 6am SLA. A dedicated finance orchestrator with its own priority means the close's compute is not competing with best-effort backfills. This is the difference between the seam being logically correct and the SLA being physically defensible.

| Key insight: The 4 pieces make the contract explicit |
| --- |
| Snapshot semantics + freshness trigger say what "ready" means; the freshness monitor + alert say who finds out when "ready" is late; the orchestrator split guarantees the compute to act on it. Together they replace "I assume you finished by 5am" with "I start when your snapshot commits, I alert if it does not, and I have my own lane to run". A cadence change upstream is now invisible to the close instead of a silent outage. |

**Follow-up questions**

1. What if `stripe_to_raw` legitimately has no new payments some days? How does the freshness check tell "stale" from "nothing to commit"?\
   *Freshness-based triggers need a heartbeat or an empty-commit convention so a quiet day does not look like a stall.*
2. How would you set the freshness threshold on the monitor so it alerts before the 6am SLA rather than at it?\
   *Tests working backward from the SLA to an upstream freshness budget.*
3. If two downstream marts both consume `raw.payments`, should they share one freshness check or each own theirs?\
   *Extends the asset-as-contract idea to fan-out consumers with different SLAs.*

</details>


<br>

### Exercise 6 of 11

**● TASK**

Redesign a fintech data platform of 412 production DAGs where an upstream cadence change broke a downstream close. Add a catalog so asset lineage is queryable. Replace plain warehouse destinations with lakehouse tables (Iceberg, Delta, or Hudi) as asset boundaries between upstream and downstream DAGs, instead of cross-DAG time offsets, so every transform is backfill-ready. Run at least 2 orchestrators to isolate customer-facing from backfill workloads, and put an observability tool plus an alert destination on the customer-facing pipelines.

**Starting canvas** (already placed for you):

- Postgres app (source, PostgreSQL)
- Payments API (source, API)
- CRM API (source, API)
- Kafka events (source, Kafka)
- Executive dashboard (consumer, Metabase)
- Finance dashboard (consumer, Metabase)
- ML feature store (consumer)

<details>
<summary><strong>Solution</strong></summary>

#### Depend on assets, not on clocks

Asset-based orchestration is the move this platform was missing. The broken close came from a downstream DAG that assumed its input was ready at a fixed time. When the upstream moved to a faster cadence, that assumption quietly became false. Once the dependency is a **lakehouse table instead of a clock**, the mart runs when its input is actually fresh, and a backfill can rebuild any date range in place. The rest of the redesign (2 orchestrators, one lineage catalog, alerting on the path that matters) then has something solid to hang on.

```mermaid
flowchart LR
    subgraph L0["Sources"]
        n0[("Postgres app<br/>(PostgreSQL)")]
        n1[("Payments API<br/>(API)")]
        n2[("CRM API<br/>(API)")]
        n3[("Kafka events<br/>(Kafka)")]
    end
    subgraph L1["Orchestration"]
        n4["Customer-facing orchestrator<br/>(Airflow)"]
        n5["Backfill orchestrator<br/>(Airflow)<br/>Backfill: partition_overwrite"]
    end
    subgraph L2["Lakehouse tables"]
        n6[("Raw lakehouse layer<br/>(Iceberg)")]
        n7[("Core marts<br/>(Iceberg)")]
    end
    subgraph L3["Lineage and alerting"]
        n8(["Lineage catalog<br/>(DataHub)"])
        n9(["Freshness monitoring<br/>(monitoring)"])
        n10(["On-call alerting<br/>(alerting)"])
    end
    subgraph L4["Consumers"]
        n11(["Executive dashboard<br/>(Metabase)"])
        n12(["Finance dashboard<br/>(Metabase)"])
        n13(["ML feature store<br/>(consumer)"])
    end
    n0 --> n6
    n1 --> n6
    n2 --> n6
    n3 --> n6
    n6 --> n7
    n4 --> n6
    n4 --> n7
    n5 --> n6
    n5 --> n7
    n4 --> n8
    n5 --> n8
    n7 --> n11
    n7 --> n12
    n7 --> n13
    n7 --> n9
    n9 --> n10
```

*Iceberg tables are the boundary between the ingestion and mart DAGs; 2 Airflow orchestrators keep backfills off the customer-facing path, and only that path is monitored and paged.*

1. **Make the lakehouse table the boundary**

   Ingestion writes the Raw lakehouse layer. The mart DAG declares that table as its upstream asset and runs when a new partition lands. With no `schedule_interval` offset there is no guess about when the upstream finishes, so a cadence change upstream can no longer break the close.

2. **Overwrite partitions so every rerun is a backfill**

   Iceberg gives ACID overwrite by partition. A transform parameterized on a date range writes only its target partitions, so rerunning last March replaces last March and duplicates nothing. The Backfill orchestrator carries `partition_overwrite` for exactly that reason: the code that runs tonight is the code that rebuilds history.

3. **Give backfills their own orchestrator**

   With 412 DAGs in one scheduler, a six-hour backfill competes for the same workers and warehouse slots as the customer-facing close. A second orchestrator dedicated to backfills and heavy reprocessing is pool isolation at its coarsest grain: the close never queues behind history.

4. **Watch and page only the customer-facing path**

   Freshness monitoring reads Core marts and routes misses to On-call alerting, so the SLA that matters is checked and a backfill's noise never wakes anyone. Both orchestrators report lineage to one catalog, so you can answer 'what breaks if I change this table' before you change it.

| Pitfall: Moving the offset only moves the bug |
| --- |
| Pushing the downstream job from '02:00' to '03:00' fixes this week, fails again at the next cadence change, and adds an hour of idle time to every run. The offset itself is the defect. A dependency on the upstream table replaces it. |

**Follow-up questions**

1. Finance needs the exact numbers behind a quarter-old board deck. What does the lakehouse table give you that makes this a single query?\
   *Table snapshots and `AS OF` time-travel reads.*
2. A new column arrives on the payments events. How does the asset-based design backfill it without rerunning unrelated marts?\
   *Schema evolution plus rematerializing only the downstream assets.*
3. Both orchestrators write to the same tables. How do you keep one lineage graph across 2 schedulers?\
   *Lineage is emitted per asset, so both schedulers report into the same graph.*

</details>


<br>

### Exercise 7 of 11

**● TASK**

Draw this nightly sensor pipeline asset-first: device reading files land in a raw object-storage table, a cleaning step builds a cleaned readings warehouse table, and an aggregation step builds a daily device health warehouse table that a fleet dashboard reads. Make each table its own stage wired by its data dependency, so lineage is visible on the graph. An orchestrator schedules both steps nightly and retries each one up to 3 times on failure.

<details>
<summary><strong>Solution</strong></summary>

#### Draw the tables, not just the jobs

Asset-based orchestration starts from the data: you name each table the pipeline produces and the table it is built from, and the work falls out of those dependencies. Task-based orchestration starts from the jobs and leaves the tables implicit. On a two-step nightly pipeline both run fine, but only the asset-first drawing shows that `device_health_daily` is built from `cleaned_readings`, which is built from `raw_readings_landing`. That chain is the lineage you need the morning a dashboard number looks wrong.

```mermaid
flowchart LR
    n0[("device_reading_files<br/>(source)")]
    n1[("raw_readings_landing<br/>(object storage)")]
    n2["clean_readings_step<br/>(Spark)<br/>Retries: 3"]
    n3[("cleaned_readings<br/>(warehouse)")]
    n4["device_health_step<br/>(Spark)<br/>Retries: 3"]
    n5[("device_health_daily<br/>(warehouse)")]
    n6(["fleet_dashboard<br/>(consumer)"])
    n7["nightly_orchestrator<br/>(orchestrator)<br/>SLA: #60; 24h"]
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n4 --> n5
    n5 --> n6
    n7 --> n2
    n7 --> n4
```

*Asset-first: each table sits between the step that writes it and the step that reads it, and the orchestrator schedules both steps nightly.*

1. **Give every table its own stage**

   Put `raw_readings_landing`, `cleaned_readings` and `device_health_daily` on the canvas as storage stages, each between the step that writes it and the step that reads it. The cleaned table is the one most drawings drop, because the dashboard never reads it directly. Keeping it visible is what lets you trace a health row back to the night of cleaned data it came from.

2. **Let the orchestrator own order and retries**

   `nightly_orchestrator` connects to both steps and carries the nightly `< 24h` cadence. Retries live on each step (`retryCount` of 3) rather than on the pipeline as a whole, so a dropped connection during aggregation reruns only the aggregation, not the cleaning that already succeeded.

| Pitfall: Chaining jobs directly hides the cleaned table |
| --- |
| Drawing `clean_readings_step` straight into `device_health_step` gives a working schedule and a blank lineage: the graph says one job follows another, but not what passes between them. That is the task-first habit this exercise is about breaking. Whenever 2 steps touch with no table between them, ask which table the first one writes. |

| Real world: An asset graph makes a partial refresh obvious |
| --- |
| When only the health logic changes, the asset graph shows that rebuilding `device_health_daily` from the existing `cleaned_readings` is enough. A task graph only tells you 2 jobs ran in order, so teams tend to rerun everything to be safe. |

**Follow-up questions**

1. A second team wants a weekly anomaly table built from `cleaned_readings`. Where does it attach, and what changes for the orchestrator?\
   *Whether a new asset hangs off the existing table instead of duplicating the cleaning step.*
2. Redraw the same pipeline task-first. Which question about the dashboard numbers can it no longer answer?\
   *The lineage difference between the 2 orchestration models.*

</details>


<br>

### Exercise 8 of 11

**● TASK**

A currency bug wrote wrong amounts into 45 days of a date-partitioned revenue table built nightly from an orders database. Design the pipeline so an orchestrator runs one load per logical date, for the nightly run and as a backfill over those 45 days. Each run must replace only its own date's partition in the warehouse, so rerunning a day never duplicates rows.

<details>
<summary><strong>Solution</strong></summary>

#### One load, any date, one partition

A backfill is the nightly load run again for dates it already covered, and a pipeline survives it only when two things hold: the load takes its date as a parameter, and its write is scoped to that date's partition. Repairing the 45 bad days is then just asking the orchestrator for 45 logical dates; nothing about the job differs between tonight's run and the repair.

1. **Hand the date to the load**

   `daily_revenue_load` runs on Airflow and receives its logical date from the orchestrator instead of computing 'yesterday' itself. The nightly schedule asks for one date, the backfill asks for each of the 45 affected dates, and both go through the same task.

2. **Scope the write to that date**

   With the backfill strategy set to partition overwrite, a run for one date deletes and rewrites only that date's partition of `revenue_warehouse`. Run it twice and the second run produces the same partition, so a retried day cannot double its revenue and the days outside the range are never touched.

```mermaid
flowchart LR
    n0[("orders_db<br/>(PostgreSQL)")]
    n1["daily_revenue_load<br/>(Airflow)<br/>Backfill: partition_overwrite"]
    n2[("revenue_warehouse<br/>(warehouse)")]
    n0 --> n1
    n1 --> n2
```

*`daily_revenue_load` runs once per logical date and overwrites only that date's partition in `revenue_warehouse`.*

| Pitfall: Appending a backfilled day doubles it |
| --- |
| A backfill that appends leaves the wrong rows in place and adds the corrected ones beside them, so each repaired day reports roughly twice its revenue. Truncating the whole table and reloading avoids the duplicates but rewrites every correct day too, which the repair never needed. |

| Real world: Every backfill reason uses the same path |
| --- |
| A bug fix, a newly added column and the initial history of a new pipeline are all the same request: run this load for these dates. Build the date parameter and the partition-scoped write once, and the one-off backfill script stops existing. |

**Follow-up questions**

1. A new `tax_amount` column must be filled for two years of history: what changes in this design?\
   *Whether the same per-date backfill path covers a column-add backfill without a separate job.*
2. What if an order's amount could be edited weeks after it was placed?\
   *Whether partitioning by date still bounds which partitions a correction must rewrite when late changes land in old dates.*

</details>


<br>

### Exercise 9 of 11

**● TASK**

Design a nightly pipeline that carries the day's shipment scans from an operations database through an orchestrated batch job into a stock-levels table in a warehouse that feeds a replenishment dashboard. Declare the 7am SLA in the orchestrator so a miss pages the on-call engineer, and add DAG-level monitoring so a stalled upstream step alerts too, not only a late final task.

<details>
<summary><strong>Solution</strong></summary>

#### A deadline the scheduler enforces, plus a watcher for the middle

An orchestrator-level SLA turns '7am fresh' from a line in a runbook into a deadline the scheduler checks and pages on. Declaring it is only half the job. Airflow attaches its `sla` to a task, and the natural home is the final publish step, so an extract that hangs at 1:30am stays silent until 7:01am, when nothing can be rebuilt before planners open the dashboard. **DAG-level monitoring closes that gap** by watching every step of the run, not just the last one.

```mermaid
flowchart LR
    n0[("shipment_scans_db<br/>(PostgreSQL)")]
    n1["airflow_orchestrator<br/>(Airflow)<br/>Alert: page if not done by 7am"]
    n2["stock_levels_batch<br/>(SQL)"]
    n3[("stock_levels_warehouse<br/>(warehouse)")]
    n4(["replenishment_dashboard<br/>(consumer)"])
    n5(["dag_monitoring<br/>(consumer)"])
    n6(["on_call_alerting<br/>(consumer)"])
    n0 --> n2
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n1 --> n5
    n1 --> n6
    n5 --> n6
```

*The orchestrator carries the 7am SLA and pages on a miss; a separate monitor reads every run and pages on a stalled step.*

1. **Put the deadline on the orchestrator**

   The SLA belongs on the thing that schedules the run, because only the scheduler knows when a run started, where it is and whether it finished. Wiring the orchestrator to the paging destination is what makes 7:01am a page instead of a planner's complaint at 9:40.

2. **Give the middle of the DAG its own watcher**

   A healthy run ends by 3:30am, so a step still running at 4am is already a signal. A monitor fed by the orchestrator's run state can flag that stall hours before the deadline, which is the window in which a rerun still lands on time.

| Pitfall: A deadline on the last task is blind to the first |
| --- |
| Putting `sla` only on the publish task looks complete, but a hung extract never fails, so nothing fires until the deadline itself has passed. The miss is reported, yet the time to fix it is gone. |

| Real world: Layer the checks by when they can still help |
| --- |
| Teams usually keep the orchestrator SLA as the contract of record and add an external run monitor for early warning. The SLA answers 'did we keep the promise'; the monitor answers 'are we about to break it'. |

**Follow-up questions**

1. A second reader needs the same table by 9am. What deadline should page, and on what?\
   *Tests treating the SLA as a commitment on the published table, with the earliest consumer driving the alert.*
2. How would you tell a slow-but-healthy night from a truly stalled extract?\
   *Tests choosing a stall threshold from the normal run time rather than from the deadline.*

</details>


<br>

### Exercise 10 of 11

**● TASK**

Thirty nightly ingestion DAGs each copy tables from one PostgreSQL read replica that serves at most 8 analytics connections. Design the ingestion from the replica into a warehouse, scheduled by an orchestrator, so that every extract across all thirty DAGs shares one pool sized to that limit and the finance extracts claim free slots first.

<details>
<summary><strong>Solution</strong></summary>

#### One budget for every DAG that touches the replica

A pool is how an orchestrator rations a resource that many DAGs share. Here the resource is the replica's 8 analytics connections, so the pool gets 8 slots, and every extract task, whichever of the thirty DAGs owns it, must hold a slot while it runs. The ninth task waits in the scheduler instead of opening a ninth connection, which is exactly the load the replica could not absorb.

```mermaid
flowchart LR
    subgraph L0["replica pool 8 slots"]
        n1["finance_extract_high_priority<br/>(Airflow)"]
        n2["other_extracts_low_priority<br/>(Airflow)"]
    end
    n0[("postgres_read_replica<br/>(PostgreSQL)")]
    n3[("analytics_warehouse<br/>(warehouse)")]
    n0 --> n1
    n0 --> n2
    n1 --> n3
    n2 --> n3
```

*Both extract stages draw from one 8-slot replica pool; finance extracts outrank the rest for each freed slot.*

| Pitfall: Per-DAG caps multiply across DAGs |
| --- |
| Setting each DAG's task concurrency to 1 feels safe, but it caps one DAG at a time: thirty DAGs at 1 each still open 30 connections. Concurrency is the single-DAG lever; only a pool sees every DAG at once, which is why the 8 belongs on the pool and nowhere else. |

| Key insight: Priority orders the line, it adds no slots |
| --- |
| Giving finance extracts a higher `priority_weight` changes who gets the next free slot, not how many slots exist. The replica still sees at most 8 connections; finance simply stops waiting behind lower-value tables. Priority without a pool does little, because with no cap there is no line to jump. |

| Real world: Size the pool to the system, not the DAG |
| --- |
| The same shape guards any capacity-limited system: a Spark cluster's executors or a partner API's rate limit gets one named pool sized to that system's real limit, shared by every DAG that calls it. When the limit changes, you change one number. |

**Follow-up questions**

1. What changes if each finance extract opens 2 connections instead of one?\
   *Whether the learner lets a task claim more than one slot so the pool still matches real connections.*
2. How would you stop a slow night's run of one DAG from overlapping its next run?\
   *Separating the per-DAG run concurrency lever from the cross-DAG pool.*

</details>


<br>

### Exercise 11 of 11

**● TASK**

A fare bug wrote wrong driver payouts into the last 90 days of a date-partitioned payouts table that an orchestrated nightly task builds from a trips PostgreSQL database into a shared warehouse. Design it so the same date-parameterized task backfills the corrected range, and rerunning any day overwrites that day's partition instead of adding rows. The backfill shares the warehouse with the nightly run, so cap it at 4 concurrent task runs through a pool. Page on-call if the nightly payout run is not finished by its 6am SLA.

<details>
<summary><strong>Solution</strong></summary>

#### One task rebuilds history, a pool keeps it polite

This capstone is a backfill run the way the lesson argues it should be: the corrected range goes through the same date-parameterized task that builds the table every night, so payouts have exactly one code path. 3 other ideas from the lesson make that safe. The task writes by partition overwrite, so a day rebuilt twice still holds one set of payouts. The backfill draws from a pool capped at 4 runs, so 90 days of rebuilds cannot crowd the nightly run off the warehouse. And the orchestrator watches the 6am SLA and pages on-call when it slips.

```mermaid
flowchart LR
    n0[("trips_db<br/>(PostgreSQL)")]
    n1["build_payout_partition<br/>(Airflow)<br/>Partitions: 4 tasks · Alert: page if not done by 6am · Idempotency: delete_write · Backfill: partition_overwrite"]
    n2[("payouts_warehouse<br/>(warehouse)")]
    n0 --> n1
    n1 --> n2
```

*`trips_db` feeds one Airflow task, `build_payout_partition`, that takes a date, overwrites that day's partition in `payouts_warehouse`, runs at most 4 at once, and pages if the nightly run misses 6am.*

1. **Parameterize the task by date**

   The task reads its date from the run rather than from `CURRENT_DATE`, so asking for one historical day rebuilds exactly that day. The nightly schedule and the backfill become the same task called with different dates: the fare fix ships once and applies to both.

2. **Make the write replace the partition**

   Each run deletes the target day's partition and writes it fresh (`delete_write`), with `partition_overwrite` as the backfill strategy. A day that fails halfway and is retried, or a day rerun next week, ends with one copy of each payout, never two.

3. **Cap the backfill with a pool**

   Put the task in a warehouse pool of 4 slots. The warehouse fits about six heavy runs and the nightly build needs two, so the backfill only ever takes what is left. Give the nightly run a higher priority weight so it claims a free slot first; at 20 minutes a day, 90 days finish in about 8 hours.

| Pitfall: A backfill script is a second pipeline |
| --- |
| The tempting fix is a one-off loop that fires 90 warehouse queries in parallel. It bypasses the pool, so it saturates the warehouse and the nightly run misses 6am; and it carries its own copy of the fare logic, which drifts from the task the next time that logic changes. |

**Follow-up questions**

1. The rebuild now has to cover a full year instead of 90 days. What changes?\
   *Whether the pool cap, not the range, sets the run time, and how you track progress across hundreds of dated runs.*
2. A summary table downstream reads `payouts_warehouse`. How do its rows get corrected too?\
   *Propagating a backfill to dependent tasks through the dependency graph instead of by hand.*

</details>
