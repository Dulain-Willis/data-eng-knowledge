# Dynamic Programming: Beginner

Priya is in the final coding round for a data engineering role at Amazon. The interviewer describes a loader that accepts batches of exactly 1, 3 or 4 files and asks for the fewest batches that load 6 files. Priya reaches for the largest batch first: 4, then 1, then 1, for 3 batches. The interviewer asks whether 2 is possible. It is: 3 plus 3. Her greedy choice looked right at every step and was wrong overall. Priya switches strategy, writes a function for the fewest batches covering any smaller count, notices it recomputes the same counts again and again, and caches them. The code change is a decorator and an import. The follow-up questions probe whether she knows why it works, how fast it runs and where it breaks. This lesson builds that answer.


<br>

### What you will be able to do

Decide whether a problem needs DP by checking for overlapping subproblems and optimal substructure, and break a greedy approach with a counterexample

Turn naive recursion into memoized DP with @lru_cache and read its cache_info() output

Solve 1D problems by stating the state, recurrence, base cases, fill order and answer before writing code

Map data engineering tasks such as job scheduling and header splitting onto 1D DP recurrences

Predict the output of DP code with broken base cases, short tables, bad initial values, stale caches and wrong fill order


<br>

---

## What Is DP and When to Use It

### What makes a problem a DP problem

Dynamic programming answers a question by answering smaller versions of the same question, storing each answer once, and reading stored answers back instead of recomputing them. That trade of memory for time pays off only when a problem has both properties below, so check for both before picking an approach to any counting or optimization question.

Throughout this section, best(t) is the minimum number of batches needed for t files when the allowed batch sizes are (1, 3, 4).

- **Overlapping subproblems** *The same smaller question is asked many times*\
  best(6) needs best(5), best(3) and best(2). best(5) needs best(4), best(2) and best(1). best(2) already appears in both lists, and the repetition multiplies at every level below.
- **Optimal substructure** *A best answer is assembled from best answers to its parts*\
  If the best plan for 6 files opens with a 3-file batch, the rest of it must be a best plan for the remaining 3 files. A better plan for those 3 would give a better plan for 6, contradicting the assumption.

Divide and conquer has optimal substructure without the overlap: merge sort splits a list into halves that share no elements, so a cache would never record a hit. A greedy algorithm commits to the locally best choice and never revisits it, which is correct only when a proof shows that choice is always safe. Batch sizes (1, 3, 4) have no such proof, and 6 files is the counterexample.

Greedy: largest batch that fits

| Step | Batch | Files left |
| --- | --- | --- |
| 1 | 4 | 2 |
| 2 | 1 | 1 |
| 3 | 1 | 0 |

DP: try every first batch

| First batch | Best for the rest | Total |
| --- | --- | --- |
| 1 | best(5) = 2 | 3 |
| 3 | best(3) = 1 | 2 |
| 4 | best(2) = 2 | 3 |

Greedy spends 3 batches. DP compares all 3 possible first batches, each followed by the best finish for what remains, and keeps the smallest total, 2. The right-hand table is the whole method in miniature: make a choice, add the best answer for the remainder, and minimize over the choices.


<br>

### What the overlap costs

The recurrence fib(n) = fib(n-1) + fib(n-2) branches twice per call, and the 2 branches recompute the same smaller values. The animation runs fib(5) both ways and counts every call. Watch the naive version re-enter n = 2 and n = 1 again and again while the memoized version answers repeats of 2 and above with a dictionary lookup.

https://github.com/user-attachments/assets/3f2fd053-0f1a-479a-bf29-9de89221046f

*Naive fib(5) makes 15 calls. The memoized version makes 9 and stores 4 results.*

Push n to 30 and the naive count multiplies by about 1.6 for each step of n, while the memoized count grows by 2 per step and the number of stored answers by 1.

- **2,692,537** — calls made by naive fib(30)
- **59** — calls made by memoized fib(30)
- **31** — distinct values fib(30) depends on

> Predict before reading on
>
> Naive `fib_naive(6)` makes 1 call for itself plus every call made by `fib_naive(5)` and `fib_naive(4)`. You saw 15 calls for n = 5, and n = 4 makes 9. How many calls does n = 6 make, and how many does `fib_memo(6)` make on an empty memo?

*Answers: 25 naive calls (1 + 15 + 9) and 11 memoized calls. In the memoized version each value from 2 to n makes 2 child calls once, and the top call adds 1, so the total is 2n - 1.*


