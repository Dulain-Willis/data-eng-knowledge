# Dynamic Programming: Intermediate

Ines is 30 minutes into a data engineering interview at Google when the interviewer pastes 2 column lists from consecutive loads of a partner feed. "Some columns were renamed and some dropped. Write a function that scores how far apart `cust_name` and `customer_nm` are, then tell me what it costs across every pair." She recognizes a table indexed by 2 prefixes. She writes the recurrence, then fills the base row. Then the follow-ups land: why her loops run in that order, how to keep only 2 rows, what changes when a replacement costs more than an insert. The interview turns on those follow-ups, and each one is about what a cell means, the order cells fill in, or how big the table gets. This lesson works through 5 families of 2D tables at that depth. Grids come first and intervals last. Knapsack follows grids, and string matching follows LCS and edit distance.


<br>

### What you will be able to do

Define the cell for a grid problem, fill it row-major, and shrink the table to a rolling row when the route is not needed.

Choose the capacity loop direction that makes knapsack 0/1 or unbounded, and size the table from the capacity's unit.

Implement LCS and edit distance, recover the shared elements, and match each measure to a data engineering task.

Adapt the prefix-pair template to wildcard matching and subsequence counting by changing what a cell holds and how the base row starts.

Fill interval tables by range length and explain why row-major order returns wrong answers without raising errors.


<br>

---

## 2D DP: Grid Problems

A grid question hands you an R by C board and a rule that usually allows moves only right or down. It then asks for a single number about the routes from the top-left cell to the bottom-right. Most often that is how many routes there are or what the cheapest one costs; sometimes it is the most a route can collect. The board may be a robot on a warehouse floor or a seat map, and in pipeline work it is often a cost matrix of stages by hour. The signal is the movement rule. If no move can return to a visited cell, every cell's answer depends only on cells that are already final, and the whole table fills in a single pass.


<br>

### The state is the cell you stand on

Define dp[r][c] as the answer to the same question asked of the smaller grid that ends at cell (r, c). With right and down as the only moves, the last step into that cell came from (r - 1, c) or (r, c - 1), so the cheapest path obeys dp[r][c] = grid[r][c] + min(dp[r - 1][c], dp[r][c - 1]). Row 0 and column 0 are the base cases because each of their cells has a single predecessor, and the start cell has none: dp[0][0] = grid[0][0].

grid: cost of entering each cell

|  | c0 | c1 | c2 |
| --- | --- | --- | --- |
| r0 | 1 | 3 | 1 |
| r1 | 1 | 5 | 1 |
| r2 | 4 | 2 | 1 |

dp: cheapest total to reach each cell

|  | c0 | c1 | c2 |
| --- | --- | --- | --- |
| r0 | 1 | 4 | 5 |
| r1 | 2 | 7 | 6 |
| r2 | 6 | 8 | 7 |

Look at 2 cells. At (1, 1) the cost is 5 plus the smaller of 4 from above and 2 from the left, giving 7. At the corner (2, 2) it is 1 plus the smaller of 6 and 8, giving 7, the cheapest total: right, right, down, down, through costs of 1 + 3 + 1 + 1 + 1. Going down first costs 1 + 1 + 4 + 2 + 1, a total of 9.


<br>

### Counting routes around blocked cells

To count routes instead of pricing them, replace min-plus with a sum: dp[r][c] = dp[r - 1][c] + dp[r][c - 1]. A blocked cell is forced to 0, so no route flows through it. The animation fills a 3 by 4 grid with 1 blocked cell at (1, 1) and prints each row as it finishes. Watch cell (1, 2): its left neighbour is the block, so it receives only from above.

https://github.com/user-attachments/assets/b8548352-cbd3-484c-ae51-ce6ba5ea57c2

*A blocked cell holds 0, so no route passes through it.*

Check the 4 it prints by counting another way. An open 3 by 4 grid has 10 monotone routes, since each is 2 downs and 3 rights in some order, which is C(5, 2). Exactly 2 routes reach (1, 1) and 3 continue from it to the corner, so 6 routes are blocked and 4 remain. Saying a cross-check like this aloud shows the interviewer you verified the table.


<br>

### Fill order and the rolling row

Row-major order is correct here because each cell reads only the cell above it and the cell to its left, and both are finished before it. The same fact lets the table shrink. Row r reads only row r - 1 and itself, so a single list of C values can stand in for the whole grid: before the update, dp[c] still holds the value from the row above, and dp[c - 1] already holds this row's left neighbour.

