# Schema Drift: Intermediate - Exercises

Lesson: [pa_schema_evolution_intermediate.md](../pa_schema_evolution_intermediate.md)

### Exercise 1 of 12

**● TASK**

Wire the starter's schema-compatibility quality_gate between the producer and the checkout_events topic so it rejects the breaking v5 schema (amount renamed to amount_cents) at registration. Have the analytics consumer total revenue in 5-minute event-time windows with a watermark and an allowed-lateness budget so late checkouts still update their window. Route checkouts that miss the budget to a dead-letter destination instead of dropping them.

**Starting canvas** (already placed for you):

- Producer: checkout_events service (publishing v5: rename amount to amount_cents) (source, API)
- Schema Registry: compatibility check (rejects breaking v5) (quality_gate, custom)
- Kafka checkout_events topic (v1 through v4 in flight) (queue, Kafka)
- Consumer: checkout analytics (5-min event-time windows) (transform, Flink)

<details>
<summary><strong>Solution</strong></summary>

#### 2 guarantees, 2 different places

This design combines **schema evolution** and late-data handling, and the trick is that they are enforced in 2 completely different spots. The rename of `amount` to `amount_cents` is a schema problem, so it gets caught at registration time by the compatibility gate, before a single byte reaches the topic. The mobile clients replaying buffered checkouts hours late are a time problem, so they get handled downstream in the streaming job by a watermark, an allowed-lateness budget, and a dead-letter destination. Neither net helps with the other's failure, which is exactly why the canvas asks you to wire both.

```mermaid
flowchart LR
    n0[("checkout_events service<br/>(API (publishes v5))")]
    n1["Schema Registry compatibility check<br/>(rejects breaking v5)"]
    n2[/"checkout_events topic<br/>(Kafka (v1-v4))"/]
    n3["checkout analytics<br/>(Flink 5-min event-time windows)"]
    n4[("revenue rollup sink<br/>(warehouse)")]
    n5[("late_checkouts dead-letter<br/>(Kafka DLQ)")]
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n3 --> n5
```

*The gate sits BEFORE the topic; the dead-letter path branches out of the windowed job as a side output.*

Notice where the `quality_gate` lives: on the edge from the producer to the topic, not after it. Registering a schema and publishing a record are 2 separate acts, and the compatibility check runs on the first. When the producer team tries to register v5, the registry sees that renaming `amount` to `amount_cents` breaks every existing reader (they look for `amount` and would find nothing) and refuses the registration outright. The producer can't publish a record it was never allowed to register, so `v5` never lands on the topic and the `v1` through `v4` consumers keep reading exactly as before.

| Pitfall: Rejecting bad data instead of bad schemas |
| --- |
| The tempting wrong version puts a validation step AFTER the topic that drops or nulls records whose `amount` field is missing. By then the damage is done: the breaking version is already committed to the log, every downstream consumer has to cope with it, and you are papering over NULLs in analytics instead of stopping the change. A compatibility gate rejects the schema at registration, which is a build-time no for the producer team, not a runtime cleanup for everyone else. |

The late-data side is about keeping a window open long enough. A 5-minute **event-time** window closes when the watermark passes the end of the window, but the watermark is deliberately held back so slightly-late checkouts still land in the right window. The allowed-lateness budget extends that grace: the job keeps each window's state around for, say, an extra hour after the watermark, so a mobile client that replays a buffered checkout 40 minutes late still updates the correct 5-minute bucket rather than being counted in the wrong window or dropped.

| Key insight: The dead-letter branch catches what the budget can't |
| --- |
| Allowed lateness has to be finite, or window state grows forever. So a checkout that arrives after its window's state has already been purged can't be folded into the total. Instead of silently discarding it, the job emits it to a `late_checkouts` dead-letter destination as a side output. Nothing is lost: those records are available for a correction job, a manual replay, or just an alert that a client's clock or buffer is badly off. |

| ✕ Inside the lateness budget | ✓ Past the lateness budget |
| --- | --- |
| Watermark plus allowed-lateness still covers the checkout's event time, so its 5-minute window state is alive. The record updates that window's revenue total and flows to the `revenue rollup sink`. | The window state has been purged, so the total can't be corrected in place. The record is routed to the `late_checkouts` dead-letter sink for out-of-band handling instead of being dropped. |

**Follow-up questions**

1. If the producer team genuinely needs to rename `amount`, how do they roll it out without the gate blocking them?\
   *Tests understanding that compatible evolution means adding `amount_cents` alongside `amount` and deprecating later, not renaming in place.*
2. What would you monitor on the `late_checkouts` dead-letter destination, and what does a sudden spike tell you?\
   *Tests treating the DLQ as an observable signal about client clocks and buffering, not a graveyard.*
3. How does raising the allowed-lateness budget trade off against the streaming job's state size?\
   *Tests the cost of keeping window state open longer versus dead-lettering more records.*

</details>


<br>

### Exercise 2 of 12

**● TASK**

