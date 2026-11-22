# Binary Search: Intermediate

A candidate interviewing for a data engineering role at Amazon gets a question that sounds like logistics. 5 packages must leave a warehouse in a fixed order within 2 days. They weigh 7, 2, 5, 10 and 8 tonnes, and the truck has the same capacity every day. What is the smallest capacity that works? Nothing in the input is sorted, so the candidate starts testing capacities upward from 10, running a full simulation each time. The interviewer asks what happens with 100,000 packages. The faster answer comes from noticing that a capacity that works keeps working as it grows, which makes the capacities themselves a sorted space to search. The follow-ups probe the same idea from other angles, first a peak in an unsorted list and a median across 2 sorted inputs, then lookups into records sorted by a single field.


<br>

### What you will be able to do

Turn a minimize-or-maximize question into a feasibility function and binary search its answer range

Find a peak in an unsorted array in O(log n) and name the assumption that makes it valid

Implement the partition search for the median of 2 sorted arrays in O(log min(m, n))

Search sorted records by a field on Python 3.9 by pairing them with a keys list or with tuples, or by wrapping each record in a class

Recognize which search fits backlog sizing or benchmark tuning, and which fits percentiles and as-of lookups


<br>

---

## Binary Search on the Answer

The binary searches you already know look for a value inside a sorted array. Here the search runs over a range of candidate answers, and that range never exists as a list in memory. What makes it searchable is a feasibility function feasible(x). It takes a single candidate and answers True or False, and once it returns True for some x, it returns True for every larger x. A predicate with that shape has a single boundary, the smallest passing value, and binary search reaches it in about log2(hi - lo) calls to the predicate.


<br>

### The intro's question, restated

The weights are [7, 2, 5, 10, 8], in tonnes. Packages ship in list order, a daily load never exceeds the capacity, and no package is split across days. The goal is the smallest capacity c that ships everything within 2 days. Two facts bound the search. Every capacity below max(weights), which is 10, fails, because the 10-tonne package fits on no day. A capacity of sum(weights), which is 32, ships the whole list on day 1. The answer therefore lies in [10, 32], a window of 23 candidates.


<br>

### Why the answer range is sorted

If a capacity ships the packages within 2 days, any larger capacity does too, because the same split still fits with room to spare. Along the window the outcomes therefore read False up to a point and True from there to the end, with a single flip. The table locates the flip between 17 and 18. Each row uses a greedy day count: keep adding packages to the current day until the next one would overflow, then open a new day. Greedy is optimal for a fixed capacity, because packing a day as full as possible never pushes any later package onto a later day than another split would.

| Capacity | Daily loads | Days needed | Ships in 2 days? |
| --- | --- | --- | --- |
| 10 | 7+2 / 5 / 10 / 8 | 4 | No |
| 14 | 7+2+5 / 10 / 8 | 3 | No |
| 17 | 7+2+5 / 10 / 8 | 3 | No |
| 18 | 7+2+5 / 10+8 | 2 | Yes |
| 21 | 7+2+5 / 10+8 | 2 | Yes |
| 32 | 7+2+5+10+8 | 1 | Yes |

The search keeps a single rule. A capacity that passes stays in the window, since it might be the smallest, and a capacity that fails leaves the window along with every capacity below it. In code a pass sets hi = mid and a fail sets lo = mid + 1, and the loop stops when the bounds meet, which happens on the boundary.

https://github.com/user-attachments/assets/d4714784-c27f-46ee-b0e2-0b3dcb01e368

*Each line is a probe: 4 greedy day counts shrink the 23 candidates in [10, 32] to the answer, 18.*

Every probe costs a single pass over the weights, so the search costs O(n log(sum - max)) in total. The window halves on every probe, whether it passes or fails. The failing probe at 17 is what proves 18 minimal: until 17 fails, nothing rules out a smaller capacity.

Scale the question to 100,000 packages of up to 500 tonnes each. The window can then span about 50 million capacities, and testing them upward from the bottom, as the candidate in the intro began to, could cost tens of millions of full passes over the input.

- **26** — probes at most for that window
- **2.6M** — package visits, worst case


<br>

### Maximize the minimum: the flipped direction