```sql
def min_path_sum(grid):
    cols = len(grid[0])
    dp = [float("inf")] * cols
    dp[0] = 0
    for row in grid:
        dp[0] += row[0]
        for c in range(1, cols):
            dp[c] = row[c] + min(dp[c], dp[c - 1])
    return dp[-1]


print(min_path_sum([[1, 3, 1], [1, 5, 1], [4, 2, 1]]))
```

| ✓ Full R x C table | ✗ Rolling row of C cells |
| --- | --- |
| • Memory grows with every row in the grid<br><br>• Walking back from the corner rebuilds the route<br><br>• Every cell's answer is readable after the fill | • Memory stays at a single row however tall the grid<br><br>• The route is lost unless each cell's choice is stored<br><br>• Only the last row survives the fill |

A 3,000 by 2,000 grid needs the full table when the question asks for the route, while a cost-only question fits in the rolling row.

- **6,000,000** — cells the full table allocates

> What the follow-ups test
>
> - A blocked start cell makes the answer 0; check the obstacle before seeding `dp[0][0] = 1`.
> - Filling row 0 with 1s as a shortcut breaks when row 0 holds a block: every cell after it stays 0.
> - Time is O(R x C); memory is O(R x C) for the full table or O(C) for the rolling row.
> - A diagonal move adds a third read at `dp[r - 1][c - 1]`. Row-major order still works.

> **TIP**
>
> Say the state in a single sentence before writing code: `dp[r][c]` is the cheapest cost of any route from the start to (r, c). Interviewers grade the recurrence against that sentence, and a vague sentence is where off-by-one bugs begin.


<br>

---

## 0-1 and Unbounded Knapsack

Tonight's maintenance window holds 5 hours, and the backlog has 3 backfill jobs: A takes 2 hours and is worth 3 points, B takes 3 hours for 4, and C takes 4 hours for 5. Each job runs at most once. Which set earns the most? That is **0/1 knapsack**: a capacity, items with a cost and a value, and a take-or-skip decision per item. Change the rule to "each job may run as often as it fits", or to "fill a 100 GB budget with files of 3 fixed sizes, any count", and it becomes **unbounded knapsack**.


<br>

### The 0/1 table: items by capacity

Let dp[i][w] be the best value using only the first i items within capacity w. Skipping item i keeps dp[i - 1][w]. If its weight fits, taking it gives dp[i - 1][w - wt] + val. Both options read row i - 1, the table as it stood before this item existed, and that is what stops an item from being taken twice.

| Items considered | w=0 | w=1 | w=2 | w=3 | w=4 | w=5 |
| --- | --- | --- | --- | --- | --- | --- |
| None | 0 | 0 | 0 | 0 | 0 | 0 |
| A only | 0 | 0 | 3 | 3 | 3 | 3 |
| A and B | 0 | 0 | 3 | 4 | 4 | 7 |
| A, B and C | 0 | 0 | 3 | 4 | 5 | 7 |

Read the bottom-right cell. Taking C leaves 1 hour, worth 0 in the row above, for a total of 5; skipping C keeps the 7 above it. The answer is 7, which A and B make together. The cell at w = 4 shows taking C winning: C alone, worth 5, beats B alone, worth 4.


<br>

### One row, and why the loop runs backwards

Every row reads only the row above it, so a single list can replace the table, provided an update never reads a value this item has already changed. The update dp[w] = max(dp[w], dp[w - wt] + val) reads a smaller index. Walking w from high to low, dp[w - wt] still holds the previous row's value. Walking from low to high, it may already include this item, so the item is counted again. For 0/1 that is a bug; for unbounded knapsack, where reuse is allowed, it is the correct recurrence. The animation runs jobs A and B through both directions at capacity 5.

https://github.com/user-attachments/assets/dd1d687b-7576-4d56-8d1a-f7a4dc4791b0

*Same items, same capacity, only the loop direction differs.*

Compare position 4 in the 2 printed lists. Right to left gives 4, job B on its own; left to right gives 6, job A run twice. Capacity 5 lands on 7 either way, which is why a single test at full capacity can pass with the wrong direction. When the prompt says "at most once", the loop direction is the line to say aloud.

