# Failure Handling: Advanced - Exercises

Lesson: [pa_failure_modes_advanced.md](../pa_failure_modes_advanced.md)

### Exercise 1 of 12

**● TASK**

Add three failure classifiers (quality gates) to this order pipeline, one each for the read, processing and write surfaces, and name each with that surface's failure modes and the response each mode gets. Transient modes get a bounded retry with exponential backoff, poison records and exhausted retries route from the classifiers to a dead letter queue, and failures no retry can fix page on-call.

**Starting canvas** (already placed for you):

- Kafka order_events source (read-side) (source, Kafka)
- enrich_orders worker (processing-side) (transform, Pandas)
- Iceberg orders_enriched (write-side) (storage, Iceberg)
- Orders dashboard (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

#### The failure surface decides the retry

**Failure classification** means you name what can break at each surface before you pick a single retry setting. Every node touches the world three times: it reads, it processes, it writes. Each of those breaks in its own ways, and each way needs its own response. One try/except around `enrich_orders` collapses all three into one answer, so a permanent break gets retried until the budget runs out and a transient blip gets escalated like a disaster. Three classifier markers keep the surfaces apart and pair every mode with the response that actually fits it.

| Trick: One question sorts every mode |
| --- |
| For each failure mode ask: can waiting and trying again fix it? Source down, table down, 'partition locked', a dependency timeout: yes, so a bounded retry with exponential backoff, and the record goes to the dead letter queue once the budget is spent. 'schema changed', a poison pill, 'constraint violated' on a malformed row: never, so the record goes straight to the dead letter queue and the stream keeps moving. Auth expired, a revoked write permission or a code bug: no retry fixes it and no single record is at fault, so page a human. |

```mermaid
flowchart LR
    subgraph L0["Read"]
        n0[("order_events<br/>(Kafka)")]
        n1["read classifier: source down -#62; retry 5x backoff; auth expired -#62; page; schema changed or retries exhausted -#62; DLQ<br/>(custom)<br/>On error: retry · Retries: 5 · Backoff: exponential"]
    end
    subgraph L1["Process"]
        n2["enrich_orders<br/>(Pandas)"]
        n3["processing classifier: dependency timeout or memory blip -#62; retry 3x backoff; poison pill or retries exhausted -#62; DLQ; code bug -#62; page<br/>(custom)<br/>On error: retry · Retries: 3 · Backoff: exponential"]
    end
    subgraph L2["Write"]
        n4["write classifier: table down or partition locked -#62; retry 5x backoff; constraint violated or retries exhausted -#62; DLQ; write permission revoked -#62; page<br/>(custom)<br/>On error: retry · Retries: 5 · Backoff: exponential"]
        n5[("orders_enriched<br/>(Iceberg)")]
        n6(["Orders dashboard<br/>(dashboard)"])
    end
    subgraph L3["Recovery"]
        n7[/"orders dead letter queue<br/>(Kafka)"/]
        n8(["on-call alert<br/>(alerting)"])
    end
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n4 --> n5
    n5 --> n6
    n1 --> n7
    n3 --> n7
    n4 --> n7
    n1 --> n8
    n3 --> n8
    n4 --> n8
```

*One classifier per surface, each naming its modes and responses: transient modes retry with exponential backoff, poison and exhausted records go to the dead letter queue, unfixable modes page on-call.*

| ✕ Retry can fix it | ✓ Retry never fixes it |
| --- | --- |
| Read: source briefly down. Processing: a memory blip or a dependency timeout. Write: table down, 'partition locked'. Response: a bounded retry with exponential backoff. The bound matters: when it is exhausted the record leaves the main path for the dead letter queue instead of spinning forever. | Read: 'schema changed' so the record no longer parses. Processing: a poison pill that throws on every attempt. Write: 'constraint violated' by a malformed row. Response: straight to the dead letter queue. Auth expired, a revoked write permission and code bugs are not the record's fault, so they page on-call. |

| Pitfall: A blanket retry treats poison like a blip |
| --- |
| The first draft is usually one `for attempt in range(3)` around the whole worker. A single 'schema changed' record burns all three attempts, throws, and in an ordered stream stalls every record behind it. An expired credential gets retried three times and still fails, when only a human refreshing the token helps. The response has to be chosen per mode, which is why each marker names the mode and the response together. |

On a real team, this classification is what the runbook is built from. When the page fires at 3am, the marker that sent it already says which surface broke and why, so the responder knows whether to refresh a credential, wait out an Iceberg lock, or leave a quarantined record for the morning. Separating read from write also means a write outage retries only the write, not a re-read of Kafka.

**Follow-up questions**

1. What retry budget and backoff would you give the write surface so a 'partition locked' retry outlasts a routine table maintenance window?\
   *Sizing a retry budget from the failure mode's expected duration.*
2. A dependency returns HTTP 429 on some calls and HTTP 400 on others. Which classifier handles each, and does either belong in the retry path?\
   *Classifying 2 modes from the same dependency differently.*
3. How would you add a fourth failure mode, 'data arrived late', to the read classifier, and what response fits it?\
   *Extending the classification to a mode that is neither transient nor poison.*

</details>


<br>

### Exercise 2 of 12

**● TASK**

Records that `enrich_worker` fails to process are currently lost. Divert them to a dead letter queue, then read that queue as a quality signal: a stream job computing the per-second arrival rate by exception type, a metrics store keeping the rolling baseline, and a paging destination that fires when a type's rate deviates from that baseline by a high z-score.

**Starting canvas** (already placed for you):

- Kafka events source (source, Kafka)
- enrich_worker (transform, Flink)
- enriched_orders (storage, warehouse)

<details>
<summary><strong>Solution</strong></summary>

#### The DLQ is a stream, not a mailbox

A dead-letter queue starts life as a safety net: every record `enrich_worker` gives up on is diverted there instead of being dropped or blocking the partition, with an envelope that carries the diagnosis (`failed_at`, `exception_type`, `attempt_count`, `correlation_id`). Read **as a quality signal**, that same queue becomes the earliest warning the pipeline has. A queue drained by hand once a week throws the signal away; the design you drew reads it continuously and turns its arrival pattern into a rate per failure reason, a stored history, and an alarm when today breaks from the recent past.

```mermaid
flowchart LR
    n0[("Kafka events source<br/>(Kafka)")]
    n1["enrich_worker<br/>(Flink)"]
    n2[("enriched_orders<br/>(warehouse)")]
    n3[/"orders dead letter queue<br/>(Kafka)"/]
    n4["dlq_rate_aggregator<br/>(Flink)"]
    n5[("metrics store<br/>(storage)")]
    n6(["z-score pager<br/>(alerting)"])
    n0 --> n1
    n1 --> n2
    n1 --> n3
    n3 --> n4
    n4 --> n5
    n5 --> n6
```

*Failures leave the main path on an error edge into the dead letter queue; the aggregator, metrics store and pager hang off it. The enrichment path to `enriched_orders` is untouched.*

1. **Divert failures, then count them by reason per second**

   Route every record `enrich_worker` cannot process onto an error path into the dead letter queue, then attach `dlq_rate_aggregator` as a stream consumer of that queue. It keys each record by `exception_type` and counts arrivals in a one-second tumbling window, emitting (timestamp, `exception_type`, rate). The per-second grain is what lets a spike show up in seconds instead of being smeared across a day.

2. **Land the rates in a time-series store**

   The rates land in the metrics store. Its rolling history IS the baseline: to know that 40 `ValidationError` per second is abnormal, you need to remember this stream normally sits near 2. No history, no baseline, no anomaly detection.

3. **Alert on deviation from the rolling baseline**

   The pager reads recent history per `exception_type`, computes a rolling mean and standard deviation, and fires when `(rate - mean) / stddev` crosses a threshold (say 3). Because the alarm is per type, it names the failure mode: a `ValidationError` spike points at a producer schema change, an `AuthError` spike at an expired credential, a slow climb in `TimeoutError` at a degrading downstream.

| Trick: The breakdown by `exception_type` is the whole game |
| --- |
| A single total DLQ rate only says failures went up. Keying by `exception_type` turns a smoke alarm into a diagnosis: each failure mode gets its own baseline and its own z-score, so the page names the cause. |

| ✕ Static threshold | ✓ Rolling z-score |
| --- | --- |
| "Alert if rate > 100/s" is one number for every stream. It floods you on a high-volume type where 100/s is normal and stays silent on a low-volume type where 5/s is a fire. | `(rate - mean) / stddev` normalizes each `exception_type` against its own recent behavior, so one rule covers every failure mode and adapts as traffic shifts. |

| Pitfall: A baseline held in memory forgets on restart |
| --- |
| Skipping the metrics store and alerting straight off the queue keeps the baseline in memory, where it dies on every restart or rebalance, exactly when history matters most. Persisting rates first also lets you look back after an incident to see when the drift began. |

**Follow-up questions**

1. Traffic has a daily cycle, so 2am and 2pm have very different baselines. How do you keep the z-score from firing every morning?\
   *Pushes toward seasonal baselines (hour-of-day, day-of-week) instead of a flat rolling window.*
2. What should the page carry besides the rate, so the on-call engineer can act immediately?\
   *Attaching sample `correlation_id` values and the `exception_type` makes the page itself diagnostic.*
3. A brief downstream blip spikes `TimeoutError` then recovers. How do you avoid paging for something that self-heals?\
   *Sustained-deviation logic: require the z-score to hold for N consecutive windows.*

</details>


<br>

### Exercise 3 of 12

**● TASK**

Turn the orders DLQ into a recovery surface: add a replay transform off it whose name covers its three jobs, inspection (payload, exception, attempts), annotation (edit a payload with an audit trail) and bounded replay (throttled, with a dry-run). Replays write idempotently into the enriched orders warehouse. Send any replay that fails a second time to a separate side-channel destination, never back into the DLQ.

**Starting canvas** (already placed for you):

- orders_dlq (source, Kafka)
- orders_enriched (storage, warehouse)

<details>
<summary><strong>Solution</strong></summary>

#### A dead-letter queue is only as good as its drain

The transform you hung off `orders_dlq` is a **replay tool**, the piece that turns a dead-letter queue from a graveyard into a buffer you can recover from. It earns the name by doing three jobs, inspection, annotation and bounded replay, by writing idempotently, and by having somewhere safe to send a message that fails again.

```mermaid
flowchart LR
    n0[("orders_dlq<br/>(Kafka)")]
    n1["inspect_annotate_bounded_replay<br/>(transform)<br/>Idempotency: upsert"]
    n2[("orders_enriched<br/>(warehouse)")]
    n3[("replay_failures<br/>(storage)")]
    n0 --> n1
    n1 --> n2
    n1 --> n3
```

*`inspect_annotate_bounded_replay` reads `orders_dlq`, upserts into `orders_enriched`, and sends anything that fails again to `replay_failures`, never back to `orders_dlq`.*

1. **Inspection: decode the envelope first**

   The DLQ record is an envelope, not a bare payload: it carries the original message, the exception that killed it, and the attempt count. Reading all three tells an operator WHY it dead-lettered before they act, so replay is not blind.

2. **Annotation: edit with an audit trail**

   Messages that died on bad data need the payload fixed before replay. Annotation allows that, but records who changed what and from what original, so you never silently mutate production data you cannot later explain.

3. **Bounded replay: throttle and dry-run**

   An hour of backlog is a flood. Replaying it wide-open turns it into a thundering herd against a downstream already struggling. Bounded replay caps the batch rate, offers a dry-run, and drains in controlled waves.

| Trick: Idempotency is the other half of replay |
| --- |
| Replay is safe only because the replay write is idempotent: `inspect_annotate_bounded_replay` upserts into `orders_enriched` on the order key. Re-delivering a message that DID succeed but dead-lettered on a timeout is harmless, because the upsert collapses the duplicate. Drop the idempotent write and every replay risks double-counting an order. |

| Pitfall: A second failure must not re-enter the source |
| --- |
| The shortcut is to let a re-failed replay flow back into `orders_dlq`. That is an infinite loop: the same poison message drains, fails, and re-enters forever, so the queue never empties and you cannot tell 'drained' from 'stuck'. `replay_failures` breaks the loop into a small, human-sized set to investigate. |

**Follow-up questions**

1. What signal separates a code bug from bad data in `replay_failures`?\
   *The second-attempt exception versus the first is the tell; treat the side channel as triage, not a graveyard.*
2. How would you make bounded replay resumable if the replay transform crashes mid-drain?\
   *Pushes on batch processing plus offset and attempt tracking so a restart resumes instead of replaying everything.*

</details>


<br>

### Exercise 4 of 12

**● TASK**

A producer streams events through an unbounded queue to a worker pool, and the service the workers call has slowed from 100ms to 2 seconds. Make the queue bounded with a blocking put, so a full queue backpressures the producer instead of growing memory until it crashes. Add a load shedder between the producer and the queue that diverts events whose put waited too long into a dead letter queue instead of losing them.

**Starting canvas** (already placed for you):

- producer (source)
- unbounded queue (queue)
- worker pool (transform)
- slow downstream service (consumer, API)

<details>
<summary><strong>Solution</strong></summary>

#### Backpressure: the queue that pushes back

Backpressure is the rule that a slow consumer gets to slow its producer down. A queue with a `maxsize` and a blocking `put()` applies it. Once the worker pool cannot drain fast enough, the queue fills and the next `put()` **waits** for a free slot. "Memory grows without limit" becomes "the producer waits", and that wait travels backward stage by stage instead of one process exhausting its memory and toppling the rest.

```mermaid
flowchart LR
    n0[("producer<br/>(source)")]
    n1["load shedder diverts after put timeout<br/>(quality_gate)"]
    n2[/"bounded queue with blocking put<br/>(queue)"/]
    n3[/"dead letter queue<br/>(queue)"/]
    n4["worker pool<br/>(transform)"]
    n5(["slow downstream service<br/>(API)"])
    n0 --> n1
    n1 --> n2
    n1 --> n3
    n2 --> n4
    n4 --> n5
```

*The shedder calls a blocking `put()` with a timeout. A full queue stalls it, and an event that waits past the timeout goes to the dead letter queue instead of piling up upstream.*

Blocking alone only moves the pressure: the producer now stalls, and whatever feeds it starts to fill its own queue. Load shedding puts a bound on that stall. The shedder sits on the source side and attempts the blocking `put()` with a timeout. When the timeout expires, it hands the event to a dead letter queue instead of discarding it. The cascade stops at the edge of the pipeline, and the shed events wait somewhere you already know how to replay from once the service is back to 100ms.

| Pitfall: An unbounded queue hides the failure, it doesn't prevent it |
| --- |
| It's tempting to call an unbounded queue "resilient" because `put()` never fails. It's the opposite: an instant `put()` is the pipeline lying about its capacity. Every un-drained item sits in memory, so a downstream that goes from 100ms to 2s doesn't slow the producer. It grows the queue until the process runs out of memory, the producer dies, and the cascade runs backward. A `maxsize` turns that invisible leak into an honest, observable wait. |

| ✕ Blocking (backpressure) | ✓ Load shedding |
| --- | --- |
| A full queue makes `put()` wait until a slot opens. Nothing is lost, and the producer is throttled to the consumer's real rate. This is the right default for every queue between 2 stages. | When the wait itself is unacceptable, the source stops waiting (`put()` with a timeout) and takes the event off the hot path. Latency stays flat. Sending the event to a dead letter queue rather than dropping it keeps it recoverable once the downstream catches up. |

**Follow-up questions**

1. During a long slowdown the dead letter queue grows too. When is it acceptable to drop shed events outright instead?\
   *Telemetry or live-state feeds can afford to lose stale events; order or billing events cannot, so their shed path needs durable room.*
2. The downstream recovers to 100ms. How does a blocking `put()` design return to full throughput on its own?\
   *Backpressure relieves itself: once workers drain faster than the producer fills, `put()` stops waiting with no operator action.*

</details>


<br>

### Exercise 5 of 12

**● TASK**

A Geo-IP config change pushed enrichment p99 from 80ms to 4 seconds, and with nowhere durable to put clicks it could not enrich, the worker lost 3 hours of events to Kafka's 24-hour retention. Redesign the failure handling: route clicks that fail enrichment to a durable dead-letter queue and retry them from there once Geo-IP recovers, put a data-quality check on that queue, and page on-call when it grows, well inside the retention window.

**Starting canvas** (already placed for you):

- Web app clickstream source (source, API)
- Kafka raw_clicks topic (24-hour retention) (queue, Kafka)
- Enrich and write worker (no retry, no dead-letter path) (transform, Flink)
- Geo-IP enrichment service (config change pushed p99 from 80ms to 4s) (source, API)
- enriched_clicks store (idempotent inserts) (storage, Redshift)
- Product analytics dashboards (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

#### The failure a dead-letter queue prevents

A dead-letter queue is a durable side channel. When the `Enrich and write worker` can't finish a click, it writes that click somewhere it will survive instead of holding it in memory or dropping it. That single move is what the old pipeline lacked. When Geo-IP's p99 jumped from 80ms to 4s, the worker stalled and `raw_clicks` kept filling. Once the 24-hour retention window rolled past the backlog, 3 hours of events were gone with no copy anywhere.

```mermaid
flowchart LR
    n0[/"raw_clicks topic<br/>(Kafka)"/]
    n1["Enrich and write worker<br/>(Flink)"]
    n2[("Geo-IP enrichment service<br/>(API)")]
    n3[("enriched_clicks store<br/>(warehouse)")]
    n4[/"dead_letter topic<br/>(Kafka)"/]
    n5["DLQ depth quality check<br/>(quality_gate)"]
    n6(["On-call alerting<br/>(consumer)"])
    n0 --> n1
    n1 --> n2
    n1 --> n3
    n1 --> n4
    n4 --> n1
    n4 --> n5
    n5 --> n6
```

*Failed enrichments land in the `dead_letter` topic and drain back for retry. A depth check on that topic pages on-call.*

| Pitfall: Retry in the hot path is not durability |
| --- |
| The tempting fix is to wrap the Geo-IP call in a retry loop. But retrying in-line against a service that is now 4s slow makes the worker slower still, and the un-enriched clicks are **still** only in `raw_clicks`, still racing the retention clock. Retry belongs on the `dead_letter` topic, drained back through the worker once Geo-IP recovers, not in the ingest path. |

| Key insight: The DLQ decouples failure from retention |
| --- |
| Once failed clicks land in a durable `dead_letter` topic, the enrichment outage stops being a data-loss clock. The clicks wait as long as you need, the worker keeps draining `raw_clicks` at full speed, and you reprocess when Geo-IP recovers. |

Durability alone isn't enough: a `dead_letter` topic that grows silently is just a slower way to lose data. The data-quality check watches its depth and fill rate, and the alert has to fire with enough lead time that on-call acts **before** the 24-hour retention on the source topic can expire anything. That lead-time budget is the whole reason you page early rather than on a threshold you happen to notice.

**Follow-up questions**

1. When Geo-IP recovers and you drain `dead_letter` back through the worker, what stops a click being written to `enriched_clicks` twice?\
   *Tests whether idempotent inserts make reprocessing safe to repeat.*

</details>


<br>

### Exercise 6 of 12

**● TASK**

Redesign a clickstream pipeline so the next latency spike, schema drift, credential rotation, downstream outage, and producer-side burst do not cause an outage. Compose every advanced-tier pattern: failure-surface classification on each node; retry budget plus circuit breaker around every external call; DLQ with envelope; DLQ-as-quality-signal monitoring (rate by exception type with z-score alerts); DLQ replay tooling with a second-failure side channel; bounded queues with backpressure; load-shedding on the source side. Route the dashboard through the resilient path.

**Starting canvas** (already placed for you):

- Web clickstream source (source, Custom)
- Kafka raw_clicks (currently unbounded) (storage, Kafka)
- Worker pool (no classification, no retry budget, no breaker, no DLQ) (transform, Python)
- Geo-IP service (storage, API)
- Clickhouse enriched_clicks (idempotent) (storage, Clickhouse)
- Product analytics dashboard (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

#### Resilience is routing: every failure gets a lane

You turned a fragile clickstream into one where a latency spike, schema drift, a rotated credential, a downstream outage, and a producer burst each become a routing decision instead of an outage. The spine that ties the 5 patterns together is failure-surface classification: on every node a failure is first labeled transient, poison, or downstream-down, and that one label picks its lane. Retry budget, circuit breaker, DLQ, bounded queues, and load-shedding are just the lanes.

```mermaid
flowchart LR
    subgraph L0["Ingest"]
        n0[("Web clickstream source (load-shedding)<br/>(Custom)")]
        n1[("Kafka raw_clicks (bounded)<br/>(Kafka)")]
    end
    subgraph L1["Process"]
        n2["Worker pool: classify + retry budget + breaker<br/>(Python)"]
        n3[("Geo-IP service<br/>(API)")]
        n4[("Clickhouse enriched_clicks (idempotent)<br/>(Clickhouse)")]
    end
    subgraph L2["Recover"]
        n5[("DLQ clicks_dead (enveloped)<br/>(Kafka)")]
        n6["DLQ monitor (z-score by exception type)<br/>(Custom)"]
        n7["Replay tool<br/>(Python)"]
        n8[("clicks_parking_lot (second-failure side channel)<br/>(Kafka)")]
    end
    subgraph L3["Serve"]
        n9(["Product analytics dashboard<br/>(dashboard)"])
    end
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n2 --> n4
    n2 --> n5
    n5 --> n6
    n5 --> n7
    n7 --> n1
    n7 --> n8
    n4 --> n9
```

*The dashboard reads only from idempotent `enriched_clicks`; every failure branches sideways into the recover layer, never forward to the dashboard.*

| Pitfall: The worker you started with treats every error the same |
| --- |
| With no classification, a slow `geoip_lookup`, a malformed event, and a Geo-IP outage all hit the same bare `except` and either crash the consumer or drop good data. Retrying a poison event forever wedges the partition; not retrying a transient timeout drops good rows. Both are the same bug: reacting before you classify. |

**The worker as a set of lanes**

```python
def handle(event):
    try:
        validate_schema(event)                 # poison if this raises
    except SchemaError as exc:
        publish_dlq(event, exc, klass="poison")
        return

    for attempt in range(RETRY_BUDGET):        # transient gets a bounded budget
        try:
            geo = breaker.call(geoip_lookup, event.ip)   # breaker fails fast when open
            clickhouse.upsert(enrich(event, geo))         # idempotent sink
            return
        except BreakerOpen as exc:
            publish_dlq(event, exc, klass="downstream_down")
            return
        except TransientError as exc:
            sleep(backoff(attempt))
            last = exc
    publish_dlq(event, last, klass="retry_exhausted")

def publish_dlq(event, exc, klass):
    envelope = {
        "payload": event.raw,
        "failure_class": klass,
        "exception_type": type(exc).__name__,
        "failed_at": now_iso(),
        "attempts": RETRY_BUDGET,
    }
    producer.send("clicks_dead", envelope)
```

*Classify first; the reaction (drop-to-DLQ, retry, fail-fast) falls out of the class. The envelope is what makes replay possible later.*

| Real world: The DLQ is a quality signal, not a graveyard |
| --- |
| Because every envelope carries `exception_type`, the monitor computes a rate per type and z-score alerts when one spikes: a jump in `SchemaError` means a producer shipped a new field; a jump in `downstream_down` means Geo-IP is down. When fixed, the replay tool re-injects events into `raw_clicks`; anything that fails again goes to `clicks_parking_lot` so a replay storm cannot loop back in. |

**Follow-up questions**

1. If the breaker is open and events pile into `clicks_dead` as `downstream_down`, how do you replay them WITHOUT re-tripping the breaker the moment Geo-IP recovers?\
   *Tests whether replay respects rate limits and breaker state rather than firing a thundering herd.*
2. What makes the `enriched_clicks` sink safe to replay into twice, and what breaks if it were not idempotent?\
   *Tests why at-least-once delivery from replay requires an idempotent sink.*

</details>


<br>

### Exercise 7 of 12

**● TASK**

A stream job reads shipment events from a queue, enriches each via a carrier API and writes to a warehouse. Classify its failures and give each class its own path: carrier timeouts are transient and retry with exponential backoff, up to 5 attempts; malformed events are poison and go straight to a dead letter queue; an expired carrier credential pages the on-call engineer. An event still timing out after its last attempt also goes to the dead letter queue.

<details>
<summary><strong>Solution</strong></summary>

#### Classify by cause, not by node

Failure classification sorts every way a node can fail by what will actually fix it, and that decides the node's exits. The carrier API fails in 2 ways that look alike in a log and need opposite answers. A timeout clears on its own, so it earns a retry with exponential backoff and a hard cap of 5 attempts. An expired credential fails the same way on every call, so retrying only delays the one fix that works: a person rotating it. Malformed events are a third class, poison. They will never succeed, so they leave the stream at once.

```mermaid
flowchart LR
    n0[/"shipment_events<br/>(Kafka)"/]
    n1[("carrier_api<br/>(API)")]
    n2["enrich_shipments<br/>(Flink)<br/>On error: retry · Retries: 5 · Backoff: exponential"]
    n3[/"dead_letter_queue<br/>(dead letter queue)"/]
    n4(["on_call_alerting<br/>(alerting)"])
    n5[("shipment_warehouse<br/>(warehouse)")]
    n0 --> n2
    n1 --> n2
    n2 --> n5
    n2 --> n3
    n2 --> n4
```

*Each failure class gets its own exit from `enrich_shipments`: bounded retries on the node, poison and exhausted events to `dead_letter_queue`, credential expiry to `on_call_alerting`.*

| Pitfall: A blanket retry turns poison into load |
| --- |
| The tempting design puts one retry policy on the whole job and stops there. A malformed event then burns 5 backed-off attempts before landing anywhere, holding up the events behind it. An expired credential spins every event through the full cap and never reaches a person. Classify first, then attach the retry only to the class that can recover. |

| Key insight: Exhausting retries is a classification too |
| --- |
| A timeout that survives 5 attempts has stopped behaving like a transient failure. Giving it the same dead letter destination as poison means the retry cap is a decision about where the event goes next, not the point where it silently disappears. |

**Follow-up questions**

1. The warehouse write sometimes fails on a locked partition and sometimes on a duplicate key. How do you classify each?\
   *Applies the same classification to the write surface of a node instead of the read.*
2. The carrier starts returning rate-limit responses during peak hours. Which class is that, and does it change the backoff?\
   *Checks that a new failure mode is placed by its cause rather than by the service it came from.*

</details>


<br>

### Exercise 8 of 12

**● TASK**

A stream job parses 40,000 smart-meter readings per second from a queue into a warehouse, and readings it fails to parse are currently skipped. Route those failures to a dead letter queue, then read the DLQ as a quality signal: compute its per-second arrival rate broken down by exception type, chart that rate on a dashboard, and page the on-call engineer when any one type's rate climbs.

<details>
<summary><strong>Solution</strong></summary>

#### A DLQ is a sensor, not a bin

Reading a dead letter queue as a quality signal means treating every entry as a data point about the system, not a chore to clear. A firmware wave that starts emitting a new timestamp format lands in the DLQ minutes after it ships, long before anyone notices gaps in the warehouse. The DLQ only tells you that if something computes its rate and breaks it down by exception type.

```mermaid
flowchart LR
    n0[/"meter_readings<br/>(Kafka)"/]
    n1["parse_readings<br/>(Flink)"]
    n2[("meter_warehouse<br/>(warehouse)")]
    n3[/"dead_letter_queue<br/>(dead letter queue)"/]
    n4["dlq_rate_by_exception<br/>(Flink)"]
    n5(["dlq_dashboard<br/>(Grafana)"])
    n6(["on_call_alert<br/>(alerting)"])
    n0 --> n1
    n1 --> n2
    n1 --> n3
    n3 --> n4
    n4 --> n5
    n4 --> n6
```

*Failures leave `parse_readings` for `dead_letter_queue`, and `dlq_rate_by_exception` turns the DLQ into per-type rates for a dashboard and a page.*

1. **Divert, then measure the rate**

   Sending `parse_readings` failures to `dead_letter_queue` keeps the bad readings, but size alone says little: 4 failures a second is normal noise at 40,000 readings a second. `dlq_rate_by_exception` counts arrivals per second keyed by exception type, so the background rate and a fresh regression stop being the same number.

2. **Put the signal in front of people**

   The per-type rates go to `dlq_dashboard` for anyone looking and to `on_call_alert` for when nobody is. Paging on one type's rate rising is what turns a day-fourteen discovery into a day-one fix.

| Pitfall: Total DLQ size hides a new failure type |
| --- |
| A fleet already failing 4 readings a second for a known reason absorbs a new failure at 2 a second without the total looking alarming. Broken down by exception type, the new type jumps from zero to 2 per second: an obvious spike. Alert on the total and the regression hides inside the baseline. |

| Real world: Each exception type points at an owner |
| --- |
| In practice a schema mismatch points at the producer team, a timeout at a downstream service, a malformed payload at a firmware release. A per-type chart tells you who to call before you open a single record. |

**Follow-up questions**

1. What changes if the rate is also broken down by firmware version?\
   *Adding a second dimension so a spike traces back to the rollout that caused it.*
2. How would you alert on an exception type that has never appeared before?\
   *Telling a brand-new failure type apart from growth in a known one.*

</details>


<br>

### Exercise 9 of 12

**● TASK**

A stream job reads payment webhook events from a queue, converts currencies and loads them into a warehouse; events it fails on already land in a dead letter queue, about 3,000 a day. Make that DLQ drainable: add an inspection view operators can filter by exception type, and a replay stage that applies their fixes and sends a chosen batch back into the input queue. Show replay progress on a dashboard.

<details>
<summary><strong>Solution</strong></summary>

#### A DLQ is only as good as its drain

Reprocessing from the DLQ is where a dead letter queue earns its keep: until someone can read, fix and resend those 3,000 events a day, they are lost payments with a storage bill. So the replay tooling sits on the canvas as real stages, an inspection view reading the DLQ and a replay stage writing back into the input queue, designed alongside the pipeline rather than improvised during an incident.

```mermaid
flowchart LR
    n0[("payment_webhooks<br/>(API)")]
    n1[/"webhook_queue<br/>(Kafka)"/]
    n2["currency_converter<br/>(Flink)"]
    n3[("payments_warehouse<br/>(warehouse)")]
    n4[/"dead_letter_queue<br/>(dead letter queue)"/]
    n5(["dlq_inspection_view<br/>(API)"])
    n6["dlq_replay<br/>(Spark)"]
    n7(["replay_progress_dashboard<br/>(Grafana)"])
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n2 --> n4
    n4 --> n5
    n5 --> n6
    n6 --> n1
    n6 --> n7
```

*Failures from `currency_converter` land in the DLQ; `dlq_inspection_view` reads it, fixes flow into `dlq_replay`, which resends to `webhook_queue` and reports to `replay_progress_dashboard`.*

1. **Give operators a read path**

   The inspection view reads the dead letter queue directly and shows each failed event's payload, exception type, attempts and correlation ID, filterable by exception type. Operators decide what to replay here instead of writing queries against raw envelopes.

2. **Carry the fix into replay**

   The edge from the inspection view into the replay stage is the modify step: an operator patches a missing currency rate or annotates a malformed payload, then selects one event, a hundred, or every event of one exception type. That selection is the blast radius.

3. **Replay into the input queue**

   The replay stage writes into the same queue the live job reads, so replayed events get the same conversion, the same warehouse load, and the same route back to the DLQ if they fail again. Its progress feeds a dashboard, so a replay whose failure count climbs is stopped early.

| Pitfall: Replaying straight into the warehouse skips the job that failed |
| --- |
| Writing fixed events directly into the warehouse bypasses the currency conversion and leaves a still-broken event nowhere to go. Send replays through the input queue so the stream job stays the only writer and its DLQ route still catches repeat failures. |

**Follow-up questions**

1. How would finance tell replayed warehouse rows apart from live ones?\
   *Carrying an operator annotation from inspection through replay into the load.*
2. How would you replay every missing-rate failure from last Tuesday without touching newer ones?\
   *Bounding a replay by exception type and time range.*

</details>


<br>

### Exercise 10 of 12

**● TASK**

A sensor gateway pushes 20,000 readings per second straight into a stream job that writes them to a time-series store. When the store slows to 5,000 writes per second, the job's memory fills and the crash spreads back to the gateway. Redesign the path with backpressure so a 30-minute store slowdown buffers durably instead of crashing anything upstream, with no reading lost. In normal running, readings land within a minute.

<details>
<summary><strong>Solution</strong></summary>

#### Where the pressure lands

Backpressure only works if some component can absorb the wait. In this pipeline the original source cannot: sensors send on a fixed schedule, so a full buffer in the stream job's memory has nowhere to push back except into the gateway, and the gateway crashes. The fix is to **end the backpressure chain at a durable log**. The gateway appends and moves on, the stream job reads at whatever rate the store accepts, and the difference piles up on disk instead of in anyone's heap.

```mermaid
flowchart LR
    n0[("sensor_gateway<br/>(API)")]
    n1[/"readings_log<br/>(Kafka)"/]
    n2["write_job<br/>(Flink)"]
    n3[("time_series_store<br/>(Cassandra)")]
    n0 --> n1
    n1 --> n2
    n2 --> n3
```

*The gateway appends to `readings_log`; `write_job` pulls at the store's pace, so a slowdown grows the log, not anyone's memory.*

1. **Put a durable log between gateway and job**

   The gateway's only job becomes appending to `readings_log`. An append is cheap and does not depend on how fast anything downstream reads, so the gateway's health no longer depends on the store's.

2. **Let the job pull at the store's pace**

   `write_job` consumes from the log and caps its in-flight writes. When the store slows, the job simply reads less often and its position falls behind the head of the log. That lag is backpressure made visible, and it is the only place the slowdown shows up.

| Performance: A 30-minute backlog fits on disk, not in memory |
| --- |
| Readings arrive at 20,000 per second and leave at 5,000, so the backlog grows by 15,000 per second: 27 million readings over 30 minutes, about 5.4 GB at 200 bytes each. A log keeps that across restarts, and once the store recovers to 30,000 writes per second the job drains the backlog in about 45 minutes while new readings keep arriving. |

| Pitfall: A bigger in-memory queue only delays the crash |
| --- |
| Raising the stream job's buffer size buys minutes, not safety. Holding 5.4 GB in a heap is the same crash later, and every buffered reading is lost when it happens. A bounded memory buffer with nothing durable behind it just hands the wait to a gateway that cannot wait. |

**Follow-up questions**

1. An anomaly detector now needs the same readings but runs slower than `write_job`. Where should it read from?\
   *Independent consumers on one log: each falls behind on its own position without slowing the other.*
2. The log keeps one hour of data and the store stays slow for 3 hours. What happens?\
   *Retention is the edge of the durable buffer; past it, backpressure has nowhere left to land.*

</details>


<br>

### Exercise 11 of 12

**● TASK**

A stream job reads 8,000 ride events per second from a queue, calls a fare-pricing service per event, and writes the priced events to a warehouse. Its postmortem found that a two-hour pricing slowdown silently dropped every event whose first call failed. Apply the action items: retry pricing calls with exponential backoff up to a fixed limit, route events that exhaust retries to a dead letter queue, and page on-call when that queue grows.

<details>
<summary><strong>Solution</strong></summary>

#### A retry policy decides whether a failure stays transient

Retry handling is the action item this postmortem keeps returning to. With no retry policy, a two-hour pricing slowdown turned recoverable timeouts into two hours of lost rides. The fix is not to retry harder: at 8,000 events per second against a service sized for about 10,000 calls, immediate retries pile load onto the one dependency already struggling.

```mermaid
flowchart LR
    n0[/"ride_events<br/>(Kafka)"/]
    n1["price_rides<br/>(Flink)<br/>On error: retry · Retries: 5 · Backoff: exponential"]
    n2[("rides_warehouse<br/>(warehouse)")]
    n3[/"pricing_dead_letter_queue<br/>(dead letter queue)<br/>Alert: page if depth #62; 1000"/]
    n0 --> n1
    n1 --> n2
    n1 --> n3
```

*Priced events flow to the warehouse; events that exhaust 5 exponential retries in `price_rides` go to a dead letter queue that pages on-call as it grows.*

1. **Back off exponentially, then stop**

   Set the pricing stage to retry with an exponential `retryBackoff` and a fixed `retryCount`. Growing waits give a slow service room to recover instead of stacking a second wave of calls on it, and the cap guarantees every event eventually leaves the retry loop. A two-hour outage is longer than any sane retry window, which is why the next step exists.

2. **Give exhausted events a durable exit**

   An event that runs out of attempts is not garbage: the ride happened and finance needs its fare. Route it from the pricing stage to a dead letter queue so the original payload survives and can be replayed once pricing is healthy. Retry and DLQ are one design: the cap is safe only because the exit exists.

| Pitfall: A retry with no limit is a second outage |
| --- |
| The tempting post-incident fix is to retry forever. Unbounded retries pin a worker on one event, the source queue backs up behind it, and every attempt adds load while pricing is down. A malformed ride ID that can never price blocks the stream outright. |

| Key insight: The page is what makes the DLQ worth having |
| --- |
| In the incident nobody noticed until finance did. A `monitorAlert` on the dead letter queue, paging when its depth climbs, turns a silent pile of failures into a signal within minutes while the events are still safe to replay. |

**Follow-up questions**

1. Pricing starts returning an error for malformed ride IDs that will never succeed. Should those be retried at all?\
   *Separating permanent failures from transient ones before the retry loop.*
2. The outage lasts 6 hours instead of two. How do you drain the dead letter queue without recreating the overload?\
   *Rate-limited replay against a recovering dependency.*

</details>


<br>

### Exercise 12 of 12

**● TASK**

A stream job reads 15,000 inventory events per second, published by three fulfillment services to a queue, and writes them to a warehouse. Last week its dead letter queue jumped from 40 to 6,000 records an hour, nearly all 'missing field' errors from one service, while timeouts stayed flat. Redesign it so a validation check sends contract violations to the dead letter queue, the stream job retries timeouts with exponential backoff before parking them in the dead letter queue, a monitor on the dead letter queue pages when one error type's hourly rate spikes, and a replay tool sends fixed records back through validation.

<details>
<summary><strong>Solution</strong></summary>

#### Read the dead letter queue by error type, then act on what it says

A dead letter queue becomes a quality signal the moment you read its growth per error type instead of its total depth. Here the total jumped 150x, but the split tells the whole story: 'missing field' errors from one service climbed while timeouts held at their usual trickle. That pattern is upstream contract drift, a permanent failure, and it calls for a different action than a transient one: stop retrying it, page the team that owns the producer, and replay once their fix ships.

```mermaid
flowchart LR
    n0[("fulfillment_services<br/>(API)")]
    n1[/"inventory_events<br/>(Kafka)"/]
    n2["contract_validation<br/>(quality_gate)"]
    n3["stream_job<br/>(Flink)<br/>Retries: 3 · Backoff: exponential"]
    n4[("inventory_warehouse<br/>(warehouse)")]
    n5[/"dead_letter_queue<br/>(Kafka)"/]
    n6(["dlq_growth_monitoring<br/>(consumer)<br/>Alert: page if one error type's hourly rate spikes"])
    n7["dlq_replay<br/>(transform)"]
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n2 --> n5
    n3 --> n5
    n5 --> n6
    n5 --> n7
    n7 --> n2
```

*Contract violations skip retries, timeouts retry and then park, and both the monitor and the replay tool read the dead letter queue.*

1. **Classify before you retry**

   A record missing a required field fails identically on every attempt, so `contract_validation` parks it on the first pass. Only the warehouse write timeout is transient, so only `stream_job` carries a `retryCount` of 3 with exponential backoff, and an exhausted retry lands in the same queue.

2. **Alert on the rate of one error type**

   Total depth hides the cause: 40 timeouts and 6,000 contract errors an hour look like one big number. `dlq_growth_monitoring` pages when a single error type's hourly rate spikes, which aims the page at the service whose release broke the contract.

3. **Replay through validation, not around it**

   After the producer ships its fix, `dlq_replay` pulls the parked records, lets someone patch or annotate them, and sends them back into `contract_validation`. A record that is still broken parks again instead of corrupting stock counts in the warehouse.

| Pitfall: More retries cannot fix a missing field |
| --- |
| The tempting reaction to a growing queue is raising the retry limit. For contract violations that multiplies load by the retry count, delays healthy events queued behind them, and still ends with the same records in the dead letter queue. |

| Real world: Error type plus producer names the owner |
| --- |
| Tag every parked record with its exception type and producing service. A spike confined to one pair right after a deploy is that team's contract break; a spike across every producer at once usually points at your own stream job or the warehouse. |

**Follow-up questions**

1. What changes if the drifted service keeps publishing broken events for two days before it ships a fix?\
   *Whether the dead letter queue retention and the replay tool are sized for a long backlog, and whether replay preserves update order per item.*
2. How would the design change if the missing field were optional and the stream job could fill a safe default?\
   *Reclassifying a failure from permanent to recoverable at validation, which shrinks what the dead letter queue has to hold.*

</details>
