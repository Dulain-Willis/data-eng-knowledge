# Pipeline Anatomy: Intermediate - Exercises

Lesson: [pa_what_is_a_pipeline_intermediate.md](../pa_what_is_a_pipeline_intermediate.md)

### Exercise 1 of 11

**● TASK**

A food-delivery marketplace has 3 sources (PostgreSQL orders, MySQL menus, a promotions API) and 4 teams that each clean their own copy, so order counts disagree and a test-order filter fix reached only 2 teams. Redesign it in bronze, silver and gold layers: land every source raw in object storage, have one job build a curated orders table on the lake that drops test orders, and give each team its own warehouse serving table read from the curated one.

<details>
<summary><strong>Solution</strong></summary>

#### One curated table between three sources and four teams

The medallion pattern earns its place the moment a second team reads the same data. With 3 sources and 4 teams each pulling and cleaning on their own, the company runs 12 extract-and-clean jobs and 4 separate copies of the test-order rule, so a fix that reaches 2 of them leaves 2 teams counting different orders. Bronze, silver and gold in the middle turn that into 3 landing jobs, 1 curated build and 4 serving jobs: **8 jobs, and the rule lives in exactly one**.

```mermaid
flowchart LR
    subgraph L0["Bronze raw"]
        n3[("raw_landing<br/>(object storage)")]
    end
    subgraph L1["Silver curated"]
        n4["drop_test_orders<br/>(dbt)"]
        n5[("curated_orders<br/>(Iceberg)")]
    end
    subgraph L2["Gold serving"]
        n6[("finance_serving<br/>(warehouse)")]
        n7[("marketing_serving<br/>(warehouse)")]
        n8[("operations_serving<br/>(warehouse)")]
        n9[("pricing_serving<br/>(warehouse)")]
    end
    n0[("orders_db<br/>(PostgreSQL)")]
    n1[("menus_db<br/>(MySQL)")]
    n2[("promotions_api<br/>(API)")]
    n0 --> n3
    n1 --> n3
    n2 --> n3
    n3 --> n4
    n4 --> n5
    n5 --> n6
    n5 --> n7
    n5 --> n8
    n5 --> n9
```

*Bronze lands three sources raw on object storage, one job drops test orders and writes the curated orders table on the lake, and four warehouse tables read only from it.*

1. **Land each source raw in the lake**

   Bronze holds the three sources exactly as they arrived, on object storage. Its promise to the next layer is completeness, not cleanliness: nothing is filtered here, so when the test-order rule changes again, silver is rebuilt from history instead of re-pulled from the sources.

2. **Curate orders once**

   Silver is one job and one table: orders joined to menus and promotions, with test orders removed. Its promise is that every row is a real customer order under the company's single definition. Keeping it on the lake in an open table format means raw and derived data share one storage layout.

3. **Give each team one serving table**

   Gold is one warehouse table per team, each read from silver only: finance gets revenue, pricing gets per-restaurant features. Each team owns its gold job, so a fifth team adds one node on the right and nothing on the left.

| Pitfall: A shared raw zone does not fix the counts |
| --- |
| Landing everything in one lake and letting each team read the raw zone looks like consolidation, but every team still writes its own cleaning, so the test-order filter still exists in four places. Agreement comes from the silver table, not from shared storage. |

| Performance: The middle layer costs one hop and extra copies |
| --- |
| Each layer runs on its own schedule, so an hourly silver build bounds every gold table at hourly freshness or slower. Storage roughly triples: three copies of the 2TB order history at about $23 per compressed TB a month is around $140 a month, less than one afternoon of teams reconciling order counts. |

**Follow-up questions**

1. Customer support now needs order data for refund reports. How many jobs change, and where?\
   *Checks that a new consumer adds one gold table and leaves bronze and silver untouched.*
2. Pricing asks for numbers no older than 15 minutes. What does the hourly silver build do to that request?\
   *Checks that each layer's schedule bounds the freshness of everything downstream of it.*

</details>


<br>

### Exercise 2 of 11

**● TASK**

An ingestion feeds a warehouse from app events (millions an hour, each with a customer email) and product catalog images, which warehouse SQL cannot decode. Its six transforms are type casts, deduplication, email hashing, image feature extraction, sessionizing and a join to the product dimension. Emails may never land unhashed, and sessions must be queryable within 15 minutes. Place each before the load (ETL) or as SQL in the warehouse over a raw copy (ELT).

<details>
<summary><strong>Solution</strong></summary>

#### Each transform goes where its constraint lives

ETL versus ELT is a choice you make per transform, not per pipeline. Since cloud warehouses split storage from compute, the default is ELT: land a raw copy, then transform it as SQL where analysts can rerun it. A transform moves before the load only when something makes the warehouse the wrong place for it. Of these six, 3 have such a reason.

```mermaid
flowchart LR
    n0[("app events<br/>(Kafka)")]
    n1[("product catalog<br/>(API)")]
    n2["hash emails and sessionize<br/>(Flink)"]
    n3["image feature extraction<br/>(Spark)"]
    n4[("raw warehouse tables<br/>(warehouse)")]
    n5["ELT models<br/>(dbt)"]
    n6[("curated warehouse tables<br/>(warehouse)")]
    n0 --> n2
    n1 --> n3
    n2 --> n4
    n3 --> n4
    n4 --> n5
    n5 --> n6
```