| ✓ 0/1 knapsack | ✗ Unbounded knapsack |
| --- | --- |
| • Each item is taken 0 or 1 times<br><br>• Capacity loop runs high to low<br><br>• The 2D form reads dp[i - 1][w - wt]<br><br>• Subset sum, equal partition, choosing backfills for a window | • Each item can be taken any number of times<br><br>• Capacity loop runs low to high<br><br>• The 2D form reads dp[i][w - wt]<br><br>• Coin change, rod cutting, filling a budget with repeatable sizes |


<br>

### Pseudo-polynomial time

Time is O(n x W) and memory is O(W) with the rolling row, where W is the capacity's numeric value, so the unit you count in is a design decision. That is why this complexity is called pseudo-polynomial: polynomial in the capacity's value, exponential in the number of bits that write it. Take 50 jobs and a 10 GB budget. Counted in megabytes, each row has 10,001 columns. Counted in bytes, each row has 10,000,000,001 columns, and the table cannot be built.

- **~500K** — table cells, megabyte units
- **~500B** — table cells, byte units

The fix is a coarser unit. Rounding every size up to the next megabyte can only overstate it, so any set the table accepts still fits the real budget, at the price of some wasted capacity. When all weights share a common divisor, dividing by it shrinks W with no loss.

> Same table, different question
>
> - Subset sum: booleans, where `dp[w]` is True when some subset weighs exactly w.
> - Equal partition: subset sum aimed at total / 2, after checking the total is even.
> - Fewest coins: unbounded, min instead of max, every cell starting at infinity except `dp[0] = 0`.
> - Count coin combinations: unbounded, add instead of max, coin loop outside the amount loop.
> - Count ordered sequences: amount loop outside, so 1 + 2 and 2 + 1 count separately.

| ✓ Do | ✗ Don't |
| --- | --- |
| • State whether each item is single-use before writing the loop<br><br>• Test a capacity where reuse would change the answer<br><br>• Size W in the coarsest unit the question allows | • Copy a knapsack loop without checking its direction<br><br>• Trust a test that only checks full capacity<br><br>• Build a byte-level table for a gigabyte budget |


<br>

---

## LCS and Edit Distance

Both problems compare 2 sequences in a table whose cell (i, j) covers the first i elements of one and the first j of the other. The **longest common subsequence** (LCS) is the longest list of elements appearing in both in the same order, gaps allowed. **Edit distance**, also called Levenshtein distance, is the fewest single-element edits that turn one sequence into the other, counting each insert or delete as 1 edit and a replacement as 1 edit too. The elements can be characters, lines of a file, or column names.


<br>

### LCS: a match moves along the diagonal

dp[i][j] is the LCS length of a[:i] and b[:j]. When the last elements match, pairing them never hurts, so dp[i][j] = dp[i - 1][j - 1] + 1. Otherwise at least one of them is left out, and the cell keeps the better of dropping either: max(dp[i - 1][j], dp[i][j - 1]). Row 0 and column 0 hold 0, since an empty prefix shares nothing. The code runs that table over 2 versions of a schema and walks back from the corner to recover the shared columns.

```sql
def lcs_table(a, b):
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp


def shared(a, b):
    dp = lcs_table(a, b)
    i, j, out = len(a), len(b), []
    while i > 0 and j > 0:
        if a[i - 1] == b[j - 1]:
            out.append(a[i - 1])
            i, j = i - 1, j - 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    return out[::-1]


v1 = ["id", "email", "name", "created_at"]
v2 = ["id", "name", "phone", "created_at"]
print(shared(v1, v2))
```

Walking back retraces the choice that set each cell: a match steps diagonally and records the element, a mismatch steps toward the larger neighbour. Here `email` was dropped and `phone` added. Line-based diff tools use the same table: the diff algorithm Hunt and McIlroy published in 1976 reports the lines outside a longest common subsequence of 2 files as removed or added.


<br>

### Edit distance reads 3 neighbours

dp[i][j] is the fewest edits turning a[:i] into b[:j]. The base row and column count edits against an empty prefix: dp[i][0] = i deletes and dp[0][j] = j inserts. When the last characters match, the cell copies its diagonal at no cost. Otherwise it pays 1 for the cheapest of 3 moves: delete a[i - 1] and read up, dp[i - 1][j]; insert b[j - 1] and read left, dp[i][j - 1]; or replace one with the other and read the diagonal.

Suppose a source renamed `amount` to `amt` between loads. The animation measures the gap between the 2 names, printing each row beside the letter of `amount` it covers.

https://github.com/user-attachments/assets/216bf214-e14b-4fee-a3f5-d3afb194e671

*Each printed row adds the next letter of amount.*

