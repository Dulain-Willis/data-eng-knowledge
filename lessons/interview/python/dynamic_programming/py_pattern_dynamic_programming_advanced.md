# Dynamic Programming: Advanced

The third round of an Uber data engineering onsite opens with routing. A courier has 12 pickups, the interviewer says. Each leg's cost depends on the previous stop; return the cheapest order. The candidate starts listing permutations and, doing the arithmetic aloud, stops at 479 million orderings. The interviewer nods and changes the setting. The same courier events now arrive twice, from 2 app versions that format them differently, and the task is collapsing the duplicates without comparing every pair. The final question moves into the warehouse: a 9-table query, and why the engine never tries every join order either. The candidate who passes hears a single pattern in all 3 questions: enumerate a small state and reuse it through a recurrence, after estimating what the table costs before writing a line.


<br>

### What you will be able to do

Encode subset states as bitmasks, fill them in numeric order, and size the table before writing code

Propagate include and exclude states up a tree with an iterative post-order, and reroot for per-node answers

Build thresholded token alignment for log and record dedupe, with blocking that bounds the pair count

Cut DP memory with rolling rows and replace long linear recurrences with matrix powers

Explain how a cost-based optimizer orders joins with subset DP, and where its answer stops being trustworthy


<br>

---

## Bitmask DP

Bitmask DP fits problems where the answer depends on which members of a small set are already used, and on nothing else about the path that got there. A route through 12 pickups and an assignment of 10 backfill jobs to 10 worker slots both carry a subset as their state. Store that subset as the bits of an integer and the state space becomes a list with 1 entry per subset, indexed by the integer itself.


<br>

### Spotting it in a prompt

- The set is small, usually 20 items or fewer, and the prompt says every, all or each
- Each step's cost depends on what is already used, so a greedy pick can strand you later
- Order matters only through the most recent item, which adds 1 index to the state


<br>

### Masks as sets

| Question | Python | Result for mask = 13 |
| --- | --- | --- |
| Is item 2 in the set? | `mask >> 2 & 1` | 1 |
| Is item 1 in the set? | `mask >> 1 & 1` | 0 |
| Add item 1 | `mask | 1 << 1` | 15 |
| Remove item 3 | `mask & ~(1 << 3)` | 5 |
| How many items? | `bin(mask).count("1")` | 3 |
| Lowest item's bit | `mask & -mask` | 1 |
| All 4 items used | `(1 << 4) - 1` | 15 |

The integer 13 is `0b1101`, because 13 = 8 + 4 + 1; every item except item 1 is in the set. Python's precedence helps here: shifts bind tighter than `&`, and `&` binds tighter than `==`, so `mask >> i & 1 == 1` needs no parentheses to mean `((mask >> i) & 1) == 1`. Popcount is where 3.9 bites. Calling `(13).bit_count()` stops with `AttributeError: 'int' object has no attribute 'bit_count'`, because `int.bit_count` arrived in Python 3.10, while `bin(mask).count("1")` runs on both.


<br>

### Assignment: the mask is the set of busy workers

The prompt: 3 jobs, 3 workers, a cost for every job-worker pairing, and each worker takes exactly 1 job. Define `dp[mask]` as the cheapest way to hand the first k jobs, where k is the number of set bits, to exactly the workers in `mask`. The next job to place is never stored, since the popcount already names it. The fill order needs no extra work either: setting a bit always yields a larger integer, so a loop from 0 to `2**n - 1` reaches each mask after every mask that leads into it.

https://github.com/user-attachments/assets/0af520ae-b917-4b7e-86e8-df9c761e2deb

Read the printed list by index. `dp[3]` is 8. With workers 0 and 1 busy, job 0 on worker 1 for 2 plus job 1 on worker 0 for 6 beats the 13 of the reverse pairing. `dp[7]` is 9, and 3 masks competed for it: mask 3 offered 9, against 10 from mask 6 and 20 from mask 5.

