# Sliding Window: Advanced

Ines is 40 minutes into an onsite loop at Cloudflare when the interviewer pastes a list of per-second request counts from a single customer zone. The first ask is the peak load over every 60-second span, and her nested loop holds up until the interviewer mentions 86,400 readings a day per zone. The follow-up arrives before she finishes: count the spans in which exactly 3 distinct client IPs sent traffic. Then the readings stop being a list and become a stream that never ends. The last question is the one the role exists for: turn this into the limiter that decides, per IP, whether request 101 in the current minute gets through, with many threads calling it at once and millions of IPs that come and go. Each step is a sliding window, and each step breaks the version before it.


<br>

### What you will be able to do

Maintain a monotonic deque that returns every window max or min in O(n), and defend the amortized bound

Rewrite exact-count and take-from-both-ends problems as monotone windows with the complement trick

Build generator pipelines that window an unbounded stream in O(k) memory without yielding shared state

Pair windows with heaps and binary search for medians, out-of-order expiry and k-th smallest answers

Design a sliding-window rate limiter that holds a lock and caps its keys, then a sessionizer that handles late events with a watermark


<br>

---

## Window Max via Monotonic Deque

A running sum slides because subtraction undoes addition. Maximum has no inverse. When the current max falls off the left edge, no stored number says which value replaces it, so the direct fix rescans all k values of every window at O(n \* k). The interview version asks for every width-k max in time that stays flat as k grows. For a day of per-second readings and a 60-second window, the rescan does 30 times the deque's work.

- **5,184,000** — comparisons when every window rescans
- **172,800** — deque pushes plus pops, worst case


<br>

### The invariant that makes it linear

Keep a deque of indices whose values strictly decrease front to back. Each new index i does 3 things. It pops from the back every index whose value is <= the new value: an older, smaller reading can never be the max again, because i is at least as large and outlives it. It appends itself. Then it pops the front if that index has expired (dq[0] <= i - k). Now nums[dq[0]] is the window max. The left edge moves 1 position per step, so at most 1 index expires and an if covers it.

https://github.com/user-attachments/assets/aa6e4f29-7dde-44f1-a4c2-97894f81cf68

*Indices enter at the back; dominated ones leave from the back and expired ones from the front.*

| i | x | popped from back | expired from front | deque values after | window max |
| --- | --- | --- | --- | --- | --- |
| 0 | 4 | none | none | [4] | not full |
| 1 | 2 | none | none | [4, 2] | not full |
| 2 | 12 | 2, 4 | none | [12] | 12 |
| 3 | 3 | none | none | [12, 3] | 12 |
| 4 | 8 | 3 | none | [12, 8] | 12 |
| 5 | 1 | none | 12 (index 2) | [8, 1] | 8 |
| 6 | 7 | 1 | none | [8, 7] | 8 |
| 7 | 5 | none | 8 (index 4) | [7, 5] | 7 |

In row 2, 12 clears both 2 and 4 in 1 step, and those indices are never compared again; 12 then serves 3 windows before expiring at row 5. Row 7 shows the other exit: 8 leaves from the front because its index fell out, though it is larger than everything behind it.

Edge cases to state before coding

- k = 1 returns the input unchanged
- k = n returns a single value, the global max
- k > n or an empty input returns an empty list with no exception
- Ties: with <= the newer of 2 equal values stays, which is the one that lives longer


<br>

### Why the inner loop stays out of the bound

A single step's `while` can pop k indices, so the worst case looks like k work per step. Count per index instead. Every index enters the deque once and leaves at most once, whether it is popped from the back or expired from the front, so the whole run does at most 2n pushes and pops however they cluster. On a strictly falling input nothing leaves from the back, so the deque fills to k entries and the front expires every step. Extra memory is the deque, never more than k indices.


<br>

### Indices over values, and the min twin

| ✓ Deque of indices | ✗ Deque of values |
| --- | --- |
| • Expiry is a single comparison: dq[0] <= i - k<br><br>• Equal values are separate entries, so popping with <= is safe<br><br>• Extends to time windows by storing (ts, value) pairs | • Expiry compares the outgoing value with the front<br><br>• Must pop with < so duplicates survive; with <=, [5, 5, 1] at k = 2 returns 1 for the last window<br><br>• Has no way to express a time-based window |