*Hashing, sessionizing and image features run before the load; casts, dedup and the dimension join run as dbt SQL over the raw copy.*

1. **Hash emails in flight**

   The rule is about storage, not queries. A plaintext email that lands in a raw table and is hashed by a later model has already been stored. Hashing has to happen in the stage that writes, so it lives in the stream processor before the load.

2. **Extract image features outside the warehouse**

   Warehouse SQL works on rows and columns; it cannot decode pixels or run a vision model. A Spark job reads the images, computes the features, and loads only the feature columns.

3. **Sessionize the stream before it lands**

   Millions of events an hour with a 15-minute bar is stateful windowing over an unbounded stream. Flink holds each user's open session and emits it when the gap closes, loading both the hashed events and finished sessions.

4. **Leave the rest to ELT**

   Type casts, deduplication and the dimension join have no such constraint. The dimension already sits in the warehouse, and a dedup rule that keeps changing is cheaper to rerun from the raw copy than to re-extract. dbt models keep all 3 versioned and repeatable.

| Pitfall: A hash after the load is too late |
| --- |
| Putting email hashing in a dbt model feels tidy because it sits beside the other SQL. But the raw table it reads has already stored every plaintext email, and warehouse time travel keeps old versions even after you delete them. |

| Key insight: Before-load needs a named reason |
| --- |
| For each transform, ask what would break if it ran in the warehouse. A compliance rule, a data type SQL cannot read, or a freshness bar a scheduled model cannot meet are reasons. Habit is not. |

**Follow-up questions**

1. Duplicate events reach the sessionizer before the in-warehouse dedup runs. When would you move deduplication before the load too?\
   *Whether a before-load transform pulls an upstream one along with it.*
2. Compliance now allows emails in a locked raw schema for 24 hours. Does hashing move?\
   *Whether a changed constraint changes the placement.*

</details>


<br>

### Exercise 3 of 11

**● TASK**

An hourly merge step joins 4 inputs into an enriched shipments table: shipments and carrier invoices land hourly, GPS pings every 15 minutes, and a fuel price file daily around 14:00. Have an orchestrator run the merge each hour only after both hourly inputs pass checks for partial input. GPS pings up to an hour old are fine, and a late fuel file must not hold up a run: the run uses the latest price on or before its date.

<details>
<summary><strong>Solution</strong></summary>

#### A merge runs at the pace of the inputs it waits on

When several inputs converge on one step, that step takes on dependency management for all of them. It can only run as often as the inputs it waits on, and it only writes a correct hour if each input is pinned to that hour. Here the 2 hourly drops set the cadence, so the merge is hourly. The 15-minute GPS feed is faster than the run needs, and the daily fuel file is far slower, so neither should gate it.

#### Break down the requirements

1. **Find the effective cadence**

   A run cannot start before both hourly drops for its hour exist, so hourly is the fastest the merge can go. Running it every 15 minutes would only re-read the same hourly data four times.

2. **Pin each input to the run's interval**

   Shipments and invoices are read for exactly the run's hour. GPS is read as the latest pings at or before the hour, accepted up to an hour old. Fuel is the latest price on or before the run's date, which before 14:00 means yesterday's.

3. **Stop a partial hour before the write**

   A sensor waits until both hourly partitions have landed, then a row-count check compares each drop with the count its source published. If either fails, the run stops before the enriched table is touched.

#### The reference architecture

```mermaid
flowchart LR
    n0[("shipments_db<br/>(PostgreSQL)")]
    n1[("carrier_invoices_api<br/>(API)")]
    n2[("gps_pings<br/>(source)")]
    n3[("fuel_price_file<br/>(source)")]
    n4["hourly_orchestrator<br/>(Airflow)"]
    n5["partition_landed_sensor<br/>(custom)"]
    n6["row_count_check<br/>(Great Expectations)"]
    n7["hourly_merge<br/>(SQL)"]
    n8[("enriched_shipments<br/>(warehouse)")]
    n0 --> n5
    n1 --> n5
    n5 --> n6
    n6 --> n7
    n2 --> n7
    n3 --> n7
    n7 --> n8
    n4 --> n5
    n4 --> n7
```

*Hourly inputs pass the landed sensor and the row-count check; GPS pings and the fuel price file feed the merge directly under its as-of rule.*

The orchestrator owns the schedule and the order: `partition_landed_sensor`, then `row_count_check`, then `hourly_merge`. Only the hourly inputs go through the gates. `gps_pings` and `fuel_price_file` go straight to the merge, where the as-of rule decides which version each run reads.

| Pitfall: Waiting on the daily file stalls every morning run |
| --- |
| If the merge waits for the fuel file, the 03:00 run sits until 14:00 and every later hour piles up behind it. Yesterday's price is already acceptable, so the wait buys nothing. |

| Key insight: Every input is a place a backfill can start |
| --- |
| If invoices are reloaded for a past day, every hourly merge that read that day has to rerun over the same dates. Otherwise the enriched table keeps the old numbers. |

**Follow-up questions**

1. What changes if finance needs today's fuel price, never yesterday's?\
   *Trading freshness for a blocking dependency: either the morning runs wait, or they rerun once the file lands.*
2. A third hourly input usually lands at 50 past the hour. What happens to each run's start time?\
   *The slowest gating input sets when each run can start.*

</details>


<br>

### Exercise 4 of 11

