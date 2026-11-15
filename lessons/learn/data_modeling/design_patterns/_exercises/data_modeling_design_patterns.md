# Design Patterns - Exercises

Lesson: [data_modeling_design_patterns.md](../data_modeling_design_patterns.md)

### Exercise 1 of 12

**● TASK**

Design the three medallion layers (bronze → silver → gold) for an order pipeline, showing how data is progressively cleaned and enriched.

<details>
<summary><strong>Solution</strong></summary>

A **medallion architecture** stores the same order data three times, each copy at a different level of refinement. `bronze_orders` keeps the feed exactly as it landed. `silver_orders` holds one clean, typed row per order. `gold_daily_revenue` holds the pre-aggregated answer the business reads. Data flows one way, bronze to silver to gold, and each layer has one job.

![Schema diagram](../_images/data_modeling_design_patterns_exercise_1_schema.png)

*One dataset, three refinement levels. The layers are linked by transforms, not foreign keys, so no edges are drawn.*

1. **Land the raw feed in `bronze_orders`**

   Store `raw_payload` as it arrived, plus `ingested_at`. Do not parse, validate or drop anything here. When a downstream bug corrupts `amount`, you replay from bronze instead of re-fetching from a source that may no longer have the data. Bronze is your undo button.

2. **Flatten and clean into `silver_orders`**

   This is where `raw_payload` becomes real columns: `customer_id`, `product_id`, `amount` as a `DECIMAL`, `order_date` as a `DATE`. Cast types, deduplicate on `order_id`, drop malformed rows. Silver is the trusted grain, one record per order, that every gold table builds on.

3. **Change the grain in `gold_daily_revenue`**

   The key moves from `order_id` to `date`: thousands of silver rows collapse into one row per day carrying `total_revenue` and `order_count`. That change of grain is the pre-aggregation. Key gold by how the data is queried, not how it was ingested, and the daily revenue chart reads one row instead of scanning every order.

| Pitfall: Skipping silver duplicates the cleaning |
| --- |
| Computing `gold_daily_revenue` straight off `bronze_orders` means every aggregate re-parses `raw_payload` and re-applies the cleaning rules. 2 gold tables then disagree because they cleaned bronze slightly differently. Silver makes the cleaning happen once, so every gold table sums the same trusted `amount`. |

| Real world: Same layers, different names in dbt |
| --- |
| Databricks lakehouses use bronze, silver and gold by name; dbt projects call them staging, core and marts. The discipline is identical: a replayable landing zone, a conformed clean layer, and purpose-built aggregates on top. |

**Follow-up questions**

1. A refund arrives a week later. Which layer do you update, and does `gold_daily_revenue` need a rebuild?\
   *Gold is derived, so a change in silver must flow up into it.*
2. The business wants revenue by `product_id` as well as by day. Do you widen `gold_daily_revenue` or add a new gold table?\
   *Gold tables are cheap, single-purpose aggregates, each keyed to one question.*

</details>


<br>

### Exercise 2 of 12

**● TASK**

Create bronze, silver, and gold layers for a clickstream pipeline, demonstrating raw ingestion → cleaning → business-ready metrics.

<details>
<summary><strong>Solution</strong></summary>

#### The pattern: medallion architecture

What you just modeled is the **medallion architecture**: 3 layers that each do one job. `bronze_events` is raw ingestion, you land the payload exactly as it arrived and never lose it. `silver_events` is the cleaned, typed, one-row-per-event table you can actually query. `gold_daily_sessions` is the pre-aggregated, business-ready table a dashboard reads directly. Data flows one way, bronze to silver to gold, and each layer is rebuildable from the one before it.

![Schema diagram](../_images/data_modeling_design_patterns_exercise_2_schema.png)

*3 tables, one direction of flow. Grain gets coarser and value gets higher as you move right.*

1. **Land everything raw in bronze**

   `bronze_events` keeps `raw_json` as the untouched payload plus `received_at`, the moment YOU got it. You don't parse or reshape here. If a downstream bug corrupts silver, you replay from bronze; if the source adds a field next month, it's already captured. `event_id` is the primary key so a retried delivery doesn't land twice.

2. **Clean and flatten into silver**

   `silver_events` pulls the fields out of `raw_json` into typed columns, `user_id`, `event_type`, `page_url`, and `occurred_at`, the event's real time rather than the arrival time. The grain is still one row per event, so `event_id` stays the key. This is the layer analysts join against.