The users table is renaming signup_date to created_at and changing it from DATE to TIMESTAMP, and 12 consumer teams read that column, so no single synchronized deploy is possible. Plan the change with expand-contract: add four phase-marker nodes between the producer and the consumers, in order (expand, dual-write, migrate, contract). Name each marker for its phase and for what the producer and the consumers do during it.

**Starting canvas** (already placed for you):

- Producer: users service (filing rename signup_date to created_at, DATE to TIMESTAMP) (source)
- Postgres users table (the schema being evolved) (storage, PostgreSQL)
- Consumer A: signup analytics (consumer)
- Consumer B: lifecycle email (consumer)
- Consumer C: 10 other downstream consumers (consumer)

<details>
<summary><strong>Solution</strong></summary>

Expand-contract is how you rename `signup_date` to `created_at` and widen `DATE` to `TIMESTAMP` without a flag-day: the old shape and the new shape coexist while 12 teams migrate on their own clock. The four markers you placed are an ordering constraint, not a to-do list to shuffle. Each phase only removes something once its replacement is already in place, so the system stays releasable at every step.

```mermaid
flowchart LR
    n0[("Producer: users service<br/>(source)")]
    n1["1 Expand: producer adds created_at, consumers read signup_date<br/>(transform)"]
    n2["2 Dual-write: producer fills both, consumers verify created_at<br/>(transform)"]
    n3["3 Migrate: producer dual-writes, consumers cut over one by one<br/>(transform)"]
    n4["4 Contract: producer drops signup_date, all 12 consumers on created_at<br/>(transform)"]
    n5(["12 downstream consumers<br/>(consumer)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n4 --> n5
```

*The markers sit between producer and consumers because the rollout is sequential: `created_at` exists before it is written, both columns agree before anyone reads the new one, and `signup_date` survives until the last consumer moves.*

1. **Expand: add `created_at`, keep `signup_date`**

   Add a nullable `created_at TIMESTAMP` and change nothing else. It is purely additive, so it ships with zero coordination: nobody breaks on a column they do not read yet.

2. **Dual-write: populate both for every event**

   The producer now writes both columns on every insert and update, and you backfill history so `created_at` is complete. Do this before any consumer switches, so a reader that flips finds real data, not nulls.

3. **Migrate: cut consumers over one at a time**

   Each team swaps its read to `created_at` when ready. Both columns stay in sync, so a half-migrated world is fine, and the flag-day dissolves into 12 small, reversible deploys.

4. **Contract: drop `signup_date` after the last consumer moves**

   Only once all 12 read `created_at` do you stop dual-writing and drop the old column. This is the sole destructive phase, and it is gated on a verified fact, not a hope.

| Pitfall: Contract before everyone moved is the flag-day again |
| --- |
| The tempting shortcut is to reorder the phases: rename the column in place, or drop `signup_date` once the loud teams have migrated. Both reintroduce the exact break the pattern prevents. Never remove the old shape until its replacement is proven present everywhere. |

**Follow-up questions**

1. How do you actually confirm all 12 consumers read `created_at` before you contract?\
   *Gates the drop on evidence (access metrics, query logs, a per-team sign-off), not assumption.*
2. During dual-write, what stops `signup_date` and `created_at` from drifting if a write touches only one?\
   *Points toward a generated column, a trigger, or a single write path so the shapes cannot diverge.*

</details>


<br>

### Exercise 3 of 12

**● TASK**

A finance dashboard reports daily revenue and is audited monthly, so a rerun must reproduce identical history. An operations dashboard shows the events per second the engine is processing right now, to detect lag. Both read one streaming aggregation today. Split it into two transforms, each named for the time domain it buckets by, and connect each to the dashboard whose question that domain answers.

**Starting canvas** (already placed for you):

- Kafka events topic (source, Kafka)
- Single aggregation (currently uses processing_time for both consumers) (transform, Flink)
- Finance dashboard (audited; reruns must produce identical history) (consumer, Metabase)
- Operations dashboard (events-per-second; lag detection) (consumer, Grafana)

<details>
<summary><strong>Solution</strong></summary>

#### Name the consumer, then pick its clock

Every windowed aggregation buckets records by a timestamp, and the real decision is which clock supplies it. **Event time** is when the event actually happened, carried on the record itself; processing time is the wall-clock moment the engine saw it. The single aggregation you started with used one clock for both consumers, so the split was forced: finance and operations are asking about two different clocks and cannot share one bucketing transform.

Finance reports daily revenue and gets audited, so a rerun next month must reproduce today's history exactly. Only event time does that: a record's own timestamp never changes, so re-reading the topic drops each sale into the same day it always belonged to. Operations wants the events per second the engine is keeping up with, a question about the engine's own clock, so processing time there is not a compromise but the correct answer.

```mermaid
flowchart LR
    n0[("Kafka events topic<br/>(Kafka)")]
    n1["Event-time bucketing<br/>(Flink)"]
    n2["Processing-time bucketing<br/>(Flink)"]
    n3(["Finance dashboard<br/>(Metabase)"])
    n4(["Operations dashboard<br/>(Grafana)"])
    n0 --> n1
    n0 --> n2
    n1 --> n3
    n2 --> n4
```

