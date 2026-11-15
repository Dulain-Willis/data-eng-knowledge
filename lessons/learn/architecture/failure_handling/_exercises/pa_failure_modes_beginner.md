# Failure Handling: Beginner - Exercises

Lesson: [pa_failure_modes_beginner.md](../pa_failure_modes_beginner.md)

### Exercise 1 of 10

**● TASK**

The nightly ingest_orders load hit four errors: HTTP 503 during a downstream CPU spike, HTTP 429 from a rate limiter, HTTP 401 from an expired service-account token, and a JSON parse error on one malformed row. Downstream of the ingest transform, add one quality-gate node per error, named with the error, then its bucket (transient or permanent), then the response that bucket calls for.

**Starting canvas** (already placed for you):

- Order events source (source, Kafka)
- ingest_orders transform (transform, Pandas)
- Orders warehouse (storage, warehouse)
- Orders dashboard (consumer, dashboard)

<details>
<summary><strong>Solution</strong></summary>

#### Name the bucket before you pick the response

Sorting failures into **transient vs permanent** comes down to one question you ask of every error: would the exact same request succeed if the pipeline simply ran it again later? If yes, the cause is a temporary condition and the failure is transient, so the response is to try again. If no, nothing about waiting will change the outcome, so the failure is permanent and the response is to stop trying and fix or set aside the thing that is broken.

```mermaid
flowchart LR
    n0[("Order events source<br/>(Kafka)")]
    n1["ingest_orders transform<br/>(Pandas)"]
    n2[("Orders warehouse<br/>(warehouse)")]
    n3(["Orders dashboard<br/>(dashboard)"])
    n4["503 CPU spike: transient, retry<br/>(quality_gate)"]
    n5["429 rate limit: transient, retry after the stated wait<br/>(quality_gate)"]
    n6["401 expired token: permanent, rotate credential and alert<br/>(quality_gate)"]
    n7["JSON parse error: permanent, quarantine the row<br/>(quality_gate)"]
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n1 --> n4
    n1 --> n5
    n1 --> n6
    n1 --> n7
```

*One classifier gate per error off `ingest_orders transform`, each naming the bucket and the response that follows from it.*

Run last week's four errors through that question. The '503' came from a downstream that was briefly overloaded; once the spike passes the same call works, so it is transient. The '429' is transient too: the rate limiter is saying not yet, and it even tells you how long to wait. The '401' is a bad credential, and the section lists that as permanent: the expired token fails identically on every attempt until someone rotates it. The malformed JSON row is permanent as well: parsing the same bytes gives the same error forever, so that one row is set aside while the rest of the load continues. Any response that stops retrying fits a permanent error: alerting a human, rotating the credential, quarantining or dead-lettering the row.

| Pitfall: One response for every error gives up nothing and fixes nothing |
| --- |
| Wrapping the whole transform in one blanket try-again rule treats every error as transient. It burns compute replaying a row that can never parse and a token that will never authenticate, and it delays the healthy rows behind them. The bucket decides the response, not a single counter. |

| ✕ Transient: 503, 429 | ✓ Permanent: 401, JSON parse |
| --- | --- |
| A temporary condition caused it, so the identical request will work later. Try again; for the '429', wait the time the server named first. | The input or the credential itself is wrong, so retrying changes nothing. Stop, rotate the credential or set the bad row aside, and let a human know. |

| Key insight: An ambiguous error starts transient and gets escalated |
| --- |
| A plain '500' does not say whether the downstream is briefly overloaded or truly broken. The pragmatic call from the section is to treat it as transient with a small budget, and escalate it to permanent once that budget is spent. |

**Follow-up questions**

1. A request fails with HTTP '500' and no other detail. Which bucket does it start in, and what moves it to the other one?\
   *The ambiguous row of the section's table: transient with a small budget, then permanent.*
2. A downstream returns '400 Bad Request' on one order payload. Transient or permanent?\
   *Applying the same would-it-work-next-time question to a new status code.*

</details>


<br>

### Exercise 2 of 10

**● TASK**

An order-enrichment pipeline calls a pricing API that returns 503 while its backend restarts, and the current enrich transform retries every exception forever with no wait. Replace it with a bounded retry: give the transform a retry count of 5, and name it for its fixed wait between attempts and the transient errors it catches. A permanent error such as a bad request must fail on the first attempt. It writes to the enriched orders table, which merges on the event id.