3. **Pre-aggregate the metrics into gold**

   `gold_daily_sessions` collapses events to one row per `date` with `unique_users`, `total_sessions`, and `avg_duration` already computed. The grain CHANGED, so the primary key changed too: it's `date`, not `event_id`. A dashboard reads a handful of rows instead of scanning millions of events on every page load.

| Pitfall: Common pitfall: parsing straight into one table |
| --- |
| The tempting shortcut is to skip bronze and write parsed columns directly, or to compute metrics on the fly against `silver_events` every time. Both hurt you later. Without bronze you can't replay when parsing logic changes, and a malformed `raw_json` payload becomes a dropped row instead of a stored one. Without gold, every dashboard hit re-scans the full event history. |

| Key insight: Grain drives the primary key |
| --- |
| Notice the key moves from `event_id` (bronze, silver) to `date` (gold). That's not arbitrary: the primary key is whatever makes a row unique at that layer's grain. When you pre-aggregate to one row per day, the day IS the identity. Getting this right is what keeps a re-run idempotent instead of doubling your counts. |

**Follow-up questions**

1. If you needed sessions per user per day instead of per day, what becomes the primary key of the gold table?\
   *Tests whether they see the key as a function of grain (`(date, user_id)` here).*
2. How would you handle a late-arriving event whose `occurred_at` is yesterday but `received_at` is today?\
   *Tests understanding that silver keys on event time while bronze keys on arrival, and gold may need reprocessing.*

</details>


<br>

### Exercise 3 of 12

**● TASK**

Design a Data Vault hub for customers: the core entity table that holds only business keys and metadata.

<details>
<summary><strong>Solution</strong></summary>

#### The hub: an entity's identity, and nothing else

A Data Vault **hub** is the table that declares a business entity exists. For customers, `hub_customer` answers exactly one question: which distinct customers have we ever seen? It holds the business key that identifies a customer and the metadata that says when and where we first loaded it. It holds no name, no email, no address, no status. Those descriptive attributes belong in a satellite, and the relationships this customer participates in belong in links. Keeping the hub to identity alone is the whole point of the pattern: the key stays stable while everything else about the customer changes around it.

![Schema diagram](../_images/data_modeling_design_patterns_exercise_3_schema.png)

*The four-column shape every hub takes: a hash surrogate key, the business key it hashes, and 2 load-metadata columns.*

1. **Store the business key that a person would recognize**

   `customer_bk` is the natural identifier the source system uses, the customer number or account ID a human could point at. This is what makes the row mean something. If 2 source loads carry the same `customer_bk`, they are the same customer, full stop.

2. **Make the primary key a hash of the business key**

   `customer_hk` is a surrogate key, but a deterministic one: it is a hash (typically MD5 or SHA over the business key). Because it is computed, not sequence-generated, every process that touches this customer derives the same `customer_hk` independently, with no lookup against the hub first. That is what lets satellites and links load in parallel and still join correctly.

3. **Record when and where each key arrived**

   `load_date` is when this business key first landed in the warehouse, and `record_source` names the feed it came from (`crm`, `billing`, `web_signup`). These 2 are mandatory on every Data Vault table, not optional audit sugar: they make the load auditable and let you trace any key back to its origin.

| Trick: Why hash the key instead of an auto-increment surrogate |
| --- |
| A classic surrogate key from a sequence forces a serial dependency: you must insert into the hub, read back the generated `customer_hk`, then use it in the satellite. A hash of `customer_bk` removes that round trip entirely. `customer_hk` is a pure function of the business key, so every table computes it in isolation and the joins line up. That is the difference between a sequence surrogate and a hash surrogate, and it is the reason Data Vault reaches for the hash. |

| Pitfall: The descriptive-attribute leak |
| --- |
| The most common wrong answer adds `customer_name`, `email`, or `status` to the hub. The moment you do, the hub is no longer a stable identity table: a name change or a status flip means rewriting a row that other tables key off of. Descriptive, changing attributes go in a satellite hanging off `customer_hk`; the hub keeps only the key and its load metadata. |