*One source, two transforms: event-time bucketing feeds finance, processing-time bucketing feeds operations.*

| Pitfall: A processing-time rerun is a different history |
| --- |
| The tempting shortcut is to leave finance on processing time because the numbers look close. They are, until you rerun. A sale from 23:58 that arrives at 00:04 lands in the wrong day when you bucket by arrival. Arrival times differ on every replay, so the audited totals shift with each reprocess. That reproducibility is exactly what the audit checks, and processing time quietly fails it. |

| Key insight: Late data is why the clocks diverge |
| --- |
| If every event were processed the instant it happened, the two clocks would agree and this split would not exist. They diverge because of late data: network delays, retries and backfills let a record's event time trail its processing time by minutes or hours. Bucketing by event time puts each late record back in the day it belongs to, while operations still reports what the engine saw just now. |

**Follow-up questions**

1. A backfill replays last week's events through both transforms. Which dashboard's history changes, and why?\
   *Only buckets keyed on the engine's clock depend on when a run happens.*
2. Operations also wants revenue per hour of the day the sales happened. Which transform should feed that chart?\
   *The domain follows the consumer's question, not the dashboard it is shown on.*

</details>


<br>

### Exercise 4 of 12

**● TASK**

Events on the Kafka topic arrive 0 to 30 seconds after their event_time, and the Flink job sums revenue in 1-minute tumbling windows on event_time. Closing a window on the wall clock drops late events silently, while never closing it emits nothing. Add a watermark generator between the source and the aggregation, named for its strategy (bounded out-of-orderness fits this source) and the lag it subtracts from the max event_time seen.

**Starting canvas** (already placed for you):

- Kafka events topic (events arrive 0-30 seconds after event_time) (source, Kafka)
- Flink streaming aggregation: 1-minute tumbling windows on event_time (transform, Flink)
- minute_revenue dashboard (consumer, Grafana)

<details>
<summary><strong>Solution</strong></summary>

#### The watermark, plainly

A **watermark** is the engine's own clock for event time. It is a timestamp the stream carries forward that means: "I do not expect to see any more events with `event_time` earlier than this." A tumbling window fires when the watermark passes the window's end, not when the wall clock does. That one substitution is the whole trick here: the wall clock reaching '09:01:25' says nothing about whether every event for [09:00, 09:01) has landed, but a watermark that has advanced past '09:01' does.

The strategy that fits this source is **bounded out-of-orderness**: the watermark is `max(event_time) - 30s`. The lag of 30 seconds is not arbitrary. The source promises events arrive 0 to 30 seconds after their `event_time`, so an event stamped at time T can show up as late as T plus 30 seconds. Subtracting exactly that bound from the highest `event_time` you have seen keeps the watermark from running ahead of the slowest event that could still be in flight.

```mermaid
flowchart LR
    n0[("Kafka events topic<br/>(Kafka)")]
    n1["Watermark: bounded out-of-orderness, 30s lag<br/>(Flink)"]
    n2["1-minute tumbling windows on event_time<br/>(Flink)"]
    n3(["minute_revenue dashboard<br/>(Grafana)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
```

*The watermark generator sits between the source and the aggregation: it stamps event-time progress onto the stream so the window knows when it is safe to close.*

1. **Trace when the window actually closes**

   The window [09:00, 09:01) fires when the watermark reaches '09:01'. The watermark is `max(event_time) - 30s`, so it hits '09:01' only once some event with `event_time` '09:01:30' has been seen. By that point the late event stamped '09:00:46' has already arrived (it was due by '09:01:16' at the latest), so it lands inside the open window and is counted. The wall clock at '09:01:25' never entered the decision.

| Pitfall: A lag that is too small drops the late data silently |
| --- |
| Set the lag to 0 (watermark = `max(event_time)`) and the moment an event stamped '09:01:00' arrives, the watermark jumps to '09:01:00' and closes [09:00, 09:01) at once. The event at '09:00:46' is still in the broker and gets discarded with no error. That is exactly the silent drop the watermark was supposed to prevent, so the lag must cover the source's full out-of-orderness bound, 30 seconds, not a guess. |

| ✕ Lag too small | ✓ Lag too large |
| --- | --- |
| The watermark races ahead of slow events, windows close early and late rows are dropped. `minute_revenue` reads low and no one is told why. | The watermark trails reality, every window waits longer than it needs to, and the dashboard falls further behind live. The result is correct but stale. The lag is a latency-versus-completeness dial: match it to the measured skew. |

| Real world: Measure the skew before you set the lag |
| --- |
| You rarely hardcode the bound blind. Measure the real distribution of `wall_clock - event_time` at the source and set the lag to cover it, then keep watching it. If the skew grows, a watermark that was safe last month starts closing windows early, and the dashboard drifts low without any error. |

**Follow-up questions**

1. What happens to an event whose `event_time` is '09:00:59' but that arrives 40 seconds late, past the 30s bound?\
   *The watermark is a promise sized to a bound: an event beyond the bound reaches a window that has already closed.*