The bottom row ends at 3: delete the 3 letters oun from the middle. Normalized by the longer name, that is 3 out of 6, a similarity of 0.5, so a matcher that accepts 0.7 and above rejects a rename any analyst would accept. LCS sees it differently: all 3 letters of `amt` appear in order inside `amount`, so the LCS covers the whole shorter name. Typos are single-character edits and suit edit distance; abbreviations delete characters and suit an LCS ratio against the shorter name.

#### How the 2 measures connect

With replacement removed, distance equals len(a) + len(b) - 2 x LCS, because every element outside the LCS is deleted from a or inserted from b. For `amount` and `amt` that gives 6 + 3 - 6 = 3, matching the table, since no replacement helped. For `date` and `data` it gives 4 + 4 - 6 = 2, while full edit distance is 1: a single replacement does the work of a delete plus an insert.

| Data engineering task | Elements compared | Measure |
| --- | --- | --- |
| Fuzzy-match customer names across 2 feeds | characters | edit distance, normalized by length |
| Detect a renamed column between schema versions | characters | LCS length over the shorter name |
| Diff 2 versions of a SQL or config file | lines | LCS, with unmatched lines as changes |
| Find which columns were added or dropped | column names | LCS, walked back for the shared set |


<br>

### Cost and the length-check shortcut

Each comparison costs O(n x m) time. When only the distance is needed, a cell reads its own row and the row above, so 2 rows of length m + 1 suffice; listing the edits needs the full table or a stored choice per cell. A length check prunes pairs before any table exists: if the lengths differ by more than k, the distance exceeds k, because each surplus character needs its own insert or delete.

> Follow-ups to expect
>
> - List the edits: walk back from the corner; a diagonal step on a mismatch is a replace, an up step a delete, a left step an insert.
> - Replacement costing 2: the table turns into the insert-and-delete distance, len(a) + len(b) - 2 x LCS.
> - Swapped neighbours as 1 edit: a fourth case reads `dp[i - 2][j - 2]` when the 2 characters cross.
> - Distance-only memory: keep 2 rows and swap them after each row.


<br>

---

## DP on Strings

Many string questions share a single state: dp[i][j] answers the question for the prefixes s[:i] and t[:j]. Each cell compares the last characters s[i - 1] and t[j - 1] and builds its answer from at most 3 finished neighbours: the diagonal, where both characters are consumed; the cell above, where only s[i - 1] is; and the cell to the left, where only t[j - 1] is. Recognize it when the input is 2 sequences whose order matters. The question asks for 1 value about the pair. Usually it is a count or a length; cost and yes/no questions take the same shape.


<br>

### Same template, different cell contents

| Problem | dp[i][j] holds | Last chars equal | Otherwise | Answer |
| --- | --- | --- | --- | --- |
| LCS | length of the LCS | diag + 1 | max(up, left) | `dp[n][m]` |
| Longest common substring | length of the shared run ending at both | diag + 1 | 0 | largest cell |
| Edit distance | fewest edits | diag | 1 + min(up, left, diag) | `dp[n][m]` |
| Distinct subsequences | ways t[:j] occurs inside s[:i] | diag + up | up | `dp[n][m]` |
| Wildcard match | whether p[:j] matches s[:i] | diag, also for ? | star: left or up; else False | `dp[n][m]` |

The base row and column, where a prefix is empty, are where these problems differ most and where most wrong answers start. LCS and substring start at 0. Edit distance starts at i and j. Distinct subsequences set dp[i][0] = 1, because the empty target occurs exactly once in any string. Wildcard matching sets dp[0][0] = True and keeps dp[0][j] True only while p[:j] is all stars. Test every solution with an empty s and an empty t before anything else.


<br>

### Matching file names against a glob

A loader that takes a pattern such as events_\*.gz must decide which names in a directory listing it picks up. A ? matches exactly 1 character and a \* matches any run, including an empty one. With dp[i][j] meaning that p[:j] matches s[:i], a star cell takes dp[i][j - 1], the star matching nothing, or dp[i - 1][j], the star absorbing s[i - 1] while staying available for more. The animation checks f1.gz against f\*.gz.

https://github.com/user-attachments/assets/9b1991f5-a89b-412d-be69-d4bf813a1e6e

*Column 2 is the star; True runs down it as the star absorbs characters.*

Follow column 2, the star. Row f sets it True through the left case, and every later row inherits True from above while the star absorbs 1 first and z last, with . and g between. The final True arrives along a diagonal: . matches at row 3, g at row 4 and z at row 5, each reading the cell up and to the left.