*Predict before reading on: raise cost[2][2] from 1 to 9 and rerun. What is dp[7] now, and which mask supplies it? Answer: 10, through mask 6, because the route through mask 3 now costs 17.*


<br>

### Sequencing adds the last item to the state

Now let each job's setup time depend on the job that ran before it, as a warm cache does. The used set alone has forgotten where the machine is, so the state becomes `(mask, last)`. This is the Held-Karp recurrence, published in 1962: `n * 2**n` states with up to n moves out of each, for O(n^2 \* 2^n) time against n! for brute force. Memoized recursion keeps it short.

```sql
from functools import lru_cache


def cheapest_sequence(setup):
    n = len(setup)
    full = (1 << n) - 1

    @lru_cache(maxsize=None)
    def best(mask, last):
        if mask == full:
            return 0
        options = []
        for nxt in range(n):
            if not mask >> nxt & 1:
                step = setup[last][nxt]
                options.append(step + best(mask | 1 << nxt, nxt))
        return min(options)

    return min(best(1 << start, start) for start in range(n))


setup = [
    [0, 4, 9, 3],
    [4, 0, 2, 7],
    [9, 2, 0, 5],
    [3, 7, 5, 0],
]
print(cheapest_sequence(setup))
```

It prints 9: the order runs 3, 0, 1, 2, and the setups between consecutive jobs add up as 3 + 4 + 2.

| n | Masks | Assignment steps | Sequencing bound | Orderings (n!) |
| --- | --- | --- | --- | --- |
| 10 | 1,024 | 10,240 | 102,400 | 3,628,800 |
| 16 | 65,536 | 1,048,576 | 16,777,216 | 20,922,789,888,000 |
| 20 | 1,048,576 | 20,971,520 | 419,430,400 | 2,432,902,008,176,640,000 |

This table is the interview answer. At n = 16 the sequencing bound is about 17 million transitions, which CPython clears in well under a minute; at n = 20 it is 419 million, and the memo holds about 10.5 million `(mask, last)` keys. That is the moment to say the exact method stops, and to name what replaces it: a heuristic route, clusters of stops solved separately, or the same recurrence in compiled code.


<br>

### Submasks: splitting a set in 2

Some problems split a set instead of growing it 1 item at a time, such as cutting a group of tables into the 2 sides of a join. The update `sub = (sub - 1) & mask` steps through every submask of `mask` in decreasing order. Summed over all masks, that walk touches about 3^n pairs, because each item lands in exactly 1 of 3 places: the submask, the rest of the mask, or outside the mask.

```sql
mask = 0b1011
sub = mask
while sub:
    print(format(sub, "04b"))
    sub = (sub - 1) & mask
```

It prints 7 lines, `1011`, `1010`, `1001`, `1000`, `0011`, `0010`, `0001`: every nonempty submask of the 3 set bits, largest first.

> What the grader listens for
>
> - The state named in full, with the extra index when order matters
> - The table size, 2^n or n \* 2^n, computed before any code
> - Numeric order justified, since setting a bit yields a larger integer


<br>

---

## DP on Trees

Warehouse data is full of hierarchies: employees and managers, product categories, folder trees, comment threads. A tree DP computes a value at every node from the values its children report, so a node can only be finished once its whole subtree is. That order is post-order, and the design work is deciding what each node hands up.


<br>

### What each node hands to its parent

The prompt: pick employees for a skip-level survey to maximize total score, never picking someone together with their direct manager. Each node returns a pair. `take` is the best subtree total with the node picked: its score plus every child's `skip`. `skip` is the best total with it left out: the sum over children of the larger of `take` and `skip`. A single number per node fails, since a parent that sees only a child's best total cannot tell whether that total used the child.

Rows as they land

| employee | manager | score |
| --- | --- | --- |
| ceo | NULL | 5 |
| vp_a | ceo | 3 |
| vp_b | ceo | 4 |
| m1 | vp_a | 4 |
| m2 | vp_a | 2 |
| m3 | vp_b | 6 |