| ✕ `customer_bk` (business key) | ✓ `customer_hk` (hash key) |
| --- | --- |
| The human-meaningful identifier from the source, like a customer number. Stable in meaning but variable in length and format, and awkward as a join column across many wide tables. | A fixed-width hash of `customer_bk` used as the `PK` and as the foreign key in every satellite and link. Uniform, fast to join, and computable anywhere without touching the hub. |

**Follow-up questions**

1. A customer can be identified by both a CRM ID and a billing account number. How does the hub change?\
   *Tests composite business keys: the hub carries multiple `_bk` columns and `customer_hk` hashes all of them together.*
2. Where does the customer's current mailing address live, and how do you get its history?\
   *Checks that descriptive, time-varying attributes belong in a satellite keyed by `customer_hk`, not in the hub.*

</details>


<br>

### Exercise 4 of 12

**● TASK**

Create a Data Vault satellite for customer attributes: the descriptive data that changes over time, linked to the hub.

<details>
<summary><strong>Solution</strong></summary>

#### The satellite: where change lives

A Data Vault splits a customer into 2 objects that change at different rates. The **hub** holds the thing that never changes: the identity. The satellite holds everything that does: the name, the email, the city. You just built `sat_customer`, and the move that makes it a satellite is its key. It is not keyed by `customer_hk` alone, but by `customer_hk` plus `load_date` together. That composite is how one customer accumulates many rows over time instead of overwriting a single one.

![Schema diagram](../_images/data_modeling_design_patterns_exercise_4_schema.png)

*The hub owns identity once; the satellite carries the changing attributes, one row per version, pointing back at the hub.*

Read the columns as 3 jobs. `customer_hk` is the surrogate key: a hash of the business key `customer_bk`, so every satellite row points at the hub without re-storing the natural key. `load_date` stamps when this version arrived, so the pair `customer_hk` + `load_date` is unique per version. `hash_diff` is a hash of the descriptive columns, the cheap way to ask "did anything actually change?" And `record_source` records which feed the row came from, because a vault takes the same customer from many systems.

| Trick: The composite key IS the history |
| --- |
| Putting `load_date` in the primary key alongside `customer_hk` is the whole idea. It turns an UPDATE into an INSERT: a new version becomes a new row rather than clobbering the old one. This is SCD Type 2 done the vault way, no `is_current` flag and no `end_date` needed to store it. The latest version is just the row with the newest `load_date` for that `customer_hk`. |

| ✕ Attributes on the hub (wrong) | ✓ Attributes on the satellite (right) |
| --- | --- |
| Hang `name`, `email`, `city` directly on `hub_customer`. Now the hub has one row per customer and an email change is an UPDATE that destroys the old value. You have collapsed identity and description into one table and thrown history away. | Keep the hub to identity (`customer_hk`, `customer_bk`) and push every descriptive column into `sat_customer` keyed by `customer_hk` + `load_date`. Identity is asserted once; every change appends a version. The hub stays stable while the satellite grows. |

| Pitfall: Loading a new row on every batch |
| --- |
| The common mistake is inserting a satellite row every load even when nothing changed, which floods the table with duplicate versions. That is what `hash_diff` prevents: compare the incoming hash to the latest stored `hash_diff` for that `customer_hk`, and only INSERT when they differ. No change, no row. |

| Real world: Why teams split it this way |
| --- |
| In production you rarely have one satellite. A customer's slow-changing profile (`name`, `city`) and fast-changing contact fields often live in separate satellites off the same `hub_customer`, so a noisy feed never rewrites the quiet one. Because every satellite hangs off the hub by `customer_hk`, you add a new one without touching anything that already exists, which is exactly why vaults tolerate schema change so well. |

**Follow-up questions**

1. How would you query the current state of every customer from `sat_customer`?\
   *Tests the SCD Type 2 read pattern: the newest `load_date` per `customer_hk`, usually a window function like `ROW_NUMBER()` partitioned by `customer_hk`.*
2. The same customer arrives from a CRM and a billing system. What keeps their versions from colliding?\
   *Checks that they see `record_source` and the shared `customer_hk` cooperating rather than fighting.*
3. You need to model which orders a customer placed. Which vault object carries that, and why not a satellite?\
   *Extends the concept to links: a relationship between 2 hubs is a link, not descriptive data on one hub.*

</details>


<br>

### Exercise 5 of 12

**● TASK**