> **TIP**
>
> A recursive matcher with no table branches at every star, and its running time multiplies with each added star on patterns like `*a*a*a*b` against a long run of a's. The table fills each of its (n + 1) x (m + 1) cells once, so a 200-character name against a 20-character pattern costs about 4,200 cells.


<br>

### Counting funnel paths with distinct subsequences

Product analytics asks the counting version: in how many ways does the ordered funnel view, cart, buy occur inside a user's event stream, gaps allowed? Each occurrence is a choice of positions. When s[i - 1] equals t[j - 1], the cell adds dp[i - 1][j - 1], which counts occurrences that use this event, to dp[i - 1][j], which counts occurrences that skip it. On a mismatch only the skip remains, and a rolling list over the funnel dimension is enough.

```sql
def funnel_count(events, funnel):
    m = len(funnel)
    dp = [1] + [0] * m
    for e in events:
        for j in range(m, 0, -1):
            if e == funnel[j - 1]:
                dp[j] += dp[j - 1]
    return dp[m]


events = ["view", "cart", "view", "cart", "buy"]
print(funnel_count(events, ["view", "cart", "buy"]))
```

The inner loop walks the funnel from its last step back to its first, for the same reason the 0/1 knapsack loop runs high to low: within an occurrence, a single event fills at most 1 funnel step, so `dp[j - 1]` must still hold its value from before this event. Loop forward instead and a lone view event, checked against the funnel view, view, reports 1 occurrence instead of 0.

> Spot the prefix-pair shape
>
> - The input holds 2 sequences, one of which may be a pattern.
> - Order matters, with gaps allowed (subsequence) or forbidden (substring).
> - The question wants a number or a yes/no for the pair.
> - Time is O(n x m); memory drops to O(m) with a rolling row.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Write what dp[i][j] means, in prefix lengths, before the recurrence<br><br>• Fill the base row and column first, then test an empty string<br><br>• Track the best cell in substring problems, where the corner can be 0 | • Read s[i] in a cell covering s[:i]; its last character is s[i - 1]<br><br>• Skip the all-stars base row in wildcard matching<br><br>• Loop forward over a rolling row when each element is single-use |


<br>

---

## Interval DP

Some problems work on contiguous ranges of a single sequence. The state is dp[i][j], the answer for elements i through j inclusive, and the transition picks how the range divides: where the final merge happens, which balloon bursts last, or whether the outer pair belongs to a palindrome. The tell is a cost that depends on a whole range, so no element's choice can be settled without knowing what happens around it.


<br>

### Merging adjacent files at minimum cost

Compaction gives the data engineering form. Take 4 sorted files with sizes 5, 4, 4, 5 GB. They must become 1 file, and only neighbours may merge so key order is preserved. Merging 2 runs reads and writes both, so it costs their combined size. However the range i..j is merged, its last step joins a left part i..k with a right part k + 1..j, and that step costs sum(i..j) whichever k is chosen. So dp[i][j] = min over k of dp[i][k] + dp[k + 1][j] + sum(i..j), with dp[i][i] = 0.

| ✓ Greedy: cheapest adjacent pair first | ✗ Interval DP |
| --- | --- |
| • Merge 4 + 4 = 8, leaving 5, 8, 5<br><br>• Merge 5 + 8 = 13, leaving 13, 5<br><br>• Merge 13 + 5 = 18<br><br>• Total cost 39 | • Merge 5 + 4 = 9<br><br>• Merge 4 + 5 = 9<br><br>• Merge 9 + 9 = 18<br><br>• Total cost 36 |


<br>

### Why length comes first

The recurrence reads dp[i][k] and dp[k + 1][j], and both are ranges strictly shorter than i..j. Filling cells in order of range length guarantees each read is finished. Row-major order breaks this: dp[0][3] reads dp[1][3] before row 1 is filled, finds the 0 it was initialised with, and returns a cost lower than any real plan, with no error raised.

```sql
for i in range(n):
    for j in range(i + 1, n):
        best = min(dp[i][k] + dp[k + 1][j] for k in range(i, j))
        dp[i][j] = best + prefix[j + 1] - prefix[i]
```

The animation fills the same 4 files by length, and each printed line is a finished range: all 3 ranges of length 2 come out before any range of length 3.

https://github.com/user-attachments/assets/be916dd4-ab2c-4bc0-8e14-bf45db4c00b6