Some questions ask for the largest value that still passes. Pick 3 maintenance hours from the free hours [1, 2, 8, 4, 9] so that the closest pair of picked hours sits as far apart as possible. The predicate can_place(gap) asks whether 3 hours can be picked with every pair at least gap apart. A wider gap is harder to satisfy, so the outcomes read True up to a point and False after it, and the answer is the last True. That direction changes 2 lines of the template: a pass sets lo = mid, and mid rounds up with (lo + hi + 1) // 2. Rounding down loops forever once hi == lo + 1, because mid then equals lo and a passing probe sets lo to the value it already holds.

```sql
def can_place(hours, k, gap):
    count, last = 1, hours[0]
    for h in hours[1:]:
        if h - last >= gap:
            count += 1
            last = h
    return count >= k


def max_min_gap(hours, k):
    hours = sorted(hours)
    lo, hi = 0, hours[-1] - hours[0]
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if can_place(hours, k, mid):
            lo = mid
        else:
            hi = mid - 1
    return lo


print(max_min_gap([1, 2, 8, 4, 9], 3))
```

> How the pattern hides in a question
>
> - Smallest capacity that meets a deadline or budget, and the same question asked of a rate or a size
> - Largest batch under a limit that must still hold; gaps and thresholds work the same way
> - Minimize the maximum load, or maximize the minimum distance
> - The input is unsorted, yet the expected complexity contains a log factor

> **TIP**
>
> When the answer is a real number, such as a rate in events per second, replace `while lo < hi` with a fixed loop of 100 iterations. Each iteration halves the window and a fixed count always terminates, while a test like `hi - lo > 1e-9` can spin forever once the floats near the answer are spaced wider than the tolerance.


<br>

---

## Find Peak Element

The input is an unsorted list in which neighbouring values always differ, and the positions outside both ends of the list count as negative infinity. A peak is an index whose value beats both neighbours, and the task is to return any peak. A scan finds one in O(n). Binary search finds one in O(log n) with nothing sorted, because a single comparison between nums[mid] and nums[mid + 1] proves which part of the window still holds a peak.


<br>

### What a single comparison proves

The window [lo, hi] carries an invariant: lo is either 0 or a position whose value rose from its left neighbour, and hi is either the last index or a position whose value falls to its right neighbour. Now suppose nums[mid] < nums[mid + 1]. Walk right from mid + 1 toward hi. Either the values keep rising all the way to hi, which is then a peak by the invariant, or they fall somewhere first, and the value before that first fall is a peak. In both cases a peak lies in [mid + 1, hi], and the new lo still satisfies the invariant. The mirror case puts a peak in [lo, mid], with mid itself a candidate. When the window shrinks to a single index, that index rose from its left and falls to its right, which is the definition of a peak.

| ✓ nums[mid] < nums[mid + 1] | ✗ nums[mid] > nums[mid + 1] |
| --- | --- |
| • The slope rises toward the right<br><br>• A peak lies in mid + 1 through hi<br><br>• Move: lo = mid + 1 | • The slope falls toward the right<br><br>• A peak lies in lo through mid, mid included<br><br>• Move: hi = mid |

```sql
def find_peak(nums):
    lo, hi = 0, len(nums) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if nums[mid] < nums[mid + 1]:
            lo = mid + 1
        else:
            hi = mid
    return lo


print(find_peak([1, 2, 1, 3, 5, 6, 4]))
```

| lo | hi | mid | nums[mid] | nums[mid + 1] | Move |
| --- | --- | --- | --- | --- | --- |
| 0 | 6 | 3 | 3 | 5 | lo = 4 |
| 4 | 6 | 5 | 6 | 4 | hi = 5 |
| 4 | 5 | 4 | 5 | 6 | lo = 5 |
| 5 | 5 | - | - | - | return 5 |

The search returns index 5, value 6. A left-to-right scan stops at index 1, value 2, which is also a peak. Both answers are correct, and a complete answer says so before the interviewer asks: the problem accepts any peak, and the halving lands on whichever peak its probes climb toward. The read of nums[mid + 1] never runs off the end, because lo < hi forces mid < hi.

Predict 3 boundary cases before running them. find_peak([5, 4, 3, 2, 1]) returns 0: every comparison falls, hi walks down to 0, and index 0 beats the negative infinity on its left. find_peak([1, 2, 3, 4, 5]) returns 4 by the mirror path. A list of length 1 skips the loop and returns 0.


<br>

### Where the guarantee breaks