Design a One Big Table (OBT) for order-line analytics with one row per order line, keyed by the composite order_id plus product_id since an order holds several products. Pre-join customer name and country and product name and category as flat columns so analysts never write a JOIN, and carry quantity, unit_price, line_revenue and order_date. Model only this wide gold-layer table, not its normalized sources.

<details>
<summary><strong>Solution</strong></summary>

#### Denormalized down to one row per line

A **One Big Table** (OBT) takes denormalization as far as it goes. It is one wide gold-layer table that pre-joins every attribute an analyst filters or groups by, so a dashboard or BI extract reads it in a single scan with no JOIN. There is no thin fact pointing at `customers` and `products` dimensions. Instead, `customer_name`, `customer_country`, `product_name` and `product_category` sit on every row, and the table is rebuilt from the normalized sources on a schedule.

![Schema diagram](../_images/data_modeling_design_patterns_exercise_5_schema.png)

*One table and no edges. The customer and product attributes are flat columns, and the composite PK shows the grain: one row per order line.*

1. **Pin the grain first**

   One row is one product within one order. Everything else follows from that sentence. The measures must be line-level too, which is why `quantity`, `unit_price` and `line_revenue` belong on the row and an order total does not.

2. **Let the grain choose the key**

   `order_id` repeats across the lines of a multi-product order, so it cannot identify a row alone. The pair `order_id` plus `product_id` can. The composite key is simply the grain written in columns.

| Key insight: A many-to-many grain takes a two-column key |
| --- |
| Orders hold many products, and products appear in many orders. The order line is the bridge between them, so its natural key is one column from each side. When a grain sits on a many-to-many, expect a composite key. |

| Pitfall: A lone `order_id` key collides on line two |
| --- |
| With `order_id` as the only PK, an order's second product collides with the first or gets dropped. A related slip is copying an order-level `order_total` onto each line. Repeat it across 3 lines and `SUM(order_total)` triples the real figure. |

**Follow-up questions**

1. If a product's `product_category` changes, should past lines show the new value or keep the one in effect at `order_date`?\
   *Freezing attributes at event time or showing the latest value is a slowly changing dimension decision.*
2. Where would order-level totals go without breaking the line grain?\
   *Keep measures at the grain of their table, for example in a separate order-grained table.*

</details>


<br>

### Exercise 6 of 12

**● TASK**

Create a marketing analytics OBT with session, user, and campaign data flattened into one wide table.

<details>
<summary><strong>Solution</strong></summary>

#### One Big Table, plainly

A One Big Table is **denormalization taken all the way**: the session, the user who owns it and the campaign that drove it are pre-joined so every attribute a marketing analyst needs sits on one row. The join happens once, at build time. After that, 'which channel converts best' is a single `GROUP BY channel` scan over `sessions_obt`, with no three-way join.

![Schema diagram](../_images/data_modeling_design_patterns_exercise_6_schema.png)

*One row per session. User and campaign attributes are copied in, not referenced.*

The decision that holds it together is the **grain**: one row per session. `pages_viewed` and `converted` describe the session; `user_segment` and `country` are folded in from the user; `campaign_name` and `channel` from the campaign. `session_id` is the PK because it identifies the grain, and `user_id` stays as a plain column so sessions can still roll up per user.

| ✕ Normalized star schema | ✓ One Big Table |
| --- | --- |
| `fact_sessions` joined to `dim_users` and `dim_campaigns` at query time. No duplicated attributes, cheap updates, but every query pays for the joins and must know the keys. | `sessions_obt` with `user_segment`, `channel` and the rest copied onto each row. More storage, and a rename means a rebuild, but reads are one flat scan. |

| Pitfall: Mixing grains onto one row |
| --- |
| Adding `campaign_total_spend` or `user_lifetime_revenue` puts a coarser fact on the session grain. Summing `revenue_attributed` stays correct; summing `campaign_total_spend` counts it once per session. Keep session facts on the row and leave rollups to the query. |

| Real world: Wide is cheap in a columnar warehouse |
| --- |
| BigQuery, Snowflake and Redshift store by column, so a query touching only `channel` and `revenue_attributed` never reads the rest. That is why BI tools point straight at tables like `sessions_obt`. |

**Follow-up questions**

1. A session touches 2 campaigns before converting. Does one row per session still hold?\
   *A many-per-session attribute breaks the grain and needs a bridge table or an array column.*
