# Failure Handling: Intermediate - Exercises

Lesson: [pa_failure_modes_intermediate.md](../pa_failure_modes_intermediate.md)

### Exercise 1 of 12

**● TASK**

The order-processing worker gives up after 5 retry attempts and silently drops the message. Add a dead letter queue downstream of the worker so exhausted messages land in a durable destination instead of being lost or crashing the worker. Name, on the queue, the envelope each failed message carries so it can be replayed and debugged: the original payload, failure timestamp, exception type, attempt count and correlation ID.

**Starting canvas** (already placed for you):

- Kafka order_events source (source, Kafka)
- process_orders worker (retry budget: 5 attempts; failures currently silently dropped) (transform, Python)
- Iceberg orders_enriched (idempotent sink) (storage, Iceberg)
- Orders dashboard (consumer, Metabase)

<details>
<summary><strong>Solution</strong></summary>

A **dead letter queue** is the durable side channel a message goes to once its retry budget is spent. Instead of looping forever on a message that will never succeed, the `process_orders` worker gives up after its 5 attempts and hands the message somewhere it can be inspected and replayed rather than throwing it away. That destination is the DLQ, and the whole trick is that it is a real, persistent queue, not a log line.

| Pitfall: Silent drop trades a stuck message for lost data |
| --- |
| The 3 tempting exits all lose information. Dropping after the 5th attempt makes one order vanish with no trace. Crashing the worker turns one poison message into a full outage, since it stops every healthy message behind it. Writing the failure to stdout leaves it in a log nobody can replay from. The DLQ is the option that keeps the message and keeps the worker moving. |

```mermaid
flowchart LR
    n0[("Kafka order_events<br/>(Kafka)")]
    n1["process_orders worker<br/>(Python)"]
    n2[("Iceberg orders_enriched<br/>(Iceberg)")]
    n3(["Orders dashboard<br/>(Metabase)"])
    n4[/"orders dead letter queue (payload, failure timestamp, exception type, attempt count, correlation id)<br/>(Kafka)"/]
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n1 --> n4
```

*The dead letter queue hangs off the worker as a second output: success flows to `orders_enriched`, and a message whose 5 attempts are spent flows to the Kafka dead letter queue with its envelope.*

The DLQ is only useful if its envelope is rich enough to recover from without the original stream. Write 5 fields per message: the original payload (so you can replay it verbatim), the failure timestamp, the exception type, the attempt count, and the correlation ID. Together they answer what failed, when, why, how hard the worker tried, and which order it was. That is enough to reprocess the message or to debug the class of failure without going back to the source topic.

| Real world: The DLQ is a queue you drain, not a graveyard |
| --- |
| In production a dead letter queue has an owner and an alarm on its depth. A rising queue usually means a systematic bug (a schema change upstream), not one bad row. The envelope's exception type lets you group those messages and fix the whole batch at once, then replay them back through `process_orders`. |

**Follow-up questions**

1. Should a transient timeout and a permanent schema error both land in the same dead letter queue?\
   *Tests whether the learner separates retriable from non-retriable failures: a timeout deserves the 5 retries, a malformed payload should go to the DLQ on attempt 1.*
2. Why does an idempotent sink like `orders_enriched` make DLQ replay safe?\
   *Checks that replaying a recovered message cannot double-write, so draining the DLQ carries no duplication risk.*

</details>


<br>

### Exercise 2 of 12

**● TASK**

A pipeline's tax API call retries with max_attempts=5 and a 60-second cap, so the naive worst case is 1+2+4+8+60=75 seconds. Each call can itself time out after 30 seconds, so real retry time runs to minutes. Replace the retry transform with one whose name states the full retry budget that bounds the worst case: max_attempts, base_delay, max_delay, max_total_elapsed and jitter.

**Starting canvas** (already placed for you):

- Kafka order_events source (source, Kafka)
- call_tax_api: max_attempts=5, cap=60s, no max_total_elapsed (real worst case is unbounded) (transform, Python)
- Tax API downstream (per-call 30s timeout) (storage, API)
- Iceberg orders_enriched (idempotent sink) (storage, Iceberg)

<details>
<summary><strong>Solution</strong></summary>

A retry budget is the set of five numbers that turns "keep trying until it works" into a bounded, predictable operation, and naming them on the transform is how you set it. `max_attempts` caps how many times you call, `base_delay` sets the first backoff, `max_delay` caps any single wait, `jitter` spreads the waits so retries don't synchronize, and `max_total_elapsed` caps wall-clock time across the whole sequence. The starter node carried 4 of them; the missing one, `max_total_elapsed`, is exactly why the real worst case was unbounded.

```mermaid
flowchart LR
    n0[("Kafka order_events source<br/>(Kafka)")]
    n1["call_tax_api: max_attempts=5, base_delay=1s, max_delay=60s, max_total_elapsed=120s, jitter=full<br/>(Python)"]
    n2[("Tax API (per-call 30s timeout)<br/>(API)")]
    n3[("Iceberg orders_enriched (idempotent sink)<br/>(Iceberg)")]
    n0 --> n1
    n1 --> n2
    n1 --> n3
```