**Starting canvas** (already placed for you):

- Order events source (source, Kafka)
- Pricing API (returns 503 during downstream restarts) (source, API)
- enrich_prices: while-True loop, bare except, no sleep, no max_attempts (transform)
- Iceberg enriched_orders (idempotent: MERGE on event_id) (storage, Iceberg)

<details>
<summary><strong>Solution</strong></summary>

#### The retry that knows when to quit

What the transform needed is a **bounded retry**: call again a fixed number of times, wait between tries, then give up and let the error surface. 3 numbers make one correct: `max_attempts`, the `wait` between attempts, and the exact transient exception types you catch. One rule ties them together: only transient failures retry, and a permanent error propagates on the first hit. On the canvas the retry count of 5 lives in the transform's settings and its name carries the other two, so anyone reading the DAG knows the contract without opening the code.

```mermaid
flowchart LR
    n0[("Order events source<br/>(Kafka)")]
    n1[("Pricing API (returns 503 during downstream restarts)<br/>(API)")]
    n2["enrich_prices_wait_2s_transient_only<br/>(transform)<br/>Retries: 5"]
    n3[("Iceberg enriched_orders (idempotent: MERGE on event_id)<br/>(Iceberg)")]
    n0 --> n2
    n1 --> n2
    n2 --> n3
```

*A pricing `503` is absorbed by up to 5 attempts 2 seconds apart; a permanent `4xx` fails the record on the first try.*

**What you replaced**

```python
def enrich_prices(order):
    while True:
        try:
            return call_pricing_api(order)
        except Exception:
            pass  # every error, retried forever, no sleep
```

*The `while True` with a bare `except` retries a bad request as eagerly as a timeout, and never stops.*

**The bounded retry**

```python
import time
import requests

PRICING_URL = "https://pricing.internal/price"
TRANSIENT_STATUS = {502, 503, 504}


class TransientPricingError(Exception):
    pass


def enrich_prices_wait_2s_transient_only(order, max_attempts=5, wait=2):
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(PRICING_URL, params={"id": order["event_id"]}, timeout=10)
            if resp.status_code in TRANSIENT_STATUS:
                raise TransientPricingError(resp.status_code)
            resp.raise_for_status()   # permanent 4xx -> propagates
            return {**order, "price": resp.json()["price"]}
        except (requests.Timeout, requests.ConnectionError, TransientPricingError):
            if attempt == max_attempts:
                raise
            time.sleep(wait)
```

*3 numbers (`max_attempts=5`, `wait=2`, the transient tuple) and one rule: `raise_for_status()` lets a `4xx` escape the loop.*

| Pitfall: A bare except cannot tell a blip from a bug |
| --- |
| The trap in the original is `except Exception`. A `503` from a restarting dependency and a `400` from a malformed order both land in the same branch, so the malformed order is retried forever and the whole pipeline wedges on one poison record. Narrowing the catch to `(Timeout, ConnectionError, TransientPricingError)` is what makes `raise_for_status()` meaningful: a permanent error is never swallowed, it propagates on the first attempt. |

| Key insight: Idempotent writes are the permission slip to retry |
| --- |
| Retrying is only safe because the sink does a `MERGE on event_id`. If attempt 3 succeeds after attempts 1 and 2 timed out mid-write, you still get exactly one row per `event_id`. Without that idempotent write, a bounded retry would double-insert an order every time a response was lost after the write committed. |

**Follow-up questions**

1. The fifth attempt still gets a `503`. What should the run do with that order, and why is re-raising better than returning `None`?\
   *Tests what happens when the retry budget is exhausted.*
2. What has to change first if the sink were an append that did not `MERGE on event_id`?\
   *Tests whether retry safety depends on the idempotent write, not the loop.*

</details>


<br>

### Exercise 3 of 10

**● TASK**

500 workers call a pricing API every minute, and when a latency spike times them all out at once, their fixed one-second retry sends 500 retries back in one synchronized wave that turns the blip into an outage. Replace the fixed-delay retry stage with one named for its exponential backoff and jitter policy. Credential errors and malformed records will never succeed, so route those permanent failures to a quarantine node instead of retrying them.