<br>

### Top-down or bottom-up

Both implementations evaluate the same states with the same recurrence. They differ in who controls the evaluation order and in what fails first as inputs grow.

| ✓ Top-down: memoized recursion | ✗ Bottom-up: tabulation |
| --- | --- |
| • Write the recurrence as a recursive function, then add a cache<br><br>• Evaluates only the states the answer reaches<br><br>• The recursion discovers the evaluation order for you<br><br>• Each level of recursion is a stack frame, and the default limit is 1000 | • Fill a list from the base cases up to the answer<br><br>• Evaluates every state from 0 to n, reachable or not<br><br>• You choose the fill order, and a wrong order gives wrong answers<br><br>• No recursion, so input size is bounded by memory alone |


<br>

### Reading the problem statement

| Problem as asked | Approach | Deciding signal |
| --- | --- | --- |
| Fewest batches of sizes (1, 3, 4) for 6 files | DP | Openings overlap and greedy fails |
| Ways to climb n stairs with steps of 1 or 2 | DP | ways(n) reuses ways(n-1) and ways(n-2) |
| Sort 1 million log lines by timestamp | Divide and conquer | Halves share no work |
| Fewest coins for an amount with coins 1, 5, 10, 25 | Greedy | This coin set is proven greedy-safe |
| Best revenue from days where picking a day blocks the next | DP | Each choice changes what is left |

> **TIP**
>
> When you claim DP in an interview, name a repeated state out loud, such as 'best(2) is needed by both best(6) and best(5)'. The named repeat shows the overlap exists, and the greedy counterexample shows a greedy approach fails.


<br>

---

## Memoizing with @lru_cache

### What the decorator does on every call

functools.lru_cache wraps a function in a dictionary keyed by its arguments. On each call it builds a key from the positional and keyword arguments, returns the stored result on a hit, and on a miss runs the body and stores the return value. Recursive calls pass through the wrapper too, because the function's name inside its own body refers to the decorated version. That detail is what turns exponential recursion into memoized DP.

```sql
def min_batches(target, sizes):
    if target == 0:
        return 0
    best = float("inf")
    for s in sizes:
        if s <= target:
            best = min(best, min_batches(target - s, sizes) + 1)
    return best
```

Placing @lru_cache(maxsize=None) above the `def` leaves the body untouched. The program below writes out by hand what that wrapper does: build a key from the arguments, look it up, and count hits and misses. It calls the function with the sizes as a list, then as a tuple. Predict its first printed line before you play it.

https://github.com/user-attachments/assets/f441a325-c729-4943-a394-37ff4abd5e04

*Hits return from the cache without running the body, so only misses enter the loop.*


<br>

### What the 3 printed lines tell you

The list call never reaches the body. Looking up the key hashes every argument inside it, a list has no hash, and the lookup raises TypeError: unhashable type: 'list' before a miss is recorded. The decorator raises the same error at the same point. The tuple call returns 2. Then {'hits': 7, 'misses': 7} 7 is the speedup in numbers, and the decorated version's cache_info() reports it as CacheInfo(hits=7, misses=7, maxsize=None, currsize=7): the 7 misses are targets 0 through 6, each computed once, and the 7 hits are repeat requests answered without running the body.

Total work is misses times the work inside a single miss: target + 1 states, each looping over the sizes, so O(target \* len(sizes)) time and O(target) memory for the cache. State the cost in that shape when an interviewer asks: number of states times work per state.


<br>

### Keep the key small and hashable

Arguments must be hashable: ints, strings, tuples and frozensets work, while lists, dicts and sets raise. The cleaner design keeps fixed inputs out of the key altogether. Define the cached function inside the solver, let it read the sizes from the enclosing scope, and cache on the single argument that changes.

```sql
from functools import lru_cache


def fewest_batches(target, sizes):
    @lru_cache(maxsize=None)
    def best(t):
        if t == 0:
            return 0
        result = float("inf")
        for s in sizes:
            if s <= t:
                result = min(result, best(t - s) + 1)
        return result

    answer = best(target)
    return -1 if answer == float("inf") else answer


print(fewest_batches(6, [1, 3, 4]))
print(fewest_batches(7, [2, 4]))
```