2. One idle Kafka partition stops sending events. Why might the watermark stall so that no window ever closes?\
   *The watermark advances only on observed events, so a silent input holds it back.*

</details>


<br>

### Exercise 5 of 12

**● TASK**

A revenue aggregation tumbles in 5-minute event-time windows behind a watermark that tolerates 60 seconds of out-of-orderness. Mobile retries up to an hour late must still correct the totals; anything later must be set aside, not dropped. Name the aggregation with its 60-minute allowed-lateness budget, and wire a dead-letter destination from the aggregation that captures events past the budget for the next-day reconciliation pass.

**Starting canvas** (already placed for you):

- Kafka events topic (source, Kafka)
- Watermark generator: bounded out-of-orderness, 60s lag (transform, Flink)
- Flink aggregation: 5-minute tumbling on event_time (no allowed-lateness budget yet) (transform, Flink)
- minute_revenue dashboard (consumer, Grafana)

<details>
<summary><strong>Solution</strong></summary>

#### 2 clocks, not one: watermark vs. allowed lateness

**Allowed lateness** gives an event-time window a second tolerance for late data, separate from the watermark, and the dead-letter destination catches whatever outlives it. The watermark (bounded out-of-orderness, 60s lag) decides when a window fires its first result: it says "I believe I've seen everything up to time T minus 60 seconds, so windows that ended before that are ready to emit." Allowed lateness decides how long that window's state stays alive after it fires, so stragglers can still correct the total. The 2 are set to very different values here (60 seconds vs. 60 minutes) because they answer different questions.

```mermaid
flowchart LR
    n0[("Kafka events topic<br/>(Kafka)")]
    n1["Watermark generator: bounded out-of-orderness, 60s lag<br/>(Flink)"]
    n2["Flink aggregation: 5-minute tumbling on event_time, allowedLateness 60min<br/>(Flink)"]
    n3(["minute_revenue dashboard<br/>(Grafana)"])
    n4[/"late_events DLQ for next-day reconciliation<br/>(Kafka)"/]
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n2 --> n4
```

*The finished topology: a 60-minute lateness budget on the window, plus a DLQ branch off the aggregation for events past the budget.*

1. **Give the window a 60-minute lateness budget**

   On the aggregation, set `allowedLateness` to 60 minutes. Each 5-minute tumbling window keeps its state for a full hour after the watermark fires it. When a mobile retry for an already-fired window arrives within that hour, the window re-fires and emits an updated total, so the dashboard corrects itself. The watermark stays at 60 seconds: the first result still lands within about a minute, and the state is kept for an hour.

2. **Branch a dead-letter destination off the aggregation**

   Wire a second edge from the aggregation to a `late_events` DLQ. In Flink this is the side output from `.sideOutputLateData(...)`: any event older than window end plus `allowedLateness` is emitted there instead of being silently dropped. The branch comes off the aggregation, not the source, because only the window operator knows which events actually missed their budget.

| Pitfall: Widening the watermark makes every window an hour stale |
| --- |
| The tempting wrong move is to widen the watermark to 60 minutes and skip `allowedLateness`. Late data does get in, but every window's first emission is now delayed by an hour, so the dashboard is an hour stale for the events that arrived on time. Allowed lateness separates freshness (watermark) from correctness over time (state retention): a fast first result and a slower, complete final one. |

| Key insight: Past the budget, it is drop or set aside |
| --- |
| Window state has to be released eventually, because the engine cannot hold every window forever. Events past the budget can only be dropped or set aside. Without the side output they vanish with no record; with the DLQ they become a bounded, auditable backlog that a batch job reconciles the next day. |

| ✕ Watermark (60s) | ✓ Allowed lateness (60min) |
| --- | --- |
| Governs when a window fires its first result. Kept small so the `minute_revenue` dashboard stays near real time. Events behind the watermark are late but may still be accepted. | Governs how long fired window state is retained for corrections. Large enough that an hour of mobile retries can re-fire and update totals. Events past it are routed to the `late_events` DLQ. |

**Follow-up questions**

1. What would you change if the DLQ backlog had to feed corrections back into the dashboard rather than a separate report?\
   *Reconciliation as a batch re-aggregation that overwrites the same sink the streaming job writes.*
2. How does raising `allowedLateness` to 6 hours affect state size, and when would you move window state from heap to RocksDB?\
   *Links the lateness budget to how much window state the engine must hold.*

</details>


<br>

### Exercise 6 of 12

**● TASK**

Extend this live metrics pipeline so the producer can ship a breaking schema change through expand-contract while the real-time dashboard keeps serving correct numbers. Put a schema registry between the producer and the topic, and name the compatibility mode it enforces at registration. Rebucket the Flink aggregation by event_time instead of processing_time, with a bounded out-of-orderness watermark of 60 seconds and an allowed lateness of 60 minutes. Route events that arrive past that budget to a dead-letter sink instead of dropping them.

**Starting canvas** (already placed for you):

- Producer: live_metrics events (preparing breaking schema change) (source, API)
- Kafka live_metrics topic (queue, Kafka)
- Flink streaming aggregation (currently no watermark, no lateness budget, buckets by processing_time) (transform, Flink)
- Real-time metrics dashboard (consumer, Grafana)