**● TASK**

A hotel-booking platform lands three sources in a raw store: bookings by change stream flushed every 15 minutes, clickstream as hourly files, and partner rates once a day. An hourly Airflow DAG merges them, retrying 3 times; a quality gate releases each hour to a revenue dashboard and a pricing model, while a finance export reads the merge output directly. Draw it with each stage's cadence, and page on-call from the one job whose failure stalls all three readers.

<details>
<summary><strong>Solution</strong></summary>

#### Find the job every reader waits on

A production diagram gets read for **blast radius**: for each job, follow its edges forward and count the readers that go stale when it fails. Here the fan-in sits at `hourly_merge`, and the fan-out splits right after it: 2 readers wait behind `quality_gate`, and `finance_export` reads the merge output directly. Only one job sits upstream of all three, so that is where the page belongs. Cadence and failure behaviour are the other 2 columns of the reading: how often each edge moves data, and what each job does when it breaks.

```mermaid
flowchart LR
    n0[("bookings_cdc<br/>(CDC)<br/>SLA: #60; 15min")]
    n1[("clickstream_files<br/>(source)<br/>SLA: #60; 1h")]
    n2[("partner_rates_api<br/>(API)<br/>SLA: #60; 24h")]
    n3[("raw_landing<br/>(storage)")]
    n4["hourly_merge<br/>(Airflow)<br/>SLA: #60; 1h · Alert: page on-call on failure · Retries: 3"]
    n5["quality_gate<br/>(quality_gate)"]
    n6(["revenue_dashboard<br/>(consumer)"])
    n7(["pricing_model<br/>(consumer)"])
    n8(["finance_export<br/>(consumer)"])
    n0 --> n3
    n1 --> n3
    n2 --> n3
    n3 --> n4
    n4 --> n5
    n5 --> n6
    n5 --> n7
    n4 --> n8
```

*Three sources land in `raw_landing`; the hourly Airflow merge retries 3 times and pages on failure, then feeds `quality_gate` (dashboard and pricing) and `finance_export` directly.*

1. **Write the cadence on every edge into the merge**

   Bookings arrive every 15 minutes, clickstream hourly, partner rates daily, and the merge runs hourly. So each merge picks up 4 bookings flushes, one clickstream file and, for 23 of 24 hours, the same partner rates it used last hour. Marking `slaFreshness` on each source turns those mismatches into something you can see instead of something you learn from an incident.

2. **Put failure behaviour on jobs, not stores**

   `raw_landing` holds files; it does not run on a schedule, so it has no retry to set. The jobs are the Airflow merge and the gate. The merge retries 3 times, which absorbs a slow read from the raw store, and only an hour that still fails after the third attempt is worth waking someone for.

3. **Trace each job forward and count readers**

   `quality_gate` reaches the dashboard and the pricing model: 2 readers. `hourly_merge` reaches the gate and `finance_export`, so all three. That count is why the alert sits on the merge: it is the single job whose failure every reader feels.

| Pitfall: The gate looks central, but finance reads past it |
| --- |
| The gate sits closest to the consumers, so it is the tempting place for the page. Trace the edges and `finance_export` never touches it: a gate-only alert stays silent through an outage finance notices first, while a merge failure also leaves the gate with nothing to check. |

| Real world: Owners change where layers change |
| --- |
| Fill the owner column the same way: the bookings, clickstream and partner teams own their feeds up to `raw_landing`; the platform team owns the store, the merge and the gate; each consumer team owns its reader. The page goes to the platform team because the merge is theirs, and a broken source feed goes back to the team that publishes it. |

**Follow-up questions**

1. A fraud model starts reading bookings from `raw_landing` every 15 minutes, skipping the merge. Which job's failure now reaches the most readers, and what protects the fraud model?\
   *Recounting blast radius when a reader bypasses the fan-in, and watching freshness where no job failure would fire.*
2. The partner rates file arrives 6 hours late but nothing errors. Which readers see stale prices, and would the merge's page fire?\
   *Telling lateness apart from failure, and why freshness monitoring sits beside failure alerts.*

</details>


<br>

### Exercise 5 of 11

**● TASK**

A ride-hailing app publishes trip events to one Kafka topic, read by a finance dashboard of hourly driver earnings and a feature store of per-rider features refreshed every 10 minutes. Land the events raw, keep one curated trips table that both readers agree on, and choose where the pipeline forks and how often curated runs. Then attach a surge-pricing service that must react within 1 second, plus a nightly job reconciling its decisions against curated trips.

<details>
<summary><strong>Solution</strong></summary>

#### Fork after the curated layer, not at the topic

When 2 readers of one source must agree on what a trip is, they fork at the **curated layer**. Fork at ingestion instead and each branch writes its own cleaning: finance drops cancelled trips one way, the feature job another, and the dashboard and the model quietly disagree. Forking after `curated_trips` gives one bronze landing, one silver definition, and 2 gold outputs that differ only in shape and cadence.

1. **Run curated at the faster reader's cadence**

   The feature store needs trips no older than 10 minutes, and it can only be as fresh as the layer it reads. So `curate_trips` runs every 10 minutes, inside the `< 15min` band. An hourly curated run would starve the feature store; a streaming one would buy the dashboard nothing it asked for.