Children built from manager

| node | children |
| --- | --- |
| ceo | vp_a, vp_b |
| vp_a | m1, m2 |
| vp_b | m3 |
| m1 | none |
| m2 | none |
| m3 | none |

https://github.com/user-attachments/assets/51cfa760-78fe-449a-8603-15dd82cb0a70

The prints arrive leaves first, and ceo comes last: m3 precedes vp_b, while m2 and m1 precede vp_a. Each node is pushed twice, once to schedule its children and once, flagged done, to combine their pairs, which is how an explicit stack produces post-order. At the root, `take` is 17, the CEO plus all 3 managers with both VPs left out, and `skip` is 12. The answer is the larger of the 2.

*Try it first: raise vp_b's score from 4 to 9. What pair does vp_b hand up, and does the answer move? Answer: vp_b reports (9, 6); the root's skip rises to 15, and the answer stays 17.*


<br>

### Why the traversal is iterative

Ingested hierarchies are often far from balanced: a reply chain 1,500 messages deep, or a bad load that set every row's manager to the row before it, is a path of depth 1,500. CPython's default recursion limit is 1,000 frames.

```sql
import sys


def depth(node, children):
    best = 0
    for child in children[node]:
        best = max(best, depth(child, children))
    return best + 1


chain = {i: [i + 1] for i in range(1500)}
chain[1500] = []
print(sys.getrecursionlimit())
print(depth(0, chain))
```

It prints 1000, then a traceback whose last line begins `RecursionError: maximum recursion depth exceeded`. Adding `@lru_cache` changes nothing, because caching removes repeated work and the depth comes from the shape. Raising the limit with `sys.setrecursionlimit` depends on version: on CPython 3.10 and earlier each Python call also uses C stack, so a high limit overflows it and kills the process with no exception. From 3.11, pure-Python calls leave the C stack alone, yet a high limit trades a clean error for memory growth, and recursion through C code stays capped. The done-flag stack sidesteps all of it on every version.


<br>

### Rerooting: an answer at every node

The follow-up: for every service in a call tree, return its total hop count to all other services. A traversal from each of n nodes costs O(n^2), 10 billion node visits at 100,000 services. Rerooting gets every answer in 2 passes. The first, post-order, computes each subtree's size and the root's total. The second visits parents before children and moves the root across 1 edge at a time: the child's own subtree gets 1 hop closer and the other `n - size[child]` nodes get 1 hop farther.

```sql
def hops_to_all(n, edges):
    adj = [[] for _ in range(n)]
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    parent = [-1] * n
    order = [0]
    for node in order:
        for nb in adj[node]:
            if nb != parent[node]:
                parent[nb] = node
                order.append(nb)
    size = [1] * n
    down = [0] * n
    for node in reversed(order[1:]):
        size[parent[node]] += size[node]
        down[parent[node]] += down[node] + size[node]
    total = [0] * n
    total[0] = down[0]
    for node in order[1:]:
        total[node] = total[parent[node]] - size[node] + (n - size[node])
    return total


print(hops_to_all(6, [(0, 1), (0, 2), (2, 3), (2, 4), (2, 5)]))
```

It prints `[8, 12, 6, 10, 10, 10]`. Node 2, the hub with 3 leaves, has the smallest total. Check it by hand: 1 hop to node 0, 2 hops to node 1, 1 hop to each leaf, 6 in all.

> Checks before trusting the tree
>
> - Count roots: 0 means a manager cycle somewhere, and more than 1 means a forest to hang under a virtual root
> - Compare visited nodes to input rows: a cycle away from the root is never reached and drops out without an error
> - Resolve manager keys that point at missing rows before building children, or each becomes an extra root


<br>

---

## Sequence Alignment for Dedupe