<details>
<summary><strong>Solution</strong></summary>

#### What the capstone wired together

This capstone is 4 intermediate moves standing in one line, each guarding a different failure. **Schema evolution** puts a schema registry in front of the topic so an incompatible producer schema is rejected at registration, not discovered downstream when the dashboard breaks. Stream processing buckets the aggregation by `event_time` instead of `processing_time`, so a metric lands in the minute it actually happened. Late-data handling gives that bucketing a 60-second watermark and a 60-minute lateness budget, and a dead-letter queue catches whatever arrives past the budget. The expand-contract steps below are how the producer gets its breaking change through a FULL-compatibility registry without the dashboard noticing.

```mermaid
flowchart LR
    n0[("Producer: live_metrics events<br/>(API)")]
    n1["Schema registry (FULL compatibility)<br/>(schema registry)"]
    n2[/"Kafka live_metrics topic<br/>(Kafka)"/]
    n3["Flink aggregation by event_time (60s watermark, 60m allowed lateness)<br/>(Flink)"]
    n4(["Real-time metrics dashboard<br/>(Grafana)"])
    n5[/"Late events dead letter queue<br/>(dead letter queue)"/]
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n3 --> n5
```

*The solved topology: the registry gates the topic, the aggregation buckets by `event_time` behind a 60-second watermark, and late events split between the window (within 60 minutes of lateness) and the dead letter queue (past it).*

| Pitfall: `processing_time` counts the wrong minute |
| --- |
| The Flink job you started from buckets by `processing_time` with no watermark. Under load or a consumer restart, events queue up and get counted whenever they are read, so a real spike at 10:00 smears across 10:05. Switching the key to `event_time` fixes placement, but `event_time` alone needs a watermark to know when a minute is done. |

| Key insight: The late-data triad is one mechanism |
| --- |
| Watermark, allowed lateness, and dead-letter are 3 parts of one decision, not 3 features. The `WatermarkStrategy` with 60 seconds of bounded out-of-orderness decides when a window fires; `allowedLateness` of 60 minutes keeps the window state alive to fold in stragglers; the dead letter queue catches anything later than that so it is quarantined, not silently dropped. Remove any one and late data either blocks the window forever or vanishes without a trace. |

1. **Expand: register the compatible superset**

   Add the new field and keep the old one. Under `FULL` compatibility the registry accepts this schema because both old readers and new readers still work; a schema that removed or retyped a field here would be rejected at registration.

2. **Dual-write from the producer**

   Producers start emitting both the old and new fields. Nothing reads the new field yet, so a bad producer rollout stays invisible to the dashboard and is trivially reversible.

3. **Migrate the consumers**

   Point the `event_time` aggregation and the dashboard at the new field and stop depending on the old one. This is the phase where the 2 schemas genuinely coexist in flight.

4. **Contract: drop the old field**

   Only now, once no reader touches the old field, register the schema that removes it. The breaking change landed with no flag day, because the registry never let an incompatible version through at any step.

**Follow-up questions**

1. If only consumers upgrade first and producers never change, would `BACKWARD` compatibility be enough instead of `FULL`?\
   *Maps a rollout direction to the minimal compatibility mode.*
2. Where should the 60-minute `allowedLateness` number come from, rather than being a guess?\
   *Tuning the budget from the observed event-delay distribution, not a round number.*
3. What happens to events in the dead letter queue once the incident is over?\
   *Replay-and-reaggregate vs alert-only handling of quarantined late events.*

</details>


<br>

### Exercise 7 of 12

**● TASK**

Firmware teams on a fleet of IoT devices publish readings to one Kafka topic, and a Flink job lands them in a lake table. New firmware adds fields every few weeks. Add a schema registry that producers register each new version with before publishing and that the Flink job fetches each record's version from on read, and land the readings in a table that takes added columns without a rewrite.

<details>
<summary><strong>Solution</strong></summary>

#### The registry sits beside the stream, not in it

A schema registry is a separate service the pipeline consults, not a stage the readings flow through. Producers register a version before they publish, and the registry runs its compatibility check right then, so a breaking change is refused while it is still a release candidate. Each record carries only its version ID; the reader looks that ID up and decodes with the exact schema the record was written under. Old and new firmware then share one topic without the reader guessing.

```mermaid
flowchart LR
    n0[("firmware_producers<br/>(source)")]
    n1["schema_registry<br/>(Apicurio)"]
    n2[/"readings_topic<br/>(Kafka)"/]
    n3["stream_reader<br/>(Flink)"]
    n4[("readings_table<br/>(Iceberg)")]
    n0 --> n1
    n0 --> n2
    n2 --> n3
    n1 --> n3
    n3 --> n4
```

*Producers register with `schema_registry` before publishing to `readings_topic`; `stream_reader` fetches each record's version from the registry and lands readings in `readings_table`.*

1. **Hang the registry off the producers**

   Draw the producers connecting to the registry as well as to the topic. That edge is the registration call, made before the first reading under a new version is published. If the compatibility check fails, the release stops there and the topic never sees the bad shape.