2. **Let the hourly reader aggregate the slices**

   The finance branch is the one that aggregates. Each hourly run of `hourly_earnings_rollup` reads the 6 10-minute curated slices that make up the hour and sums earnings by driver. The feature job reads only the newest slice and updates each rider's rolling values in `rider_feature_store`.

3. **Attach the 1-second reader at the topic**

   No batch layer meets a 1-second budget: curated is up to 10 minutes old by design. Surge pricing reads `trip_events` directly through a streaming job with minimal cleaning and logs each decision to `surge_decisions`. This is the case where forking at ingestion is right: latency forces it, not convenience.

```mermaid
flowchart LR
    n0[("trip_events<br/>(Kafka)")]
    n1[("raw_trip_landing<br/>(object storage)")]
    n2["curate_trips<br/>(Spark)<br/>SLA: #60; 15min"]
    n3[("curated_trips<br/>(Delta Lake)")]
    n4["hourly_earnings_rollup<br/>(dbt)<br/>SLA: #60; 1h"]
    n5(["finance_dashboard<br/>(Metabase)"])
    n6["rider_feature_job<br/>(Spark)<br/>SLA: #60; 15min"]
    n7[("rider_feature_store<br/>(Feast)")]
    n8["surge_pricing<br/>(Flink)<br/>SLA: real-time"]
    n9[("surge_decisions<br/>(PostgreSQL)")]
    n10["nightly_surge_reconciliation<br/>(Spark)<br/>SLA: #60; 24h"]
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n4 --> n5
    n3 --> n6
    n6 --> n7
    n0 --> n8
    n8 --> n9
    n9 --> n10
    n3 --> n10
```

*Bronze `raw_trip_landing`, silver `curated_trips` every 10 minutes, 2 gold branches, and a real-time branch off `trip_events` checked nightly.*

| Pitfall: Forking at ingestion doubles the definition of a trip |
| --- |
| The tempting design gives each team its own job off the Kafka topic. It looks decoupled, but a refund rule fixed in one branch stays wrong in the other, and every backfill runs twice. A shared silver table means the fix happens once. |

| Key insight: A shortcut off the topic needs a nightly check |
| --- |
| Surge pricing acts on uncleaned events, so some decisions rest on trips later cancelled or corrected. `nightly_surge_reconciliation` compares `surge_decisions` with `curated_trips` each night, keeping the fast branch honest against the one definition everyone else uses. |

**Follow-up questions**

1. Finance now wants yesterday's earnings final by 08:00, and some trip events arrive up to 2 hours late. What changes in the hourly branch?\
   *Late data: reprocessing past curated slices and rerunning the hourly aggregates they touch.*
2. A city-operations map needs open trips refreshed every minute. Does it fork at curated or at the topic?\
   *Whether a 1-minute need fits a batch curated cadence or belongs on the streaming branch.*

</details>


<br>

### Exercise 6 of 11

**● TASK**

A subscription software company's billing events, CRM and product usage logs are read directly by a finance dashboard, sales operations and a churn model, each cleaning its own copy. Redesign it as bronze, silver and gold: every source lands raw in object storage, one curated layer and the gold tables live in the warehouse, and each reader reads its own gold table. Usage logs carry IP addresses that may never be stored and arrive at 2 million events an hour, though readers need usage only per account per day. Run each transform before the warehouse load (ETL) or as SQL inside it (ELT), as its constraint requires.

<details>
<summary><strong>Solution</strong></summary>

#### A constraint decides where each transform runs

This is the medallion pattern with a placement decision inside it. Bronze, silver and gold give three readers one agreed version of every account, and ETL versus ELT decides, transform by transform, whether the work happens before the warehouse load or as SQL inside the warehouse. On a cloud warehouse the default is ELT. A transform moves before the load only when a constraint forces it, and this pipeline has exactly two: IP addresses that may never be stored, and 2 million usage events an hour that no reader needs at that grain.

| ✕ Before: every reader cleans its own copy | ✓ After: one curated layer |
| --- | --- |
| Finance, sales operations and the churn model each read billing, CRM and usage straight from the sources and clean them in their own jobs. That is up to 9 cleaning jobs, three definitions of an active account, and IP addresses copied into three places. | 4 jobs: IP stripping before landing, a usage rollup before the warehouse load, SQL that cleans billing and CRM inside the warehouse, and SQL that builds each reader's gold table. A fix to the account definition lands once and reaches all three readers. |

```mermaid
flowchart LR
    subgraph L0["Bronze"]
        n0[("billing_events<br/>(source)")]
        n1[("crm<br/>(source)")]
        n2[("usage_logs<br/>(source)")]
        n3["strip_ip_addresses<br/>(Spark)"]
        n4[("raw_lake<br/>(Iceberg)")]
    end
    subgraph L1["Silver"]
        n5["usage_rollup<br/>(Spark)"]
        n6["curate_billing_crm<br/>(dbt)"]
        n7[("curated_warehouse<br/>(warehouse)")]
    end
    subgraph L2["Gold"]
        n8["build_gold<br/>(dbt)"]
        n9[("gold_tables<br/>(warehouse)")]
        n10(["finance_dashboard<br/>(Metabase)"])
        n11(["sales_operations<br/>(consumer)"])
        n12(["churn_model<br/>(consumer)"])
    end
    n0 --> n4
    n1 --> n4
    n2 --> n3
    n3 --> n4
    n4 --> n5
    n4 --> n6
    n5 --> n7
    n6 --> n7
    n7 --> n8
    n8 --> n9
    n9 --> n10
    n9 --> n11
    n9 --> n12
```