**Starting canvas** (already placed for you):

- Order events (500 workers consume in parallel) (source, Kafka)
- call_pricing_api: retry on a fixed 1-second sleep (synchronizes all 500 workers) (transform, Python)
- Pricing API (external, overloaded by the synchronized retry wave) (consumer, API)
- Enriched order events (storage, PostgreSQL)

<details>
<summary><strong>Solution</strong></summary>

#### The retry became the load

A thundering herd is many clients getting knocked back at the same instant and then all retrying at the same instant. Your 500 workers timed out together during the blip, each slept a flat one second, and one second later 500 retries hit the pricing API as a single spike. The fix has 2 independent parts: make each worker wait a **different, growing** amount of time before retrying, and stop retrying failures that can never succeed.

| Pitfall: A fixed sleep shifts the wave, it doesn't spread it |
| --- |
| It is tempting to read a `sleep(1)` between attempts as 'backing off'. It isn't. A constant delay moves all 500 workers forward by the same second, so they stay in phase: the spike just lands a second later at the same height. Any policy that hands every worker the same delay leaves the herd intact. |

```mermaid
flowchart LR
    n0[("Order events<br/>(Kafka)")]
    n1["retry_with_exponential_backoff_and_jitter<br/>(Python)"]
    n2(["Pricing API<br/>(API)"])
    n3[("Enriched order events<br/>(PostgreSQL)")]
    n4[("Quarantine (dead-letter)<br/>(DLQ)")]
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n1 --> n4
```

*The fixed retry transform becomes `retry_with_exponential_backoff_and_jitter`, and permanent failures branch to a dead-letter path instead of looping.*

| Key insight: Jitter is the part that desynchronizes |
| --- |
| Exponential backoff grows the delay (1s, 2s, 4s), capped with `min(2 ** attempt, 30)` so a struggling API gets exponentially fewer requests while a recovered one is picked back up promptly. But backoff alone keeps the herd together: 500 workers on the same schedule double in lockstep and still arrive together. A random offset (`delay * random()`) makes one worker wait 3.2s and another 6.9s, smearing the spike into a smooth curve. **Backoff protects the API over time; jitter protects it at any single instant.** |

| ✕ Retry it (transient) | ✓ Quarantine it (permanent) |
| --- | --- |
| A timeout, a `503`, a dropped connection could plausibly succeed on a later attempt, so it belongs in the backoff-and-jitter loop. | A `401` from a bad credential or a malformed record fails identically every time. Retrying it just burns attempts and adds load forever. Route it once to the dead-letter path for a human or a repair job, and let the stream keep moving. |

**Follow-up questions**

1. How would you stop a message from retrying forever, even when the failure looks transient?\
   *Tests whether the learner caps attempts with a max-retries budget and drains exhausted messages to the same dead-letter path.*
2. What does full jitter (`delay * random()`) trade off against equal jitter (`delay/2 + random()*delay/2`)?\
   *Tests that full jitter spreads arrivals most aggressively while equal jitter keeps a guaranteed minimum wait.*

</details>


<br>

### Exercise 4 of 10

**● TASK**

Exponential backoff in one sentence: each successive retry waits roughly twice as long as the previous one (base * 2^attempt), capped at a maximum, with jitter applied. Without a cap the seventh retry waits 64 seconds, the tenth waits 512, the fifteenth waits 4 hours. The cap is non-optional. Compute the wait by replacing the retry transform with one whose name states the formula's three knobs: base, cap, and a jitter strategy.

**Starting canvas** (already placed for you):

- Order events source (source, Kafka)
- call_tax_api: retry with no cap (seventh wait = 64s, fifteenth wait = 4 hours) (transform, Python)
- Tax API downstream (storage, API)
- Iceberg enriched_orders (idempotent: MERGE on event_id) (storage, Iceberg)

<details>
<summary><strong>Solution</strong></summary>

#### Bounded exponential backoff

The retry transform you rewrote is **bounded exponential backoff with jitter**, and its new name says all three knobs out loud: a `base` delay, a `cap` that clamps the growth, and a jitter strategy. The wait for an attempt is `min(cap, base * 2 ** attempt)`, then jitter perturbs it so a fleet of workers doesn't wake in lockstep. The doubling makes it back off; the `cap` keeps the doubling from running away.