2. Marketing renames the segment 'smb' to 'small business'. What happens to `sessions_obt`?\
   *Denormalized attributes are copies, so a dimension change means a rebuild or backfill.*

</details>


<br>

### Exercise 7 of 12

**● TASK**

Dashboards, notebooks and a finance API each compute monthly recurring revenue differently from the same payments and customers tables. Model a semantic layer over those tables: define each metric once with its aggregation expression, its filter (such as excluding refunded payments) and the physical table it reads. Define the dimensions consumers may group by, each mapped to a physical table and column, and record which dimensions each metric allows.

<details>
<summary><strong>Solution</strong></summary>

#### Metrics live above the tables

A **semantic layer** earns its name by holding definitions, not data. `payments` and `customers` stay exactly as the warehouse stores them. Above them sit 3 small tables that say what monthly recurring revenue means, which columns a consumer may group it by, and which pairings are allowed. Every dashboard, notebook and API call reads the definition from here instead of rewriting `SUM(amount)` its own way, so the numbers finally agree.

![Schema diagram](../_images/data_modeling_design_patterns_exercise_7_schema.png)

*`metrics`, `dimensions` and `metric_dimensions` define MRR once over the physical `payments` and `customers` tables. Every consumer reads these rows instead of writing its own SQL.*

1. **Give each metric one row with its full recipe**

   `metrics` holds the `aggregation_expression` (for MRR, `SUM(amount)`), the `filter_condition` (`status <> 'refunded'`) and the `source_table` it reads. The filter is part of the definition. Leave it out, and marketing's revenue with refunds and finance's revenue without them both look 'correct'.

2. **Register dimensions as pointers to physical columns**

   `dimensions` maps a business name like 'customer country' to a `source_table` and `source_column` (`customers`, `country`). Consumers group by the name. The layer resolves the column and the path to it through `payments.customer_id`.

3. **Allow each metric only its valid dimensions**

   `metric_dimensions` holds one row per allowed pairing, keyed by both ids. MRR by 'plan tier' is listed and MRR by 'payment id' is not, so no tool can serve a meaningless slice.

| Pitfall: A view per team is not a semantic layer |
| --- |
| The usual miss is drawing only the physical tables, or one `revenue_by_country` view per dashboard. Each view hard-codes its own filter, the views drift apart, and you are back to 3 revenue numbers. The definition has to be data that every consumer reads. |

| Real world: dbt metrics and LookML store this same shape |
| --- |
| MetricFlow's YAML and a LookML view both declare a measure with its expression and filter, the dimensions it can reach, and the table underneath. The tables you drew are that YAML written as rows. |

**Follow-up questions**

1. How would you add average revenue per customer, defined from 2 other metrics?\
   *Derived metrics: a metric whose expression references other metrics rather than a column.*
2. What changes when finance needs MRR converted at one agreed exchange rate?\
   *Where a shared conversion rule lives so every consumer applies it the same way.*

</details>


<br>

### Exercise 8 of 12

**● TASK**

Build a semantic layer metrics catalog: one table where each row documents a defined business metric. Give each metric its own primary key, plus a name, a description, its SQL formula, the base table it reads from, a category, and an owner.

<details>
<summary><strong>Solution</strong></summary>

#### A table of meanings, not measurements

A **semantic layer** at its smallest is one table whose rows are definitions of business metrics. They are not values of those metrics. A fact table records that revenue was 4,210 on Tuesday. A metrics catalog records what 'Net Revenue' means: this `sql_formula`, read from this `base_table`, owned by this person. Here the metric itself is the entity, and every column is one attribute of it.

![Schema diagram](../_images/data_modeling_design_patterns_exercise_8_schema.png)

*One entity, 7 attributes: each row in `semantic_metrics` documents a metric and stores no measured value.*

1. **Name the entity, then list its attributes**

   One row per defined metric. Everything a consumer needs to trust and reproduce it becomes a column. Humans read `metric_name` and `description`, the query generator reads `sql_formula` and `base_table`, and governance uses `category` and `owner`. All of them describe the one entity, so the design stays a single table.

2. **Key it with a surrogate `metric_id`**

   `metric_id` is a system-generated surrogate key. It carries no business meaning and exists only so the row has a stable identity. Dashboards, tests and lineage point at `metric_id`, which leaves a metric free to be renamed without breaking any of them.