*All five numbers now live in the transform's name; `max_total_elapsed` is the one that makes the worst case a value you can state.*

| Pitfall: The 75-second worst case never existed |
| --- |
| The math `1+2+4+8+60=75` only sums the waits between attempts, assuming each call returns instantly. In production every attempt can burn the full 30-second per-call timeout before it fails, so five calls add up to 150 seconds of work on top of the waiting. With no ceiling on the total, the true worst case drifts into minutes. |

| Key insight: Only `max_total_elapsed` bounds the clock |
| --- |
| `max_attempts` bounds the count of calls, not their duration; `max_delay` bounds one wait, not the run. The single number that caps wall-clock time is `max_total_elapsed`: the loop checks it before every sleep and every call and gives up the moment the budget is spent. That is what lets you promise a worst case instead of estimating one. |

| Real world: Retries lean on the idempotent sink |
| --- |
| A retry often means the tax API already processed the order and only the response was lost. The `orders_enriched` sink is labeled idempotent for exactly this reason: writing the same enriched order twice must land once. A budget without an idempotent sink turns transient failures into duplicate rows. |

**Follow-up questions**

1. Should `max_total_elapsed` start at the first attempt, or when the event was pulled off `order_events`?\
   *Whether the budget covers queue wait or only the API call sequence.*
2. If the tax API returns a `Retry-After` header, how should it interact with `base_delay` and `max_delay`?\
   *Server-directed backoff versus the client's own budget.*

</details>


<br>

### Exercise 3 of 12

**● TASK**

The tax API that the order worker calls has been down for 15 minutes, and every call waits out a 30-second timeout before failing. Put a circuit breaker between the worker and the API, named for its closed, open and half-open states and the failure threshold and cool-down that move it between them. Give the worker capped retries with exponential backoff, and send orders that exhaust them to a dead letter queue for replay.

**Starting canvas** (already placed for you):

- order_events (source, Kafka)
- process_orders (transform)
- tax_api (consumer, API)
- orders_enriched (storage, Iceberg)

<details>
<summary><strong>Solution</strong></summary>

#### A breaker in front, a retry budget behind it

A circuit breaker guards against a sustained outage of a whole service, while a retry budget guards against the momentary failure of one request. This design stacks the two. `process_orders` retries a capped number of times with exponential backoff. Every attempt passes through the breaker. An order that spends its whole budget lands in `orders_dead_letter_queue` instead of stalling the partition.

```mermaid
flowchart LR
    n0[("order_events<br/>(Kafka)")]
    n1["process_orders<br/>(transform)<br/>Retries: 3 · Backoff: exponential"]
    n2["tax_api_breaker_closed_open_half_open_5_failures_60s_cooldown<br/>(transform)"]
    n3(["tax_api<br/>(API)"])
    n4[("orders_enriched<br/>(Iceberg)")]
    n5[/"orders_dead_letter_queue<br/>(dead letter queue)"/]
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n1 --> n4
    n1 --> n5
```

*`process_orders` reaches `tax_api` only through the breaker; orders that exhaust their retries go to `orders_dead_letter_queue`.*

The breaker is a three-state machine. In the closed state, calls pass through and failures are counted. After 5 consecutive failures it trips open, and every call returns immediately for the 60-second cool-down without touching the API. When the cool-down ends it goes half-open and lets one trial request through. A success closes it, and a failure opens it again for a fresh cool-down. Putting the states and both numbers in the stage name makes the behavior readable from the canvas.

| Pitfall: Retrying a dead service multiplies the wait |
| --- |
| The usual first attempt is a retry loop alone: catch the timeout, back off, call again. During a 15-minute outage, that turns one 30-second stall into three per order, with every worker doing it at once, so the API stays buried under timeouts. Backoff spaces the attempts out, but only the breaker stops sending them. |

| Key insight: An open breaker makes the retry budget cheap |
| --- |
| While the breaker is open, each retry fails in milliseconds, so an order spends its 3 attempts in seconds and moves on to `orders_dead_letter_queue`. The worker keeps draining `order_events`. Once a half-open trial succeeds, the parked orders are replayed into `orders_enriched`. |

**Follow-up questions**

1. When the breaker closes again, how would you replay `orders_dead_letter_queue` without reopening it with a burst of traffic?\
   *Combines the breaker's half-open caution with the replay rate of the dead letter queue.*
2. Should a 400 response from the tax API count toward the breaker's failure threshold?\
   *Separates a bad record, which belongs in the dead letter queue, from an unhealthy service, which should trip the breaker.*

</details>


<br>

### Exercise 4 of 12

**● TASK**

The Spark job aggregate_pageviews feeding a product analytics dashboard fails the whole batch on one malformed row. Choose all-or-nothing, skip-and-quarantine, or partial commit with checkpoint for this analytics workload, and rename the transform to name that strategy and its failure-rate threshold as a percentage: the dashboard tolerates up to 1% bad rows per batch. Connect the transform to a dead letter queue where set-aside rows land for inspection.

**Starting canvas** (already placed for you):