Window min is the same code with the comparison flipped to >=, which keeps values strictly increasing so the front is the smallest. The 2 deques combine in a common follow-up: the longest subarray whose max minus min stays within a limit. The window is now variable, so expiry is driven by a left pointer instead of i - k. When the spread breaks the limit, left advances. Each deque then drops its front if that index now sits left of left.

```sql
from collections import deque

def longest_within_limit(nums, limit):
    hi, lo = deque(), deque()
    left = best = 0
    for right, x in enumerate(nums):
        while hi and nums[hi[-1]] <= x:
            hi.pop()
        while lo and nums[lo[-1]] >= x:
            lo.pop()
        hi.append(right)
        lo.append(right)
        while nums[hi[0]] - nums[lo[0]] > limit:
            left += 1
            if hi[0] < left:
                hi.popleft()
            if lo[0] < left:
                lo.popleft()
        best = max(best, right - left + 1)
    return best
```

> **TIP**
>
> Use `collections.deque`. `list.pop(0)` shifts every remaining pointer left, so a list-backed version passes small tests while each front removal costs O(k).


<br>

---

## The Complement Trick

Every shrinking window rests on 1 property: if a window satisfies the constraint, so does every window inside it. At most 3 distinct values, a sum of at most S over non-negative numbers, no repeated character: each passes, which is why the left pointer knows when to move. Exact constraints fail. In [1, 2, 1, 2, 3] with exactly 2 distinct values required, [1, 2] qualifies, while its inner [2] and the outer [1, 2, 1, 2, 3] do not, so neither pointer has a rule. The complement trick rewrites the exact question as monotone ones that do.


<br>

### Counting complements: exactly and at least

Each at_most pass is the at-most-K counter you already know, adding right - left + 1 windows per right end. Nesting is what makes exactly(K) = at_most(K) - at_most(K - 1) exact: every window with at most K-1 distinct values also has at most K, so the subtraction removes only the windows with fewer than K. The same nesting gives at_least(K) = n \* (n + 1) // 2 - at_most(K - 1), where n \* (n + 1) // 2 counts every subarray. A constraint can look monotone and still fail to nest: a sum of at most 2 holds for [4, -3] (sum 1) and fails for its inner [4], so a shrinking window drops 4 at right 0 and never counts [4, -3].

https://github.com/user-attachments/assets/253c9894-c085-4b7a-af80-5214ce567b20

*2 monotone passes, and their difference is the exact count.*

| right | value | at_most(2) adds | at_most(1) adds | difference | exactly-2 windows ending here |
| --- | --- | --- | --- | --- | --- |
| 0 | 1 | 1 | 1 | 0 | none |
| 1 | 2 | 2 | 1 | 1 | [1, 2] |
| 2 | 1 | 3 | 1 | 2 | [2, 1], [1, 2, 1] |
| 3 | 2 | 4 | 1 | 3 | [1, 2], [2, 1, 2], [1, 2, 1, 2] |
| 4 | 3 | 2 | 1 | 1 | [2, 3] |
| total |  | 12 | 5 | 7 | 7 windows |

The difference column is exact at every right end, so the trick holds for any constraint whose valid sets nest: at most K odd numbers, at most K values above a threshold, at most K late events. Each `at_most` pass is O(n) with a counter of at most K + 1 keys, so the exact count costs 2 linear passes.

The 1-pass follow-up tracks far and near as its left pointers: far is the first start that leaves at most K distinct values and near the first that leaves at most K-1. Every start in [far, near) gives exactly K, so each right end adds near - far. It is the subtraction fused into 1 loop with 2 counters, so the same preconditions apply: valid windows must nest and K = 0 needs its own return. Sums over negative values break both pointers.


<br>

### Positional complements: taking from both ends

The second form hides in take-from-both-ends problems. Take i items from the left and k - i from the right, and what remains is always a contiguous middle block of n - k items. Maximizing what you take equals minimizing what you leave, and the leftover is a fixed-width window. For cards [1, 2, 3, 4, 5, 6, 1] with k = 3, the middle has width 4 and there are exactly 4 placements of it.