| Pitfall: The uncapped version is a time bomb |
| --- |
| The starter node computed `base * 2 ** attempt` with no `cap`. That looks fine early, but `2 ** attempt` grows without bound: the seventh wait is 64s, the tenth 512s, the fifteenth over 4 hours. A transient Tax API blip that clears in a minute leaves your consumer parked for an afternoon while Kafka lag climbs. The `cap` bounds worst-case latency. |

```mermaid
flowchart LR
    n0[("Order events source<br/>(Kafka)")]
    n1["call_tax_api: backoff(base=1s, cap=30s, full jitter)<br/>(Python)"]
    n2[("Tax API downstream<br/>(API)")]
    n3[("Iceberg enriched_orders (MERGE on event_id)<br/>(Iceberg)")]
    n0 --> n1
    n1 --> n2
    n1 --> n3
```

*The retry transform names its three knobs; the sink stays idempotent so replays are safe.*

**The wait, made concrete**

```python
import random

def backoff_delay(attempt, base=1.0, cap=30.0):
    capped = min(cap, base * 2 ** attempt)
    return random.uniform(0, capped)  # full jitter
```

*`min()` applies the cap; full jitter picks a point in `[0, capped]`.*

| Trick: Jitter is what prevents the thundering herd |
| --- |
| Deterministic `min(cap, base * 2 ** attempt)` makes every worker that failed at the same instant retry together, hammering the API in waves. **Full jitter** sleeps a random amount in `[0, capped]`, smearing retries across the window and breaking the correlation that turns a recoverable outage into a self-inflicted DDoS. |

Retries and idempotency are two halves of one design: once you retry, the same order event may be processed twice (the first call may have succeeded before the timeout). That is why the sink is a `MERGE on event_id`, not a blind `INSERT`. Backoff makes retries survivable upstream; idempotent writes make them survivable downstream.

**Follow-up questions**

1. After how many attempts should `call_tax_api` stop retrying and route the event to a dead-letter topic?\
   *Backoff bounds each wait, but you still need a max-attempts ceiling so a broken event doesn't loop forever.*
2. If the Tax API returns a 429 with a `Retry-After` header, how should that override the computed `cap`?\
   *Server-directed backoff should win over the client's own schedule.*

</details>


<br>

### Exercise 5 of 10

**● TASK**

Give transient errors capped exponential-backoff retries, but stop retrying three failures that never heal. Send an event missing a required field to quarantine storage a human can inspect, and an HTTP 401 to a paging tool instead of risking a lockout. Send a poison pill, a message that crashes the worker on every pull, and any event that exhausts its retries to a separate dead-letter queue so the queue keeps flowing. Wire each one from the worker on an error path.

**Starting canvas** (already placed for you):

- Kafka events source (source, Kafka)
- process_events transform (currently retries every error class indefinitely) (transform, Python)
- Iceberg processed_events (downstream sink) (storage, Iceberg)
- Events dashboard (consumer, dashboard)

<details>
<summary><strong>Solution</strong></summary>

#### When retrying can't change the outcome

Error routing by retry-ability is the idea behind what you drew. A retry only helps when something can change between attempts: a timeout, a briefly unavailable sink, a throttled call. Those failures are transient, so the worker retries them a capped number of times with exponential backoff, and an event that exhausts its retries falls through to the dead-letter queue instead of looping forever. A **deterministic** failure returns the identical result on every re-run, so retrying it burns cycles and can do real harm. All three failures here are deterministic, so each one skips the retry loop and leaves the worker on its own error path to a terminal home.

The destination follows who resolves the failure. A validation failure sees the same missing field on every attempt, so it goes to durable quarantine storage (an object store or a table) where a human inspects the bad record. A `401` keeps presenting the same wrong credential and can lock the account out, so it pages an on-call engineer who can rotate the secret. A poison pill crashes the worker on every pull and blocks every message behind it, so it goes to a dead-letter queue, which isolates the bad message and keeps the main queue flowing.