- Page-view events Kafka (millions of events per batch) (source, Kafka)
- aggregate_pageviews batch transform (currently fails the entire batch on any malformed row) (transform, Spark)
- Iceberg daily_pageviews (idempotent: partition overwrite by event_date) (storage, Iceberg)
- Product analytics dashboard (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

#### Skip-and-quarantine, and the dead letter queue

An analytics rollup is the textbook home for **skip-and-quarantine**: keep processing the good rows, route each bad row to a side channel, and abort only if the failure rate crosses a threshold. That side channel is a dead letter queue, a place records go when the main transform cannot handle them. You applied it by renaming `aggregate_pageviews` to state the strategy and its bounding parameter, then wiring it to a quarantine destination the transform writes rejects to.

```mermaid
flowchart LR
    n0[("Page-view events<br/>(Kafka)")]
    n1["aggregate_pageviews (skip-and-quarantine, abort if #62;1% of rows fail)<br/>(Spark)"]
    n2[("daily_pageviews<br/>(Iceberg)")]
    n3(["Analytics dashboard<br/>(dashboard)"])
    n4[("quarantine_pageviews (dead letter queue)<br/>(Iceberg)")]
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n1 --> n4
```

*The transform now has 2 outputs: good rows to `daily_pageviews`, rejects to the quarantine table. The threshold decides when to keep going and when to stop.*

| Pitfall: Both extremes lose something you need |
| --- |
| Failing the whole batch on one bad row throws away work on 9,999 good rows and stalls the dashboard for a single malformed event. Silently dropping the bad row inside the transform is worse: the row vanishes with no record, so an upstream schema change that starts corrupting thousands of rows looks exactly like a healthy run. Skip-and-quarantine avoids both because the set-aside rows land somewhere you can count and inspect. |

| Key insight: The threshold is what makes it skip, not silently drop |
| --- |
| A quarantine destination without a bounding parameter is just a silent drop with extra steps. The percentage threshold (here `>1%`) is the whole point: one bad row in 10,000 is noise and the batch should proceed, but 3,000 bad rows means something systemic broke and the batch must stop before it publishes garbage to `daily_pageviews`. Name the parameter in the transform so the strategy is legible on the canvas, not buried in config. |

| Real world: The workload picks the strategy, not the tool |
| --- |
| Analytics workloads tolerate a little loss for a lot of freshness, which is why this pattern is the default there. A daily ledger is the opposite case: it must balance, so it runs all-or-nothing, and that is only safe because the sink is idempotent, the way `daily_pageviews` overwrites its partition by `event_date`. Partial commit with checkpoint is the heavier tool for a batch so large that re-running from the top is expensive. |

**Follow-up questions**

1. What should a downstream job do with the rows in `quarantine_pageviews`?\
   *Tests whether the learner sees the dead letter queue as rows to reprocess or alert on, not a graveyard.*
2. How would you set the threshold if the batch size varied from 10,000 to 10 million rows?\
   *Pushes toward a percentage rather than an absolute count, and toward watching the rate trend over time.*

</details>


<br>

### Exercise 5 of 12

**● TASK**

Extend the starter so the worker survives 3 failures on the tax API call: a one-off 503, a 15-minute 503 outage, and a permanent validation failure. Add a validation gate that classifies errors, a circuit breaker, and a bounded retry with backoff as 3 separate nodes, with the breaker upstream of the retry. Route permanent failures from the gate and retry-exhausted messages from the retry stage to one durable dead letter queue.

**Starting canvas** (already placed for you):

- Kafka order_events source (source, Kafka)
- Worker pool (transform, Flink)
- Tax API (consumer, API)
- Snowflake enriched_orders (storage, Snowflake)
- Orders dashboard (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

#### Layered failure handling in one worker

Composing retry, breaker and DLQ is **defense in depth** for a streaming worker: one worker faces 3 different failures, and no single mechanism handles all three. A transient blip (a `503` once, then success) wants a retry. A sustained outage (a `503` for 15 minutes) wants a circuit breaker so you stop hammering a downed service. A permanent failure (a validation error that fails every time) wants to be routed aside so it never blocks the stream. Classification tells these apart, and the order you place breaker and retry in front of the tax API call is the whole exercise.

```mermaid
flowchart LR
    n0[("order_events<br/>(Kafka)")]
    n1["error classifier<br/>(custom)"]
    n2["circuit breaker<br/>(transform)"]
    n3["tax API retry<br/>(transform)<br/>Retries: 3 · Backoff: exponential"]
    n4(["Tax API<br/>(API)"])
    n5[/"dead letter queue<br/>(Kafka)"/]
    n6[("enriched_orders<br/>(warehouse)")]
    n7(["Orders dashboard<br/>(dashboard)"])
    n0 --> n1
    n1 --> n2
    n1 --> n5
    n2 --> n3
    n3 --> n4
    n3 --> n6
    n3 --> n5
    n6 --> n7
```

*Classify first. The breaker sits in front of the bounded retry on the tax API call, and 2 error paths reach the dead letter queue: permanent failures and budget-exhausted messages. Only enriched events land in the warehouse.*

1. **Classify before you react**

   The classifier's first job is to decide which of the 3 classes it is holding, and that decision fans out immediately. A permanent failure (a schema violation, a field the tax API rejects on every call) has no retry path that ends well, so it goes straight to the dead letter queue and never touches the breaker. Only a retriable error is worth handing to the resilience layer. Skip this step and you burn the whole retry budget on a message that can never succeed, then dead-letter it anyway.

2. **Put the retry budget inside the breaker**

   The nesting is `breaker(retry(tax_api_call))`. The retry budget absorbs the one-off `503`: a few bounded attempts with backoff, and the blip is gone. The breaker sits outside and watches whole retry sequences across many messages. When failures persist through the fifteen-minute outage, it opens and short-circuits, so new messages fail fast instead of each spending a fresh budget against a service that is down. A budget that exhausts while the breaker is still closed sends its message to the dead letter queue.

| Pitfall: Retry outside the breaker drains every budget |
| --- |
| Flipping the nesting to `retry(breaker(call))` means the retry loop keeps calling a breaker that is already open, treating each fast `CircuitOpen` rejection as one more attempt. The outage the breaker was meant to absorb now drains every message's budget one rejection at a time. Merging breaker and retry into one node hides the same question: draw them apart so the order is visible. |

| Real world: Recovery creates duplicates the sink must absorb |
| --- |
| Every layer here creates duplicates: Kafka is at-least-once, the retry re-issues calls, and an open breaker leaves offsets uncommitted so messages are redelivered when it closes. In production the warehouse write would upsert on `event_id` so a reprocessed order lands on the same row. Without that key, recovery turns transient errors into duplicate rows on the dashboard. |

**Follow-up questions**

1. When the breaker is open, should the worker keep consuming `order_events` or pause?\
   *Failing fast with uncommitted offsets means redelivery, and an idempotent write at the sink is what lets you choose either.*
2. What signal would tell you a message in the dead letter queue is replayable rather than truly permanent?\
   *Separates budget-exhausted messages (replayable once the API recovers) from validation failures (never replayable) inside the same DLQ.*

</details>


<br>

### Exercise 6 of 12

**● TASK**

Settlement events flow from Kafka through a worker that calls a tax-jurisdiction API, then into the Snowflake settlement_mart the finance dashboard reads. Redesign the failure handling: add an error classifier stage, wrap the tax-API call in a circuit breaker stage with a bounded retry budget, and send permanent and budget-exhausted events to a dead letter queue. Skip malformed rows into a quarantine store that alerts above 1% of traffic, and route credential failures to a paging tool. Keep Snowflake feeding the dashboard.

**Starting canvas** (already placed for you):

- Kafka settlement_events source (source, Kafka)
- settlement_worker (retries on bare except) (transform, Flink)
- Tax-jurisdiction API (occasional 503; sustained outages monthly) (source, API)
- Snowflake settlement_mart (MERGE on settlement_id) (storage, Snowflake)
- Finance dashboard (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

#### One question decides every arrow: what kind of failure is this?

What holds this whole board together is **error classification**. A resilient stream worker does not ask "did this event fail?" It asks "which class of failure did I just see?" and lets the answer pick the destination. Every pattern you composed (retry budget, circuit breaker, DLQ, skip-and-quarantine, paging) is a named response to one class. The starter `settlement_worker` collapses all of them into a single `except:` that retries, which is why it can hammer a dead credential forever and stall on a malformed row. Give each class its own lane and the pipeline stops guessing.

```mermaid
flowchart LR
    n0[("Kafka settlement events<br/>(Kafka)")]
    n1[("tax jurisdiction api<br/>(API)")]
    n2["tax api circuit breaker<br/>(Flink)<br/>On error: dlq · Retries: 5 · Backoff: exponential"]
    n3["error classifier<br/>(Flink)"]
    n4[/"settlement dlq<br/>(Kafka)"/]
    n5[("malformed row quarantine<br/>(object storage)<br/>Alert: page if malformed #62; 1%")]
    n6(["credential pager<br/>(alerting)"])
    n7[("settlement mart<br/>(Snowflake)")]
    n8(["Finance dashboard<br/>(consumer)"])
    n0 --> n2
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n3 --> n5
    n3 --> n6
    n3 --> n7
    n7 --> n8
```

*Each failure class gets its own lane: transient retries behind a breaker, permanent and budget-exhausted to the DLQ, malformed to quarantine, credential to paging.*

1. **Put the retry budget inside a circuit breaker**

   A `503` from the tax-jurisdiction API is transient: the row is fine, the dependency blinked. Retry it, but inside a **budget** (bounded attempts with exponential backoff), never an open-ended loop. When occasional `503`s become a sustained monthly outage, per-event retries just multiply load on something already down, so the circuit breaker wraps the budget: after N consecutive failures it trips open and fast-fails for a cooldown. Events that hit an open breaker or burn through the budget are not lost; they land in the settlement dlq.

2. **Split permanent failures by whether a human must act**

   A malformed row will never parse no matter how often you retry, so it takes the skip-and-quarantine lane: write it to the malformed row quarantine and keep the stream moving, alerting if the rate crosses 1% (that smells like an upstream schema change, not one bad record). A credential failure (`401`/`403`) is also permanent, but quarantining it hides an outage only on-call can fix, so it routes to the paging tool. Same 'permanent' label, 2 destinations, because the classifier asks who resolves it.

| Pitfall: A bare `except:` retry hides 3 different failures |
| --- |
| The starter worker retries on `except:`. That treats a malformed row, a dead credential and a blipping API as one thing: the malformed row loops instead of reaching quarantine, the `401` hammers the auth endpoint and never pages anyone, and only the `503` is helped. A bare retry feels defensive but turns 3 handleable failures into one silent stall. |

| Key insight: An idempotent sink makes every lane safe to replay |
| --- |
| You can retry, trip a breaker and drain a DLQ without corrupting finance's numbers because the sink is idempotent: the mart does a `MERGE` on `settlement_id`, so writing the same settlement twice is a no-op. Without it, a retry after a partial write double-counts revenue, and a DLQ replay double-counts again. |

| Real world: The DLQ is where the money is recovered |
| --- |
| On a revenue pipeline the DLQ is a work queue, not a graveyard. Budget-exhausted settlements wait in the settlement dlq through the outage, then a drain job replays them once the tax API recovers. The quarantine store doubles as a schema-drift early warning. |

**Follow-up questions**

1. The quarantine rate crosses 1% mid-day. Do you halt the worker or keep quarantining and alert?\
   *Whether the 1% threshold is a tripwire or a hard stop.*
2. A DLQ replay runs while the live stream processes the same `settlement_id`. What keeps the mart correct?\
   *Idempotent `MERGE`, not ordering, is the guarantee.*
3. Where does the circuit breaker keep its open/closed state so every worker instance agrees?\
   *Extends the breaker from one process to a worker fleet.*

</details>


<br>

### Exercise 7 of 12

**● TASK**

A shipment-tracking pipeline reads about 2 million carrier scan events a day from a Kafka topic, parses each one, and writes it to a PostgreSQL tracking table. About 1 in 10,000 events has a payload the parser still rejects after its retries, and today the worker either drops it or stalls every event behind it. Add a dead letter queue so those events are kept for an operator to inspect while the rest keep flowing.

<details>
<summary><strong>Solution</strong></summary>

#### A third exit for events that cannot be parsed

Once retries are spent, a dead letter queue gives a poison message somewhere to go besides the trash or the front of the line. The event leaves the main flow for a durable side channel, and the parser moves straight on to the next scan. At 2 million events a day and a 1 in 10,000 failure rate, that is about 200 events an operator reads each morning instead of 200 delivery updates that vanish, or a topic that stops moving.

1. **Retry first, then divert**

   `parse_scans` keeps its retry count. The dead letter queue only receives what retrying could not fix, so a short network blip never puts a healthy scan in front of an operator.

2. **Give failures their own queue**

   Draw a second edge out of the parser into `failed_scans_dlq`. It is durable like the main topic, so nothing written there is lost, and the parser picks up the next event as soon as the write succeeds.

3. **Put a reader on the other end**

   A dead letter queue nobody reads is just a slower way to drop data. `operator_review` consumes it, and that is where a human sees the payload next to its error.

```mermaid
flowchart LR
    n0[("carrier_scans<br/>(Kafka)")]
    n1["parse_scans<br/>(transform)<br/>Retries: 3"]
    n2[("tracking_table<br/>(PostgreSQL)")]
    n3[/"failed_scans_dlq<br/>(dead letter queue)"/]
    n4(["operator_review<br/>(consumer)"])
    n0 --> n1
    n1 --> n2
    n1 --> n3
    n3 --> n4
```

*Good scans land in `tracking_table`; scans that still fail after retries go to `failed_scans_dlq` for `operator_review`.*

| Pitfall: Logging a failure is not keeping it |
| --- |
| Writing the bad payload to an application log and moving on looks like a dead letter queue, but logs rotate and nothing reads them back as events. The message has to land in durable storage with the same shape it had on the main topic, so it can be inspected and later sent through the parser again. |

**Follow-up questions**

1. The parser is fixed. How do the 200 dead letters from yesterday get into `tracking_table`?\
   *Treating the dead letter queue as input for a recovery process, not a graveyard.*
2. A carrier ships a bad release and failures jump to 5 percent of events. What should notice?\
   *A fast-filling dead letter queue is a signal that needs watching, not just a place to park events.*

</details>


<br>

### Exercise 8 of 12

**● TASK**

An hourly job uses 40 parallel workers to fetch shipping rates for 3,000 lanes from a carrier API that answers bursts with HTTP 429, then loads them into a rates warehouse. On the stage that calls the API, set a retry budget: a capped retry count and an exponential retry backoff with jitter, so the 40 workers stop retrying in lockstep. Requests that exhaust the budget go to a dead letter queue so the run still finishes inside its hour.

<details>
<summary><strong>Solution</strong></summary>

#### A retry budget you can bound before it runs

A retry budget is 5 numbers you commit to up front: maximum attempts, base wait, which errors retry, a cap on total elapsed time, and the jitter strategy. Writing them down lets you answer the worst-case question for this specific job: 40 workers, 3,000 lanes, one hour, and one rate-limited carrier API.

1. **Cap the attempts and grow the wait**

   Set `retryCount` to 5 on the fetch stage and `retryBackoff` to 'exponential', which gives waits of roughly 2, 4, 8 and 16 seconds. A 429 is the API asking for room, and a doubling wait gives it room quickly.

2. **Add jitter so 40 workers spread out**

   All 40 workers start at the top of the hour, so they hit the limit together. Without jitter they also retry together, at exactly 2, 4 and 8 seconds, and each wave trips the limit again. Full jitter picks a random wait between zero and the backoff ceiling. That turns 40 synchronized retries into a trickle.

3. **Give exhausted requests a home**

   When the fifth attempt fails, the request goes to the dead letter queue from the previous section, carrying its lane and last error. The run moves on and loads every lane that succeeded. Ops re-drives the parked lanes afterwards.

```mermaid
flowchart LR
    n0[("carrier_rates_api<br/>(API)")]
    n1["fetch_rates_with_jitter<br/>(transform)<br/>Retries: 5 · Backoff: exponential"]
    n2[/"dead_letter_queue<br/>(dead letter queue)"/]
    n3[("rates_warehouse<br/>(warehouse)")]
    n0 --> n1
    n1 --> n3
    n1 --> n2
```

*`fetch_rates_with_jitter` retries up to 5 times with jittered exponential backoff, loads successes into `rates_warehouse`, and parks exhausted lanes in `dead_letter_queue`.*

| Performance: Attempts alone do not bound the hour |
| --- |
| Each worker owns 75 lanes. If a hung call times out at 30 seconds, one lane's worst case is 5 x 30 seconds of calls plus 30 seconds of waits, or 180 seconds. During a full outage that adds up to 75 x 180 = 13,500 seconds per worker, far past the hour. A `max_total_elapsed` clamp of about 45 seconds per lane caps the worst case at 75 x 45, or about 56 minutes, whatever the attempt count says. |

| Pitfall: A 400 will fail all 5 times |
| --- |
| Which errors retry is one of the 5 numbers. A 429 or a 503 clears up on its own; a 400 for a lane the carrier does not recognize never will. Retrying it burns the budget and adds load to an API that is already limiting you, so send it straight to the dead letter queue. |

**Follow-up questions**

1. The carrier starts sending a `Retry-After` header on 429s. How does that change the wait?\
   *Whether the server's hint should replace the computed backoff, and whether it still sits inside the attempt cap and `max_total_elapsed`.*
2. The lane count grows to 12,000 with the same 40 workers. Which number in the budget breaks first?\
   *Recomputing the worst case per worker against the hourly window.*

</details>


<br>

### Exercise 9 of 12

**● TASK**

A worker reads 400 delivery orders a minute from a Kafka topic, geocodes each through a partner address API and writes them to a warehouse. Keep exponential-backoff retries on that call for one-off failures, but in a sustained outage every call waits out a 30-second timeout, so put a circuit breaker in front of it that fails fast. Orders the open breaker refuses, and orders out of retries, wait in a queue for replay, and the on-call is paged when the breaker opens.

<details>
<summary><strong>Solution</strong></summary>

#### Stop calling a partner that is already down

A circuit breaker is a few lines of state in front of a downstream call that decide whether to make the call at all. Retries with backoff rescue one request that hiccups; in a full outage they make things worse, because all 400 orders a minute still wait out a 30-second timeout and pile load onto a partner that is already drowning. The breaker counts consecutive failures and, past a threshold, **opens**: every call fails in milliseconds, the partner gets room to recover, and after a cool-down a half-open probe lets one call through to decide whether to close again.

```mermaid
flowchart LR
    n0[("orders_topic<br/>(Kafka)")]
    n1["address_circuit_breaker<br/>(quality_gate)<br/>Alert: page if breaker open"]
    n2["geocode_worker<br/>(transform)<br/>On error: retry · Backoff: exponential"]
    n3[/"replay_queue<br/>(Kafka)"/]
    n4[("orders_warehouse<br/>(warehouse)")]
    n0 --> n1
    n1 --> n2
    n2 --> n4
    n1 --> n3
    n2 --> n3
```

*`address_circuit_breaker` passes orders to `geocode_worker` while closed and diverts them to `replay_queue` while open; orders out of retries take the same error path.*

1. **Put the breaker in front of the call**

   The breaker has to see an order before `geocode_worker` spends 30 seconds on it, so it sits upstream of the call. The retry budget from the last section stays on the worker: it still handles the single 503, and its failures are what the breaker counts.

2. **Give refused orders somewhere to wait**

   Failing fast only helps if the order survives it. Both error paths land in `replay_queue`, the same idea as the dead letter queue from section 0, so once the breaker closes those orders get geocoded late instead of never. The `monitorAlert` on the breaker pages the on-call the moment it opens.

| Pitfall: A bigger retry budget lengthens the outage |
| --- |
| The tempting fix for a long outage is raising the retry count. That multiplies the timed-out calls hitting the partner and keeps it overloaded, which is how a twenty-minute outage becomes a six-hour one. |

| Key insight: Failing in milliseconds is the feature |
| --- |
| An open breaker returns an error almost instantly, so workers are not tied up for 30 seconds per order, and an open breaker is a single clear signal on a dashboard: the partner is unhealthy and recovery is in progress. |

**Follow-up questions**

1. The worker adds a second partner for traffic estimates. Does one breaker cover both calls?\
   *Whether a breaker belongs to one downstream, so one outage cannot block an unrelated call.*
2. When the breaker closes, 40 minutes of orders sit in `replay_queue`. How do you replay them without knocking the partner over again?\
   *Applying the retry budget and pacing to the recovery backlog.*

</details>


<br>

### Exercise 10 of 12

**● TASK**

A nightly batch loads about 3 million smart-meter readings from CSV files into a warehouse that feeds an energy usage dashboard. Roughly 0.1% of rows fail validation (a missing meter ID or a negative kWh value), and today one bad row aborts the whole run. Design the batch so every valid row still loads and each failing row is quarantined in a separate store where it can be inspected and replayed, never silently dropped.

<details>
<summary><strong>Solution</strong></summary>

#### Skip and quarantine keeps the good rows moving

Skip-and-quarantine is the middle point on the partial-failure spectrum: a row that fails validation leaves the batch on its own path, and the run carries on with everything else. At 3 million readings a night and a 0.1% failure rate, that is about 3,000 rows set aside and 2,997,000 loaded, instead of zero loaded because one meter reported a negative kWh.

```mermaid
flowchart LR
    n0[("meter_reading_files<br/>(source)")]
    n1["validate_readings<br/>(quality_gate)"]
    n2[("usage_warehouse<br/>(warehouse)<br/>SLA: #60; 24h")]
    n3[("quarantine_dlq<br/>(dead letter queue)")]
    n4(["usage_dashboard<br/>(consumer)"])
    n0 --> n1
    n1 --> n2
    n1 --> n3
    n2 --> n4
```

*Rows that pass `validate_readings` load into `usage_warehouse` for the morning dashboard; rows that fail branch into `quarantine_dlq` for inspection and replay.*

| Pitfall: Both extremes lose something |
| --- |
| Aborting the run on the first bad row throws away every good row and leaves the dashboard empty until someone reruns it. Filtering bad rows out with a `WHERE` clause and moving on fails more quietly: nobody sees that 3,000 readings vanished, so a faulty meter or a changed file layout stays hidden. The quarantine store is what makes skipping safe, because every skipped row is still there to count, inspect and replay. |

| Trick: Quarantine the reason with the row |
| --- |
| Store each failing row together with why it failed ('missing meter id', 'negative kwh') and the run date. Replay then means fixing that cause and sending exactly those rows back through validation, not rerunning the whole night. |

| Key insight: The workload decides the strategy |
| --- |
| Usage trends survive a few thousand missing readings, so skipping is right here. A daily financial ledger is the opposite case: a ledger built from a subset of rows does not balance, so that batch should be all-or-nothing, and it is only safe to rerun because the load is idempotent. |

**Follow-up questions**

1. What should happen on a night when 40% of rows land in quarantine?\
   *Whether the quarantine rate is itself a signal worth watching rather than just a bin.*
2. If these readings also fed a monthly billing run, would that batch use the same strategy?\
   *Telling apart workloads where a partial result is fine from ones where it is worse than none.*

</details>


<br>

### Exercise 11 of 12

**● TASK**

A streaming pipeline reads about 5,000 listing events a minute from Kafka, sends each to a content-moderation API, and writes moderated listings to a warehouse. Compose all three failure paths on that call: 429 and 503 blips retried with backoff, 400s for malformed listings sent straight to a dead letter queue, and timeouts given a small retry budget, then dead-lettered. An outage lasting hours must halt the calls rather than drain every event's retries.

<details>
<summary><strong>Solution</strong></summary>

#### Three failures, three destinations

Composing the failure patterns means one stage makes three decisions at once. Every response from the moderation API falls into a class, and each class has exactly one destination: success goes to the warehouse, a permanent 400 goes to the dead letter queue on its first attempt, and a transient or ambiguous error goes back through the retry budget, which hands it to the dead letter queue only when the budget runs out.

1. **Classify before you retry**

   A 400 says the listing is malformed, so retrying it only spends API calls on an event that will fail every time: route it out immediately. A 429 or 503 is the API asking you to come back shortly, so it earns exponential backoff with jitter.

2. **Give timeouts a small budget**

   A timeout is ambiguous: the API may just be slow, or this listing may hang it. Three tries with backoff resolve the slow case; a listing still timing out after that is treated as permanent and dead-lettered, so one poison listing cannot stall its partition.

3. **Let the breaker guard the budget**

   In a three-hour outage, every listing would exhaust its retries and pile into the dead letter queue even though nothing is wrong with it. The breaker opens after repeated failures and pauses consumption; Kafka holds the backlog, and processing resumes from the last committed offset once a probe call succeeds.

```mermaid
flowchart LR
    n0[("listing_events<br/>(Kafka)")]
    n1["moderate_with_circuit_breaker<br/>(Flink)<br/>Retries: 3 · Backoff: exponential"]
    n2[/"listing_dead_letter_queue<br/>(Kafka)"/]
    n3[("listings_warehouse<br/>(warehouse)")]
    n0 --> n1
    n1 --> n3
    n1 --> n2
```

*`moderate_with_circuit_breaker` retries blips and timeouts with backoff, sends 400s and exhausted retries to `listing_dead_letter_queue`, and writes successes to `listings_warehouse`.*

| Pitfall: One retry loop for every error wastes the budget twice |
| --- |
| Wrapping the call in a single retry policy retries 400s that can never succeed. Without a breaker, it also turns a long outage into thousands of dead-lettered listings that only needed to wait. Each error class needs its own path, and the breaker decides when the retry path is worth trying at all. |

**Follow-up questions**

1. Replays from the dead letter queue could write a listing to the warehouse twice. What makes the warehouse write safe to repeat?\
   *Connects dead-letter replay to idempotent writes.*
2. The API starts returning 429 at 150 requests a second instead of 200. Which part of the design absorbs that, and which part should not react to it?\
   *Separates rate-limit backoff from breaker-worthy outages.*

</details>


<br>

### Exercise 12 of 12

**● TASK**

A streaming pipeline reads about 2,000 signup events a minute from Kafka, sends each to a fraud-scoring API, and writes the scored signups to a warehouse. Retry transient API errors under a budget of at most 4 attempts and 2 minutes total per event. The API sometimes goes down for 20 minutes at a time: put a circuit breaker in front of it so the pipeline stops calling it during the outage instead of spending every event's retry budget. Events rejected as invalid, or still failing when their budget runs out, must go to a dead letter queue, never dropped.

<details>
<summary><strong>Solution</strong></summary>

#### Let the breaker spend the outage, not the retries

A retry budget and a circuit breaker answer different failures, and this pipeline needs both, plus a dead letter queue for what neither fixes. The budget covers one call that hiccups: a timeout or a 503 that clears on the next attempt. The breaker covers a service that is down for everyone. Without it, a 20-minute outage at 2,000 events a minute means 40,000 events each spending 4 attempts and up to 2 minutes: roughly 160,000 calls into a dead service, then 40,000 perfectly good signups dumped in the DLQ.

1. **Bound each event's retries**

   Set the budget on the scoring call itself: at most 4 attempts, and a 2-minute ceiling on the total time one event may spend retrying. The attempt cap alone is not enough, because growing waits can stack past what the events queued behind it can tolerate. Retry only what can clear on its own, timeouts and 503s. A 400 means the payload is bad, and another try will not change that.

2. **Trip the breaker before the budget burns**

   The breaker watches the scoring call's failures. Closed, calls flow normally. When failures stay high it opens: no calls go out and the worker stops pulling from the topic, so events wait in Kafka with their budgets untouched. After a cool-down it goes half-open and lets a few probe calls through; success closes it, failure opens it again. That is why `fraud_api_circuit_breaker` sits in front of `fraud_scoring_worker`: it decides whether an event is sent to the API at all.

3. **Dead-letter only what the budget cannot fix**

   2 kinds of event reach `fraud_score_dlq`: one the API rejects as invalid, sent straight there with no retries, and one still failing after 4 attempts or 2 minutes while the breaker was closed. Both keep the stream moving and both are kept for inspection. Neither is an outage casualty, because while the breaker was open nothing was attempted.

```mermaid
flowchart LR
    n0[("signup_events<br/>(Kafka)")]
    n1["fraud_api_circuit_breaker<br/>(custom)"]
    n2["fraud_scoring_worker<br/>(transform)<br/>Retries: 4"]
    n3[("scored_signups_warehouse<br/>(warehouse)")]
    n4[/"fraud_score_dlq<br/>(Kafka)"/]
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n2 --> n4
```

*Signups pass `fraud_api_circuit_breaker` into the retrying `fraud_scoring_worker`. Scored events land in the warehouse, unrecoverable ones in `fraud_score_dlq`.*

| Pitfall: Retries alone turn an outage into a DLQ flood |
| --- |
| The common draft puts a retry policy and a DLQ on the scoring call and stops there. It looks complete, but in a sustained outage every event exhausts its budget against a dead API and lands in the DLQ. The queue meant for genuinely bad events fills with 40,000 good ones that someone must replay by hand. The breaker is what keeps the DLQ meaningful. |

**Follow-up questions**

1. The API recovers and the half-open probes succeed. How do the 40,000 backlogged events get scored without knocking it over again?\
   *Draining a backlog with jitter and a bounded rate so recovery does not trigger a second outage.*
2. The fraud team fixes the payload format and wants dead-lettered signups replayed. What does the replay path need so no signup is written to the warehouse twice?\
   *Replaying from a DLQ combined with idempotent writes to the warehouse.*

</details>