| middle left behind | middle sum | taken: left | right | taken sum |
| --- | --- | --- | --- |
| [1, 2, 3, 4] | 10 | none | 5, 6, 1 | 12 |
| [2, 3, 4, 5] | 14 | 1 | 6, 1 | 8 |
| [3, 4, 5, 6] | 18 | 1, 2 | 1 | 4 |
| [4, 5, 6, 1] | 16 | 1, 2, 3 | none | 6 |

The total is 22, the smallest middle is 10, and the best take is 22 - 10 = 12. The variable-width version makes the same move: the fewest end removals summing to x equals n minus the longest middle summing to sum(nums) - x. On [3, 2, 20, 1, 1, 3] with x = 10, the total is 30, the longest middle summing to 20 is [20], and the answer is 6 - 1 = 5 removals. Every value is positive, so the middle's sum rises as it widens and a shrinking window finds it.

```sql
def min_end_removals(nums, x):
    target = sum(nums) - x
    if target < 0:
        return -1
    left = window = 0
    best = -1
    for right, value in enumerate(nums):
        window += value
        while window > target:
            window -= nums[left]
            left += 1
        if window == target:
            best = max(best, right - left + 1)
    return -1 if best == -1 else len(nums) - best
```

> When the complement stops working
>
> - Negative values: switch to prefix sums with a dict of first positions.
> - K = 0 in exactly-K: `at_most(-1)` shrinks past the right end and indexes off the array, so return 0 for it explicitly.
> - Counts outgrow 32-bit columns: `n * (n + 1)  2` for n = 100,000 is 5,000,050,000. Python ints never overflow; an INT column does.

> **TIP**
>
> Words that signal a complement: "exactly", "at least", "from either end", "remove from the front or back". Say the rewrite aloud before coding: naming why the direct window fails is half of what the interviewer scores.


<br>

---

## Streaming Windows via Generators

Next, the readings arrive individually from a message consumer and never stop. There is no len(nums) and no nums[i - k] to look back at, so the window keeps its own copy of whatever it may still need. A generator fits the shape. Each next() pulls 1 input, updates state held in the generator's paused frame, and hands back 1 result, so memory is the window's state and nothing more.


<br>

### A rolling window in O(k) memory

```sql
from collections import deque

def rolling_mean(stream, k):
    window = deque(maxlen=k)
    total = 0.0
    for x in stream:
        if len(window) == k:
            total -= window[0]
        window.append(x)
        total += x
        if len(window) == k:
            yield total / k
```

deque(maxlen=k) evicts the oldest item on append without reporting it, so the generator subtracts window[0] before appending; reverse those 2 lines and it subtracts a value still inside the window. The float total also gathers rounding error with every add and subtract, drifting from the true sum over millions of readings. Keep integer units (milliseconds, cents) or re-sum the window with math.fsum every few thousand items.

- **320 MB** — a list holding 10M Python floats
- **2 KB** — a 60-slot deque and its floats


<br>

### Pull-based pipelines and lazy evaluation

Chained generators form a pipeline the consumer drives. Creating them runs nothing. The first next() asks rolling_max for a value, which asks readings for an input, and each reading passes through every stage before the source produces another. That ordering makes an infinite source safe: islice stops after 3 peaks, so the source reads only the 4 values they needed. With no list to index, the max deque stores (index, value) pairs from enumerate.

https://github.com/user-attachments/assets/948f45cc-68c2-479e-886b-fd5e1cbfdf50

*The prints interleave: each reading reaches the consumer before the next is read.*


<br>

### The yield that hands out one shared object

```sql
from collections import deque

def windows(stream, k):
    window = deque(maxlen=k)
    for x in stream:
        window.append(x)
        if len(window) == k:
            yield window

print(list(windows([1, 2, 3, 4, 5], 3)))
for w in windows([1, 2, 3, 4, 5], 3):
    print(w)
```

Predict the output first. The list(...) line prints deque([3, 4, 5], maxlen=3) 3 times: list holds 3 references to 1 deque, which the generator finished mutating before the print. The for loop prints deque([1, 2, 3], maxlen=3), then [2, 3, 4], then [3, 4, 5], because each print runs before the generator resumes. The generator is the same in both cases, and the answer depends on when the consumer reads. Any stage that buffers, such as a batch writer collecting 500 windows, sees the list behavior.

The fix is yield tuple(window), a snapshot the generator cannot change, at O(k) per item: 10M readings with k = 1,000 copy 10 billion references. A consumer that needs only an aggregate should get the aggregate, with no copy.


