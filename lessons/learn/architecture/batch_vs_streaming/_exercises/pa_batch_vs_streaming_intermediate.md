# Batch vs Streaming: Intermediate - Exercises

Lesson: [pa_batch_vs_streaming_intermediate.md](../pa_batch_vs_streaming_intermediate.md)

### Exercise 1 of 11

**● TASK**

An orders pipeline moves 1 billion events a day from PostgreSQL into a warehouse mart, and an executive dashboard reads that mart once, at 7am each morning. Decide whether latency or throughput is the constraint here, and pick batch or streaming for the transform to match. Set the mart's freshness SLA to the loosest value the dashboard still accepts.

**Starting canvas** (already placed for you):

- Orders database (1 billion events/day) (source, PostgreSQL)
- Transform job (transform)
- Orders warehouse mart (storage, warehouse)
- Executive dashboard (7am) (consumer, dashboard)

<details>
<summary><strong>Solution</strong></summary>

#### Freshness and volume are 2 different axes

Splitting the vague word "fast" into 2 measurements is what decides this design. **Latency** is how soon a result must be ready after an event lands; throughput is how many events per unit of time the pipeline has to move. They are separate dials, and a pipeline is usually constrained by one of them. Here the dashboard reads once a day at 7am, so the latency ask is loose (anything under a day works), while a billion events a day is genuinely heavy volume. Loose latency and heavy throughput make throughput the constraint, and batch is built for exactly that.

So the transform runs as a scheduled batch job, and the mart carries a `slaFreshness` of '< 24h'. That chip writes the freshness contract on the canvas instead of leaving it implied. It records the loosest latency the reader accepts, which is what licenses the batch rhythm.

```mermaid
flowchart LR
    n0[("Orders database (1 billion events/day)<br/>(PostgreSQL)")]
    n1["Batch transform job<br/>(Spark)"]
    n2[("Orders warehouse mart<br/>(warehouse)<br/>SLA: #60; 24h")]
    n3(["Executive dashboard (7am)<br/>(dashboard)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
```

*One scheduled batch run fills the mart before the 7am read; the '< 24h' freshness chip is the contract the rhythm is sized against.*

| Pitfall: "A billion events" is not a reason to stream |
| --- |
| The common miss is to see the volume number, feel the pressure, and reach for a streaming engine. Streaming buys low **latency**, not more throughput, and low latency is exactly what this pipeline does not need. Nobody reads the mart between the nightly run and 7am, so a result that lands at 2am is worth the same as one that lands a moment after each order. |

| ✕ Batch (the pick) | ✓ Streaming (rejected) |
| --- | --- |
| One scheduled run reads the day's orders, builds the mart in large passes, and finishes well before 7am. The volume is absorbed by spreading per-event overhead across the whole batch, and the '< 24h' contract is met with room to spare. | A standing job keeps compute running all day to hold end-to-end latency in seconds. It meets a freshness target nobody asked for, and the dashboard shows the same numbers at 7am either way. |

| Performance: Buy only the latency the reader needs |
| --- |
| Higher throughput on the same hardware comes from batching work, and batching raises latency. When the only reader looks once a day, that extra latency costs nothing: '< 24h' is the loosest SLA that still satisfies it, so the pipeline can batch as aggressively as the volume demands. Find the real latency requirement first, then pick the rhythm. |

**Follow-up questions**

1. If the executive team also wants a noon refresh, does that flip you to streaming?\
   *Checks whether a second scheduled batch run still meets an hours-scale latency ask.*
2. What reader would make latency, not throughput, the constraint on this pipeline?\
   *Looks for a consumer that acts on each order within seconds or a few minutes of it landing.*

</details>


<br>

### Exercise 2 of 11

**● TASK**

A support-ops dashboard reads Kafka events through an hourly Spark batch, but agents need events visible within 15 minutes of arrival. Replace the batch transform with Flink on a 1 to 5 minute micro-batch trigger and tag the warehouse mart slaFreshness < 15min. Do not push to real-time or under 1 minute: sub-second streaming costs 5 to 50 times more for freshness the consumer does not need.

**Starting canvas** (already placed for you):