Edit distance and LCS reach dedupe with their recurrences unchanged; what changes is everything around them. Dedupe asks which units to align (characters for names, tokens for log lines), what each edit costs, and how to skip pairs that cannot reach the threshold. The prompts sound like 'the same event arrives from 2 services with different formatting, collapse them' or 'merge customer records typed in by 3 call centers'.


<br>

### Align tokens, after masking what varies

A pair of log lines from the same template differ mostly in their variable fields: user ids, IP addresses, request ids, timestamps. Character distance between them stays large even when the template matches. Replace variable fields with placeholders and split on whitespace; the alignment then runs over token lists, where the alphabet is words and each sequence shrinks to a handful of entries.

```sql
import re


def template(line):
    line = re.sub(r"\b\d+\.\d+\.\d+\.\d+\b", "{IP}", line)
    line = re.sub(r"\b\d+\b", "{NUM}", line)
    return line.split()


def within(a, b, k):
    if abs(len(a) - len(b)) > k:
        return False
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            sub = prev[j - 1] + (a[i - 1] != b[j - 1])
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, sub)
        if min(cur) > k:
            return False
        prev = cur
    return prev[-1] <= k


a = template("user 4821 login failed from 10.0.0.7")
b = template("user 9930 login failed from 10.0.0.9 retry")
print(a)
print(within(a, b, 1))
```

It prints `['user', '{NUM}', 'login', 'failed', 'from', '{IP}']`, then `True`: the second line masks to the same 6 tokens plus `retry`, a distance of 1 against a limit of 1. The IP pattern runs before the bare-number pattern for a reason: in the other order, `10.0.0.7` would become 4 `{NUM}` placeholders joined by dots.

*Predict before reading on: what does within(a, b, 0) return for the same 2 lines, and which line of the function decides it? Answer: False, from the length check, before a single cell is filled, since the token lists differ in length by 1.*


<br>

### 3 cuts that skip work

- Length gap: the distance is at least the difference in lengths, so a gap above k ends the comparison before any DP.
- Row minimum: each cell comes from the row above plus a nonnegative cost, or from its left neighbour, so a row's smallest value never drops below the previous row's. Once min(cur) > k, no later row recovers.
- Band: cell (i, j) is at least |i - j|, so only the 2k + 1 cells nearest the diagonal can stay within k, turning O(mn) work into O(kn).


<br>

### Global or local alignment

| ✓ Global (Needleman-Wunsch, 1970) | ✗ Local (Smith-Waterman, 1981) |
| --- | --- |
| • Scores both sequences end to end<br><br>• Unmatched tokens at either end cost gaps<br><br>• The answer sits in the bottom-right cell<br><br>• Fits records with a fixed shape: names, addresses, masked templates | • Scores the best-matching stretch inside each sequence<br><br>• Cells floor at 0, so a bad prefix stops counting<br><br>• The answer is the largest cell anywhere<br><br>• Fits a known message buried in lines with different prefixes |

Edit costs are a design choice as well. Adjacent transpositions are among the commonest typos in names, and plain edit distance charges 2 for `Jhon` against `John`. Adding a case that reads 2 rows back and charges 1 for a swapped pair, the optimal string alignment variant, brings that to 1.


<br>

### Record linkage: the pair count is the cost

Per pair, alignment is O(mn), cheap for short fields; the pair count is what breaks. A table of 1 million customer records forms 499,999,500,000 unordered pairs. Blocking compares only records that share a cheap key, such as postal code. With 10,000 postal codes of 100 customers each, every block holds 4,950 pairs and the whole job 49.5 million, about 10,000 times fewer.

```sql
SELECT
  a.customer_id AS left_id,
  b.customer_id AS right_id,
  LEVENSHTEIN_DISTANCE(a.full_name, b.full_name) AS name_distance
FROM customers AS a
JOIN customers AS b
  ON a.postal_code = b.postal_code
    AND a.customer_id < b.customer_id
WHERE LEVENSHTEIN_DISTANCE(a.full_name, b.full_name) <= 2
```