| Pitfall: A metric's name is a label, not its identity |
| --- |
| Keying on `metric_name` looks fine because names look unique. Then 'Revenue' becomes 'Gross Revenue' and every reference breaks, or 2 teams define 'Active Users' differently. If you need names to be unique, add a `UNIQUE` constraint on `metric_name` as its own rule, separate from the key. |

| Real world: BI tools generate SQL from these rows |
| --- |
| dbt's semantic layer, LookML and Cube all sit on this shape. When a query runs, the tool reads `sql_formula` and `base_table` to write the SQL, so 'Net Revenue' comes out the same on every dashboard. Analysts search and browse metrics by `owner` and `category`. |

**Follow-up questions**

1. How would you record who changed a metric's `sql_formula`, and when?\
   *Points toward a history table keyed on `metric_id` instead of overwriting the definition in place.*
2. What if a metric may only be grouped by certain dimensions?\
   *Grows the single entity into a small cluster: a child table of allowed dimensions with an FK to `metric_id`.*

</details>


<br>

### Exercise 9 of 12

**● TASK**

Design a pipeline runs model in bronze, silver and gold layers. The orchestrator emits raw JSON run events (queued, started, succeeded, failed), sometimes twice, and every event must be kept exactly as received. Analysts need one clean row per pipeline run with its status, start and end times, and the logical date it ran for. On-call engineers need a curated daily summary per pipeline of runs, failures and average duration.

<details>
<summary><strong>Solution</strong></summary>

#### 3 layers, 3 grains

Medallion layering is what turns a stream of orchestrator chatter into a runs table people can trust. Each layer gets its own grain. Bronze holds one row per event, exactly as the scheduler sent it. Silver holds one row per run. Gold holds one row per pipeline per day. The trap is a single runs table fed straight from the event stream: a duplicated 'failed' event becomes 2 failures, a retry overwrites the first attempt, and nothing is left to replay when the parsing logic changes.

![Schema diagram](../_images/data_modeling_design_patterns_exercise_9_schema.png)

*Bronze keeps the raw `payload`, silver holds one row per run in `silver_pipeline_runs`, and gold `gold_pipeline_daily_health` is keyed by `pipeline_id` and `summary_date`.*

1. **Land events in bronze untouched**

   `bronze_run_events` stores the `payload` as JSON plus `received_at`, and nothing else: no status column, no dedup, no parsing. If the event format changes, or your silver logic has a bug, you rebuild silver from bronze. You never have to ask the orchestrator to resend history.

2. **Collapse events to one row per run in silver**

   `silver_pipeline_runs` dedups the events and folds the queued, started and finished events into one row: `status`, `started_at`, `ended_at` and the `logical_date` the run was for. Status is normalized here, so 'SUCCESS' and 'succeeded' land as one value. A run still in flight has a null `ended_at`. Pipelines get their own small silver table, so a renamed DAG keeps its history.

3. **Build the daily summary from silver only**

   `gold_pipeline_daily_health` holds `run_count`, `failure_count` and `avg_duration_seconds`, all computed from clean silver runs. In the DAG that loads these tables, the gold task waits on the silver task, which waits on the bronze landing. **Dependencies flow downward**, never from bronze straight to gold.

| Pitfall: Gold built from bronze counts every duplicate |
| --- |
| Aggregating `gold_pipeline_daily_health` directly from raw events skips the dedup step. An event sent twice doubles the failure count, and a 'started' event with no matching finish has no duration at all. Every rule silver applies would then have to be copied into gold, and the 2 copies drift apart. |

**Follow-up questions**

1. How would you add per-task timing inside each run, and which layer would that table live in?\
   *Pushes the silver grain one level finer, with a task-run table that references `run_id`.*
2. A parsing bug mislabeled a week of failed runs as 'succeeded'. Which layers do you rebuild, and in what order?\
   *Tests that bronze is the replay source and that gold reloads only after silver is fixed.*

</details>


<br>

### Exercise 10 of 12

**● TASK**

Create a DAG dependency graph schema for a ride-hailing pipeline that lands raw trip events and driver records, cleans each source separately, then builds a curated daily driver earnings table. Model the pipelines, their tasks, the dataset each task writes, and the medallion layer each dataset lives in (bronze, silver or gold). Give each layer an order so dependencies can be checked to flow downward, and record each task's upstream tasks: a task can have several.