*Ranges finish shortest first, so every read is ready.*

The final cell picks k = 1: 9 for files 0..1 plus 9 for files 2..3, then 18 for the last merge, 36 in all, the plan in the right column of the comparison above.

> **TIP**
>
> A second valid order runs `i` from `n - 1` down to 0 and `j` upward from `i + 1`. Then `dp[i][k]` sits earlier in the current row and `dp[k + 1][j]` in a row already finished. Interviewers accept either order once you name the reads it protects.


<br>

### Palindromes: the same shape on a string

The longest palindromic subsequence fits the same frame, with the outer pair as the decision. If s[i] equals s[j], both ends wrap the best palindrome inside: dp[i + 1][j - 1] + 2. Otherwise an end is dropped: max(dp[i + 1][j], dp[i][j - 1]). A single character is a palindrome of length 1.

```sql
def longest_palindrome_subseq(s):
    n = len(s)
    dp = [[0] * n for _ in range(n)]
    for i in range(n):
        dp[i][i] = 1
    for length in range(2, n + 1):
        for i in range(n - length + 1):
            j = i + length - 1
            if s[i] == s[j]:
                dp[i][j] = dp[i + 1][j - 1] + 2
            else:
                dp[i][j] = max(dp[i + 1][j], dp[i][j - 1])
    return dp[0][n - 1]


print(longest_palindrome_subseq("bbbab"))
```

The 2 problems differ in work per cell. The palindrome transition reads a fixed number of neighbours, so its table costs O(n^2) time. The merge transition scans every split point, so it costs O(n^3). For a partition of 500 small files, both fill the same triangle, but the merge does about 166 times the palindrome's work. Say which of O(n^2) and O(n^3) applies before you write the loops.

- **~125K** — cells in the upper triangle
- **~20.8M** — split points the merge scans

> Interval DP checklist
>
> - The state is a contiguous range i..j of a single sequence.
> - The transition picks a split point k or the outer pair.
> - Cells fill by range length, or by i descending with j ascending.
> - The answer is `dp[0][n - 1]`, the whole range.
> - Cost is about n^2 / 2 cells times the work per cell.

Other questions in this family

- Burst balloons: dp[i][j] picks the balloon in the range that bursts last.
- Matrix chain multiplication: dp[i][j] picks the last product computed.
- Cutting a stick at marked points: dp[i][j] picks the first cut between marks i and j.
- Optimal binary search tree: dp[i][j] picks the root for keys i through j.


<br>

---

## Putting It All Together

An online marketplace loads nightly catalog files from its sellers. Each night the job lists the landing directory against seller-supplied glob patterns, compares each feed's header to the previous night's to catch renamed or dropped columns, fuzzy-matches new seller names against the existing seller table, compacts the many small output files into fewer large ones before morning readers arrive, and spends whatever remains of a fixed maintenance window on the highest-value backfills.

- Picking up the night's files is wildcard matching. Each file name gets a prefix-pair table against each seller's pattern, and the tables stay cheap because names and patterns are short.
- Header drift uses LCS over column names to list dropped and added columns, then a character-level LCS ratio to pair an abbreviated new name with the column it replaced.
- Seller-name matching normalizes edit distance by length and prunes pairs whose lengths differ by more than the allowed distance before building any table.
- Compaction of adjacent sorted files is interval DP over file ranges filled in order of length. On inputs like 5, 4, 4, 5 it beats the cheapest-pair greedy.
- The leftover window is 0/1 knapsack over backfill jobs, counted in hours with a right-to-left loop, since each backfill runs once.
- Each of these tables is built the way the grid table was: say what a cell means, fill the cells it reads first, then decide whether a rolling row is enough.


<br>

---

## Key Takeaways

- Every 2D DP answer starts with a sentence defining the cell. Write the recurrence from that sentence; the base cases and fill order come out of it too.
- Grid tables fill row-major because each cell reads above and left, and a rolling row cuts memory to O(C) at the cost of the route.
- The capacity loop direction decides the knapsack: high to low for single-use items, low to high when items repeat.
- Knapsack time scales with the capacity's numeric value, so the unit you count in is a design decision.
- LCS and edit distance share the prefix-pair table; with inserts and deletes only, distance is len(a) + len(b) - 2 x LCS.
- String DP problems differ mostly in what a cell holds and how the empty-prefix row starts.
- Interval tables read only shorter ranges, so cells fill by length, and row-major order returns wrong answers without errors.
