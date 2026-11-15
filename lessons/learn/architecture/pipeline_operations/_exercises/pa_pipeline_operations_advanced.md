# Pipeline Operations: Advanced - Exercises

Lesson: [pa_pipeline_operations_advanced.md](../pa_pipeline_operations_advanced.md)

### Exercise 1 of 11

**● TASK**

50-plus pipelines share one warehouse bill that climbs monthly. Build a monthly scheduled job that reads the warehouse query history and applies one cost lever per cycle (storage tiering, partition pruning, materialized-view ROI, warehouse right-sizing or query rewriting) to those pipelines. Feed each run into an automated audit that flags any pipeline tier without a named cost owner, and alert the owners when a run fails or a tier is flagged.

**Starting canvas** (already placed for you):

- Warehouse query history (source, API)
- Pipeline materializations (transform, dbt)
- Warehouse (storage, warehouse)

<details>
<summary><strong>Solution</strong></summary>

#### Cost as a monitored loop

Monitoring cost as a rhythm means treating your own bill like any other pipeline signal. You measure it on a schedule, act on it one lever at a time, and give it a named owner. Here an Airflow DAG wakes once a month, reads the warehouse query history, pulls one lever on the pipeline materializations, and then hands off to an automated ownership audit. What keeps the loop proactive is **monitoring the rhythm itself**. If a run fails silently, or an audit flag reaches nobody, you are back to reactive cost work the moment the bill spikes.

```mermaid
flowchart LR
    n0[("Warehouse query history<br/>(API)")]
    n1["Monthly cost-rhythm job<br/>(Airflow)<br/>Alert: page cost owners if the monthly run fails"]
    n2["Pipeline materializations<br/>(dbt)"]
    n3[("Warehouse<br/>(warehouse)")]
    n4["Ownership audit<br/>(custom)"]
    n5(["Cost owner alerts<br/>(Email)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n1 --> n4
    n4 --> n5
```

*The monthly job reads query-history telemetry and applies one lever to the pipelines. It then drives the ownership audit, whose flags go to the owners. A monitor alert on the job pages them if a run fails.*

1. **Rank levers from telemetry**

   The query history already shows which of the 50-plus pipelines dominate compute and stored bytes, so start the job there. If you skip it, you end up tuning the pipeline you only assume is expensive.

2. **Pull exactly one lever per cycle**

   Change one thing per cycle so you can attribute the result. If partition pruning and a warehouse resize ship in the same month, a 20% drop can't be credited to either one, and a regression in one hides behind the win from the other.

3. **Alert on the audit and on the job**

   Draw the ownership audit as a quality gate downstream of the job, and route its flags to an alerts consumer so an ownerless tier lands with a person. Put a monitor alert on the job too, because a rhythm that stopped running 3 months ago looks exactly like one with nothing to report.

| Pitfall: A report nobody opens is not an alert |
| --- |
| Writing audit flags to a table feels like accountability, but nobody checks that table until finance escalates. The flag has to reach a person, and the job's own failures have to page someone. Otherwise the rhythm decays back into the quarterly firefight. |

**Follow-up questions**

1. How would the job choose which lever to pull in a given month?\
   *Ranking levers by measured spend and effort rather than habit.*
2. What should happen when a tier stays flagged ownerless for 2 cycles running?\
   *Adding an escalation path to the audit's alert.*

</details>


<br>

### Exercise 2 of 11

**● TASK**

Build a pipeline from the production source to dev, CI, and staging stores. Add a masking step whose name states how the PII columns (email, name, address, phone) are hashed or redacted, then a data-quality check confirming no raw PII survives before any store. Name each store for its data shape: dev a small sample committed to the repo, CI a slim recent-prod subset of modified models plus descendants, staging a last-7-days subset or masked full prod.

**Starting canvas** (already placed for you):

- Production data (PII columns include email, name, address, phone) (source, PostgreSQL)
- Masking pipeline (currently absent; define PII handling per column) (transform, Pandas)
- Data quality check (verify masked output, no raw PII) (quality_gate, Great Expectations)
- Dev environment (no formal data shape) (storage, PostgreSQL)
- CI environment (no formal data shape) (storage, PostgreSQL)
- Staging environment (no formal data shape) (storage, PostgreSQL)

<details>
<summary><strong>Solution</strong></summary>

#### Match the data shape to the bug you're hunting