<details>
<summary><strong>Solution</strong></summary>

#### Layers give the DAG its direction

Medallion layering is what turns a pile of task edges into a DAG you can trust. Every dataset a task writes lives in exactly one layer: 'bronze' for raw landings, 'silver' for cleaned per-source tables, 'gold' for curated business tables. Each layer also carries a `layer_rank`. A common shortcut is to tag tasks with a free-text layer and stop there. **Nothing then says gold sits below silver**, so an edge from a gold task back into bronze looks as valid as any other.

![Schema diagram](../_images/data_modeling_design_patterns_exercise_10_schema.png)

*Each dataset sits in one ranked layer; `task_dependencies` holds one edge per row between 2 `tasks`.*

1. **Place each dataset in its layer**

   `trips_raw` and `drivers_raw` land in bronze untouched. `trips_clean` and `drivers_clean` are the silver tables, one per source, deduplicated and typed. `daily_driver_earnings` is the single gold table. Each is a row in `datasets` pointing at its `layer_id`, so the layer is decided once, by the data, not retyped on every task.

2. **Point tasks at what they write**

   A task is the unit the scheduler runs, and `output_dataset_id` tells you which layer it works in. The 2 bronze ingestion tasks have no upstreams, so they run side by side. A failed trips landing never blocks the driver side.

3. **Store edges as rows**

   `task_dependencies` holds one row per edge, keyed by `(upstream_task_id, downstream_task_id)`. The gold earnings task fans in from both silver cleaning tasks. A single `parent_task_id` column on `tasks` could only hold one of them.

| Pitfall: A gold task reading bronze skips the cleaning |
| --- |
| Wiring `daily_driver_earnings` straight to `trips_raw` makes the graph look shorter, but gold then computes earnings from duplicated, untyped events. With `layer_rank` on each layer, you can catch it with a check that every edge moves down at most one rank and never up. |

**Follow-up questions**

1. Where would a data quality check between silver and gold live in this schema?\
   *Model it as its own task: the silver tasks feed it and the gold tasks depend on it, so a failed check stops gold.*
2. How would you stop a cycle, such as `A` depending on `B` and `B` depending on `A`, from being recorded?\
   *Keys cannot forbid cycles; a recursive check over `task_dependencies` before each insert can.*

</details>


<br>

### Exercise 11 of 12

**● TASK**

Design a complete medallion + dimensional architecture for e-commerce: raw ingestion layers feeding into a star schema.

<details>
<summary><strong>Solution</strong></summary>

A medallion architecture and a star schema answer different questions, and this design needs both. The medallion is the horizontal flow: raw data lands in bronze, gets cleaned into silver, and is rolled up into gold. The star schema is the shape of the clean middle: one fact table pointing at the dimension tables around it. The key is that **`silver_orders` does double duty**. It is the silver layer of the medallion and the fact table of the star.

![Schema diagram](../_images/data_modeling_design_patterns_exercise_11_schema.png)

*Bronze feeds silver; `silver_orders` is the fact pointing at `dim_customer` and `dim_product`; gold is the rollup.*

1. **Land the raw layer untouched**

   `bronze_orders` keeps data exactly as it arrived: a `raw_payload`, a `raw_order_id` and an `ingested_at` timestamp. It has no foreign keys and no parsed columns. Bronze is replayable: when cleaning logic changes, you rebuild silver from bronze instead of re-fetching from the source.

2. **Split the clean data into facts and dimensions**

   The measures, one row per order with `quantity` and `revenue`, go in `silver_orders`. Descriptive context moves into `dim_customer` and `dim_product`. The fact carries only `customer_id` and `product_id`, so a country name lives in one place instead of on every order row.

3. **Pre-aggregate the gold layer**

   `gold_revenue_by_category` is derived from the star, not part of it. Its grain is one row per `category` per `month`, so its key is the composite `(category, month)`, with no foreign keys back. A dashboard reads this small table instead of rescanning every order.

| Pitfall: Foreign keys point from fact to dimension |
| --- |
| The many side references the one side. `dim_customer` knows nothing about orders; it is a clean lookup of customer attributes. If you catch yourself adding an `order_id` to `dim_customer`, the star is inverted. |