```mermaid
flowchart LR
    n0[("Kafka source<br/>(Kafka)")]
    n1["process_events worker<br/>(Python)<br/>On error: retry · Retries: 3 · Backoff: exponential"]
    n2[("Iceberg processed_events<br/>(Iceberg)")]
    n3(["Events dashboard<br/>(dashboard)"])
    n4[("Quarantine store<br/>(PostgreSQL)")]
    n5(["On-call alerting<br/>(alerting)"])
    n6[/"Dead-letter queue<br/>(Kafka)"/]
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n1 --> n4
    n1 --> n5
    n1 --> n6
```

*Three capped retries with exponential backoff on the worker for transient errors, then three error paths, each failure class routed to a home that matches how it gets resolved.*

| Pitfall: One retry loop for every error class |
| --- |
| The starter worker retries everything indefinitely. A poison pill re-crashes the worker and stalls the whole partition, and a `401` retried in a tight loop trips the account lockout you were trying to avoid. Even a transient error needs a cap: without one, an outage that outlasts the backoff turns into an endless loop. Retrying a deterministic failure never reaches a different result. It only spreads the damage from one bad record to the whole stream. |

| Real world: The DLQ is where debugging starts |
| --- |
| The dead-letter queue and the quarantine store are worklists, not graveyards. On-call replays the DLQ after a fix ships, and quarantined records become test cases for the schema check that let them through. An alert on DLQ depth is often the first sign that an upstream producer changed its payload. |

**Follow-up questions**

1. A throttled call returns 429 and a bad credential returns 401: how does the worker tell them apart before it decides whether to retry?\
   *Tests whether the learner classifies an error by its status before the retry decision, not after.*
2. What metadata would you attach to a quarantined validation record so a human can reproduce and fix it?\
   *Checks that quarantine storage carries the offset, the raw payload and the error, not just the rejected event.*

</details>


<br>

### Exercise 6 of 10

**● TASK**

A logistics ETL enriches Kafka shipment events against a route API that returns 503s while restarting, then writes them to a Snowflake mart the operations dashboard reads. Its enrich step treats every exception alike, retries on a fixed one-second clock across 200 workers, and loops forever on unparseable rows. Rebuild it so the enrich step's name states its retry policy (bounded attempts, capped exponential backoff, jitter, transient errors only), validation failures land in a quarantine store, auth failures page an on-call alert, poison pills go to a dead-letter queue, and the mart keeps feeding the dashboard.

**Starting canvas** (already placed for you):

- Kafka shipment_events (200 workers fan-in) (source, Kafka)
- Route lookup API (third-party; 503 during restarts) (source, API)
- enrich_routes: while-True bare except, fixed 1s sleep, no classification, no quarantine (transform, Flink)
- Snowflake shipments_enriched (idempotent: MERGE on shipment_id) (storage, Snowflake)
- Logistics dashboard (consumer, Looker)

<details>
<summary><strong>Solution</strong></summary>

#### The catch block that couldn't tell failures apart

What you rebuilt is **error classification**: before reacting to a failed enrichment, you name what KIND of failure it was. The old `enrich_routes` had one bare `except` that treated a route API `503`, a malformed shipment, an expired credential, and an unparseable poison row as the same event, then answered every one by sleeping a fixed second and looping. Three of those 4 never heal on retry, so the loop meant to ride out a brief restart spun forever.

| Pitfall: A fixed retry clock is a self-synchronizing herd |
| --- |
| All 200 workers retried on the same one-second clock, so failed rows hit the API in synchronized waves. The moment it recovered it took 200 simultaneous requests, fell over, and returned everyone another `503` on the same clock. Capped exponential backoff spreads the attempts; `jitter` randomizes each worker's wait so the herd never re-synchronizes. |

```mermaid
flowchart LR
    n0[("shipment_events_source<br/>(Kafka)")]
    n1[("route_lookup_source<br/>(API)")]
    n2["enrich_bounded_backoff_jitter_transient_only<br/>(Flink)"]
    n3[("shipments_mart<br/>(Snowflake)")]
    n4(["logistics_dashboard<br/>(dashboard)"])
    n5[("validation_quarantine<br/>(object storage)")]
    n6(["auth_failure_alert<br/>(alerting)"])
    n7[/"poison_pill_dead_letter<br/>(DLQ)"/]
    n0 --> n2
    n1 --> n2
    n2 --> n3
    n3 --> n4
    n2 --> n5
    n2 --> n6
    n2 --> n7
```

*One enrich stage, 4 exits: only transient errors loop back; each other class forks to a lane that matches its cause.*