Blocking trades recall for cost: a customer who moved between postal codes is never compared with their old record. The standard counter is 2 or 3 blocking passes on different keys, with their candidate pairs unioned; a pass on postal code might be followed by one on phone suffix and another on surname prefix. Skew needs its own guard. A default postal code like `00000` holding 50,000 rows adds 1,249,975,000 pairs by itself, more than 25 times the rest of the job, so profile block sizes and split any block over a cap with a second key.

Thresholds need normalizing too. Both pairs here are 2 edits apart. `Katherine` and `Catharine` are likely the same name, but `Jo` against `Al` share nothing. Divided by the longer length, they score 0.22 and 1.0.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Mask every variable field in a log line before aligning it<br><br>• Divide distance by length before picking a threshold<br><br>• Union candidate pairs from 2 or more blocking keys<br><br>• Profile block sizes and split any block above a cap | • Run character distance on raw lines that carry request ids<br><br>• Apply 1 absolute threshold to 3-letter and 30-letter names<br><br>• Generate all pairs and filter them afterwards<br><br>• Merge on a name match alone without a second field agreeing |


<br>

---

## Space Optimization Techniques

A DP table is sized by its states, yet each cell reads only a few others. Space optimization keeps those few and drops the rest, and every version of the question underneath reduces to 2 checks: which earlier cells does a cell read, and what is lost once the others are gone?


<br>

### Count how far back each recurrence reads

| Recurrence | Reads from | What to keep |
| --- | --- | --- |
| Edit distance, LCS | Row i - 1 and the cell to the left | 1 row plus 1 saved diagonal |
| Optimal string alignment | Rows i - 1 and i - 2 | 3 rows |
| 0/1 knapsack | Capacities c and c - w in the previous row | 1 row, filled from high capacity down |
| Assignment over masks | Masks with 1 fewer set bit | 2 popcount layers, as dicts keyed by mask |
| Interval DP | Every shorter interval inside it | The full table |

Cell j needs 3 neighbours: `row[j]` from the previous row (up), `row[j - 1]` from the current row (left), and the previous row's `row[j - 1]` (diagonal), which was overwritten 1 step earlier. Save `up` before writing, hand it to the next cell as `diag`, and a single list carries the whole edit distance computation.

https://github.com/user-attachments/assets/5e6988d4-d8f1-4540-9ae9-a3a5422a6f9f

Each printed line is the entire memory of the run at that moment. The full table for `flaw` against `lawn` has 25 cells; this run keeps 5 numbers plus 2 saved values. The final 2 is the distance: delete the f, append an n.

*Try it first: delete the line diag = up. Which value would every cell after the first in a row use as its diagonal? Answer: the value saved at the top of the row, i - 1, so from column 2 onward each diagonal match reads a stale number.*


<br>

### What rolling throws away

The full table also records which edit produced each cell, and the traceback walks it to recover the alignment itself: which tokens matched and which were inserted. With 1 row, only the distance survives, and a dedupe threshold needs nothing more. When the alignment is the output, as in a field-by-field merge of 2 records, Hirschberg's 1975 method recovers it in linear space. It runs the rolling DP forward over the first half of a and backward over the second half, picks the column of b where the 2 halves meet at the lowest total, and recurses on the 2 smaller problems, for about twice the arithmetic of a plain fill. On a pair of 20,000-token sequences held in Python lists, the 2 layouts compare like this.

- **3.2 GB** — Full-table list slots, 20,000 tokens
- **160 KB** — Slots in 1 rolling row, 20,000 tokens

> **TIP**
>
> An `lru_cache` memo keeps every state it has ever stored. For the 20-job sequencing DP that is about 10.5 million `(mask, last)` keys, each a tuple in a dict, well past a gigabyte. A bottom-up fill by popcount layer holds 2 layers at once, about 3.7 million states at the widest point, and gives up the traceback in exchange.


<br>

### Matrix powers for fixed linear updates