This challenge is about **environment-appropriate data provisioning**: you don't feed dev, CI, and staging the same dataset, because each one exists to catch a different class of failure. Dev catches typos and broken references, so it wants the smallest dataset that still runs, a tiny fixture committed to the repo. CI catches schema regressions on the models you just touched, so it wants a slim subset scoped to the modified models plus their descendants. Staging catches integration and scale problems that a slim CI run structurally cannot, so it wants a large, realistic slice, the last 7 days or a masked full copy of prod. The data shape IS the design decision here; naming each store by its shape is how the pipeline documents which failure it is built to surface.

```mermaid
flowchart LR
    n0[("Production (PII: email, name, address, phone)<br/>(PostgreSQL)")]
    n1["Mask PII: hash email/phone, redact name/address<br/>(Pandas)"]
    n2["Assert no raw PII survives masking<br/>(Great Expectations)"]
    n3[("Dev: tiny sample fixture, committed to repo<br/>(PostgreSQL)")]
    n4[("CI: slim subset, modified models + descendants<br/>(PostgreSQL)")]
    n5[("Staging: last-7-days slice or masked full prod<br/>(PostgreSQL)")]
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n2 --> n4
    n2 --> n5
```

*One masking transform and one quality gate feed three differently-shaped stores. The gate is shared; only the downstream shape changes per environment.*