2. **Point the reader at the registry**

   The Flink job needs its own edge from the registry. When a record arrives with a version ID it has not seen, it fetches that schema once, caches it and decodes. A reading from last month's firmware and one from today's decode side by side.

| Pitfall: Readings never pass through the registry |
| --- |
| Wiring producers to the registry and the registry to the topic makes every reading look like it flows through it. It does not: the registry serves a few lookups per version, while the readings go straight to Kafka. Drawn inline, it becomes a choke point carrying 2 million readings an hour. |

| Key insight: The landing table is part of the contract too |
| --- |
| The registry keeps producer and reader in agreement, but the table they write into must keep up. An Iceberg table adds a column as a metadata change, so a new firmware field lands without rewriting the history already stored. |

**Follow-up questions**

1. A second service starts reading the same topic. What does it need from the registry, and what changes for the producers?\
   *Whether one registered version serves every reader without producer changes.*
2. What goes wrong if a producer publishes under a new shape without registering it first?\
   *Why registration has to happen before publishing, not after.*

</details>


<br>

### Exercise 8 of 12

**● TASK**

A payments topic in Kafka carries a decimal `amount` that must be replaced by an integer `amount_minor` and a `currency` field. A fraud stream job, a nightly finance warehouse load and a partner export all read it, each migrating on its own schedule. Design the expand phase of expand-contract: the producer writes both shapes through a schema registry check, and the warehouse takes the new columns while the old one stays.

<details>
<summary><strong>Solution</strong></summary>

#### Add first, remove last

Expand-contract earns its keep on a change like this one, where a field is restructured rather than simply added. Swapping the decimal `amount` for `amount_minor` plus `currency` in one deploy would break every reader still parsing `amount` the moment the new events land. The expand phase only adds: the producer writes the old field and the new pair side by side, and nothing downstream has to move yet.

```mermaid
flowchart LR
    n0[("payments_dual_write<br/>(source)")]
    n1["schema_registry_check<br/>(Apicurio)"]
    n2[/"payments_topic<br/>(Kafka)"/]
    n3["fraud_stream_job<br/>(Flink)"]
    n4["finance_nightly_load<br/>(Spark)"]
    n5[("finance_warehouse<br/>(Iceberg)")]
    n6(["partner_export<br/>(consumer)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n2 --> n4
    n4 --> n5
    n2 --> n6
```

*Expand phase: the producer writes `amount` and `amount_minor` plus `currency`, the registry passes the additive version, and three readers migrate on their own schedules.*

1. **Write both shapes and let the registry vouch for it**

   The expand version adds `amount_minor` and `currency` and keeps `amount`. Because it removes nothing, the registry check in front of the topic passes it as compatible, and every existing reader keeps decoding events exactly as before. That same check is what refuses a version that drops `amount` before its readers are ready.

2. **Give each reader its own path off the topic**

   The fraud job, the nightly finance load and the partner export each read the topic directly, so each team flips from `amount` to `amount_minor` in its own deploy. The warehouse takes the new columns as an additive change: a table format with schema evolution adds them while the old column keeps its history.

| Pitfall: A one-deploy swap is a flag day |
| --- |
| The tempting design changes the field at the producer and asks every team to ship the same afternoon. The partner export cannot: it ships on someone else's calendar, so it either breaks outright or silently reads nulls where `amount` used to be. |

| Key insight: The slowest reader sets the contract date |
| --- |
| Dropping `amount` is the contract phase, and it waits until every reader uses only the new fields. The fast fraud team never waits on the partner, and the partner is never rushed; that final step is the only coordination the pattern asks for. |

**Follow-up questions**

1. A refunds job is being built now. Which field should it read on day one?\
   *Whether a new reader starts already migrated, so it never pushes back the contract phase.*
2. Older rows in the finance warehouse only have `amount`. How do they get `amount_minor` before finance switches over?\
   *Filling the new column for historical data as part of the migration.*

</details>


<br>

### Exercise 9 of 12

**● TASK**

Scooters publish ride-start events to a Kafka topic at 5,000 per second, and phones that lose signal upload them up to 20 minutes late. Design a streaming pipeline that counts rides per zone in 10-minute event-time windows for a city operations dashboard that must be fresh within a minute. Keep the raw events in an archive so that replaying them through the same job after a bug fix reproduces identical counts.

<details>
<summary><strong>Solution</strong></summary>

#### Bucket by when the ride happened

Event time is the timestamp the scooter stamped when the rider unlocked it; processing time is whenever that event happened to reach the counting job. With phones uploading up to 20 minutes late, the 2 can disagree by 2 whole 10-minute windows, and only event time puts each ride in the window the city actually wants to see.

```mermaid
flowchart LR
    n0[("ride_events<br/>(Kafka)")]
    n1[("raw_ride_archive<br/>(Iceberg)")]
    n2["event_time_zone_counts<br/>(Flink)"]
    n3[("zone_ride_counts<br/>(Redis)")]
    n4(["city_ops_dashboard<br/>(Grafana)"])
    n0 --> n2
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
```