The proof leaned on neighbours differing. With equal neighbours, nums[mid] == nums[mid + 1] points in no direction. Run find_peak on [1, 1, 1, 1, 1, 2, 1]: every probe compares 2 equal values, the else branch moves hi left each time, and the function returns 0. Index 0 fails the strict definition, because its right neighbour equals it, and the only strict peak sits at index 5. No algorithm repairs this in O(log n): a flat list can hide its single larger value at any position, so the worst case reads every position.

> Assumptions to state out loud
>
> - Adjacent values differ, so every comparison has a direction
> - Positions outside the list count as negative infinity
> - Any peak is an acceptable answer, and the code may return a different peak than a scan would
> - With plateaus allowed, the worst case is O(n), and saying so is part of the answer


<br>

### Mountain arrays and bitonic targets

A mountain array strictly rises and then strictly falls, so it has exactly 1 peak, and find_peak returns it. A common follow-up asks whether a target appears in a mountain array. The answer takes 3 binary searches: find the peak, search [0, peak] with the usual ascending comparison, then search [peak + 1, n - 1] with the comparison reversed. Each costs O(log n), so the total stays O(log n). A rotated sorted array, met earlier in this track, yields to the same move: locate the break with a comparison against a neighbour or an endpoint, then search a sorted piece.

*The same idea extends to a grid: take the largest value in the middle column, compare it with its left and right neighbours, and keep the half on the larger side. That costs O(rows \* log(columns)).*

> **TIP**
>
> State the invariant before writing code: the window always contains a peak. The 2 branches follow from it, the interviewer can check your reasoning in a sentence, and a wrong move such as `hi = mid - 1` shows up at once as a step that can discard the peak.


<br>

---

## Median of Two Sorted Arrays

Two sorted arrays, a of length m and b of length n, together hold the values whose median is wanted. A merge walks both arrays to the middle in O(m + n). The O(log min(m, n)) solution never builds the merged order. It searches for a cut: a split of each array into a left part and a right part such that the 2 left parts together hold exactly the smaller half of all values.


<br>

### The cut condition

Cut a after i values and b after j values. The left side must hold half = (m + n + 1) // 2 values, so j = half - i. Once i is picked, the whole cut is fixed. The cut is correct when every left value is at most every right value. Inside each array that already holds, since each array is sorted, so only 2 cross checks remain: a[i - 1] <= b[j] and b[j - 1] <= a[i]. When the first check fails, a sends too many values left and i must shrink. When the second fails, i must grow. Every probe therefore yields a direction, which is all binary search needs.

Left of the cut: 6 values

| Source | Values |
| --- | --- |
| a[0:4] | 1, 3, 8, 9 |
| b[0:2] | 7, 11 |

Right of the cut: 5 values

| Source | Values |
| --- | --- |
| a[4:5] | 15 |
| b[2:6] | 18, 19, 21, 25 |

The animation runs the search on those arrays, 11 values in total, and then on [1, 2] and [3, 4], an even total. With an odd total the extra value goes left, so the median is the largest left value. With an even total it is the mean of the largest left value and the smallest right value.

https://github.com/user-attachments/assets/c4590c90-ed2c-4f4e-a22c-56ae6ae0f78d

*The odd total settles in 2 probes at 11; the even total ends with b entirely on the right and returns 2.5.*

The first probe, i = 2, puts 19 on the left and 8 on the right, so b sent too much left and i grows to 4, where both checks pass and the median is max(9, 11), which is 11. The second call ends at i = 2, j = 0: all of b sits on the right, and b_left becomes negative infinity so its check passes without a special case. The sentinels matter in Python for a second reason. Without them, a[i - 1] at i = 0 reads a[-1], the last value of a, and the comparison quietly uses the wrong number where an error would have been far more useful.


<br>

### Why the search runs on the shorter array

The function swaps so that a is the shorter array, and the swap does 2 jobs. It keeps j in range: with m <= n, half is at least m and at most n, so j = half - i stays inside [0, n] for every i from 0 to m. Searching the longer array instead lets j go negative, and b[j - 1] then indexes from the end of the list. The swap also sets the cost, because the window is the m + 1 possible cuts of the shorter array.

Take m = 1,000 latency samples from a small shard and n = 1,000,000 from a large one, both sorted.

- **10** — partition probes, at most
- **500K** — merge steps to reach the middle


<br>

### Other routes to the same median