Only transient errors, `503`s and timeouts, flow back into the loop, and `enrich_bounded_backoff_jitter_transient_only` fences even those: bounded attempts, exponentially growing waits, a cap so the wait never runs away, and jitter. Everything else forks by cause. A schema failure goes to `validation_quarantine`, a durable object store where it waits for inspection instead of blocking the stream. An auth failure routes to `auth_failure_alert`, because an expired credential needs a human, not a backoff. A row that exhausts its attempts is a poison pill and lands in `poison_pill_dead_letter`, so one bad message can never wedge the pipeline.

| Key insight: The stage name is the retry contract |
| --- |
| Spelling the policy into `enrich_bounded_backoff_jitter_transient_only` makes the guarantee auditable at a glance. Retrying is safe only because `shipments_mart` does a `MERGE` on `shipment_id`, so a re-delivered row updates in place instead of double-writing. |

**Follow-up questions**

1. If the route API starts returning `429` with a `Retry-After` header, where does that fit your classification?\
   *Checks whether rate-limiting is treated as transient but honors the server's clock instead of blind backoff.*

</details>


<br>

### Exercise 7 of 10

**● TASK**

A job pulls JSON order documents from a partner API and loads them into a warehouse. Warehouse writes sometimes time out during restarts, and some documents are malformed and will never parse. Retry the timed-out writes up to 3 times, never retry a malformed document, and set aside malformed documents and writes still failing after the last attempt in a quarantine store.

<details>
<summary><strong>Solution</strong></summary>

#### Name the bucket, then pick the response

Every failure in this pipeline lands in one of 2 buckets, and the bucket decides what the pipeline does next. A warehouse write that times out during a restart is **transient**: the same request succeeds a minute later, so trying again is correct. A malformed JSON document is permanent: the partner sends the same bytes on every attempt, so a retry only burns compute. Your canvas puts that split where everyone can see it.

```mermaid
flowchart LR
    n0[("partner_api<br/>(API)")]
    n1["json_check<br/>(quality_gate)"]
    n2["write_to_warehouse<br/>(SQL)<br/>Retries: 3"]
    n3[("warehouse<br/>(warehouse)")]
    n4[("quarantine<br/>(dead letter queue)")]
    n0 --> n1
    n1 --> n2
    n2 --> n3
    n1 --> n4
    n2 --> n4
```

*Malformed documents leave at `json_check` with no retry. Writes get 3 attempts, then escalate to `quarantine`.*

Read the 2 edges into `quarantine` as the two halves of the classification. The edge out of `json_check` is the permanent bucket. That stage has no retry setting, so a bad document goes straight to quarantine and the rest of the run keeps loading. The edge out of `write_to_warehouse` is the transient bucket's escape hatch. The stage has a budget of 3 attempts, and a write that still fails after the third is escalated to permanent and parked in the same store. Without that budget, a timeout that turned out to be a real outage would retry forever.

| Pitfall: One retry setting for everything retries the unfixable |
| --- |
| If you put a retry count on the whole pipeline, or on the parse step, a malformed document is attempted 3 times and fails 3 times. It gets worse if a parse failure stops the run, because every good order behind it waits too. Retries belong only on the stage whose failure can heal. |

| Key insight: Ambiguous errors get a small budget, then escalate |
| --- |
| Most real errors don't announce their bucket. A bare 500 could mean a brief overload or a broken endpoint. Treat it as transient for a handful of attempts, and once those are spent, handle it exactly like a permanent failure. The quarantine edge out of the retrying stage is that escalation. |

**Follow-up questions**

1. The partner API starts returning 500s with no message. Which bucket does that go in, and what changes on the canvas?\
   *Applies the ambiguous-as-transient hedge to a stage that had no retry budget.*
2. The warehouse credential expires overnight. Should the 3 retries on `write_to_warehouse` still apply?\
   *Spots a permanent failure arriving at a stage built for transient ones.*

</details>


<br>

### Exercise 8 of 10

**● TASK**

An hourly job fetches currency exchange rates from a rates API and loads them into a warehouse. The API returns 503s during its deploys, which last up to two minutes. Set the fetch step's retry backoff to exponential (a setting of its own, not just a retry count), with waits doubling from one second and capped at one minute, and enough retry attempts that the waits outlast a deploy. When the retries run out, page the on-call engineer instead of retrying further.