It prints 2, then -1. Each call to fewest_batches creates a fresh best with its own empty cache, so answers for a batch set never leak into the next, and the cache is freed when the call returns. The second batch set has only even sizes, so 7 files are unreachable, best(7) stays at infinity, and the wrapper turns that into -1.


<br>

### Settings that change how the cache behaves

Behavior worth knowing

- **maxsize**: @lru_cache() with no argument keeps 128 entries and evicts the least recently used. States evicted before their last use are recomputed, so DP code passes maxsize=None.
- @functools.cache: added in Python 3.9, it is shorthand for lru_cache(maxsize=None).
- cache_clear(): empties the cache. A cached function defined at module level holds every entry, with strong references to its arguments and results, until the process exits or the cache is cleared.
- **Recursion depth**: the default limit is 1000 frames, and min_batches(5000, (1, 3, 4)) on an empty cache recurses 5000 levels down the size-1 chain and raises RecursionError. Calling it for targets 0, 1, 2 and upward fills the cache a level at a time, and bottom-up code needs no recursion at all.


<br>

### Predict the cache statistics

```sql
from functools import lru_cache


@lru_cache(maxsize=None)
def ways(n):
    if n <= 1:
        return 1
    return ways(n - 1) + ways(n - 2)


print(ways(6))
print(ways.cache_info())
```

Write down ways(6) and all 4 numbers in its CacheInfo before reading the answer.

*It prints 13, then CacheInfo(hits=4, misses=7, maxsize=None, currsize=7). The misses are the 7 values 0 through 6. Each n from 3 to 6 asks for n - 2 after its first branch has already cached it, giving 4 hits. A second ways(6) would add 1 hit and no misses.*

| ✓ Do | ✗ Don't |
| --- | --- |
| • Pass only hashable arguments such as ints, strings and tuples<br><br>• Define the cached function inside the solver for a fresh cache per input<br><br>• Use maxsize=None or @cache for DP state spaces<br><br>• Check that cache_info() misses equal your expected number of states | • Cache a function that reads a global list you later change<br><br>• Leave maxsize at its default of 128 for large state spaces<br><br>• Recurse thousands of levels deep on an empty cache |


<br>

---

## Classic 1D DP Problems

### Five answers before any code

A 1D DP solution is fully specified by 5 answers, and writing them down first catches most mistakes while each is still a single line. The table fills them in for the batch problem, which the previous section solved with a cache. Here it becomes a loop over a list.

| Step | Question it answers | Batch sizes (1, 3, 4) |
| --- | --- | --- |
| State | What does a cell mean, in words? | dp[t] is the fewest batches that sum to exactly t files |
| Recurrence | How is a cell built from smaller cells? | dp[t] = 1 + min(dp[t - s]) over sizes s <= t |
| Base case | Which cells need no recurrence? | dp[0] = 0 |
| Fill order | Which cells must be final first? | t from 1 up to the target |
| Answer | Which cell is returned? | dp[target], or -1 if it is still infinity |

```sql
def fewest_batches(target, sizes):
    inf = float("inf")
    dp = [0] + [inf] * target
    for t in range(1, target + 1):
        for s in sizes:
            if s <= t and dp[t - s] + 1 < dp[t]:
                dp[t] = dp[t - s] + 1
    return dp[target] if dp[target] != inf else -1


print(fewest_batches(6, [1, 3, 4]))
```

It prints 2. Slot 0 holds 0 because 0 files need 0 batches, and every other slot starts at infinity, meaning not reached yet. The loop runs t upward because dp[t] reads only dp[t - s], a smaller index that is already final.

| t | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dp[t] | 0 | 1 | 2 | 1 | 1 | 2 | 2 |
| Best plan | none | 1 | 1 + 1 | 3 | 4 | 4 + 1 | 3 + 3 |

Read dp[6] as 1 batch plus the smallest of dp[5], dp[3] and dp[2], which are 2, 1 and 2. Time is O(target \* len(sizes)) and memory is O(target), matching the cached version, with no recursion to overflow.


<br>

### Counting: climbing stairs

Count the distinct sequences of 1-step and 2-step moves that climb n stairs. **State**: ways[i] is the number of sequences ending exactly on stair i. **Recurrence**: each sequence that reaches stair i ends with a 1-step from i - 1 or a 2-step from i - 2, and the 2 groups share no sequence, so ways[i] = ways[i - 1] + ways[i - 2]. **Base cases**: ways[0] = 1, the single empty sequence, and ways[1] = 1. Each cell reads only the 2 before it, so 2 variables can replace the list.