Notice the masking step and the quality gate sit ONCE, upstream of all three stores. You transform PII out of the data as it leaves production, then every environment reads from the cleaned stream, so no raw `email`, `name`, `address`, or `phone` ever lands in a non-prod box. The step name states the per-column policy (hash the identifiers you still need to join on, redact the free text you don't) so the policy is legible from the diagram instead of buried in code. The quality check right after it is a hard gate, not a hope: it asserts no raw PII made it through before anything downstream is allowed to load. That is data quality used as a barrier, the one place you fail the run rather than warn.

| Pitfall: Copying full prod into every environment |
| --- |
| The tempting shortcut is one masked dump loaded identically into dev, CI, and staging. It looks uniform and safe, but it makes dev slow to seed and heavy to commit, makes every CI run drag a full dataset through tests that only touch a handful of models, and hides nothing the shapes were meant to expose. Uniform data means each environment catches the SAME bugs, and the cheap, fast feedback dev and CI are supposed to give evaporates. |

| Key insight: Slim vs. full is a state question, not a size dial |
| --- |
| CI's 'modified models + descendants' is state-based selection, the same idea as dbt's `state:modified+`: build only what your change could have broken. Staging's 'last-7-days or masked full prod' is a volume/recency slice chosen so integration and scale behavior actually show up. Same source, same mask, but one subset is scoped by the DAG of what changed and the other by how much recent data you need, because they answer different questions. |

**Follow-up questions**

1. If 2 rows share an `email`, should the hash collide so joins still work across the masked stores?\
   *Tests that hashing preserves referential joins while redaction destroys them, the reason the policy differs per column.*
2. What has to change if a new model in CI depends on a model that was NOT modified?\
   *Probes the 'plus descendants' half of state selection versus 'plus ancestors'.*

</details>


<br>

### Exercise 3 of 11

**● TASK**

Two orders workloads need pipeline-as-code. Nightly, export yesterday's orders from the orders database and push them to a partner API, retrying the push when the partner is down. Separately, keep raw_orders, fct_orders and the revenue mart within an hour of the database, rebuilding downstream when a raw partition is corrected. Build each with the model, declarative or imperative, that fits its workload, and name each orchestrator for its model.

**Starting canvas** (already placed for you):

- orders database (source, PostgreSQL)

<details>
<summary><strong>Solution</strong></summary>

#### One source, two models

Imperative and declarative pipelines both end up as a dependency graph run by an orchestrator; what differs is what a node in that graph means. In the **imperative** model the nodes are tasks. The partner delivery is `export_orders_task` then `push_to_partner_task`, ordered by explicit edges and fired by a nightly schedule, with retries on the step that talks to the partner. In the declarative model the nodes are data assets. `raw_orders`, `fct_orders` and `revenue_mart` are stored tables, the edges are lineage, and the one-hour target on the mart decides when anything runs.

```mermaid
flowchart LR
    n0[("orders_database<br/>(PostgreSQL)")]
    n1["imperative_task_orchestrator<br/>(Airflow)<br/>SLA: #60; 24h"]
    n2["export_orders_task<br/>(SQL)"]
    n3["push_to_partner_task<br/>(transform)<br/>Retries: 3"]
    n4(["partner_api<br/>(API)"])
    n5["declarative_asset_orchestrator<br/>(orchestrator)"]
    n6[("raw_orders<br/>(warehouse)")]
    n7[("fct_orders<br/>(warehouse)")]
    n8[("revenue_mart<br/>(warehouse)<br/>SLA: #60; 1h")]
    n0 --> n2
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n0 --> n6
    n6 --> n7
    n7 --> n8
    n5 --> n8
```

*A nightly task graph for the partner push; an asset graph that keeps `revenue_mart` within an hour.*

| ✕ Imperative: partner delivery | ✓ Declarative: orders tables |
| --- | --- |
| The work is a procedure with a side effect: calling the partner's API. There is no table to declare, only steps to run in order, so the graph is `export_orders_task` then `push_to_partner_task` on a nightly schedule. The retry sits on the push because that is the step that fails when the partner is down. | The work is a set of tables that must exist and stay fresh. You declare `fct_orders` from `raw_orders` and `revenue_mart` from `fct_orders`. The order falls out of lineage, and the orchestrator works back from the mart's one-hour target instead of a clock. |

| Key insight: A corrected partition is the deciding tell |
| --- |
| When a `raw_orders` partition is fixed, an asset graph already knows that `fct_orders` and `revenue_mart` depend on it and rebuilds exactly those. A task graph makes you rerun task instances for a date range and remember yourself what sits downstream. |

| Pitfall: One tool for both is the wrong fit for one of them |
| --- |
| Forcing both workloads into the model the team already runs gives you one of two bad pipelines. The first is a partner push modelled as an asset with nothing to store. The second is a mart rebuilt on a cron that drifts out of its one-hour window. Each pipeline works, and each resists every later change. |

**Follow-up questions**

1. The partner now wants the file only after `revenue_mart` is fresh. Which graph owns that dependency, and how does it cross from one model to the other?\
   *Extends the choice to a handoff between the two models.*
2. If the mart's target loosened to once a day, would a nightly task graph fit it just as well?\
   *Checks that the workload's facts, not the tool, drive the choice.*

</details>


<br>

### Exercise 4 of 11

**● TASK**

Half of the catalog's thousands of pipelines belong to engineers who left, and their cold partitions keep billing on the warehouse. Have the orchestrator run the ownership audit quarterly, reading the catalog and flagging every pipeline with no current owning team. Feed those flags directly into a cold-storage tier that takes the orphaned tables' cold partitions off the warehouse. Alert the platform team when a quarterly run fails.

**Starting canvas** (already placed for you):

- Pipeline catalog + active-team registry (source, PostgreSQL)
- Quarterly rhythm orchestration (schedules the audit and tiering) (transform, Airflow)
- Ownership audit (flags pipelines with no current owning team) (quality_gate, custom)
- legacy_orders_table (cold partitions still billing) (storage, warehouse)
- Existing consumers (consumer, API)

<details>
<summary><strong>Solution</strong></summary>

#### Let the audit flags be the work order

An ownership audit only pays off when its output becomes the input to the next step. When the gate flags a pipeline as having no current owning team, that same flag tells the cold-storage step which tables to move. The gate produces one list once, and the mover consumes it downstream. That is why the edge runs straight from the audit into the cold-storage node, instead of the tiering step going back to the catalog to decide again what counts as orphaned.

```mermaid
flowchart LR
    n0[("Pipeline catalog + active-team registry<br/>(PostgreSQL)")]
    n1["Quarterly orchestration<br/>(Airflow)"]
    n2["Ownership audit (no current owning team)<br/>(Great Expectations)"]
    n3[("legacy_orders_table (cold partitions)<br/>(warehouse)")]
    n4[("Cold-storage tier<br/>(object storage)")]
    n5(["Existing consumers<br/>(API)"])
    n6(["Run failure alerts<br/>(Email)"])
    n1 --> n2
    n0 --> n2
    n2 --> n4
    n3 --> n4
    n3 --> n5
    n1 --> n6
```

*The orchestrator fires the audit and alerts on a failed run; the orphan flags drive the tiering edge into object storage directly.*

| Pitfall: 2 paths that re-derive the same orphans |
| --- |
| The version most people try first runs tiering as its own step that queries the catalog again for unowned pipelines, sitting beside the audit rather than downstream of it. Now 'orphaned' has 2 definitions that drift apart as soon as the 2 queries differ by one line: you tier a table the audit never flagged, or you leave a flagged one billing on the warehouse. Feed the gate's output into the mover so there is exactly one list. |

| Pitfall: A silent quarterly job loses a whole quarter |
| --- |
| This rhythm runs 4 times a year, so a failed run that nobody notices lets a full quarter of orphans pile up before anyone looks. Monitoring applies to the audit itself: wire the orchestrator to an alert destination so a failed run reaches the platform team the same day. The audit makes sure every other pipeline has an owner, and the alert makes sure the audit has one too. |

| Key insight: Move cold partitions, not whole tables |
| --- |
| The cost saving comes from partitioning. You do not evict `legacy_orders_table` wholesale. You move only its cold partitions to object storage, so the hot partitions stay on the warehouse and existing consumers keep working. An orphaned table is usually mostly cold, which is why it keeps billing for storage nobody reads. |

| Real world: Quarterly batch carrying an event-shaped trigger |
| --- |
| Ownership changes slowly, so the orchestrator runs this quarterly as a batch job, not a live stream. Inside that batch the flags behave like events: each flag triggers a tiering action for its table. You get the simplicity of a scheduled `DAG` and the decoupling of an event-driven design, without standing up streaming for something that runs once a quarter. |

**Follow-up questions**

1. What has to happen when a new team adopts a pipeline whose cold partitions were already moved to cold storage?\
   *Tests whether the audit stays the single source of truth when data moves back, not just when it moves out.*
2. How does the tiering step behave if a flagged table's cold partitions are still receiving late-arriving writes?\
   *Probes the boundary between cold and hot partitions and whether the mover is safe to run again.*
3. How would you catch a quarterly run that never started, rather than one that started and failed?\
   *Extends the failure alert into a freshness check on the rhythm itself.*

</details>


<br>

### Exercise 5 of 11

**● TASK**

The hourly_subscription_metrics pipeline rebuilds its whole Snowflake table every hour from a Postgres replica and a full Stripe pull, though its 3 consumers only need data within two hours. Redraw it keeping every stage, with a batch transform loading Snowflake incrementally on a cadence matched to that need, a data-quality check verifying each load before consumers read it, and an alert that pages on-call when the table goes stale past two hours.

**Starting canvas** (already placed for you):

- Postgres replica (subscription state) (source, PostgreSQL)
- Stripe API (billing events; full pull every hour) (source, API)
- hourly_subscription_metrics (full rebuild every hour, partitioned on ingest_time) (transform, dbt)
- Snowflake hourly_subscription_metrics (storage, Snowflake)
- Finance dashboard, churn ML, ad-hoc analytics (consumer, Tableau)

<details>
<summary><strong>Solution</strong></summary>

#### Why it costs ten times too much

The lever here is **incremental refresh**: instead of rebuilding `hourly_subscription_metrics` from scratch each run, you extract only the rows that changed since the last watermark and `MERGE` them into the table that already exists. A full rebuild's cost tracks the size of the table, not how much actually changed, so most of every run re-derives rows that were already correct. That is the ten-times gap. The second lever is cadence: the dashboard only needs data within two hours, so an hourly schedule does double the work freshness asks for.

```mermaid
flowchart LR
    subgraph L0["Ingest"]
        n0[("Postgres replica<br/>(PostgreSQL)")]
        n1[("Stripe API (billing events)<br/>(API)")]
    end
    subgraph L1["Merge every 2h"]
        n2["dbt incremental MERGE by watermark<br/>(dbt)<br/>SLA: #60; 2h"]
        n3[("Snowflake staging partition<br/>(Snowflake)")]
    end
    subgraph L2["Audit and publish"]
        n4["Data-quality gate<br/>(Great Expectations)"]
        n5[("hourly_subscription_metrics (published)<br/>(Snowflake)<br/>Alert: page on-call if stale #62; 2h")]
    end
    subgraph L3["Serve"]
        n6(["Finance dashboard, churn ML, analytics<br/>(dashboard)"])
    end
    n0 --> n2
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n4 --> n5
    n5 --> n6
```

*Merge only what changed every two hours into a staging partition, gate on a quality check, publish, and page on-call if the published table goes stale.*

| Pitfall: The half-fix that still overpays |
| --- |
| The tempting shortcut is to keep the full rebuild but run it every two hours. That halves the bill, it does not tenth it, because each run still rescans and rewrites the whole table. Cadence alone buys 2x; the other 5x comes only from an incremental `MERGE` that touches just the changed rows. You need both. |

| Key insight: Stage, audit, then publish |
| --- |
| Land changed rows with a `MERGE` keyed on subscription id into a staging partition, run the quality check against it (row count in range, no null keys, watermark advanced), and publish into the table the dashboard reads only if it passes. Consumers never see a half-loaded slice, and a bad load stalls on the last good data. |

| Real world: A cheaper pipeline needs a louder alarm |
| --- |
| Moving to a two-hour cadence spends the slack the SLA used to have: one failed run now puts the dashboard past its promise. A freshness alert on the published table that pages on-call once it falls more than two hours behind fires whether the `MERGE` failed, the quality gate held a bad load back, or a scheduled run never started. That alert is how you prove the cost cut did not quietly break the SLA. |

**Follow-up questions**

1. A Stripe event arrives late, stamped inside a window you already published. What keeps the row correct?\
   *Idempotent `MERGE` plus watermark handling for late-arriving data.*
2. You need to correct 6 months of history after a mapping bug. How does partitioning let you backfill without a full rebuild?\
   *Reprocess partition by partition, reusing the same idempotent `MERGE`.*

</details>


<br>

### Exercise 6 of 11

**● TASK**

Wire the full operations program onto the representative pipeline on the canvas so the rest of the portfolio can copy it, with the dashboards still reading the serving warehouse. Schedule the declarative dbt models from an imperative orchestrator, and record their lineage in a column-level lineage catalog. Watch the curated warehouse table with five-pillar monitoring that pages the owning team, and roll query-tagged spend up into a cost dashboard for the monthly cost review. Build a masked staging copy through a PII-hashing step, and run the slim-CI tests against it.

**Starting canvas** (already placed for you):

- Postgres source (source, PostgreSQL)
- dbt build (transform, dbt)
- Serving warehouse (storage, warehouse)
- Downstream dashboards (consumer, dashboard)

<details>
<summary><strong>Solution</strong></summary>

#### One pipeline, every plane wired

Treating operations as a template is what makes a year-end pass tractable. You hang every operational plane on one representative pipeline and stamp the rest of the portfolio from it. The tension is reach versus reproducibility: a plane added by hand to one pipeline is a fix, while the same planes wired the same way on a model pipeline are a program. Only the program survives the next 50 pipelines.

```mermaid
flowchart LR
    subgraph L0["Dataflow"]
        n0[("Postgres source<br/>(PostgreSQL)")]
        n1["Airflow orchestrator<br/>(Airflow)"]
        n2["dbt build<br/>(dbt)"]
        n3[("Serving warehouse<br/>(warehouse)")]
        n4(["Downstream dashboards<br/>(dashboard)"])
    end
    subgraph L1["Operations planes"]
        n5(["Lineage catalog<br/>(OpenLineage)"])
        n6(["Five-pillar monitoring<br/>(consumer)<br/>Alert: page owning team on pillar breach"])
        n7(["Cost rollup dashboard<br/>(dashboard)"])
    end
    subgraph L2["Environments"]
        n8["PII hashing<br/>(transform)"]
        n9[("Masked staging<br/>(warehouse)")]
        n10["Slim CI tests<br/>(dbt tests)"]
    end
    n0 --> n2
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n2 --> n5
    n3 --> n6
    n3 --> n7
    n3 --> n8
    n8 --> n9
    n9 --> n10
```

*The dataflow stays 4 stages. The program is what hangs off the dbt build and the serving warehouse.*

| Key insight: Declarative models, imperative schedule |
| --- |
| The dbt models declare what each table should be. The orchestrator decides when the build runs and which upstream loads it waits on. Drawing that split makes the declarative-versus-imperative choice explicit, and the build is where column-level lineage is sent to the catalog. |

| Pitfall: One hashing rule across every shape |
| --- |
| Masked staging is the prod schema with PII hashed on the way in. Hash `user_id` with a different salt than prod and rows that join in prod stop joining in staging. The slim-CI tests then pass on data that cannot reproduce prod. Keep the hashing deterministic and shared by every non-prod shape. |

| Performance: Spend needs a tag and an owner |
| --- |
| Query tags attribute each warehouse query to its pipeline. The cost dashboard rolls those tags up for the monthly review, where the 5 levers get pulled. The monitor pages the owning team for the same reason: a breach or a cost spike with no named owner goes unread. |

**Follow-up questions**

1. If masked staging is rehashed with a rotated salt mid-quarter, which pillar fires first, and is that a real incident?\
   *Tests whether hashing consistency reads as an environment invariant rather than a data-quality failure.*
2. A pipeline is in phase 3 of deprecation but its query tag shows rising cost. Who owns removing the last consumer?\
   *Ties deprecation to the cost rollup and the owning team.*

</details>


<br>

### Exercise 7 of 11

**● TASK**

Build a daily cost job that reads the billing and access logs, attributes spend and partition reads to each owning team, and lands the results in a cost warehouse. A tiering job reads those read counts from the warehouse and moves data lake partitions unread for 90 days into cold object storage. When a team's daily spend runs 20% over its trailing 30-day average, alert that team's owner from the warehouse figures.

<details>
<summary><strong>Solution</strong></summary>

#### Measurement only pays off when it drives a lever

Cost monitoring is the measurement part of the proactive rhythm, and it earns its keep only when its output reaches a lever and a person. Your design has one measured fact (spend and reads per partition, per owner, per day) feeding 2 readers: the storage tiering lever and the owner alert. Without the daily job, both run on guesses: tiering by age, and alerts nobody owns.

1. **Attribute spend once a day, per owner**

   The logs arrive daily, so `daily_cost_attribution` runs on a `< 24h` cadence and writes one row per team, partition and day into `cost_warehouse`. That table is the measurement: every later decision reads it instead of the raw bill.

2. **Let read counts pick the tier**

   `tier_partitions_unread_90d` joins the lake's partitions to the access counts and moves only those with zero reads in 90 days to `cold_partition_archive`. Access frequency is the decision rule, so an old partition a quarterly report still reads stays hot.

3. **Send the alert to the team that owns the spend**

   `team_owner_alerting` compares each team's daily spend to its trailing 30-day average and fires at 1.2x. Routing it to the owner rather than a shared platform channel is the accountability part: the person who can change the pipeline is the one who hears.

```mermaid
flowchart LR
    n0[("billing_access_logs<br/>(source)")]
    n1["daily_cost_attribution<br/>(Spark)<br/>SLA: #60; 24h"]
    n2[("cost_warehouse<br/>(warehouse)")]
    n3[("data_lake<br/>(storage)")]
    n4["tier_partitions_unread_90d<br/>(Spark)"]
    n5[("cold_partition_archive<br/>(object storage)")]
    n6(["team_owner_alerting<br/>(consumer)<br/>Alert: alert owner if daily spend #62; 1.2x 30-day avg"])
    n0 --> n1
    n1 --> n2
    n2 --> n4
    n3 --> n4
    n4 --> n5
    n2 --> n6
```

*Daily attribution fills one `cost_warehouse` that drives both the tiering lever and the owner alert.*

| Pitfall: Tiering by age alone moves partitions people still read |
| --- |
| A rule like 'archive everything older than a year' is easier to write, but it skips measurement. A partition a compliance report reads monthly lands in a cold class with retrieval fees and hours of latency, and the next read costs more than the storage saved. Drive the move from the read counts in `cost_warehouse`, not from partition dates. |

**Follow-up questions**

1. Finance wants each team's monthly cost trend on a dashboard. What do you add?\
   *Reusing the measured table for a second reader instead of building a second job.*
2. A team's spend doubles because a planned backfill runs for 2 weeks. How do you keep the alert credible?\
   *Tuning the trailing baseline so accountability alerts are not ignored.*
3. Reads start hitting a partition already in `cold_partition_archive`. What tells you to move it back?\
   *The same access counts driving tiering in both directions.*

</details>


<br>

### Exercise 8 of 11

**● TASK**

Design the refresh that seeds staging from the production orders database (200 million rows). Staging receives a 10 percent sample, and every column the data catalog tags as PII is masked before it leaves production. The masked sample passes a validation check before landing in a staging store isolated from production, which the staging run of the orders pipeline reads instead of production.

<details>
<summary><strong>Solution</strong></summary>

#### Staging gets a shape, not a copy

Environment management means choosing a data shape for each environment on purpose. Staging exists to run the real pipeline against realistic data. It needs production's structure and skew, but not its 200 million rows or its customers' identities. A 10 percent sample keeps the distributions honest at a tenth of the cost. Masking the catalog-tagged PII columns keeps the copy legal. An isolated store means a staging run cannot read or write production, even by mistake.

```mermaid
flowchart LR
    n0[("production_orders_db<br/>(PostgreSQL)")]
    n1(["pii_column_tags<br/>(DataHub)"])
    n2["sample_and_mask_pii<br/>(Spark)"]
    n3["validate_masked_sample<br/>(Great Expectations)"]
    n4[("staging_orders_db<br/>(PostgreSQL)")]
    n5(["staging_pipeline_run<br/>(consumer)"])
    n0 --> n2
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n4 --> n5
```

*Production orders are sampled and masked using the catalog's PII tags, then validated. They land in an isolated staging store, which is the only thing the staging run reads.*

| Pitfall: Masking inside staging is already too late |
| --- |
| The tempting design copies production into staging and runs the mask there. Between the copy and the mask, real emails sit in an environment with broader access. If the mask job fails, they stay there. Mask inside the refresh, ahead of `validate_masked_sample`, so unmasked rows never cross production's boundary. |

| Key insight: Tags, not a column list, decide what gets masked |
| --- |
| `sample_and_mask_pii` reads the PII tags from the catalog instead of carrying a hardcoded list of columns. When someone adds a `billing_phone` column and tags it, the next refresh masks it with no code change. A hardcoded list would leak that column until someone remembered to edit the job. |

**Follow-up questions**

1. Developers want a laptop-sized slice of the same data. Where does dev branch off, and what changes?\
   *Reusing one masking path to serve a second, smaller environment shape.*
2. Tests join orders to customers by email. What breaks if masking turns the same email into a different value in each table?\
   *Deterministic masking that keeps the masked data joinable.*

</details>


<br>

### Exercise 9 of 11

**● TASK**

Each night a partner's settlement file must be pulled from a flaky API, retried up to 3 times on failure, and loaded into a raw warehouse table before anything downstream runs. Three reporting tables are derived from that raw table and must be fresh within 24 hours. Express the procedural pull-and-load imperatively as an Airflow task, and the derived reporting tables declaratively as dbt models.

<details>
<summary><strong>Solution</strong></summary>

#### Steps for side effects, assets for derived data

This workload sits on both sides of the declarative versus imperative line, and the design splits it right there. Pulling a file from a flaky API is a procedure: call, wait, retry, load, in that order, with side effects an orchestrator has to sequence. The three reporting tables are not steps at all. They are assets that should exist, derived from the raw table, at a stated freshness, which is exactly what a dbt model declares.

```mermaid
flowchart LR
    n0[("partner_api<br/>(API)")]
    n1["pull_and_load<br/>(Airflow)<br/>Retries: 3"]
    n2[("raw_settlements<br/>(warehouse)")]
    n3["reporting_models<br/>(dbt)"]
    n4[("reporting_tables<br/>(warehouse)<br/>SLA: #60; 24h")]
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
```

*The Airflow `pull_and_load` task retries the flaky API and lands `raw_settlements`; the dbt `reporting_models` declare the reporting tables from it.*

1. **Keep the side-effecting pull imperative**

   The pull is an Airflow task with `retryCount` set to 3, so a timeout retries that one task instead of failing the night. Its edge into the raw warehouse table is the ordering guarantee: nothing downstream reads until the load lands.

2. **Declare the derived tables as dbt models**

   Each reporting table is a model that selects from the raw table. dbt reads those references and builds the dependency graph itself, so you never hand-wire which table runs before which. The `< 24h` freshness sits on the asset, which is where a declarative pipeline says how fresh something must be.

| Pitfall: One operator per table is the brittle version |
| --- |
| The tempting design adds an Airflow operator for each reporting table and chains them with explicit dependencies. It runs, but every new table means editing the task graph, and the order you wired by hand slowly drifts from the data dependencies the SQL already states. |

| Key insight: Adding a table is the test of the split |
| --- |
| When finance asks for a fourth table, the declarative side absorbs it as one new model reading the raw table. The orchestrated pull does not change at all, and that is the leverage choosing by workload fit buys you. |

**Follow-up questions**

1. The partner starts publishing a correction file later the same morning. Which side of the design owns rebuilding the affected night, and what changes?\
   *Whether a replay is a procedural step for the orchestrator or a rebuild of declared assets.*
2. One reporting table now needs hourly freshness while the other 2 stay daily. Where does that difference live?\
   *Freshness as a property declared per asset rather than a schedule wired per task.*

</details>


<br>

### Exercise 10 of 11

**● TASK**

A legacy nightly pipeline still writes an old revenue table that a replacement has superseded, and its author has left the company. Design the deprecation monitor for the table's 30-day sunset window: a daily scheduled job reads the warehouse query log and the lineage catalog to find every remaining reader, and lands each reader's read count in a usage table. Each day the job alerts the owning team of every reader still querying the old table.

<details>
<summary><strong>Solution</strong></summary>

#### Deprecation is a monitoring job with an end date

A defined deprecation process exists because a pipeline whose author left has nobody who can list its readers from memory. So the readers get measured: every day of the sunset window, the design asks who still touched the old table, records the answer, and tells each owning team directly. That is **monitoring pointed at usage** instead of failures, and it lets the shutoff happen on evidence rather than on a calendar date.

```mermaid
flowchart LR
    n0[("warehouse_query_log<br/>(source)")]
    n1[("lineage_catalog<br/>(API)")]
    n2["daily_reader_scan<br/>(Airflow)"]
    n3[("reader_usage<br/>(warehouse)")]
    n4(["owner_alerts<br/>(Email)"])
    n0 --> n2
    n1 --> n2
    n2 --> n3
    n2 --> n4
```

*The query log and lineage catalog feed `daily_reader_scan`, which lands per-reader counts in `reader_usage` and emails owning teams.*

1. **Read both reader signals**

   The query log catches analysts and dashboards running ad hoc SQL; the lineage catalog catches scheduled jobs that read the table on their own cadence. Either alone misses a whole class of reader, so `daily_reader_scan` reads both.

2. **Land a count per reader, every day**

   Writing each reader's daily read count to `reader_usage` turns the window into a trend: the reader list shrinks, and the day it stays empty is the day the pipeline can go. The same run sends `owner_alerts` to every team still on the list.

| Pitfall: An announcement is not a migration |
| --- |
| The common version posts a deprecation notice and switches the pipeline off on day 30. Readers whose owners left never see the notice, and the first signal is a failed downstream job. Alerting from measured reads reaches exactly the teams still depending on the table. |

| Real world: Zero reads are the shutoff evidence |
| --- |
| The platform team holds the switch, and the usage table is what they bring to review: reads at zero after the alerts went out. The same pattern retires a column or a Kafka topic: measure consumers, notify their owners, retire on evidence. |

**Follow-up questions**

1. A reader's owning team was dissolved last quarter. Where should its alert go?\
   *Ties deprecation back to the ownership audit: an orphan reader needs a claim or transfer before shutoff.*
2. Some readers run only at month end. How does the sunset window need to change?\
   *Tests whether the window covers the slowest reader's cadence before zero reads mean anything.*

</details>


<br>

### Exercise 11 of 11

**● TASK**

A payments pipeline lands 40 million card transactions a day in a production warehouse, with the cardholder name, email and card number columns tagged as PII. Build its non-prod side: an orchestrated weekly refresh that masks every tagged column before any copy leaves production, a dev store holding a 1 percent sample, and a staging store holding the most recent month at full volume. Non-prod must cost a fraction of prod, so add a daily cost check over both stores that alerts the owning team when either runs over budget.

<details>
<summary><strong>Solution</strong></summary>

#### Masking sits upstream of every non-prod copy

Environment management for a pipeline with PII is three choices made together: what shape of data each environment holds, where the sensitive columns get masked, and who notices when the copies start costing real money. At 40 million transactions a day, the most recent month is about 1.2 billion rows. Staging takes that month so release tests see real volume; dev takes a 1 percent sample, about 12 million rows, so queries return in seconds and cost almost nothing.

```mermaid
flowchart LR
    n0[("prod_warehouse<br/>(warehouse)")]
    n1["weekly_refresh<br/>(Airflow)"]
    n2["mask_pii_columns<br/>(SQL)"]
    n3[("dev_store_1_percent_sample<br/>(storage)")]
    n4[("staging_store_most_recent_month<br/>(storage)")]
    n5["daily_cost_check<br/>(SQL)<br/>SLA: #60; 24h"]
    n6(["owning_team_alert<br/>(Email)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n2 --> n4
    n3 --> n5
    n4 --> n5
    n5 --> n6
```

*`weekly_refresh` pulls the month, `mask_pii_columns` writes the 1 percent dev sample and the full staging month, and `daily_cost_check` alerts the owning team.*

1. **Give each environment the shape its tests need**

   Dev is for writing and debugging transforms, so it needs realistic rows, not realistic volume: a 1 percent sample is enough and keeps every query cheap. Staging is where a release proves it holds at production scale, so it gets the most recent month at full volume. An empty dev tests nothing; a full-history staging costs as much as prod.

2. **Mask once, before anything leaves production**

   `mask_pii_columns` sits between the refresh and both stores, so the only way into dev or staging runs through it. Masking deterministically (the same card number always becomes the same token) keeps joins and distinct counts behaving like production while no raw value ever lands outside it.

3. **Orchestrate the refresh, watch the bill daily**

   `weekly_refresh` is an Airflow DAG: extract the month, mask it, then load staging and sample dev, each task waiting on the one before. `daily_cost_check` reads the spend of both stores every day and notifies `owning_team_alert` when either crosses its budget, so drift shows up within a day instead of on the monthly invoice.

| Pitfall: Masking after the copy lands is already a leak |
| --- |
| Copying production into staging and then masking there means raw card numbers sit in a less-guarded environment for as long as the job takes, and indefinitely if it fails. Masking belongs upstream of every non-prod write. The other common miss is loading a new staging month without dropping the old one: copies pile up and staging quietly becomes a second production bill. |

**Follow-up questions**

1. A data science sandbox now needs the same masked month as staging. What changes?\
   *Adding a third environment fed from the same masking stage and covered by the same cost check.*
2. Legal adds date of birth to the PII tags. How does the design keep up without a code change per column?\
   *Whether masking is driven by column tags rather than a hard-coded column list.*
3. Staging spend doubles after a schema change widens the table. How do you find out, and what do you cut first?\
   *Treating the daily cost check as an ongoing cost rhythm rather than a one-off audit.*

</details>