Three other approaches come up, and naming their costs shows why the cut is the expected answer. The value-range route reuses the search on the answer from the first section: count the values at or below x with bisect_right on both arrays, and find the smallest x whose count reaches the target rank.

| Approach | Cost | Catch |
| --- | --- | --- |
| Merge to the middle | O(m + n) | Linear in the larger array |
| Search the value range, counting with bisect | O(log V \* (log m + log n)) for V possible values | Needs a bounded range; floats need a fixed iteration count |
| Discard k/2 values per step, recursively | O(log(m + n)) | Index bookkeeping across 2 arrays invites off-by-one bugs |
| Cut search on the shorter array | O(log min(m, n)) | Needs the swap and the infinity sentinels |

> What the interviewer is checking
>
> - The partition condition comes before code: 2 cross comparisons and nothing else
> - The swap puts the search on the shorter array, with a reason why `j` stays in range
> - Empty sides use infinities, so no branch special-cases `i = 0` or `i = m`
> - Even totals return the mean of 2 values as a float: `(2 + 3) / 2` is 2.5
> - The cut generalizes to the k-th smallest value of the combined arrays

The same cut answers the k-th smallest value: replace half with k and restrict i to [max(0, k - n), min(k, m)] so that j stays valid. A merge still wins in 2 situations: when both arrays are small enough that O(m + n) means a few hundred steps, and when many quantiles are needed at once, because a single merge then answers all of them by index.

> **TIP**
>
> The odd case returns the int 11 and the even case returns the float 2.5. If a caller checks types or serializes the result, wrap both returns in `float(...)`.


<br>

---

## bisect with Custom Keys

Sorted data in a pipeline is usually a list of records: price versions keyed by start time, config snapshots keyed by version number, rate tiers keyed by threshold. bisect compares whole elements with <, so a search by a single field needs elements that compare by that field. Python 3.10 added a key parameter for this. On Python 3.9, which this lesson's code targets, passing key= to bisect_right raises TypeError, and 3.9 code uses one of 3 other approaches.


<br>

### A parallel list of keys

Keep the records in a list and their sort keys in a second list, aligned index for index. Search the keys, then read the record at the same index. In an as-of lookup, each version takes effect at its start time and stays in effect until the next version starts, so the version in effect at ts is the last start that is <= ts, found as bisect_right(starts, ts) - 1.

https://github.com/user-attachments/assets/09238390-5617-43a3-a830-92f6c2c4c15e

*The guarded lookups print rate_v2 twice, then None, then rate_v3; the unguarded one returns rate_v3 for a time before any version began.*

At ts = 250 the lookup returns rate_v2, the version that starts exactly then. bisect_left(starts, ts) - 1 would return rate_v1 there, because bisect_left places 250 before the equal start, and that off-by-one only shows at an exact boundary. The last 2 lines show why the guard exists. At ts = 50, before history begins, the index is -1, and versions[-1] is a valid Python expression that returns the newest version. No exception warns that the event predates every version.

The keys list costs O(n) to build and gives O(log n) lookups on plain integer comparisons. An insert costs O(n), since both lists shift, and both inserts must use the same index or every later lookup reads the wrong record. That trade suits version tables that are rebuilt in batch and read on every event.


<br>

### Tuples and their comparison traps

Storing each record as a tuple with the key first makes the records themselves sortable. A probe tuple then searches them: (250,) sorts before every (250, ...), because a tuple that is a prefix of a longer one compares smaller. That finds the first record at or after 250. Finding the last record at or before 250 needs a probe that sorts after every (250, ...), and the natural candidate breaks.

```sql
from bisect import bisect_left, bisect_right

versions = [(100, "rate_v1"), (250, "rate_v2"), (400, "rate_v3")]
print(bisect_left(versions, (250,)))
print(bisect_right(versions, (250,)))
print(bisect_right(versions, (250, float("inf"))))
```

The third call ties on 250, so Python moves to the second fields and evaluates float('inf') < 'rate_v2', which raises. With integer keys, bisect_left(versions, (251,)) - 1 gives the last record at or before 250 without touching the second field. Ties cause the same failure on insert: insort with 2 records stamped at the same time compares their payloads, and 2 dicts raise TypeError. A unique sequence number as the second field, (ts, seq, payload), settles every tie before the payload is reached.


<br>

### A wrapper class that defines <