*Every source lands in `raw_lake`. `strip_ip_addresses` and `usage_rollup` run before the load (ETL), and the dbt nodes run as SQL inside the warehouse over raw copies loaded as-is (ELT).*

1. **Strip IPs before anything is stored**

   The IP constraint is about storage, not about who may read it, so the removal has to happen before bronze. `strip_ip_addresses` is ETL by necessity: it is the only transform ahead of the raw landing, and it drops exactly one field. Everything else in the usage event lands untouched, so bronze is still a faithful raw copy.

2. **Roll up usage before the warehouse load**

   Readers need usage per account per day. Loading 48 million events a day into the warehouse only to `GROUP BY` them away pays warehouse compute for a grain no one reads. `usage_rollup` runs Spark over bronze and loads only the per-account daily table: ETL, and its constraint is volume.

3. **Leave everything else to warehouse SQL**

   Billing and CRM are small and carry nothing that may not land, so no constraint pulls their cleaning out of the warehouse. They load raw, and `curate_billing_crm` cleans and joins them as SQL: ELT, the cloud default. `build_gold` is ELT too, shaping one gold table per reader from the shared curated layer.

| Pitfall: Dropping IPs in silver is already too late |
| --- |
| If bronze lands the usage logs as they arrive and silver drops the `ip_address` field, the IPs sit in bronze for good, and bronze is the layer you keep for replay. A field that may never be stored has to go before the first write. |

| Performance: 48 million events a day shrink to one row per account |
| --- |
| 2 million events an hour is about 48 million a day. With roughly 40,000 accounts, the daily rollup loads about 40,000 rows. Spark over the lake does the heavy pass once, and every warehouse query after it runs on the small table. |

| Key insight: Bronze keeps the grain the rollup throws away |
| --- |
| Because bronze holds every stripped event, a question at a finer grain, such as usage per feature, is a new rollup over bronze rather than a re-ingest from the source. |

**Follow-up questions**

1. Legal now allows a salted hash of the IP for fraud review. Where does the hashing run, and what changes in bronze?\
   *Whether the before-landing transform changes shape when the constraint loosens.*
2. The churn model moves to scoring every 15 minutes. Which jobs change cadence, and does the usage rollup still belong before the load?\
   *Batch versus streaming on the usage path, and whether volume still decides ETL.*

</details>


<br>

### Exercise 7 of 11

**● TASK**

A retailer is moving reporting off an on-prem appliance with fixed, shared compute to a cloud warehouse that bills storage and compute separately. Design its ELT pipeline: point-of-sale rows and a nightly mainframe inventory export land raw in the warehouse, and SQL inside it rebuilds curated tables each night for analyst dashboards. The export arrives as EBCDIC fixed-width records the warehouse cannot parse, so one transform still has to run before the load.

<details>
<summary><strong>Solution</strong></summary>

#### Load first, except where the warehouse cannot read it

ELT moves the transform into the warehouse, and 2 cost changes made it the sensible default for this retailer. On the appliance, compute was a fixed rack every analyst shared, so a heavy transform slowed every dashboard. In the cloud warehouse, storage is billed apart from compute and stored bytes are cheap, so keeping a raw copy costs little. Compute is also sized per workload and billed only while it runs, so a nightly transform no longer competes with morning dashboards. What ELT cannot remove is a transform the warehouse has no way to run: it cannot parse EBCDIC fixed-width records, so decoding happens before the load.

1. **Land the sales rows untouched**

   The point-of-sale rows load as close to verbatim as the types allow. Nothing is filtered or reshaped on the way in, so when an analyst asks a question the curated tables cannot answer, the raw table already holds the answer instead of a new extract request.

2. **Decode the export, and only decode it**

   The pre-load job turns mainframe records into ordinary rows: character set, field boundaries, numeric formats. It does not join, filter or aggregate. Every business rule stays downstream, where changing it is a SQL edit rather than a change to the loader.

3. **Curate in SQL, nightly**

   A dbt transform reads the raw tables each night and rebuilds the curated tables the dashboards read. It runs on its own warehouse compute, so its size no longer threatens anyone else's queries.

```mermaid
flowchart LR
    n0[("point_of_sale_db<br/>(PostgreSQL)")]
    n1[("mainframe_inventory_export<br/>(source)")]
    n2["decode_ebcdic_records<br/>(Spark)"]
    n3[("raw_tables<br/>(warehouse)")]
    n4["curation_sql<br/>(dbt)<br/>SLA: #60; 24h"]
    n5[("curated_tables<br/>(warehouse)")]
    n6(["analyst_dashboard<br/>(consumer)"])
    n0 --> n3
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n4 --> n5
    n5 --> n6
```

*Only the mainframe export is transformed before load. Everything else lands raw and is curated by nightly SQL inside the warehouse.*

| Pitfall: A decoder that also cleans is ETL again |
| --- |
| The tempting shortcut is to let the job that decodes the export also drop discontinued items and roll stock up by store, since it touches every row anyway. Then the warehouse holds only the finished table, the raw inventory is gone, and the next new question needs a change to that job. Keep the pre-load step to what the warehouse truly cannot do. |

**Follow-up questions**

1. What changes if the mainframe team starts exporting UTF-8 CSV instead?\
   *Whether the decode step disappears and the export loads raw like the sales rows.*