<details>
<summary><strong>Solution</strong></summary>

#### Doubling waits, with a ceiling

Exponential backoff picks each retry's wait by doubling the last one and stopping at a ceiling. Here that means 1, 2, 4, 8, 16 and 32 seconds, then 60 for every attempt after, because the cap holds. The doubling gives the rates API more room to finish its deploy with every failure, and the cap keeps a late attempt from sleeping through the next run.

```mermaid
flowchart LR
    n0[("rates_api<br/>(API)")]
    n1["fetch_rates<br/>(Airflow)<br/>Retries: 8 · Backoff: exponential"]
    n2[("rates_warehouse<br/>(warehouse)")]
    n3(["on_call_alert<br/>(alerting)"])
    n0 --> n1
    n1 --> n2
    n1 --> n3
```

*`rates_api` feeds `fetch_rates`, which retries with exponential backoff for 8 attempts, loads `rates_warehouse`, and pages `on_call_alert` when the retries run out.*

1. **Size the attempts against the deploy**

   Add up the capped waits until they clear two minutes: 1 + 2 + 4 + 8 + 16 + 32 + 60 = 123 seconds after 7 attempts, which beats a two minute deploy with almost no margin. An eighth attempt adds another 60 for 183 seconds, the same 3 minute budget the section worked through, so a `retryCount` of 8 rides out a slow deploy with room to spare.

| Pitfall: Doubling without a cap runs away |
| --- |
| Leave the ceiling off and the tenth wait is 512 seconds, the twelfth over half an hour. The hourly job would still be asleep when the next run starts, and rates that arrive hours late are worse than a run that failed loudly. |

| Real world: Past the budget, stop retrying and page |
| --- |
| After 3 minutes of escalating waits the API is no longer mid-deploy; something is actually broken. That is why `fetch_rates` connects to `on_call_alert`: retries absorb the outage that heals itself, and a person handles the one that does not. |

**Follow-up questions**

1. Deploys start taking 5 minutes. What changes in the policy?\
   *Re-sizing `retryCount` against a longer budget while the cap stays at 60 seconds.*
2. 40 hourly jobs share this API and all hit the same deploy at the same second. What would you add to the waits?\
   *Whether doubling alone keeps the retries from arriving together, and how jitter spreads them.*

</details>


<br>

### Exercise 9 of 10

**● TASK**

An hourly Spark job reads payment rows from a PostgreSQL replica, checks each row's currency code against the reference list, and writes the rows to a data lake. Retry lake write timeouts a bounded number of times with exponential backoff. Do not retry the permanent failures: rows with an unknown currency code go to a quarantine store a person can inspect, and a 403 from the lake stops the job and alerts the on-call engineer.

<details>
<summary><strong>Solution</strong></summary>

#### Retry what can heal, route what cannot

Knowing when not to retry comes down to one question per failure: does anything change between attempts? A lake write that times out can succeed a minute later, so it earns a bounded retry with exponential backoff. A row whose currency code is not on the reference list fails the same check forever, and a 403 means the job's credentials lack write access until someone fixes them. Retrying either one burns compute and buries a clear error under a pile of identical ones.

```mermaid
flowchart LR
    n0[("payments_replica<br/>(PostgreSQL)")]
    n1["currency_check<br/>(custom)"]
    n2[("quarantine<br/>(object storage)")]
    n3["load_payments<br/>(Spark)<br/>Retries: 3 · Backoff: exponential"]
    n4[("payments_lake<br/>(Delta Lake)")]
    n5(["on_call_alert<br/>(alerting)"])
    n0 --> n1
    n1 --> n3
    n1 --> n2
    n3 --> n4
    n3 --> n5
```

*Only `load_payments` retries; `currency_check` routes bad rows to `quarantine` and a 403 goes to `on_call_alert`.*

1. **Bound the retries on the lake write**

   Put the retry policy on `load_payments`, the stage that talks to the lake: three attempts, each waiting roughly twice as long as the last. The cap matters as much as the backoff, because a timeout that survives three spaced attempts is no longer a blip.

2. **Route unknown currencies to quarantine**

   `currency_check` sends failing rows down an error path to `quarantine`, where a person can see the bad code and ask the producer to fix it. Good rows keep flowing, and nothing loops back to run the check again.