Matrix powers attack the other end: a recurrence with a tiny state that runs for an enormous number of steps. Fibonacci needs 2 numbers of memory but n steps of time. When the update from 1 state vector to the next is the same linear map at every step, write it as a matrix M. The state after k steps is M^k applied to the start, and repeated squaring builds M^k from about log2(k) squarings plus at most that many extra products. For an s-by-s matrix that is O(s^3 log k), against O(s^2 k) for stepping.

https://github.com/user-attachments/assets/76d4318a-6e9e-4cd1-8e17-7b5516e55faa

The power of `[[1, 1], [1, 0]]` holds F(n) in its top-right entry, so the run prints `10 55` and then `90 2880067194370816120`. For k = 90, binary `1011010`, the loop squares 7 times and multiplies into the result 4 times, once per set bit. At 90, a loop of additions would still win; the matrix method only pulls ahead once k reaches the billions.

The same move counts paths. Put a session's allowed event transitions in an adjacency matrix A, with a 1 where event j may follow event i; entry (i, j) of A^k is then the number of distinct k-step event paths from i to j, which a funnel report or a synthetic-data generator may need. These counts can grow exponentially, so interview versions often ask for them modulo 1,000,000,007; Python's integers never overflow, but each multiplication slows as the digits pile up.


<br>

---

## DP in Data System Design

A classic cost-based optimizer handed a multi-join query runs the subset DP from this lesson's first section. Patricia Selinger and colleagues published the design in 1979, in 'Access Path Selection in a Relational Database Management System': build the cheapest plan for every subset of the query's tables, smallest first, and each answer is then reused inside every larger subset that contains it.


<br>

### Join order as a subset DP

The state is a set of tables, and its value is the cheapest plan that joins exactly that set. The principle of optimality makes the reuse safe: if the best plan for a query over orders with customers and regions joins customers to regions first, it contains the best plan for that pair, so a settled pair never needs revisiting. Here is a 3-table query written fact table first.

```sql
SELECT
  r.region_name,
  COUNT(*) AS order_count
FROM orders AS o
JOIN customers AS c
  ON o.customer_id = c.customer_id
JOIN regions AS r
  ON c.region_id = r.region_id
GROUP BY r.region_name
```

The toy below plans it with 1,000,000 orders, 50,000 customers and 20 regions, each join predicate dividing the product of its inputs by the size of the table it points at.

```sql
from itertools import combinations

rows = {"O": 1_000_000, "C": 50_000, "R": 20}
divisor = {frozenset("OC"): 50_000, frozenset("CR"): 20}


def card(tables):
    size = 1
    for t in tables:
        size *= rows[t]
    for pair, d in divisor.items():
        if pair <= tables:
            size //= d
    return size


best = {frozenset(t): (0, t) for t in rows}
names = sorted(rows)
for k in range(2, len(names) + 1):
    for combo in combinations(names, k):
        subset = frozenset(combo)
        for t in combo:
            rest = subset - {t}
            cost = best[rest][0] + card(subset)
            if subset not in best or cost < best[subset][0]:
                best[subset] = (cost, f"({best[rest][1]} x {t})")
print(best[frozenset(rows)])
```

It prints `(1050000, '((R x C) x O)')`: join the 20 regions to their customers, a 50,000-row intermediate, then bring in orders. The written order, orders with customers first, costs 2,000,000 under the same model, because its first intermediate already holds 1,000,000 rows. Orders with regions shares no predicate, so that pair is a 20,000,000-row cross product, which the DP prices and discards like any other candidate. The cost model here is the sum of intermediate result sizes.

*Predict before reading on: how many entries does best hold when the loop ends, and how many would it hold for 10 tables? Answer: 7, 1 per nonempty subset of 3 tables; for 10 tables, 1,023.*


<br>

### Left-deep, bushy, and when exactness stops