2. If the sales rows carried full card numbers, what would also have to run before the load?\
   *Whether a compliance rule, not just a file format, can keep a transform ahead of the warehouse.*

</details>


<br>

### Exercise 8 of 11

**● TASK**

A bike-share operator lands Kafka dock events hourly and a membership database change stream every 15 minutes in a raw store, and an orchestrated hourly job builds curated rides once both have landed. A quality check releases each hour to the finance dashboard and the maintenance report together or not at all. The change stream once went silent at 02:10 and finance noticed at 09:00. Draw it so a silent source pages the ingestion team from the raw store.

<details>
<summary><strong>Solution</strong></summary>

#### Catch silence on the side of the boundary that can fix it

Reading a production diagram means asking 3 things of every node: how often it runs, what it does on failure, and who owns it. This pipeline shows why. The curated build fans in on both sources and the release check hands an hour to both readers or neither, so a source that goes quiet at 02:10 breaks nothing loudly. It stops hours from being released, and the first symptom is a dashboard stuck on 01:00, owned by a team that cannot fix the cause.

1. **Start at the consumers**

   Both readers sit behind the same release check, so both freeze on the 01:00 hour. Finance looks first, at 09:00, and what it sees is not an error: the last loaded hour simply stops moving. Maintenance sees the same stale hour an hour later.

2. **Walk back to the fan-in**

   At 03:00 the orchestrator finds the membership data missing, so `curated_build` waits instead of running. Waiting is correct, since an hour without memberships would misprice rides, but a wait raises nothing on its own. That is how 7 hours pass quietly.

3. **Put the alarm where the owner works**

   The fix is upstream of raw: restart the change-stream connector, which ingestion owns. So the freshness alert sits on `raw_landing` and pages ingestion within 30 minutes of silence. Analytics never crosses into a connector it does not own, and once memberships land, the held hours build and release in order.

```mermaid
flowchart LR
    n0[("dock_events<br/>(Kafka)")]
    n1[("membership_changes<br/>(CDC)")]
    n2[("raw_landing<br/>(object storage)<br/>Alert: page ingestion if a source is silent #62; 30min")]
    n3["curated_build<br/>(Airflow)<br/>SLA: #60; 1h"]
    n4[("curated_rides<br/>(warehouse)")]
    n5["hour_check<br/>(custom)"]
    n6(["finance_dashboard<br/>(consumer)"])
    n7(["maintenance_report<br/>(consumer)"])
    n0 --> n2
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n4 --> n5
    n5 --> n6
    n5 --> n7
```

*Both sources land in `raw_landing`, which pages ingestion when either goes silent; the hourly `curated_build` waits for both, and `hour_check` releases each hour to both readers or neither.*

| Pitfall: A stale-data alert on the dashboard pages the wrong team |
| --- |
| A freshness check on `finance_dashboard` does catch the incident, but it fires hours late and lands on analytics, who can only see that the hour is held. They then have to trace back across the raw boundary to learn which source stopped. Alert where the silence starts, on the layer the paged team owns. |

**Follow-up questions**

1. The dock events stream goes quiet at 14:00 instead. Which reader notices first, and does the page change?\
   *Applies the same reading to the other source: same fan-in, same alert owner.*
2. The membership stream is legitimately empty for an hour most nights. How do you keep the silence alert from paging every night?\
   *Separates a source that is quiet from one that is broken, for example by alerting on missed flushes rather than on zero rows.*

</details>


<br>

### Exercise 9 of 11

**● TASK**

A parcel logistics company's operations dashboard reads a curated shipments table in a warehouse. Land three inputs raw in object storage: depot scan events hourly, a carrier rate file daily, and vehicle telemetry every 5 minutes. An orchestrated hourly job, retrying 3 times, joins them into the curated table once the hour's scans pass a completeness check, using the latest rate file on or before its date and the newest telemetry at or before the hour. When the rate file is 6 hours late, page the rates team from the raw store.

<details>
<summary><strong>Solution</strong></summary>

#### Only one input gets to block the run

Dependency management in a multi-input join comes down to one question per input: does this input decide when the run happens, or does the run just read the newest version it can find? Here the hourly scans decide, because they are the rows the table is about, so they are the only input behind a completeness check. The daily rate file and the 5-minute telemetry are read as-of: the latest rate file on or before the run's date, the newest telemetry at or before the hour. That keeps the join's effective cadence hourly, set by the scans, instead of collapsing to daily, which is what happens when the slowest input is allowed to block.

```mermaid
flowchart LR
    n0[("depot_scan_events<br/>(source)")]
    n1[("carrier_rate_file<br/>(source)")]
    n2[("vehicle_telemetry<br/>(source)")]
    n3[("raw_landing<br/>(object storage)<br/>Alert: page rates team if rate file 6h late")]
    n4["scan_completeness_check<br/>(quality_gate)"]
    n5["hourly_shipments_join<br/>(Airflow)<br/>SLA: #60; 1h · Retries: 3"]
    n6[("curated_shipments<br/>(warehouse)")]
    n7(["operations_dashboard<br/>(consumer)"])
    n0 --> n3
    n1 --> n3
    n2 --> n3
    n3 --> n4
    n4 --> n5
    n3 --> n5
    n5 --> n6
    n6 --> n7
```