```sql
def climb(n):
    prev, curr = 1, 1
    for _ in range(n - 1):
        prev, curr = curr, prev + curr
    return curr


print(climb(5), climb(1), climb(0))
```

It prints 8 1 1. For n = 5 the loop runs 4 times, sliding the pair (1, 1) to (1, 2), (2, 3), (3, 5) and (5, 8). For n = 1 and n = 0 the range is empty, so the base value 1 comes back. Memory drops from O(n) to O(1) and time stays O(n).


<br>

### Maximizing: promotions with a cooldown

A marketing team can run a promotion on any day, but each promotion needs a quiet day after it, so 2 adjacent days never both run one. Projected revenue per day is [2, 7, 9, 3, 1], in thousands of dollars. **State**: dp[i] is the best revenue from the first i days. **Recurrence**: day i is skipped, leaving dp[i - 1], or run, adding its revenue to dp[i - 2]. **Base cases**: dp[0] = 0 for no days, and dp[1] equals day 1's revenue.

https://github.com/user-attachments/assets/f422c46d-5285-4d11-ab8d-397d55f67239

*Each row prints i, the skip value, the take value and the winner stored in dp[i].*

Day 4 is the first day where skipping wins, 11 against 10, because running day 4 would give up day 3's 9. The best plan runs days 1, 3 and 5 for 12.

> Your turn
>
> Revenue is `[5, 1, 1, 5]`. A rule that runs every other day starting on day 1 earns 6. Fill `dp[0]` through `dp[4]` by hand and find what DP earns.

*dp is [0, 5, 5, 6, 10]. DP earns 10 by running days 1 and 4, which are not adjacent. Fixed alternation cannot see that a 2-day gap is allowed.*

| Problem | State | Recurrence | Base cases |
| --- | --- | --- | --- |
| Fewest batches | fewest batches for t files | 1 + min(dp[t - s]) | dp[0] = 0 |
| Climbing stairs | sequences ending on stair i | ways[i - 1] + ways[i - 2] | ways[0] = ways[1] = 1 |
| Promotions | best revenue from the first i days | max(dp[i - 1], dp[i - 2] + day i) | dp[0] = 0, dp[1] = day 1 |

> **TIP**
>
> Say the state in words before typing `dp = [...]`. A sentence like 'dp[i] is the best revenue from the first i days' tells you what `dp[0]` must be, the best revenue from 0 days, and it tells the interviewer you know what each cell means.


<br>

---

## DP in Data Engineering

Pipeline work produces DP problems wherever a plan is assembled from choices that constrain each other: which jobs share a slot, where to cut a string, how many fixed-size batches to send. Brute force over n yes-or-no choices tries 2^n combinations, which passes 1 billion at 30 jobs. A 1D DP visits each state once.


<br>

### Backfill jobs on a single worker slot

A team reserves a single worker slot overnight for backfill jobs. Each job has a start hour, an end hour and a priority score, and the slot runs a single job at a time. The goal is the set of non-overlapping jobs with the highest total score, where a job may start at the hour another job ends.

| Job | Start hour | End hour | Score |
| --- | --- | --- | --- |
| A | 0 | 3 | 6 |
| B | 0 | 6 | 16 |
| C | 3 | 6 | 7 |
| D | 5 | 9 | 15 |
| E | 6 | 10 | 4 |

The table is already sorted by end hour. **State**: dp[i] is the best score using only the first i jobs. **Recurrence**: either drop job i and keep dp[i - 1], or run it and add its score to dp[p], where p counts the earlier jobs that end no later than job i starts. This is the promotion recurrence with a jump back to p in place of a fixed jump of 2.

https://github.com/user-attachments/assets/82521572-1b96-478d-966a-89095fe77e56

*p is found by scanning the earlier jobs, which are sorted by end hour.*

The best total is 21, from jobs A and D. Taking the highest score first grabs B for 16, which blocks everything but E, and ends at 20. Taking the earliest end first picks A, C and E for 17. Earliest end is the proven greedy rule only when every job is worth the same. The inner scan makes this O(n^2), and binary search over the sorted end hours brings it to O(n log n).


<br>

### Splitting run-together field names