<br>

### Time-based windows on a stream

Real events arrive at irregular times, so the question becomes "the last 60 seconds", however many events that holds. Store (ts, value) pairs. Each new event is appended, then the front is popped while the oldest timestamp is at or before ts - width_s. The deque's size now tracks the peak arrival rate times the width: 2,000 events per second over 60 seconds holds 120,000 entries during a spike.

```sql
from collections import deque

def events_last(stream, width_s):
    window = deque()
    total = 0
    for ts, value in stream:
        window.append((ts, value))
        total += value
        while window[0][0] <= ts - width_s:
            _, old = window.popleft()
            total -= old
        yield ts, len(window), total
```


<br>

### When the window outlives the process

A generator's state lives in its paused frame, which cannot be pickled or checkpointed. After a crash, a streaming job restarts with an empty window, and its first k outputs are averages over fewer readings than they claim. Jobs that must resume keep the window in a plain class whose fields (the deque, the running total, the last offset read) serialize to a state store, with the generator as a thin loop that calls it.

> What the interviewer probes next
>
> - A generator runs once. A second `for` over the same object yields nothing and raises no error.
> - Cleanup belongs in `try`/`finally`: closing the generator raises `GeneratorExit` at the paused `yield`.


<br>

---

## Adding Heaps and Binary Search

The deque works for max and min because a larger, newer value dominates a smaller, older one for the rest of its life. Median, k-th largest and counts of close pairs have no dominance rule: an old middling value matters until it expires. They need order from somewhere. Either the window keeps a heap or a sorted list, or a search outside the window tests each guess with a window pass.


<br>

### Heaps with lazy deletion

A heap cannot remove an arbitrary item cheaply, so it removes expired items only when they surface. For window max, push (-value, index) and, before reading the top, pop while its index is <= i - k. Each step is O(log n). On a rising input the newest value always sits on top, the expired ones stay below it untouched, and the heap grows to all n entries, where the deque never holds more than k.

| ✓ Monotonic deque | ✗ Heap with lazy deletion |
| --- | --- |
| • O(n) total, at most k entries<br><br>• Answers only max or min<br><br>• Needs items to expire in arrival order | • O(n log n), up to n entries without pruning<br><br>• Any priority, including composite keys<br><br>• Handles items that expire in any order, such as bids with their own deadlines |


<br>

### Sliding median: sorted window or 2 heaps

https://github.com/user-attachments/assets/7ac3fc53-824e-450a-a350-0a54b80a15d9