*Three inputs land in `raw_landing`; only scans pass `scan_completeness_check`, and the hourly join reads rates and telemetry as-of. The arrival alert on the raw store pages the rates team.*

1. **Land all three inputs raw before joining**

   Each input lands in object storage at its own cadence: scans hourly, the rate file daily, telemetry every 5 minutes. The raw store is the one place where arrival can be watched, so the join reads all three from it rather than from the sources.

2. **Gate only the input that defines the hour**

   A run on a partial hour of scans undercounts shipments, so the completeness check sits on the scan path only. The rate file and telemetry take a direct edge into the join: the as-of rule already says what to use when the newest copy is missing.

3. **Attach each failure to the team that can fix it**

   Retries belong to the join task, since a transient warehouse error is the join's own problem. A missing rate file is not: the join keeps succeeding on yesterday's rates, so the alert watches the file's arrival on the raw store and pages the rates team.

| Pitfall: Blocking on the daily file turns an hourly table daily |
| --- |
| Putting the rate file behind the same readiness check as the scans looks safe, but the join then inherits the slowest cadence: the first run of the day waits for the file, and on a late morning the dashboard freezes at last night's state while scans pile up in the raw store. |

| Key insight: The late morning, read straight off the diagram |
| --- |
| The file normally lands around 06:00. On the morning it is 6 hours late, every hourly run still fires once its scans pass the check, so the dashboard shows current shipments costed at yesterday's rates. At the 6-hour mark the alert on the raw store pages the rates team. The operations data team who own the join hear nothing, because their task never failed. |

**Follow-up questions**

1. Finance wants a daily cost report priced on the actual day's rates. Where does it fork, and what does it wait for?\
   *Tests giving a reader with a stricter need its own gated step instead of changing the hourly join's as-of rule.*
2. One depot's scan export stops arriving. What does the dashboard show, and who should hear about it?\
   *Tests that a gated input stalls the run, so its arrival needs its own owner and alert.*

</details>


<br>

### Exercise 10 of 11

**● TASK**

Surge pricing needs a decision within 500 milliseconds of each trip event a ride-hailing app publishes to Kafka; a city operations dashboard refreshes hourly and a driver-matching feature store every 5 minutes. Land trips and PostgreSQL driver records raw, build one curated trips table both slower readers share, and choose where each reader forks and how often curated runs. The orchestrated merge joining trips to drivers waits until each trip window has fully landed and uses the driver record in effect at trip time. Each night, reconcile surge decisions against curated trips.

<details>
<summary><strong>Solution</strong></summary>

#### Each reader forks at the latest layer it can afford

Fork placement decides this design: every reader leaves the pipeline at the latest layer that still meets its freshness. Surge pricing has 500 ms, which no scheduled run can meet, so it forks at the Kafka topic itself. The feature store and the dashboard can both wait minutes, so they fork after `curated_trips` and share one definition of a trip. The early fork has a price: surge acts on uncleaned events, and that is what the nightly reconciliation pays back.

```mermaid
flowchart LR
    subgraph L0["Real-time fork"]
        n2["surge_stream_job<br/>(Flink)"]
        n3(["surge_pricing_service<br/>(API)"])
    end
    subgraph L1["Bronze"]
        n0[("trip_events_topic<br/>(Kafka)")]
        n1[("driver_records_db<br/>(PostgreSQL)")]
        n4[("raw_landing<br/>(object storage)")]
    end
    subgraph L2["Silver"]
        n5["window_landed_check<br/>(quality_gate)"]
        n6["trip_driver_as_of_merge<br/>(Airflow)<br/>SLA: #60; 15min"]
        n7[("curated_trips<br/>(Delta Lake)")]
    end
    subgraph L3["Gold"]
        n8[("driver_feature_store<br/>(Feast)")]
        n9["city_hourly_rollup<br/>(dbt)<br/>SLA: #60; 1h"]
        n10[("gold_warehouse<br/>(warehouse)")]
        n11(["city_ops_dashboard<br/>(Metabase)"])
        n12["surge_reconciliation<br/>(Spark)<br/>SLA: #60; 24h"]
    end
    n0 --> n2
    n2 --> n3
    n2 --> n4
    n0 --> n4
    n1 --> n4
    n4 --> n5
    n5 --> n6
    n6 --> n7
    n7 --> n8
    n7 --> n9
    n9 --> n10
    n10 --> n11
    n7 --> n12
    n4 --> n12
    n12 --> n10
```

*Surge forks at the topic; the feature store and the dashboard fork after `curated_trips`, which an orchestrated as-of merge rebuilds every 5 minutes.*

1. **Let the fastest curated reader set the cadence**

   `curated_trips` runs every 5 minutes because the feature store refreshes every 5 minutes. The dashboard only needs hourly numbers, so `city_hourly_rollup` aggregates the same table once an hour. A slower reader can always aggregate a faster table downstream. A faster reader can never get fresh data out of a slower one.

2. **Pin the merge to landed windows and as-of drivers**

   A merge runs at the pace of its slowest input. `window_landed_check` holds each 5-minute window until its trips have arrived, including the phones that reconnect late. `trip_driver_as_of_merge` joins each trip to the driver snapshot in effect at trip time, so rerunning Tuesday 09:05 gives the same row even after that driver changes vehicle.