bisect_left evaluates a[mid] < x and bisect_right evaluates x < a[mid], and neither uses any other comparison. A class whose __lt__ compares only the key therefore works with every function in the module, insort included. The payload never gets compared.

```sql
from bisect import bisect_left, insort


class ByStart:
    def __init__(self, start, payload):
        self.start = start
        self.payload = payload

    def __lt__(self, other):
        return self.start < other.start

    def __repr__(self):
        return f"ByStart({self.start}, {self.payload!r})"


rows = []
for start, payload in [(400, {"v": 3}), (100, {"v": 1}), (250, {"v": 2})]:
    insort(rows, ByStart(start, payload))
print(rows)
print(bisect_left(rows, ByStart(250, None)))
```

| Approach | Lookup | Insert | Fails when |
| --- | --- | --- | --- |
| Parallel keys list | O(log n), plain value compares | O(n) on 2 lists at the same index | The 2 lists drift out of alignment |
| Tuples, key first | O(log n), tuple compares | O(n) | A tie reaches a field with no ordering |
| Wrapper with `__lt__` | O(log n), a Python method call per compare | O(n) | A bare value is passed as the probe |

*From Python 3.10, bisect_right(versions, 250, key=lambda r: r[0]) works directly. The key applies to the list's elements and never to the probe, so the probe is a bare key, while insort applies the key to the new record before searching.*

> **TIP**
>
> Pick the approach by the workload. Read-heavy tables rebuilt in batch favour the parallel keys list, whose integer compares avoid a Python method call per step. Tables that grow by insert favour tuples with a sequence tiebreaker, because each tuple carries its own key and so record and key can never drift apart.


<br>

---

## DE Applications: Intermediate

The 3 search shapes from this lesson, plus keyed bisect, map onto 4 recurring pipeline questions. Each subsection below names the predicate or comparison that makes the search legal, because that sentence is what separates a binary search answer from a guess that happens to run fast.


<br>

### Sizing a consumer to drain a backlog

A replay consumer starts with 200K events queued. Over the next 4 hours, 400K more arrive in the first hour, 100K in the second, 0 in the third and 300K in the fourth. What is the lowest hourly processing rate that leaves the queue empty at the end of hour 4? Dividing the 1M events by 4 hours suggests 250K per hour. The predicate drains(rate) replays the hours: each hour adds its arrivals, then removes up to rate events. A higher rate never leaves more events queued at any hour, so drains flips a single time, and the capacity template applies unchanged. The code counts in thousands.

```sql
def drains(backlog, arrivals, rate):
    queue = backlog
    for arriving in arrivals:
        queue += arriving
        queue -= min(queue, rate)
    return queue == 0


def min_rate(backlog, arrivals):
    lo, hi = 1, backlog + sum(arrivals)
    while lo < hi:
        mid = (lo + hi) // 2
        if drains(backlog, arrivals, mid):
            hi = mid
        else:
            lo = mid + 1
    return lo


print(min_rate(200, [400, 100, 0, 300]))
```

The answer is 300K, well above the 250K average. The final hour's 300K arrive with no later hour to absorb them, and capacity left idle in hour 3 cannot be saved for hour 4. The window [1, 1000] takes at most 10 simulations of 4 hours each. When the simulation is expensive, such as a replay of a full day's arrival log at minute resolution, those 10 runs are the whole cost of the answer.


<br>

### Tuning a batch size with expensive probes

Throughput as a function of batch size often climbs to a peak and then falls as memory pressure grows. Suppose there are 64 candidate sizes and each benchmark run takes 10 minutes. Peak search treats a benchmark as a read of nums[i] and stores every result, since consecutive probes often reuse a neighbour's measurement. In the code below, a formula with its peak at index 37 stands in for the benchmark.

- **640 min** — full sweep of every candidate
- **12** — benchmark runs, worst case
- **120 min** — peak search, worst case

```sql
runs = {}


def throughput(i):
    if i not in runs:
        runs[i] = 1000 - (i - 37) ** 2
    return runs[i]


lo, hi = 0, 63
while lo < hi:
    mid = (lo + hi) // 2
    if throughput(mid) < throughput(mid + 1):
        lo = mid + 1
    else:
        hi = mid
print(lo, len(runs))
```