3. **Send the 403 to a person**

   A permission failure on the write goes straight to `on_call_alert`. Only someone who can change the lake's permissions can resolve it, so the fastest fix is telling that person on the first failure, not after three wasted retries.

| Pitfall: A retry on the check repeats the same rejection |
| --- |
| Putting `retryCount` on `currency_check`, or one blanket retry policy across the whole job, looks safe but replays the identical row against the identical list. The log fills with copies of one error, the hourly run stalls, and the quarantine store that would have shown the problem stays empty. |

**Follow-up questions**

1. The lake starts returning 429 Too Many Requests at peak hours. Which path should that take?\
   *Tells a transient rate limit apart from the permanent 403.*
2. What should happen when all three write retries on `load_payments` fail?\
   *The hand-off once a transient failure stops looking transient.*

</details>


<br>

### Exercise 10 of 10

**● TASK**

Two hundred parallel workers in a nightly batch geocode customer addresses through a shared geocoding service and load the results into a warehouse. When the service is overloaded it slows down and returns 503s. Retry each 503 with exponential backoff, capped at 60 seconds per wait and spread with random jitter so the workers never retry in lockstep. Give each request a total retry budget of 5 minutes and page the on-call engineer when it runs out. A 400 for a malformed address is never retried: send it to a dead letter store for review.

<details>
<summary><strong>Solution</strong></summary>

#### A retry policy that knows when to stop

When 200 workers share one struggling service, a good retry policy does two things at once: it gives the service room to recover, and it stops before the retrying becomes its own outage. **Exponential backoff** buys the room, the cap keeps any single wait reasonable, jitter breaks up the wave that 200 synchronized workers would send, and the total budget turns 'keep trying' into a decision that ends with a person being paged.

1. **Sort the failures before retrying**

   A 503 from an overloaded service is transient: the same request succeeds once the load drops. A 400 for a malformed address is permanent: the eighth attempt fails exactly like the first. Only the 503 enters the retry loop. The 400 goes straight to the dead letter store, where a person can fix the address.

2. **Shape each wait: double, cap, randomize**

   Double the wait on each attempt (2, 4, 8, 16, 32 seconds) and stop growing at 60. Then randomize each wait, for example a random value between zero and the computed delay. Without jitter, 200 workers that failed in the same second retry in the same second, and the service sees a wave larger than the load that tipped it over.

3. **Spend the budget, then escalate**

   8 attempts at those capped waits add up to about 4 minutes, inside the 5-minute budget and longer than the service's usual recovery. Once the budget is spent, the service is not hiccuping, it is down, and more retries only hide that. The exhaustion path leads to an alert so the on-call engineer hears about it tonight, not from an empty dashboard tomorrow.

```mermaid
flowchart LR
    n0[("customer_addresses<br/>(source)")]
    n1["geocode_jittered_backoff<br/>(Spark)<br/>Retries: 8 · Backoff: exponential"]
    n2[("geocoded_addresses<br/>(warehouse)")]
    n3[("malformed_address_dlq<br/>(storage)")]
    n4(["on_call_alert<br/>(consumer)"])
    n0 --> n1
    n1 --> n2
    n1 --> n3
    n1 --> n4
```

*`geocode_jittered_backoff` retries 503s with jittered waits of 2, 4, 8, 16, 32, then 60 seconds (8 attempts, about 4 minutes, inside the 5-minute budget). Exhaustion pages `on_call_alert`; 400s go straight to `malformed_address_dlq`.*

| Pitfall: A fixed one-second retry rebuilds the overload |
| --- |
| Retrying every second with no limit is the version most first designs ship. Across 200 workers that is 200 requests a second aimed at a service that is already failing, and with no limit the batch never finishes and never pages anyone. Exponential waits shrink the load, jitter spreads it out, and the budget guarantees the loop ends. |

**Follow-up questions**

1. The service starts returning 429 with a header saying when to retry. How does the policy change?\
   *Using a server-provided wait instead of a computed one, while still respecting the total budget.*
2. Every worker exhausts its budget in the same minute and the on-call engineer gets hundreds of pages. What would you change?\
   *Escalating once per outage rather than once per failed request.*

</details>