| Pitfall: Forking the feature store at ingestion splits the truth |
| --- |
| Reading features straight off the topic looks faster. But then test trips, duplicates and late events are counted one way in matching and another way on the dashboard. A 5-minute refresh fits inside a curated run, so the early fork gains nothing and costs you agreement between the 2 readers. |

| Key insight: Reconciliation is the bill for an early fork |
| --- |
| `surge_stream_job` decides before any cleaning happens, so it also writes its decisions to `raw_landing`. Each night `surge_reconciliation` compares that log with `curated_trips` and flags surge charged on trips the curated build later dropped or merged. Any reader you fork ahead of the curated layer needs a check like this. |

**Follow-up questions**

1. The feature store moves to a 1-minute refresh. Do you speed up `curated_trips` or fork matching earlier?\
   *Tests whether the learner weighs a sub-minute curated build against a second early fork that needs its own reconciliation.*
2. A driver record correction arrives 2 days late. What reruns, and how does the as-of join keep that rerun safe?\
   *Tests pinned inputs: rerunning only the affected windows and getting deterministic results.*

</details>


<br>

### Exercise 11 of 11

**● TASK**

Design a hospital's admissions pipeline in bronze, silver and gold layers. HL7 admission messages, a staffing system and a lab feed land raw in the lake, and patient identifiers in the HL7 and lab data may never land there in clear form. An orchestrated build turns the raw data into one curated admissions table every 15 minutes for a bed-capacity dashboard, and a readmission-risk model is trained from the same curated table nightly. The build runs only once every source has landed, so if the lab feed stops, its owner is paged and the dashboard freezes on its last complete refresh instead of showing nulls.

<details>
<summary><strong>Solution</strong></summary>

#### One hash before the lake, one gate before the build

Medallion layering carries this design, with a single ETL exception carved out of an otherwise ELT pipeline. Patient identifiers decide where that line falls: bronze is a raw copy kept for replay, so anything hashed after landing has already been stored in clear form. Hashing runs in flight; joining admissions to staffing, rolling up beds and building nightly features all run inside the lake on data that is already safe.

```mermaid
flowchart LR
    subgraph L0["Ingest"]
        n0[("hl7_admissions<br/>(Kafka)")]
        n1[("staffing_system<br/>(PostgreSQL)")]
        n2[("lab_feed<br/>(API)")]
        n3["hash_patient_ids<br/>(Spark)"]
    end
    subgraph L1["Bronze raw"]
        n4[("bronze_raw_landing<br/>(Delta Lake)")]
        n5["all_sources_landed_check<br/>(Great Expectations)<br/>Alert: page lab feed owner if lab data missing 30 min"]
    end
    subgraph L2["Silver curated"]
        n6["curated_build<br/>(Airflow)<br/>SLA: #60; 15min"]
        n7[("silver_curated_admissions<br/>(Delta Lake)")]
    end
    subgraph L3["Gold serving"]
        n8["bed_capacity_rollup<br/>(dbt)"]
        n9["readmission_features<br/>(dbt)<br/>SLA: #60; 24h"]
        n10(["bed_capacity_dashboard<br/>(consumer)"])
        n11(["readmission_risk_model<br/>(consumer)"])
    end
    n0 --> n3
    n2 --> n3
    n3 --> n4
    n1 --> n4
    n4 --> n5
    n5 --> n6
    n6 --> n7
    n7 --> n8
    n7 --> n9
    n8 --> n10
    n9 --> n11
```

*`hash_patient_ids` runs before the lake; `all_sources_landed_check` holds the 15-minute `curated_build` until every source lands; the readers fork after `silver_curated_admissions`.*

1. **Hash identifiers on the way in**

   Only the HL7 messages and the lab feed carry patient identifiers, so only they pass through `hash_patient_ids` before `bronze_raw_landing`. Staffing lands untouched. A stable hash keeps admissions and lab results joinable downstream without anyone seeing the original number.

2. **Build one curated table, fork the cadences after it**

   `curated_build` runs every 15 minutes because the dashboard is the fastest reader. The fork comes after `silver_curated_admissions`: `bed_capacity_rollup` serves the dashboard and `readmission_features` runs nightly for the model, both reading the same admissions, so their counts agree.

3. **Gate the build on every source landing**

   `all_sources_landed_check` confirms all 3 sources delivered for the window before the orchestrator starts `curated_build`. When the lab feed goes quiet the check fails, the build never runs, the dashboard keeps its last complete refresh, and the check's alert pages the lab feed's owner.

| Pitfall: A join over a missing feed returns nulls, not an error |
| --- |
| If the build runs on schedule regardless, the join from admissions to lab results finds nothing for the window and writes nulls. The dashboard refreshes on time, looks healthy, and shows patients with no pending labs: the silent failure the hospital asked to rule out. |

| Key insight: Page upstream, freeze downstream |
| --- |
| The page is raised at the check closest to the broken input and goes to whoever owns it. The freeze needs no extra machinery: every reader sits behind the same gate, so a held build leaves all of them on their last complete data. |

**Follow-up questions**

1. Infection control wants to know within a minute of a positive culture. Where does that path fork, and does `curated_build` change?\
   *Forking a fast path off the hashed lab data instead of speeding up the whole curated layer.*
2. The staffing system goes down instead of the lab feed. Should the bed-capacity dashboard still freeze?\
   *Whether every input must block the build, or whether the latest staffing snapshot is an acceptable stale input.*

</details>