| Real world: Layer prefixes tell analysts what is safe |
| --- |
| A dbt project or a lakehouse uses this exact layout: raw loads in bronze, conformed models in silver, marts in gold. The `bronze_`, `silver_` and `gold_` prefixes (or separate schemas) signal which tables analysts may query directly. |

**Follow-up questions**

1. If a customer moves country, how do old orders keep reporting under the old `country`?\
   *Leads to a type 2 slowly changing dimension with effective-date rows in `dim_customer`.*
2. Revenue by country is now needed too: add a column to `gold_revenue_by_category` or build a second gold table?\
   *Gold grain is fixed, so a new grain means a new rollup.*

</details>


<br>

### Exercise 12 of 12

**● TASK**

Build a Data Vault schema for customer orders: hubs for core entities, links for relationships, and satellites for descriptive attributes. Give each hub a hash surrogate key over its business key, model the customer-to-order relationship as a link with a composite key of both hub hash keys, and track descriptive history in a satellite keyed by hub hash key plus load_date.

<details>
<summary><strong>Solution</strong></summary>

#### Data Vault: 3 table types, one job each

Data Vault is a modeling pattern that splits a subject area into 3 kinds of table, each with a single responsibility. A **hub** holds the identity of a business entity and nothing else. A link records that 2 entities are related. A satellite holds the descriptive attributes that change over time. You were asked to model customers and orders, so the answer is `hub_customer`, `hub_order`, one `link_customer_order`, and a `sat_customer` for the changing details. Keeping identity, relationships, and description in separate tables is the whole point: each can be loaded independently and reloaded without touching the others.

![Schema diagram](../_images/data_modeling_design_patterns_exercise_12_schema.png)

*2 hubs anchor identity; the link joins them; the satellite hangs history off the customer hub. Hash keys are fixed-width `CHAR` digests.*

1. **Give each hub a hash surrogate key over its business key**

   `hub_customer` carries the natural business key `customer_bk` (the value that identifies the customer in the source), plus `load_date` and `record_source` for lineage. The primary key is not the business key itself but `customer_hk`, a hash computed over `customer_bk`. Hashing gives every hub a fixed-width, single-column key you can compute in parallel across loads without a lookup or a sequence, and `hub_order` follows the identical shape with `order_hk` over `order_bk`.

2. **Model the relationship as a link with a composite key of both hash keys**

   `link_customer_order` does not describe anything; it only asserts that a customer placed an order. Its key is the pair (`customer_hk`, `order_hk`), each a foreign key back to its hub. Because a link can hold any combination of hub keys, it expresses many-to-many for free: one customer to many orders, and the same structure would carry an order shared across customers without a schema change.

3. **Track descriptive history in a satellite keyed by hub key plus `load_date`**

   `sat_customer` hangs off `hub_customer` via `customer_hk` and adds the mutable fields `name` and `email`. Its primary key is (`customer_hk`, `load_date`): the same customer gets a new row each time an attribute changes, so the table is an append-only history rather than an overwrite. `hash_diff` is a hash of the descriptive columns; comparing it against the latest row tells the loader whether anything actually changed, so identical reloads insert nothing.

| Pitfall: Don't put attributes on the hub |
| --- |
| The most common mistake is folding `name` and `email` straight into `hub_customer` and dropping the satellite. That collapses the pattern back into a plain dimension: the hub gains a `load_date` in its key or, worse, you overwrite on change and lose history. Identity belongs on the hub; anything that changes belongs on a satellite keyed by `customer_hk` plus `load_date`. |

| Key insight: Why `hash_diff` instead of comparing every column |
| --- |
| A satellite load has to answer "did this record change?" on every run. Comparing `name` and `email` individually works for 2 columns but not for twenty. `hash_diff` reduces the whole descriptive payload to one value, so the change check is a single equality test against the current row regardless of how wide the satellite gets. |

**Follow-up questions**

1. Where would you store an attribute of the relationship itself, like the order's quantity or price at the time it was placed?\
   *Tests that links carry no descriptive data; the answer is a link satellite keyed on the link's hash key plus `load_date`.*
2. If orders also belonged to a store, would you add `store_hk` to `link_customer_order` or create a new link?\
   *Tests understanding that a link's grain is fixed by its key set; a new relationship grain is usually a new link.*

</details>