A real benchmark is noisy, and 2 runs at the same size can differ by more than the gap between neighbouring sizes. Noise creates false local peaks, which break the assumption that neighbouring results differ in a meaningful direction. Repeat the runs around the returned index, compare a few neighbours on each side, and report the result as the best size found under a unimodal assumption.


<br>

### Percentiles across 2 sorted runs

An external sort writes sorted runs before merging them. A p50 or p95 across 2 runs that support reads by index uses the cut from the median section, with the left side sized to the target rank k, and costs O(log min(m, n)) probes of 4 reads each per quantile. With more than 2 runs, or a dozen quantiles at once, the merge pass the sort performs anyway is the better place to read them.


<br>

### As-of enrichment in a stream

A stream job tags each event with the exchange rate in effect at its timestamp. Each currency gets a sorted list of start times and an aligned list of rates, rebuilt when a new rate lands. With 32 versions per currency, bisect_right(starts, ts) - 1 needs at most 6 comparisons per event where a linear scan needs up to 32. The -1 guard routes events older than the first rate to a quarantine table, so they are never tagged with the newest rate.

| Interview phrasing | Technique | What makes it legal | Cost |
| --- | --- | --- | --- |
| Lowest rate that empties the backlog by hour H | Search on the answer | `drains(rate)` flips a single time from False to True | O(H log R) for a rate window of size R |
| Best batch size when throughput rises then falls | Peak search with cached probes | Neighbouring sizes give different results | O(log n) benchmark runs |
| p95 across 2 sorted runs without merging | Cut search with i + j = k | 2 cross comparisons give a direction | O(log min(m, n)) |
| Rate in effect at each event's timestamp | `bisect_right(starts, ts) - 1` | Starts sorted, each start inclusive | O(log v) per event |

> A complete answer, in order
>
> - Name the predicate or comparison and why it flips a single time
> - Give both bounds: below lo nothing passes, and hi is certain to pass
> - Pick the template: a first-True search sets `hi = mid`, a last-True search rounds mid up
> - State the cost as the number of probes times the cost of a single probe
> - Name what breaks it: ties and plateaus in the input, plus noisy measurements and the unguarded -1 index

| ✓ Do | ✗ Don't |
| --- | --- |
| • Write the feasibility function first and test it on 2 hand-picked candidates<br><br>• Cache probe results when a probe is a benchmark run or a full replay<br><br>• Guard bisect_right(...) - 1 against -1 before indexing the records<br><br>• Swap so the cut search runs on the shorter array | • Size a consumer from average arrivals when the arrivals come in bursts<br><br>• Trust a single noisy benchmark curve to be unimodal near its peak<br><br>• Pass key= to bisect functions on Python 3.9<br><br>• Probe with (ts, float('inf')) when the second field holds strings |


<br>

---

## Putting It All Together

A payments company runs a nightly settlement job. It enriches 1,000,000 card transactions with the exchange rate in effect at each transaction's timestamp, reports p50 and p95 settlement latency across 2 sorted regional runs, and replays a 200K-event backlog of late transactions, plus the day's bursty arrivals, before the morning report goes out. Engineers also tune the job's batch size against 10-minute benchmark runs.

- The replay consumer's rate is a search on the answer: drains(rate) flips a single time, and the bursty final hour pushes the answer above the average.
- Rate enrichment is bisect_right(starts, ts) - 1 over a parallel keys list per currency, with the -1 guard sending transactions older than the first rate to quarantine.
- The regional latency percentiles reuse the median cut with the left side sized to the target rank, run on the shorter regional array.
- Batch-size tuning is peak search with cached benchmark runs, confirmed by repeating runs around the returned size.
- Every piece is answered the same way. Name what flips or what the comparison proves and give the bounds; then count the probes and name the input that breaks it.


<br>

---

## Key Takeaways

- A feasibility function that flips a single time turns a minimize-or-maximize question into a binary search over candidate answers.
- First-True searches move hi to mid; last-True searches round mid up, or the loop never ends.
- Peak finding works on unsorted data because the window always holds a peak; equal neighbours break the guarantee.
- The median of 2 sorted arrays is a search for a cut on the shorter array, checked by 2 cross comparisons with infinity sentinels.
- On Python 3.9, search records by a field with a parallel keys list, tuples with a tiebreaker, or a class that defines __lt__.
- The cost of every variant is the number of probes times the price of a probe, and that price decides whether the log factor matters.