The toy only ever extends a plan by 1 table, so every plan it can produce is left-deep, for `n * 2**n` work. Bushy plans let both sides of a join be composite, so 2 dimension joins can finish before meeting the fact table; enumerating them means splitting each set into 2 nonempty parts with the submask loop, for around 3^n work in total.

- **17.6 billion** — Bushy join trees over 10 tables
- **59,049** — Set-and-subset pairs at 10 tables

At 15 tables the bushy walk is 14,348,907 pairs. At 30 it is about 206 trillion, and exhaustive enumeration is out of reach. The usual fallbacks restrict the search to left-deep plans, join greedily by the smallest estimated intermediate, or switch to randomized search above a configured table count. Naming which applies, and at what n, is the part of the answer that shows judgement.


<br>

### When the subset is not the whole state

A plan for orders and customers that costs 10% more but emits rows sorted by `customer_id` can spare a later merge join, or the query's `ORDER BY`, its own sort. Selinger's design kept, for each subset, the cheapest plan per interesting order, meaning a sort order some later step can use. That is the `(mask, last)` move from sequencing: when the future cost depends on something the subset forgets, put that thing in the key.


<br>

### A DP is only as good as its inputs

The recurrence finds the true minimum of the cost model, and the model runs on cardinality estimates built from table statistics, errors in which compound across joins. If the optimizer believes orders joined to customers yields 1,000,000 rows while duplicated customer keys make it 40 million, the plan is optimal for a query that does not exist. In daily work that means running `ANALYZE customers` after a large load, and putting `EXPLAIN ANALYZE` in front of a slow query to compare estimated and actual rows at each join.

Dynamic programming can build the statistics too. The V-optimal histogram from a 1998 VLDB paper by Jagadish and coauthors places bucket boundaries with a DP over prefixes of the sorted values. The same prefix DP splits a sorted key range into k contiguous backfill partitions with the lightest possible heaviest partition, and it has a floor: no boundaries can push that partition below the largest single key's row count, so a hot key needs a second split column.

> Connecting it in an interview answer
>
> - Name the state: a set of tables, plus a sort order when one matters
> - Size it: 2^n subsets for left-deep, 3^n splits for bushy
> - Say where exact search ends and which fallback takes over
> - Name cardinality estimates as the weakest input and say how they stay fresh


<br>

---

## Putting It All Together

A food-delivery marketplace merges restaurant records from 3 acquired regional apps into 1 catalog, rebuilds the parent-brand hierarchy over the merged rows, and serves a nightly revenue report that joins orders to that hierarchy.

- Masked-token alignment inside postal-code blocks finds duplicate restaurants, with a row-minimum cutoff and 1 rolling row per comparison.
- The merged brand links form a tree: an iterative post-order rolls revenue up to every parent, and a root count catches the cycles a bad merge introduces.
- Rerooting gives every location its total distance to the rest of its brand family in the same 2 passes.
- The nightly report's join order comes from the optimizer's subset DP, which stays sound only if statistics on the merged table are refreshed after the load.
- Backfilling the merged catalog by key range is the prefix-partition DP, whose floor is the busiest single brand's row count.


<br>

---

## Key Takeaways

- A bitmask turns a subset into a list index, and numeric order is a valid fill order because every transition sets a bit.
- When the next cost depends on the last choice, the state becomes (mask, last); size the table before writing code.
- Tree DP hands a small tuple from each child to its parent, and an explicit stack keeps deep hierarchies clear of the 1,000-frame recursion limit.
- Rerooting answers a per-node question for the whole tree in 2 passes instead of n traversals.
- Dedupe alignment wins through what it skips. Blocking keys and masked tokens shrink the input before any alignment starts; inside each alignment, bands plus length and row-minimum cutoffs end the work early.
- Keep as many rows as the recurrence reads back, and know that rolling discards the traceback unless Hirschberg's split recovers it.
- Matrix powers turn k steps of a fixed linear update into about log2(k) multiplications.
- Join ordering is subset DP: exact for its cost model, and only as right as the cardinality estimates feeding it.