*`ride_events` feeds `event_time_zone_counts` live and `raw_ride_archive` for replay; counts land in `zone_ride_counts` for the dashboard.*

1. **Window on the unlock timestamp**

   The counting job reads the timestamp inside each event and assigns the ride to the 10-minute window it falls in, no matter when it arrives. A ride unlocked at 08:07 that uploads at 08:25 still lands in the 08:00 to 08:10 window, so the dashboard reports what happened on the street.

2. **Archive the raw stream beside the live path**

   The topic fans out twice: live into the counting job, and into `raw_ride_archive`. After a bug fix you replay the archive through the same job. Because every bucket is chosen by a timestamp carried in the data, the replay rebuilds the same counts even though it runs days later and far faster than the original.

| Pitfall: Arrival-time windows move with lag |
| --- |
| Bucketing on processing time is cheaper and looks identical on a quiet afternoon. When a cell outage holds back uploads, those rides pile into whichever window is open when they finally arrive, so a zone shows a fake dip and then a fake spike. Replay is worse: the whole archive arrives in minutes and collapses into a handful of windows. |

| Key insight: The data carries its own clock |
| --- |
| Event time makes the output a function of the input alone. That is what reproducibility means for a stream, and it is why most production aggregations accept the extra state of keeping several windows open rather than counting by arrival. |

**Follow-up questions**

1. Dispatchers also want a live gauge of events received in the last minute, to spot ingest outages. Which time domain fits that one?\
   *Tests when processing time is the right choice: the question is about the pipeline itself, not the world.*
2. A firmware bug stamps some rides with the device's boot time instead of the unlock time. What does event-time bucketing do with them, and where would you catch it?\
   *Tests that event time trusts the timestamp in the data, which makes that timestamp's quality a pipeline concern.*

</details>


<br>

### Exercise 10 of 12

**● TASK**

Smart meters publish readings to a Kafka topic at 20,000 per second, and meters that lose signal flush buffered readings up to 10 minutes late. Aggregate load per feeder in 15-minute event-time windows that close when the watermark passes them, not on the wall clock, and feed a grid dashboard that refreshes every minute. Readings that arrive behind the watermark go to a late-readings store, never dropped silently.

<details>
<summary><strong>Solution</strong></summary>

#### A window closes when the stream says so

Watermarks are how a streaming engine decides a window is finished. Each 15-minute feeder window here is keyed on the time the meter took the reading, and the engine emits a watermark that trails the event times it has observed. When the watermark passes the end of a window, that window closes and its total goes to the store the dashboard reads. Because the watermark advances only with observed readings, a meter that flushes 10 minutes of buffered data does not find its windows already shut by a clock tick. A reading that still arrives behind the watermark is not added to a closed window, so the design gives it somewhere to go instead of a silent drop.

```mermaid
flowchart LR
    n0[("meter_readings<br/>(Kafka)")]
    n1["watermark_window_aggregation<br/>(Flink)"]
    n2[("feeder_load_store<br/>(Redis)")]
    n3(["grid_dashboard<br/>(Grafana)"])
    n4[("late_readings_store<br/>(object storage)")]
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n1 --> n4
```

*Readings flow from Kafka into a watermark-driven Flink window; closed totals reach the dashboard, and readings behind the watermark branch to the late-readings store.*

| Pitfall: A wall-clock timer quietly loses the flushed readings |
| --- |
| Closing each window when the clock reaches its end looks the same on a healthy stream. It is not: every meter that reconnects late finds its windows already emitted, and those readings disappear without an error. The feeder totals look plausible and are quietly low, which is the worst kind of wrong for a grid operator. |

| Key insight: A quiet feeder holds the watermark back |
| --- |
| The watermark is driven by events, so when readings stop arriving it stops advancing too. During a storm outage the open windows simply wait instead of closing on a guess. The same rule governs a fraud stream counting card swipes or a game counting matches: the result can be late, but it is not built from a window that closed before its data arrived. |

**Follow-up questions**

1. What happens to every feeder's window if one region's meters fall twenty minutes behind while the rest are current?\
   *Tests that the watermark trails the slowest input, so one lagging region holds the windows open.*
2. How would you use the late-readings store to correct a feeder total the dashboard already showed?\
   *Extends the side path into a correction: recompute the affected window from the readings that were set aside.*

</details>


<br>

### Exercise 11 of 12

**● TASK**

Mobile apps publish ad-click events to a Kafka topic, and phones that go offline upload their buffered clicks later. Design a pipeline that counts clicks per campaign in 5-minute event-time windows with a 60-second watermark and 60 minutes of allowed lateness. When a late click arrives inside that hour, the dashboard's count for its window must be corrected in place, and clicks later than that go to a dead-letter path instead of vanishing.

<details>
<summary><strong>Solution</strong></summary>

#### Allowed lateness is a second clock on every window

The watermark decides when a 5-minute window first fires: 60 seconds after event time passes its end. Allowed lateness decides how long the window's state is kept after that, here 60 minutes. A click that lands inside that hour is folded into its window, and the aggregator emits a new, larger count for the same campaign and window. A click that lands after the hour has no window left to join, so it leaves on the error path. 3 outcomes, one configuration: on time, corrected, dead-lettered.