*The sorted window gives the median by position: window[k // 2] for odd k, the mean of window[k // 2 - 1] and window[k // 2] for even k.*

bisect_left finds the outgoing value in O(log k), but pop there and insort each shift about k/2 pointers: O(n \* k) on paper, fast in practice since each shift is 1 block memory move. The O(n log k) answer keeps a max-heap for the lower half and a min-heap for the upper, deletes lazily through a dict of pending removals, rebalances by counts of live items, and for even k averages the 2 tops. It breaks on balance checks that count stale entries, which let the halves drift and return a wrong median.

| Approach | Cost per step | Extra memory | Where it breaks |
| --- | --- | --- | --- |
| Re-sort each window | O(k log k) | O(k) | Slow once k reaches the thousands |
| Sorted list with bisect | O(log k) search, O(k) shift | O(k) | Shift cost dominates at very large k |
| 2 heaps, lazy deletion | O(log k) amortized | O(k) plus stale entries | Balance checks that count stale items |

> **TIP**
>
> Name both designs: write the sorted-list version, state its O(k) shift, then sketch the 2-heap design and its stale-count bug. That covers correctness and scaling in less time than debugging a full 2-heap version at a whiteboard.


<br>

### Binary search on the answer, window as the check

Find the k-th smallest absolute difference among all pairs. With 100,000 values there are 4,999,950,000 pairs, too many to list. Invert it: for a guessed distance d, how many pairs differ by at most d? On the sorted array that is 1 window pass, because for each right end the valid left ends form a contiguous run. The count only rises with d, so binary search finds the smallest d whose count reaches k: O(n log n) to sort plus O(n log R), where R is the largest value minus the smallest.

https://github.com/user-attachments/assets/aaff088c-9bb0-4d41-a459-12d68f7e5db1

*Each guess is a window pass, and the range of guesses halves every step.*

| lo | hi | guess d | pairs within d | next range |
| --- | --- | --- | --- | --- |
| 0 | 8 | 4 | 5 | [0, 4]: 5 >= 4, keep 4 |
| 0 | 4 | 2 | 3 | [3, 4]: 3 < 4, too small |
| 3 | 4 | 3 | 5 | [3, 3]: 5 >= 4, answer 3 |

On [1, 1, 3, 6, 9] with k = 4, `lo < hi` with `hi = mid` on success converges on the lowest passing guess. Writing `hi = mid - 1` skips the answer whenever the passing guess is the answer itself, as in the last row.

When the data is sorted and queries arrive in a batch, binary search can do without the window. Given a sorted list of event timestamps, the number of events in (t - w, t] is bisect_right(ts, t) - bisect_right(ts, t - w), O(log n) per query with no state carried between queries. That suits a backfill answering 50,000 ad hoc windows over a day of events, where a moving window would have to walk the queries in order.

> Signals that the answer is a binary search
>
> - The output is a number: a distance, a capacity, a threshold, a minimum window length
> - A yes-or-no check on a guessed number flips once as the guess grows
> - Pipeline version: the fewest workers such that no 1-hour window of backlog breaks the SLA


<br>

---

## Rate Limiter and Sessionizer Design

The closing prompt asks for at most 100 requests per client per 60 seconds, with allow(key) called from many threads and millions of clients that appear and vanish. Every standard answer is a window. They differ in how much state each key stores and in whether the count stays exact when requests cluster near a bucket boundary.

| Design | State per key | Accuracy | Boundary behavior |
| --- | --- | --- | --- |
| Fixed window counter | 1 count and a window id | Over-admits across a boundary | 100 at 0:59 plus 100 at 1:00 is 200 in 2 seconds |
| Sliding log | Up to 100 timestamps | Exact | Checks the true last 60 seconds |
| Sliding window counter | 2 counts | Estimate assuming the previous window was evenly spread | Errs when traffic clusters |
| Token bucket | Token count and last refill time | Exact for its own rule: a rate plus a burst size | Admits the configured burst |

- **3.2 GB** — 1M full logs of 100 timestamps
- **32 bytes** — per timestamp: float plus deque slot

https://github.com/user-attachments/assets/0178298e-a166-4066-8aa2-ee04d92d4412

*Same 7 requests at 3 per 10 seconds: the log denies t = 15 and the counter admits it.*

At t = 15 the true last 10 seconds hold 3 requests, the latest at 12 and the other 2 at 8 and 9, so the log denies. The counter sees 3 requests in the previous bucket, sits halfway through the current one, and estimates 3 \* 5 / 10 + 1 = 2.5, under 3. It assumed even spread, and these requests clustered at the bucket's end. Production keeps only the current and previous bucket counts; the animation keeps all of them for readability.


<br>

### Check-then-act is the race

allow reads the log's length, compares it with the limit, then appends. With 2 threads on 1 key, both can read 99 and pass the check, so both append and the limiter admits 101. The global interpreter lock makes each bytecode atomic and leaves the sequence open, so hold 1 lock from the eviction through the append. One lock serializes unrelated clients. Striping it into 64 locks by hash(key) % 64 is safe only if the key map is striped too: 64 shards, where each shard owns a lock and a OrderedDict capped at max_keys // 64. Per-key locks over the single shared OrderedDict in the class below race. Inserts mutate it from every stripe at once, and so do move_to_end and popitem, and eviction can drop a key whose stripe another thread holds.

```sql
import threading
from collections import OrderedDict, deque


class SlidingLogLimiter:
    def __init__(self, limit, window_s, max_keys):
        self.limit = limit
        self.window_s = window_s
        self.max_keys = max_keys
        self.logs = OrderedDict()
        self.lock = threading.Lock()

    def allow(self, key, now):
        with self.lock:
            log = self.logs.get(key)
            if log is None:
                log = deque()
                self.logs[key] = log
                if len(self.logs) > self.max_keys:
                    self.logs.popitem(last=False)
            else:
                self.logs.move_to_end(key)
            while log and now - log[0] >= self.window_s:
                log.popleft()
            if len(log) >= self.limit:
                return False
            log.append(now)
            return True
```


<br>

### The sessionizer: a gap window per user

A session ends after more than 30 minutes of inactivity, so per user the state is the session's start and its last event. A session closes only when the stream proves the gap: an event from any user more than 30 minutes past that session's last event. Using the newest timestamp as the clock and flushing every session it has outrun keeps memory proportional to users active within the gap.

https://github.com/user-attachments/assets/d159846e-1bfe-4197-a3fb-0cbfd76c12d3

*Times are minutes. Ana's events at 20 and 50 are exactly 30 apart and stay in 1 session.*

With ts - last > GAP, a gap of exactly 30 continues the session, so pick the operator from the business definition and test that boundary. The stale scan visits every open session per event, O(u) for u open users. At scale, keep a min-heap of (last + GAP, user), pop only due entries, and check each against the user's current last, since later events leave older entries stale: lazy deletion again.

Locking open_s on every event would serialize the whole stream. Partition by user instead: route each event to worker hash(user) % 8, so each worker owns its users' state with no lock. Each worker keeps its own clock, so one that receives no events closes nothing; a periodic heartbeat carrying the stream's newest timestamp lets idle partitions flush.


<br>

### Late events and the reorder buffer

Mobile clients batch and retry, so events arrive minutes late. The sessionizer and the time window both assume order. Put a min-heap keyed on timestamp in front of them. Its release point, `max_seen - L` for allowed lateness L, is the watermark: the stream's claim that nothing earlier will arrive. Events at or before it leave the heap in order, so memory holds about L minutes of events. The sessionizer uses the watermark as its clock, closing the sessions it has passed instead of trusting the newest raw timestamp. An event already behind the watermark missed its session's close, so it goes to a side output for a correction job instead of reopening an emitted session.

```sql
import heapq
from itertools import count

def reorder(events, lateness_s):
    heap, seq = [], count()
    max_seen = None
    for user, ts in events:
        if max_seen is not None and ts < max_seen - lateness_s:
            yield ("late", user, ts)
            continue
        heapq.heappush(heap, (ts, next(seq), user))
        max_seen = ts if max_seen is None else max(max_seen, ts)
        while heap and heap[0][0] <= max_seen - lateness_s:
            ts_out, _, user_out = heapq.heappop(heap)
            yield ("ok", user_out, ts_out)
    while heap:
        ts_out, _, user_out = heapq.heappop(heap)
        yield ("ok", user_out, ts_out)
```


<br>

---

## Putting It All Together

A payments company's public API gateway fronts 2M merchant API keys. Each key may send 100 requests per 60 seconds, the operations dashboard shows every key's peak 60-second request count, fraud review wants the bursts in which a key returned exactly 3 distinct error codes, and the analytics team needs merchant dashboard sessions with a 30-minute gap, built from web and mobile events that arrive up to 5 minutes late.

- The per-key limiter is a sliding log or a 2-count estimate behind striped locks, with max_keys sized above the keys active in any 60 seconds.
- The dashboard peak is a monotonic deque over each key's per-second counts, fed by a generator so only 60 counts per key stay in memory.
- The fraud count is exactly-3 distinct over error codes, computed as at_most ( 3 ) - at_most ( 2 ) because an exact constraint cannot drive a shrinking window.
- The sessionizer sits behind a 5-minute reorder heap, flushes the sessions the watermark has outrun, and sends events past the lateness bound to a correction table.
- If the dashboard later wants median latency per window instead of the peak, the deque gives way to a sorted window or 2 heaps, since medians have no dominance rule.


<br>

---

## Key Takeaways

- A monotonic deque of indices returns every window max or min in O(n), because each index is pushed once and popped at most once.
- Exact constraints have no pointer rule; rewrite them as at_most ( K ) - at_most ( K - 1 ) , or turn take-from-both-ends into a middle window.
- A windowing generator holds O(k) state and moves each item through the whole pipeline before reading the next; yield snapshots or aggregates, never the live deque.
- Where no dominance rule exists, add order: a lazy-deletion heap, a bisect-sorted window, or a binary search whose check is a window pass.
- Rate limiters and sessionizers are windows with extra parts: the limiter needs a lock across check-then-act and a cap on keys, and the sessionizer needs a reorder buffer for late events that flushes on the watermark.