- Kafka customer-support events (source, Kafka)
- Hourly Spark batch job (transform, Spark)
- Snowflake support_queue mart (storage, Snowflake)
- CS ops dashboard (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

#### Freshness is a dial, not a switch

Between an hourly batch that lands data too late and a sub-second stream that costs 5 to 50 times more sits a middle gear: **micro-batch**. A streaming engine like `Flink` fires on a short trigger interval instead of per event, so you size the rhythm to what the consumer reads rather than to the fastest engine you can name. The agents want events inside 15 minutes; a 1 to 5 minute trigger clears that cheaply.

```mermaid
flowchart LR
    n0[("Kafka customer-support events<br/>(Kafka)")]
    n1["Flink micro-batch transform<br/>(Flink)"]
    n2[("support_queue warehouse mart<br/>(warehouse)<br/>SLA: #60; 15min")]
    n3(["CS ops dashboard<br/>(dashboard)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
```

*The hourly Spark batch becomes a `Flink` transform on a 1-5 minute trigger; the warehouse mart is re-tagged to the under-15-minute tier so downstream expectations match the new rhythm.*

| Trick: The trigger interval is the cost knob |
| --- |
| A streaming engine on a 1-5 minute trigger ingests continuously but commits output on a schedule, batching many events into each warehouse write. That one parameter turns a five-to-fifty-times pricier engine into one costing barely more than the batch it replaces, while landing data far fresher. |

| ✕ True streaming (rejected) | ✓ Micro-batch (chosen) |
| --- | --- |
| Sub-second, per-event processing. Freshness of seconds is real, but the dashboard refreshes every few minutes, so it is latency nobody reads, and tiny continuous commits hammer the warehouse. | A `Flink` job on a 1-5 minute trigger lands well under the 15-minute target and amortizes each write over many events. The freshness the dashboard needs, none of the cost it does not. |

| Pitfall: Over-fresh is as wrong as too-slow |
| --- |
| Reading 'fresher' as 'real-time' and reaching for a sub-second engine over-provisions freshness the consumer never reads. Tag the mart at the under-15-minute tier, not a real-time tier the contract cannot cheaply honor. |

**Follow-up questions**

1. If a second team wants the same `support_queue` data within seconds for an auto-escalation bot, do you tighten this trigger or add a separate path?\
   *Tests whether they match freshness tiers per consumer instead of over-serving everyone from one expensive job.*

</details>


<br>

### Exercise 3 of 11

**● TASK**

A retailer's revenue pipeline runs Flink streaming at $4,000/month to feed a CFO dashboard read once each morning at 7am, so its latency is worth nothing against a 5-50x streaming premium. Downgrade it: replace the Flink transform with a nightly batch engine (Spark, PySpark, or dbt), remove the RocksDB state store, tag the warehouse mart slaFreshness < 24h, and leave no node with a real-time or < 1min slaFreshness.

**Starting canvas** (already placed for you):

- Postgres orders (source, Postgres)
- Flink streaming job ($4K/month) (transform, Flink)
- Local state store (RocksDB) (storage, RocksDB)
- Snowflake daily_revenue (storage, Snowflake)
- CFO daily revenue dashboard (reads 7am) (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

#### Pay only for the freshness someone reads

Choosing between batch and streaming is a **cost decision** before it is an architecture one. Start by asking what a fresher number is worth to the person reading it. The CFO opens this dashboard once, at 7am. To her, a figure computed at 4am and one computed a millisecond ago look exactly the same. The latency is worth zero dollars, so the Flink job is a $4,000 monthly bill that buys nothing.

| Pitfall: Real-time is not a free default |
| --- |
| It is tempting to keep the 'real-time' tags because fresher feels safer. Streaming keeps a cluster running around the clock and holds `RocksDB` state between events, even at 3am when nobody reads the output. That typically costs 5 to 50 times the equivalent batch run. A batch job wakes up, makes one pass and exits. |

1. **Swap the engine and drop the state store**

   Replace the `Flink` node with a batch transform such as `Spark`, `dbt` or `PySpark`. Then delete the `RocksDB` node. Local state exists to carry aggregates across a continuous stream. A job that recomputes the whole day in one pass has nothing to carry, so keeping the store would leave dead infrastructure.

2. **Retag `slaFreshness` to the real need**

   Set `slaFreshness` to '< 24h' on the revenue mart and remove every 'real-time' tag. An SLA is a statement about value, and the honest statement here is that a number less than a day old is fine. The CFO's need never changed. You only stopped over-provisioning for it.

```mermaid
flowchart LR
    n0[("Postgres orders<br/>(PostgreSQL)")]
    n1["Nightly Spark batch<br/>(Spark)"]
    n2[("Daily revenue mart<br/>(warehouse)<br/>SLA: #60; 24h · SLA: #60; 24h")]
    n3(["CFO daily revenue dashboard (reads 7am)<br/>(dashboard)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
```

*The downgrade: a nightly Spark run replaces Flink, the RocksDB store is gone, and the warehouse mart carries `slaFreshness` '< 24h' to match the once-a-day read.*

**Follow-up questions**

1. The CFO now wants the number by 6am instead of 7am. What changes?\
   *A fixed daily read still calls for batch. Only the schedule moves earlier.*
2. A fraud team wants alerts on suspicious orders within seconds. Should they read from the revenue mart?\
   *When latency has real dollar value, streaming is justified, but it belongs in a separate pipeline.*

</details>


<br>

### Exercise 4 of 11

**● TASK**

The transform on the canvas keeps rolling 5-minute click counts per page from a Kafka topic, so it is stateful: each window's count depends on every click already seen in that window. Add a checkpointed state store node wired to the streaming transform, backed by RocksDB, HDFS or S3, so a worker restart does not lose the current window's partial counts. Leave the rest of the pipeline as it is.

**Starting canvas** (already placed for you):

- Kafka raw clicks (source, Kafka)
- Spark rolling 5-min counts per page (transform, Spark Structured Streaming)
- Page clicks 5-min mart (storage, warehouse)
- Click analytics dashboard (consumer, dashboard)

<details>
<summary><strong>Solution</strong></summary>

#### The windowed count is state, and state needs a home

A windowed `GROUP BY` is a **stateful** transform. To emit the count for a page's current 5-minute window, the engine must remember every click already counted for that window and add the next one to the running total. That per-(`page`, window) tally cannot be derived from the click in front of the engine. It comes only from the whole stream seen so far. Once a transform's output for one row depends on other rows, you've crossed from stateless to stateful, and the engine needs a durable place to keep that memory across micro-batches and restarts.

| ✕ Stateless | ✓ Stateful |
| --- | --- |
| A `map`, `filter`, or projection handles each event alone: parse the JSON, drop bot traffic, rename a field. A restart loses only the read position, because nothing was accumulating. No state store needed. | A windowed aggregation, streaming join, or dedup keeps a running structure keyed by something (`page`, window). The `count(*)` for a window is a fold over prior events, so that fold has to survive a crash. Your transform is in this class. |

```mermaid
flowchart LR
    n0[("Kafka raw clicks<br/>(Kafka)")]
    n1["Spark rolling 5-min counts per page<br/>(Spark Structured Streaming)"]
    n2[("Window state store<br/>(RocksDB)")]
    n3[("Page clicks 5-min mart<br/>(warehouse)")]
    n4(["Click analytics dashboard<br/>(dashboard)"])
    n0 --> n1
    n1 --> n2
    n1 --> n3
    n3 --> n4
```

*The only addition is a RocksDB state store wired to the streaming transform. The transform checkpoints window state there each micro-batch and reads it back on recovery. The mart and the dashboard are unchanged.*

| Pitfall: It runs fine until the first restart |
| --- |
| In a dev run the engine holds window state in memory and the counts look right, so the gap stays hidden. The store only proves its worth on failure. Without a checkpointed location, a restart discards every in-flight window: partially counted 5-minute buckets vanish or get recounted from a replayed offset. The dashboard's numbers then go wrong exactly when nobody is watching. |

| Key insight: Watermark bounds the state, the checkpoint persists it |
| --- |
| These are two halves of one job. The watermark tells the engine when a window is old enough that no more clicks will arrive, so its entry can be evicted and the store stops growing. The checkpointed state store is what lets that state survive a crash. You need both, which is why the store hangs off the transform rather than sitting out by the warehouse. |

**Follow-up questions**

1. What forces state to grow without bound, and which knob stops it?\
   *Connects late-arriving events and a missing watermark to unbounded state.*
2. If you added a streaming join of clicks to a `sessions` stream, would that need its own state store?\
   *Checks that the stateful classification extends beyond windowed aggregation to joins.*

</details>


<br>

### Exercise 5 of 11

**● TASK**

The nightly Spark batch on the canvas now takes 11 hours for 18 million orders a day, missing the executive dashboard's 6am refresh, while marketing needs numbers within 15 minutes. From the one Postgres source, keep the executive path on batch landing its warehouse table in under an hour, and give marketing a micro-batch path into a serving store fresh within 15 minutes. Skip real-time streaming for the whole join: it costs about 20x for freshness no one asked for.

**Starting canvas** (already placed for you):

- Postgres orders (18M/day) (source, Postgres)
- Nightly Spark batch (11 hours, missing 6am SLA) (transform, Spark)
- Snowflake fact_daily_orders (storage, Snowflake)
- Executive dashboard (tier 4, daily) (consumer, Looker)
- Marketing live dashboard (tier 2, < 15min) (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

When a batch job outgrows its window, the right move is rarely a switch to streaming. It is matching each consumer to the cheapest cadence that meets its freshness tier. The executive dashboard reads daily, so batch is still the right engine: only the 11-hour full rebuild is broken. Marketing needs '< 15min', which no nightly clock can reach, so it gets its own **micro-batch** path instead of dragging the executive path into streaming.

```mermaid
flowchart LR
    n0[("Postgres orders<br/>(PostgreSQL)")]
    n1["Hourly incremental batch<br/>(Spark)"]
    n2[("fact_daily_orders<br/>(warehouse)<br/>SLA: #60; 1h")]
    n3(["Executive dashboard<br/>(dashboard)"])
    n4["Micro-batch job<br/>(Spark)"]
    n5[("Marketing serving store<br/>(serving store)<br/>SLA: #60; 15min")]
    n6(["Marketing live dashboard<br/>(dashboard)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n0 --> n4
    n4 --> n5
    n5 --> n6
```

*One `Postgres` source, two cadences: an hourly incremental batch into a warehouse tagged '< 1h', and a micro-batch into a serving store tagged '< 15min'.*

1. **Make the executive path incremental, not faster**

   The 11-hour run rebuilds every order each night. Read only the orders past the last high-water mark, join the product dimension, and `MERGE` into `fact_daily_orders`. Run hourly, each slice is small, so the table lands inside '< 1h' and the 6am slip disappears without leaving batch. The keyed merge is idempotent, so a retried run writes the same rows instead of doubling them.

2. **Give marketing its own micro-batch path**

   A Spark job on a tight trigger picks up new orders every minute or two and writes a small serving store tagged '< 15min'. It carries only the recent slice marketing watches, not the full fact table, so its compute is a fraction of the nightly rebuild. Both paths read the one `Postgres` source but never share a clock.

| Pitfall: Don't buy freshness no one asked for |
| --- |
| The overreach is to rebuild the whole 18M-row join as true real-time streaming and point both dashboards at it. It works, but the executive path gains nothing because it reads daily, while you pay roughly 20x for an always-on cluster and standing join state. |

| ✕ Micro-batch (chosen) | ✓ True streaming (rejected) |
| --- | --- |
| A Spark job on a one- or two-minute trigger clears '< 15min' comfortably, and its cost scales with the recent slice it reads. | Per-event processing buys sub-second latency and holds join state for the full order history. No consumer asked for sub-second, so that always-on cluster is the ~20x line. |

**Follow-up questions**

1. What if a late order arrives with a `created_at` from yesterday after the hourly batch already ran?\
   *Why the idempotent `MERGE` lets you reprocess a past window safely.*
2. How would you catch the marketing path slipping past '< 15min' while the job still reports success?\
   *Freshness monitoring: alert on data lag, not just job status.*

</details>


<br>

### Exercise 6 of 11

**● TASK**

Fan 50 billion log events a day from one Kafka topic out to three consumers, picking the rhythm per branch instead of streaming all three. Land Kafka once into a shared bronze raw zone in object storage and have every branch read from bronze, never from Kafka directly. Feed the 30-second incident pager from a streaming engine tagged real-time or < 1min, the rolling five-minute ops dashboard from a micro-batch engine on a one-minute trigger tagged < 15min, and the daily billing capacity report from nightly batch tagged < 24h.

**Starting canvas** (already placed for you):

- Kafka log events (50B/day) (source, Kafka)
- Incident pager (sub-30-sec) (consumer, PagerDuty)
- Live ops dashboard (rolling 5-min) (consumer, Looker)
- Billing capacity report (daily) (consumer, Tableau)

<details>
<summary><strong>Solution</strong></summary>

#### Match the clock to the branch

**Freshness tiering** means letting each consumer's own deadline choose its processing rhythm, instead of picking one rhythm for the whole fan-out. Three consumers hang off the same 50-billion-event firehose, but their deadlines run from 30 seconds for the pager, to 5 minutes for the dashboard, to a full day for billing. So you run three engines, each just fast enough for the branch it feeds: a streaming engine for the pager, a one-minute micro-batch trigger for the dashboard, and a nightly batch job for billing.

The move that keeps this clean is landing Kafka into a shared bronze raw zone once and reading every branch from bronze. Kafka stays the transport, and object storage becomes the durable, replayable copy the three cadences share. That is the medallion idea in miniature: one raw landing that many downstream shapes read from.

```mermaid
flowchart LR
    n0[("Kafka log events<br/>(Kafka)")]
    n1[("Bronze raw zone<br/>(object storage)")]
    n2["Streaming engine<br/>(Flink)<br/>SLA: #60; 1min"]
    n3["Micro-batch engine<br/>(Spark)<br/>SLA: #60; 15min"]
    n4["Nightly batch<br/>(Spark)<br/>SLA: #60; 24h"]
    n5(["Incident pager<br/>(alerting)"])
    n6(["Live ops dashboard<br/>(dashboard)"])
    n7(["Billing capacity report<br/>(reporting)"])
    n0 --> n1
    n1 --> n2
    n1 --> n3
    n1 --> n4
    n2 --> n5
    n3 --> n6
    n4 --> n7
```

*One land into bronze, three cadences out: streaming under a minute for the pager, a one-minute micro-batch trigger for the dashboard, nightly batch for billing.*

| Pitfall: Streaming all three, or tapping Kafka three times |
| --- |
| There are 2 attempts to watch for. The first is one streaming engine feeding all three branches. It hits every deadline, but you pay for sub-minute freshness on a billing report read once a day, and you run a 24/7 cluster to do what a nightly job does in one pass. The second is pointing all three branches straight at Kafka. That means three consumer groups replaying the same 50B events, no durable replayable copy, and a daily job that depends on retention it does not control. Landing into bronze once removes both problems. |

| Key insight: True streaming vs micro-batch is a deadline decision |
| --- |
| The pager and the dashboard look similar, but the dashboard shows rolling five-minute aggregates. A one-minute micro-batch trigger lands well inside that window and spreads per-run overhead across a batch of events. The pager cannot wait for the next trigger, so it gets true record-at-a-time streaming. Micro-batch is not a weaker stream; it is the right tool when the deadline is minutes, not seconds. |

| ✕ Freshness the branch needs | ✓ Cost of over-delivering it |
| --- | --- |
| Pager: 30 seconds, genuinely needs streaming. Dashboard: rolling 5 minutes, which micro-batch clears. Billing: daily, one nightly pass. | Streaming everything means always-on compute for 2 branches that never asked for it. Freshness nobody consumes is pure spend, so the win is aligning each cadence to its deadline, not maximizing it everywhere. |

**Follow-up questions**

1. If the dashboard's requirement tightened from rolling 5 minutes to 30 seconds, what changes in this design?\
   *Promoting one branch from micro-batch to streaming while it keeps reading the same bronze zone.*
2. Billing needs to recompute a corrected total after late-arriving events are backfilled. Why does reading from bronze make that possible?\
   *The replay payoff of landing once into a durable raw zone.*

</details>


<br>

### Exercise 7 of 11

**● TASK**

A factory's sensor gateway publishes 3,000 temperature readings a second to a Kafka topic, about 260 million a day. Operators watch a live panel, backed by its own store, that must show every reading within 30 seconds of it arriving on the topic. An hourly Spark batch would clear that volume easily; weigh the latency and the throughput this needs, then design the pipeline from the topic to the panel.

<details>
<summary><strong>Solution</strong></summary>

#### 2 dials, and only one of them binds here

Latency and throughput are separate measures. Throughput asks whether the pipeline keeps up: 3,000 readings a second is about 260 million a day, and an hourly Spark job clears that comfortably. Latency asks how long one reading waits before anyone can see it, and on an hourly schedule that wait is up to an hour against a 30-second budget. Once you name both numbers the choice is clear: throughput is not the constraint, latency is, so readings go through a stream processor.

```mermaid
flowchart LR
    n0[("sensor_topic<br/>(Kafka)")]
    n1["stream_processor<br/>(Flink)"]
    n2[("panel_store<br/>(Redis)<br/>SLA: real-time")]
    n3(["live_panel<br/>(Grafana)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
```

*`sensor_topic` feeds `stream_processor` continuously, which keeps `panel_store` fresh in real time, well inside 30 seconds, for `live_panel`.*

| ✕ Hourly Spark batch | ✓ Flink reading the topic |
| --- | --- |
| Collects an hour of readings and processes about 10.8 million in one run. Throughput is excellent, but a reading that lands just after a run waits nearly an hour to appear. | Handles each reading as it arrives and writes it to `panel_store` within seconds. Per-event overhead is higher, but at 3,000 a second that overhead is affordable. |

| Pitfall: Keeping up is not the same as being on time |
| --- |
| A batch job that finishes in 5 minutes looks fast, but its latency is the schedule plus the run, not the run alone. Measure from the moment a reading lands on the topic to the moment an operator can see it. |

| Performance: Modest volume makes low latency cheap |
| --- |
| At 3,000 readings a second a small stream job holds the rate, so paying per-event overhead for 30-second freshness costs little. The tension bites at much larger volumes, where batching work to amortize that overhead starts to win on throughput. |

**Follow-up questions**

1. The plant adds a weekly report of average temperature per machine. Does it belong on the same streaming path?\
   *Weighing both dials for a second reader whose latency budget is a week.*
2. If the panel's budget relaxed to one hour, what would you change?\
   *Seeing the decision flip once latency stops being the constraint.*

</details>


<br>

### Exercise 8 of 11

**● TASK**

A food-delivery platform publishes 40 million order status events a day to a Kafka topic, and a restaurant-ops panel reads per-restaurant open-order counts from a warehouse. The panel must show a change within 2 minutes, but nothing needs per-event latency, so pay for no more freshness than that. Choose micro-batch or record-at-a-time streaming for the transform, set its freshness to fit, and design the pipeline from the topic to the panel.

<details>
<summary><strong>Solution</strong></summary>

#### Pick the trigger, not the fastest engine

Micro-batch is what most 'streaming' pipelines really run: an engine with a streaming API that wakes on a trigger interval, processes whatever accumulated, writes the result, and waits. Here the panel needs a change within 2 minutes and nobody reacts to single events, so a one-minute trigger meets the bar while each batch spreads its overhead across roughly 28,000 events (about 460 a second times 60).

```mermaid
flowchart LR
    n0[("order_events<br/>(Kafka)")]
    n1["micro_batch_counts<br/>(Spark)<br/>SLA: #60; 1min"]
    n2[("restaurant_counts<br/>(warehouse)")]
    n3(["ops_panel<br/>(dashboard)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
```

*The Kafka topic feeds a Spark micro-batch on a one-minute trigger, which writes per-restaurant counts to a warehouse the ops panel reads.*

1. **Turn the freshness bar into a trigger**

   In the worst case a status change lands just after a batch starts: it waits up to one trigger interval, then rides the next batch's few seconds of processing. A one-minute trigger plus that work stays under 2 minutes, which is why the transform carries the '< 1min' freshness chip.

2. **Rule out both neighbors**

   A per-event processor at real-time freshness also meets 2 minutes, but it pays to keep every record moving for a panel nobody reads faster than once a minute. A 15-minute trigger or an hourly batch is cheaper still and misses the bar outright.

| Pitfall: Faster than required is not more correct |
| --- |
| The common slip is reaching for record-at-a-time streaming because the problem says 'events' and 'Kafka'. Latency below what any reader consumes is pure cost: the requirement sets the trigger, not the other way round. |

| Real world: The trigger is one number you retune |
| --- |
| In Spark Structured Streaming the interval is the `processingTime` argument on the trigger. If the panel later needs 30 seconds, you shorten it and the application code stays the same; Flink exposes a similar tunable interval. |

**Follow-up questions**

1. If the panel's bar tightened to 10 seconds, would micro-batch still be the right pick?\
   *Where a shorter trigger stops amortizing per-batch overhead and per-event processing starts to earn its cost.*
2. Dinner rush runs five times the average volume. What happens to each one-minute batch?\
   *Whether a fixed trigger absorbs a burst by growing the batch rather than adding latency.*

</details>


<br>

### Exercise 9 of 11

**● TASK**

A metering service writes 200 million API-call events a day to Kafka, and the billing team reads per-customer usage totals once a day, by 6am, to draft invoices. Design the cheapest pipeline that meets that need: the current proposal is an always-on stream processor keeping running totals for 2 million customers, so decide whether its continuous compute and state are worth paying for. Land the raw events durably so any day can be recomputed.

<details>
<summary><strong>Solution</strong></summary>

#### Pay only for freshness someone reads

Streaming bills by the hour whether or not anyone is reading. That is the first of the 3 cost components from the section: continuous compute, state storage and operational overhead. Here the only reader drafts invoices once a day at 6am, so an always-on stream processor would pay for 24 hours of cluster time, a checkpointed store of running totals for 2 million customers, and an on-call rotation for consumer lag, all to serve one read a day. A daily batch run pays for the forty minutes it works and nothing else.

```mermaid
flowchart LR
    n0[("metering_events<br/>(Kafka)")]
    n1[("raw_event_landing<br/>(object storage)")]
    n2["daily_usage_rollup<br/>(Spark)<br/>SLA: #60; 24h"]
    n3[("usage_totals<br/>(warehouse)")]
    n4(["billing_team<br/>(consumer)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
```

*Kafka lands raw calls in object storage; one Spark run a day rolls them into per-customer totals in the warehouse before billing reads at 6am.*

| Pitfall: Events on a stream do not need a streaming pipeline |
| --- |
| The tempting design reaches for a stream processor because the events already sit in Kafka. Where the data arrives says nothing about how fresh the output must be. Ask who reads it and how often: when the answer is once a day, a `< 1min` freshness tier is budget spent on minutes nobody looks at. |

| Performance: Forty minutes against 24 hours |
| --- |
| Compute: rolling up 200 million events takes about forty minutes, against a cluster provisioned around the clock, roughly 36 to 1 in raw hours. State: the batch run keeps nothing between days because it rereads the raw files, so there is no 2-million-key store to checkpoint. Operations: a failed nightly run is retried before 6am; a stuck stream pages someone at 3am. |

| Key insight: The raw store is what keeps batch cheap to fix |
| --- |
| Landing every raw call in object storage means a wrong day is repaired by rerunning that one day, with no stream replay and no state to rebuild. That durable history is also why nothing needs to run between the daily runs. |

**Follow-up questions**

1. Product wants an alert within a minute when a customer exceeds their quota. What changes, and what does it cost?\
   *Whether you add a narrow streaming branch for the alert alone and keep invoicing on the cheap daily run.*
2. Billing switches to drafting invoices every hour. Is an always-on stream now worth it?\
   *Whether hourly freshness is better met by an hourly batch or micro-batch than by continuous compute.*

</details>


<br>

### Exercise 10 of 11

**● TASK**

A payments gateway publishes 50,000 card authorizations a second to Kafka. Mask each card number and archive every event in object storage; separately, count authorizations per card over a 10-minute window and publish cards above 5 to an alerts topic within a minute. Keep the stateless masking and the stateful counting as separate stages, and checkpoint the counter's state to durable storage so a restart resumes the counts.

<details>
<summary><strong>Solution</strong></summary>

#### 2 boxes on the same topic, opposite sides of the state line

Masking a card number and counting a card's authorizations look alike on the canvas: 2 transforms reading the same Kafka topic. They sit on opposite sides of the stateless versus stateful line. Masking needs only the event in hand. The per-card count needs every authorization that card made in the last 10 minutes, so the engine has to remember something between events, and **that memory is what has to survive a crash**.

1. **Classify each transform by what it must remember**

   `mask_card_number` rewrites one field on one event and forgets it, so it scales by adding workers and simply resumes from its committed offset after a failure. `count_per_card_10min` keeps a counter per card key, about 8 million live keys at this volume, and its output depends on events it saw minutes ago.

2. **Give the stateful stage, and only it, a checkpoint**

   The counter holds its keyed state in a local store and snapshots it to `state_checkpoints` together with its Kafka offsets. On restart it reloads the snapshot and replays from those offsets, so a card sitting at 5 authorizations still trips the alert on its sixth. The masker needs no snapshot at all.

```mermaid
flowchart LR
    n0[("auth_events<br/>(Kafka)")]
    n1["mask_card_number<br/>(Flink)"]
    n2[("event_archive<br/>(object storage)")]
    n3["count_per_card_10min<br/>(Flink)"]
    n4[("state_checkpoints<br/>(object storage)")]
    n5[/"fraud_alerts<br/>(Kafka)"/]
    n0 --> n1
    n1 --> n2
    n0 --> n3
    n3 --> n5
    n3 --> n4
```

*The stateless `mask_card_number` branch lands in `event_archive`; only the stateful `count_per_card_10min` checkpoints to `state_checkpoints` and feeds `fraud_alerts`.*

| Pitfall: A restarted counter must not start from zero |
| --- |
| Drawing the counter like the masker, a box with no durable state, means every deploy or crash silently resets millions of counts, and a card mid-burst slips under the threshold. Fusing masking into the counting job is the opposite mistake: the cheap stateless work inherits the checkpoint size and slower recovery of the stateful job. |

| Performance: State grows with keys, not with events |
| --- |
| 50,000 events a second is about 4.3 billion a day, and the masker's cost tracks that linearly. The counter's state tracks distinct cards in the window instead: roughly 8 million keys at a few bytes each is a few hundred megabytes, small enough to checkpoint every minute without stalling the alert path. |

**Follow-up questions**

1. Fraud wants each alert tagged with the card's home country from a separate card-profile stream. Which category is that join, and what does it add to the checkpoint?\
   *Recognizing a stream-to-stream join as stateful and placing it on the checkpointed side.*
2. What changes if the window grows from 10 minutes to 24 hours?\
   *How window length drives state size and recovery time while the masking branch stays the same.*

</details>


<br>

### Exercise 11 of 11

**● TASK**

A mobile game publishes 120 million match results a day to a Kafka topic, and a nightly Spark batch costing about $300 a month computes per-region win rates for a live-ops dashboard that now needs them within 15 minutes. A record-at-a-time job holding per-region counts in state is quoted at $6,000 a month, against a budget of $1,500. Design the pipeline from the topic to the dashboard: choose how the win rates are computed and a trigger interval that meets the 15-minute target inside the budget, and land them in a warehouse the dashboard reads.

<details>
<summary><strong>Solution</strong></summary>

#### Price the freshness, then pick the trigger

A micro-batch trigger interval is a price tag as much as a latency setting. Every trigger pays for a cluster to start, read a slice of the topic, update the per-region counts and write them out, so a shorter interval buys freshness by paying that cost more often. The job here is to find the longest trigger that still meets 15 minutes, because that is also the cheapest one that does.

1. **Turn the target into a trigger budget**

   Worst-case staleness is the trigger interval plus one run's processing time: a match that finishes just after a run starts waits a full interval, then the next run's work. At 120 million results a day (about 1,400 a second), ten minutes of data is roughly 830,000 events, which a run clears in about two minutes. A 10-minute trigger gives about 12 minutes worst case; a 15-minute trigger gives about 17 and misses.

2. **Price each option against nightly**

   Nightly uses about an hour of cluster time a day for $300, so roughly $10 an hour. A 10-minute trigger is 144 runs a day at about two minutes each, 4.8 hours a day, near $1,440 and inside budget. A 5-minute trigger means 288 runs at about 1.5 minutes, near $2,160 and over. The record-at-a-time job pays for compute, a state backend and checkpoints that never stop, which is how it reaches $6,000: 20 times nightly for freshness live-ops cannot use.

3. **Keep the state small and carried between runs**

   Win rate per region is a stateful count: each run adds its slice's wins and matches to running totals. With about 30 regions that state is a few kilobytes, carried in the run's checkpoint from one trigger to the next. Small state is what keeps the micro-batch cheap and its recovery simple.

```mermaid
flowchart LR
    n0[("match_results_topic<br/>(Kafka)")]
    n1["region_win_rate_microbatch<br/>(Spark)<br/>SLA: #60; 15min"]
    n2[("win_rate_warehouse<br/>(warehouse)")]
    n3(["live_ops_dashboard<br/>(Grafana)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
```

*The topic feeds a Spark micro-batch on a 10-minute trigger, which writes per-region win rates to the warehouse the dashboard reads.*

| Performance: Freshness is bought by the trigger, not the engine |
| --- |
| The same Spark logic that ran nightly now runs 144 times a day on a slice 1/144th the size. Cost scales with how often the cluster starts and how long each run holds it: about 5x nightly here, the cheap end of the 5x to 50x band. Evening peaks near 4x the average lengthen each run, so check the 12-minute worst case against peak load, not the daily mean. |

| Pitfall: A micro-batch job left running pays always-on prices |
| --- |
| Choosing micro-batch and then keeping the job up between triggers bills the cluster 24 hours a day and erases most of the saving. The cost case holds only when each trigger starts, processes its slice and releases the compute. The opposite miss is just as common: assuming a 15-minute target needs per-event processing at all. |

**Follow-up questions**

1. Evening traffic hits 4x the average and a run now takes 6 minutes. Does the 10-minute trigger still meet 15 minutes?\
   *Staleness is trigger plus processing time, and processing time grows with load.*
2. The budget drops to $1,000 a month. What do you change, and what do you tell live-ops?\
   *Whether the learner can name the freshness a smaller budget actually buys instead of shaving the trigger blindly.*

</details>