```mermaid
flowchart LR
    n0[("click_events<br/>(Kafka)")]
    n1["campaign_click_windows<br/>(Flink)"]
    n2[("campaign_click_counts<br/>(PostgreSQL)<br/>Idempotency: upsert")]
    n3(["campaign_dashboard<br/>(Grafana)"])
    n4[/"dead_letter_queue<br/>(Kafka)"/]
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n1 --> n4
```

*Clicks fold into 5-minute windows; late clicks within the hour re-emit an upserted count, later ones leave on the error path.*

| Pitfall: An appended correction counts the window twice |
| --- |
| If the store inserts every emission as a new row, the dashboard sums the first firing and the correction: 50 on time plus a re-emitted 54 shows 104 when the truth is 54. Each emission is the window's full count, not a delta, so the write must replace the row keyed by campaign and window start. That is the upsert setting on the store. |

| Key insight: Both lateness numbers are measurements |
| --- |
| 60 seconds matches the 99th percentile arrival lag, so the first result is right for nearly every window. 60 minutes covers the 99.9th percentile, so corrections stop after an hour and the engine can release the window state. Raise it and more windows stay in memory; lower it and more clicks land in the dead-letter queue. |

**Follow-up questions**

1. What changes if the 99.9th percentile arrival lag grows to 3 hours?\
   *Trading longer-held window state against a larger dead-letter volume.*
2. How would you fold the dead-lettered clicks back into daily totals?\
   *Reconciling very late data with a batch backfill instead of reopening streaming windows.*

</details>


<br>

### Exercise 12 of 12

**● TASK**

Handheld scanners publish parcel scans to a Kafka topic, and the event-time field `ts` is being renamed to `scanned_at` with expand-contract. A streaming job counts scans per hub in 5-minute windows on that event time for a live dashboard, allowing 60 minutes of lateness because offline scanners upload buffered scans late. The topic also lands in a lake table read by a nightly billing job that migrates last. Design the expand phase: the scanners write both fields, and every schema version is checked against a registry before publishing.

<details>
<summary><strong>Solution</strong></summary>

Expand-contract gets harder when the column being renamed is the one your watermark reads. Here `ts` is the event time that places every scan in a 5-minute window, and scanners that sat offline keep delivering scans written before the rename for up to an hour. So the rename is not finished when the last reader switches: it is finished when no record carrying only `ts` can still arrive or be reread.

```mermaid
flowchart LR
    n0[("scanner_fleet_dual_write<br/>(source)")]
    n1["schema_registry<br/>(quality_gate)"]
    n2[/"parcel_scans_topic<br/>(Kafka)"/]
    n3["hub_counts_stream<br/>(Flink)"]
    n4(["live_hub_dashboard<br/>(consumer)"])
    n5[("raw_scans_lake<br/>(Iceberg)")]
    n6["nightly_billing_job<br/>(Spark)"]
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n2 --> n5
    n5 --> n6
```

*Expand phase: dual-writing scanners pass a registry check before the topic, which feeds the event-time stream and the lake table billing reads.*

1. **Expand: write both names, guarded by the registry**

   Updated scanners emit `ts` and `scanned_at` with the same value. The registry refuses any new version that drops `ts` while a reader still needs it, so a scanner build that skips the expand phase is stopped before it reaches the topic.

2. **Migrate each reader at its own speed**

   The streaming job switches first: it takes event time from `scanned_at` and falls back to `ts` when the new field is missing, because buffered scans from scanners not yet updated carry only the old name. Billing keeps reading `ts` from the lake table until its own release next quarter; dual-writing means nobody forces it to move early.

3. **Contract only when the last old record is out of reach**

   The scanners may stop writing `ts` once billing reads `scanned_at`, every scanner runs the dual-write build, and the 60 minutes of allowed lateness have passed since the last old-only scan could arrive. Billing also reruns up to 7 days of lake partitions, so those partitions must all carry `scanned_at` before the old field goes.

| Pitfall: A missing event time silently empties windows |
| --- |
| Switching the stream to read only `scanned_at` the day scanners start dual-writing looks safe, yet a scan buffered on an offline scanner under the old build arrives with no `scanned_at`. With no event time it cannot be placed in a window, so it is dropped or miscounted, and the dashboard undercounts exactly the hubs with the worst connectivity. |

| Key insight: The slowest reader sets the contract date |
| --- |
| Each phase advance waits for the laggard, not the majority. The dashboard switching in a week moves the contract date not at all; billing next quarter does, plus the allowed lateness for old-only scans still in flight. |

**Follow-up questions**

1. A fraud model starts reading the topic and cannot switch to `scanned_at` for six months. What changes in the phase plan?\
   *Whether a new slow reader extends the expand phase and joins the conditions for contracting.*
2. If allowed lateness rose to 24 hours, how long after the last scanner update could the stream drop its `ts` fallback?\
   *Tying the contract step to the lateness bound the watermark enforces.*

</details>