A partner export strips separators from its column headers, so user_event_ts arrives as usereventts. Given a vocabulary of known field words, the loader must recover the pieces or flag the header for a human. **State**: back[i] is where the last word of a valid split of the first i characters begins, or None if no split exists. **Base case**: back[0] = 0, since the empty prefix needs no words.

```sql
def split_header(header, vocab):
    n = len(header)
    back = [None] * (n + 1)
    back[0] = 0
    for i in range(1, n + 1):
        for j in range(i):
            if back[j] is not None and header[j:i] in vocab:
                back[i] = j
                break
    if back[n] is None:
        return None
    parts = []
    i = n
    while i > 0:
        parts.append(header[back[i]:i])
        i = back[i]
    return parts[::-1]


vocab = {"user", "use", "rev", "event", "ts", "id"}
print(split_header("usereventts", vocab))
print(split_header("useridts", vocab))
print(split_header("userevent_ts", vocab))
```

It prints ['user', 'event', 'ts'], then ['user', 'id', 'ts'], then None, because no vocabulary word contains an underscore. Taking the shortest matching word first fails on the first header: it takes use, then rev, then finds no word for entts, although a split exists. The table records every reachable cut, so a dead end costs nothing, and walking back from the end recovers the pieces in reverse.


<br>

### Recognizing the shape at work

| Task | State in words | Recurrence shape |
| --- | --- | --- |
| Fewest fixed-size batches for a load | fewest batches for t files | 1 + the min over sizes |
| Retry schedules that fill a 10-minute budget with waits of 1 or 2 minutes | schedules totalling exactly t minutes | sum of the 2 previous counts, 89 at t = 10 |
| Non-overlapping backfill jobs on a single slot | best score from the first i jobs by end hour | max of skip and take, with a jump to p |
| Splitting a run-together header | whether the first i characters split into words | any earlier valid cut j with a word from j to i |

Query planners that choose how to run a SQL statement rely on the same principle: keep the best answer found for each state and build larger answers on top of it.


> Presenting a pipeline problem as DP
>
> - Name the decision in business terms: which jobs, which cut, which batch size
> - Define dp[i] in a sentence that uses the business noun
> - Show the greedy rule you rejected and the input that breaks it
> - Quote cost as states times work per state, then name the speedup you would add


<br>

---

## Common Beginner Mistakes

Each program below is a single line away from correct. Read it, predict what it prints or which exception it raises, then check the explanation. The 5 bugs cover base cases, table size, initial values, caches and fill order.


<br>

### Bug 1: a base case that shifts every count

```sql
def climb(n):
    ways = [0] * (n + 1)
    ways[1] = 1
    for i in range(2, n + 1):
        ways[i] = ways[i - 1] + ways[i - 2]
    return ways[n]


print(climb(5))
```

It prints 5, and the right count is 8. With ways[0] = 0 the table claims there is no way to stand at the bottom, so ways[2] becomes 1 and every later cell lags 1 Fibonacci step behind. Calling climb(0) is worse: the list has 1 slot, so ways[1] = 1 raises IndexError: list assignment index out of range. Starting from ways = [1, 1] + [0] \* (n - 1) and deleting the second line fixes both, since a negative repeat count yields an empty list.


<br>

### Bug 2: a table a cell short

```sql
def fewest_batches(target, sizes):
    dp = [0] + [float("inf")] * (target - 1)
    for t in range(1, target + 1):
        for s in sizes:
            if s <= t:
                dp[t] = min(dp[t], dp[t - s] + 1)
    return dp[target]


print(fewest_batches(6, [1, 3, 4]))
```

Cells for t = 1 through 5 fill normally, then t = 6 raises IndexError: list index out of range, because the list has 6 slots numbered 0 to 5. States 0 through target are target + 1 values, so the table is [0] + [float('inf')] \* target. Count the states, base included, before sizing a table.


<br>

### Bug 3: a minimum that starts at 0

```sql
def fewest_batches(target, sizes):
    dp = [0] * (target + 1)
    for t in range(1, target + 1):
        for s in sizes:
            if s <= t:
                dp[t] = min(dp[t], dp[t - s] + 1)
    return dp[target]


print(fewest_batches(6, [1, 3, 4]))
```

It prints 0. Every slot starts at 0, min(0, x) is 0 for any positive x, and no cell ever changes. A minimum must start above every real answer, which means infinity. A maximum must start below every real answer: 0 works when values cannot be negative, and float('-inf') covers the rest. Unreachable states then stay at infinity, which is how the bottom-up solver in the classic problems section returned -1.


<br>

### Bug 4: a cache that outlives its inputs

```sql
from functools import lru_cache

sizes = [1, 3, 4]


@lru_cache(maxsize=None)
def best(t):
    if t == 0:
        return 0
    return 1 + min(best(t - s) for s in sizes if s <= t)


print(best(6))
sizes = [1, 2]
print(best(6))
print(best(7))
```

It prints 2, 2, then 3. The first call caches best(0) through best(6) for sizes [1, 3, 4]. After sizes changes, best(6) is a hit and returns the stale 2, although [1, 2] needs 3. Then best(7) is a miss built on stale cells, so it returns 3, while the true answers are 2 for the old sizes and 4 for the new ones. The key is t alone, so nothing tells the cache the data changed: pass the sizes as a tuple argument, call best.cache_clear() on every change, or define best inside the solver.


<br>

### Bug 5: filling in the wrong direction

```sql
def best_from(nums):
    n = len(nums)
    dp = [0] * (n + 2)
    for i in range(n):
        dp[i] = max(dp[i + 1], nums[i] + dp[i + 2])
    return dp[0]


print(best_from([2, 7, 9, 3, 1]))
```

It prints 2 with no error. Here dp[i] is the best revenue from day i to the end, so it reads dp[i + 1] and dp[i + 2], but the forward loop reads those cells while they still hold their starting 0s. Each cell becomes its own day's revenue and dp[0] is 2. Looping with range(n - 1, -1, -1) fills from the right and returns 12. The rule: fill first the cells the recurrence points to.

| Bug | Symptom | Fix |
| --- | --- | --- |
| Base case | Counts shifted, or IndexError at n = 0 | Set every base cell from its meaning |
| Table size | IndexError at the last state | Allocate target + 1 cells |
| Initial value | Every minimum is 0 | Start a minimum at infinity |
| Stale cache | Answers that match no input | Key on every input, or clear the cache |
| Fill order | Wrong answer, no error | Fill the cells a cell reads first |


<br>

### Find the bug yourself

```sql
def rob(nums):
    dp = [0] * (len(nums) + 1)
    for i in range(2, len(nums) + 1):
        dp[i] = max(dp[i - 1], dp[i - 2] + nums[i - 1])
    return dp[-1]


print(rob([5, 1, 1, 5]))
```

Name which of the 5 bugs this is, what it prints, and the fix.

*It prints 6 instead of 10. This is bug 1, a missing base case: dp[1] stays 0 instead of day 1's 5, so day 1 never counts. Adding dp[1] = nums[0] after creating the list fixes it for any non-empty input.*


<br>

---

## Putting It All Together

An online marketplace's data team owns a nightly maintenance window on a shared cluster. Backfill jobs with start hours, end hours and priority scores compete for a single reserved slot, and the staged output files must reach the warehouse loader in batches of the fixed sizes it accepts. The on-call engineer must produce the plan and explain why it beats the hand-picked schedule the team used last quarter.

- Recognizing the problem: jobs interact through overlapping hours and batch counts reuse smaller counts, so both DP properties hold, and highest-score-first loses as soon as a big job blocks 2 better ones.
- Top-down first: an inner function cached with @lru_cache on the file count gives a correct batch planner quickly, and cache_info() confirms a single miss per state.
- Bottom-up for scale: the same recurrences written as loops avoid the 1000-frame recursion limit when file counts reach thousands.
- The framework: dp[i] as the best score from the first i jobs by end hour, and dp[t] as the fewest batches for t files, each with its base case and fill order.
- The mistake checklist: infinity for the batch minimum, target + 1 cells, a fresh cache for each night's inputs, and fills that follow the recurrence.


<br>

---

## Key Takeaways

- DP needs both overlapping subproblems and optimal substructure. Name a repeated state to show the first, and find a counterexample to rule out greedy.
- @lru_cache keys on hashable arguments. Cache an inner function on the changing argument, use maxsize=None, and confirm that misses equal your state count.
- Every 1D DP is 5 answers: state, recurrence, base case, fill order and answer. Write them before the code.
- Cost is states times work per state: O(target \* len(sizes)) for batches, O(n) for stairs and promotions.
- Job scheduling and header splitting become 1D DPs once dp[i] is defined in business terms.
- Base cases, table size, initial values, stale caches and fill order cause most DP bugs, and each has a recognizable symptom.
