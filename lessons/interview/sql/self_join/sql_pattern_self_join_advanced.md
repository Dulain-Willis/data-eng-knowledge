# Self-Join: Advanced

You are 40 minutes into a SQL round at an HR software company. The interviewer pastes a schema, `employees(employee_id, name, manager_id)`, around 50,000 rows.
"Give me everyone in Fay's org, at any depth. Then tell me who Dee reported to last June."
Most people type 2 self-joins, return Fay's reports and their reports, and stop. Nobody said how deep the tree goes, and nobody said that table only holds today's reporting lines. Two joins answer a 3-level org correctly and a 9-level org wrongly without an error, and no current-state table knows anything about last June.
The rest of the hour comes out of those 2 gaps: depth, history, a precomputed ancestor table, the same join on a table 1,000 times bigger, and a capacity question that looks unrelated and is the same join underneath.


<br>

### What you will be able to do

Explain what a chain of N self-joins can reach, and replace it with a recursive walk that terminates on cyclic data

Recover reporting lines and skip-levels as of any past date from an effective-dated table without fan-out

Design, size and maintain a closure table, and say when its upkeep outweighs its reads

Predict a self-join's output size from key skew, and say which problems an index contains and which it cannot

Compute peak concurrency with a self-join, defend the boundary rule, and switch to a sweep when the data is large


<br>

---

## Hierarchical Self-Joins and Depth

The question rarely says hierarchy. It arrives as "show each employee with their manager and skip-level", "roll headcount up to every VP", or "permissions granted on a folder apply to everything inside it, so can this user open this file?" Each one joins a parent-child table to itself, once per level of the tree. Before any SQL, say how many levels the question needs, because that number chooses between a fixed chain of joins, a recursive query and a precomputed table.


<br>

### One join per level

Each self-join climbs a single edge of the tree. The condition m1.employee_id = e.manager_id turns an employee row into a row that also carries the manager, and another alias joined on m2.employee_id = m1.manager_id climbs again. Both joins have to be `LEFT JOIN`. With inner joins, Ana, who has no manager, disappears at the first join, and Ben and Fay, who have no skip-level, disappear at the second.

https://github.com/user-attachments/assets/e3f3fb58-f3c1-4c93-9533-797fda1dd402

4 rows in, 4 out. Ana keeps her row with a NULL manager, and every other row now carries exactly 1 level more than it had. A chain repeats that move with a fresh alias per level, so a query with N aliases above `e` sees N levels and no more. Here is the 2-level version over all 6 people:

```sql
SELECT
  e.name AS employee,
  m1.name AS manager,
  m2.name AS skip_level
FROM employees AS e
LEFT JOIN employees AS m1
  ON m1.employee_id = e.manager_id
LEFT JOIN employees AS m2
  ON m2.employee_id = m1.manager_id
```

Follow Eli's row. His real chain of command runs Dee, Cal, Fay, Ana, 4 levels up, and the query shows 2 of them. Nothing fails, and the filter `WHERE 'Fay' IN (m1.name, m2.name)`, a natural way to ask for Fay's org, leaves Eli out though he sits 3 levels under her. A chain of N joins answers questions about the nearest N levels and gives confident wrong answers about anything deeper.


<br>

### When a fixed chain is the right answer

The chain is a sound design when the question fixes the depth: manager and skip-level for an approval rule, or a wide table with 1 column per level, L1 through L8, for a BI tool that cannot recurse. It plans as an ordinary multi-way join, runs on every engine, and reads well in review. What makes it safe is an enforced maximum depth, and the answer that scores names the enforcement: "This holds because the org is capped at 8 levels, and the load fails if any employee sits deeper than level 8."


<br>

### Up the tree or down

Direction changes the cost more than the syntax. Walking up from 1 employee touches 1 row per level, so Eli's chain costs 4 lookups whatever the size of the company. Walking down from a VP touches every descendant, and each level costs as much as that level is wide. The join condition is the only difference: `e.manager_id = o.employee_id` steps down and `e.employee_id = o.manager_id` steps up. Name the direction before writing the condition, because a reversed condition returns a plausible result for a different question.


<br>

### Removing the limit with a recursive CTE

When depth is unbounded, the same self-join becomes the recursive step of a `WITH RECURSIVE` query. The anchor selects the starting rows. The recursive step joins the base table to the rows the previous pass produced, and the engine repeats it until a pass returns nothing. Each pass moves 1 level, so the depth reached is set by the data rather than by the number of joins in the query text.

```sql
WITH RECURSIVE org AS (
  SELECT
    employee_id,
    name,
    0 AS depth,
    ARRAY[employee_id] AS path
  FROM employees
  WHERE employee_id = 6

  UNION ALL

  SELECT
    e.employee_id,
    e.name,
    o.depth + 1,
    o.path || e.employee_id
  FROM employees AS e
  JOIN org AS o
    ON e.manager_id = o.employee_id
  WHERE NOT e.employee_id = ANY (o.path)
    AND o.depth < 20
)

SELECT
  employee_id,
  name,
  depth
FROM org
ORDER BY depth, name
```

> **TIP**
>
> Narrate the passes while you write: "The anchor seeds Fay. Each pass joins employees to the previous pass on manager_id, so pass 1 finds Cal, pass 2 finds Dee, pass 3 finds Eli, and pass 4 finds nobody, which ends the loop." That narration shows you know the evaluation model, which the syntax alone cannot show.


<br>

### Termination is part of the answer

Real hierarchies contain cycles. A reorg loaded in 2 batches can leave Cal reporting to Dee while Dee still reports to Cal, and without a guard the recursive step walks that loop forever. What happens next depends on the engine, and saying it shows you have been paged for it: SQL Server stops at its `MAXRECURSION` setting and raises an error, MySQL stops at `cte_max_recursion_depth`, and PostgreSQL has no default cap, so the query runs until memory or a statement timeout ends it.

- **100** — SQL Server's default MAXRECURSION
- **1,000** — MySQL's default cte_max_recursion_depth

The path array is the cycle guard: each row carries the ids visited on its branch, and the recursive step refuses any node already on the path. PostgreSQL 14 added a `CYCLE` clause that keeps the same bookkeeping for you. The depth bound is the second guard and caps the work if the cycle check has a bug or the data has a shape nobody expected. Write both, and state the engine default you are staying under, so that when the limit fires you can say why it sits where it does.


<br>

---

## Reporting Lines as of a Past Date

`employees.manager_id` describes today, and a reorg overwrites it in place, so the table forgets who reported to whom last quarter. Any question with a date in it needs reporting lines that carry their own validity: "headcount by manager at quarter end", "who should have approved this expense in March", "attrition by team, month by month". The usual shape is effective-dated, 1 row per employee per stint under a manager, with `valid_from` inclusive, `valid_to` exclusive, and open stints ending on the sentinel `9999-12-31`.

The org from the first section has 3 changes on record. Fay moved from Ben to Ana on 2023-03-01, Cal moved from Ben to Fay on 2023-07-01, and Eli joined under Dee on 2023-09-01. Today's tree is what those stints say now. The opening question asks what they said on 2023-06-30.


<br>

### Date every alias

The as-of predicate belongs on every copy of the table. Alias `r1` selects each employee's stint valid on the date. Alias `r2` has to select the manager's own stint valid on the same date, or the manager's entire history joins in. Because `r2` sits on the outer side of a `LEFT JOIN`, its date conditions go in the `ON` clause.

https://github.com/user-attachments/assets/4e69849c-9a85-442b-aaa5-9a61c2652247

On these 4 stints, 3 rows come back. Cal's second stint fails the `r1` filter because it starts the next day. Dee's skip-level is 2, Ben, because on 2023-06-30 Cal still reported to Ben; the same query for today returns Fay. Ben keeps his row with a NULL skip-level, since Ana has no manager stint for `r2` to find. Over the full history of 7 stints the query also returns Fay under Ana, and leaves out Eli, whose first stint starts in September.


<br>

### The fan-out nobody sees

Delete the 2 `r2` date conditions and run it again. Dee's row now matches both of Cal's stints, the result grows from 3 rows to 4, and Dee sits under 2 skip-levels at once. Any headcount built on this counts Dee twice for June, the totals stop agreeing with Finance, and the query never errors. Interviewers plant exactly this: they hand over a query with the employee-side filter already written and ask why the numbers are "slightly high".

> How as-of self-joins break
>
> - `BETWEEN valid_from AND valid_to` is inclusive at both ends, so on 2023-07-01 Cal has 2 managers. Write `valid_from <= d AND valid_to > d`.
> - Putting the `r2` date conditions in `WHERE` turns the `LEFT JOIN` into an inner join, and Ben and Fay, whose manager has no manager, drop out.
> - A NULL `valid_to` on open stints makes `valid_to > d` unknown, and every current line vanishes. Use the sentinel or `COALESCE(valid_to, DATE '9999-12-31')`.
> - Overlapping stints in the source fan out exactly like a missing date filter: 2 open rows for one employee double every count they touch.

The rule holds at any depth. In a recursive walk over stints, the as-of conditions sit inside the recursive step as well as the anchor, so every pass picks the stint valid on the date, and a manager's old subtree never joins in through a stint that had already ended.


<br>

### When the date comes from another row

The harder variant has no single date: "for every expense, who was the submitter's manager on the day it was submitted?" The as-of date is now a column of the fact row, so the join to `reporting_lines` becomes a range join and the half-open rule applies row by row.

```sql
SELECT
  x.expense_id,
  x.employee_id,
  r.manager_id AS approver_at_submission
FROM expenses AS x
LEFT JOIN reporting_lines AS r
  ON r.employee_id = x.employee_id
    AND x.submitted_on >= r.valid_from
    AND x.submitted_on < r.valid_to
```

That proviso is the follow-up, and the answer is a data test. Stints assembled from HR exports can overlap or leave gaps, and an overlap fans out exactly like a missing date filter. The test is a self-join on the history: 2 stints for the same employee where each starts before the other ends. Any row it returns is a duplicate waiting in every as-of report, so it runs on every load.

```sql
SELECT
  a.employee_id,
  a.valid_from,
  a.valid_to,
  b.valid_from AS other_from,
  b.valid_to AS other_to
FROM reporting_lines AS a
JOIN reporting_lines AS b
  ON b.employee_id = a.employee_id
    AND a.stint_id < b.stint_id
    AND a.valid_from < b.valid_to
    AND b.valid_from < a.valid_to
```


<br>

### Which as-of?

One question separates people who have reconciled these numbers from people who have only queried them: "as of June 30 as we know it today, or as the June 30 report showed?" HR systems accept backdated changes, so a stint recorded in August can carry a `valid_from` in June. The first reading uses the valid-time columns above. The second also needs a `recorded_at` column and a `recorded_at <= d` filter on every alias, which makes the table bitemporal. Finance tying out to a published report wants the second; an analyst rebuilding history wants the first.


<br>

---

## Closure Tables for Ancestors

A recursive walk pays for the hierarchy on every read. When a dashboard asks "who is in this VP's org?" thousands of times a day and the org changes a few times a week, that work belongs at write time. A closure table stores a row for every ancestor and descendant pair together with the distance between them, so any subtree or chain-of-command question becomes a single join with no recursion.


<br>

### The shape of the table

`org_closure(ancestor_id, descendant_id, depth)` holds a row wherever the ancestor sits anywhere above the descendant, plus a depth-0 row pairing every employee with themselves. The 6-person org from the first section needs 17 rows. Eli alone contributes 5, a row for each person from himself up to Ana:

| ancestor_id | descendant_id | depth |
| --- | --- | --- |
| 5 (Eli) | 5 (Eli) | 0 |
| 4 (Dee) | 5 (Eli) | 1 |
| 3 (Cal) | 5 (Eli) | 2 |
| 6 (Fay) | 5 (Eli) | 3 |
| 1 (Ana) | 5 (Eli) | 4 |

```sql
SELECT e.employee_id, e.name, c.depth
FROM org_closure c
JOIN employees e ON e.employee_id = c.descendant_id
WHERE c.ancestor_id = 6;

SELECT c.ancestor_id, c.depth
FROM org_closure c
WHERE c.descendant_id = 5
ORDER BY c.depth;
```

The depth-0 rows look redundant and do real work. They make "Fay and everyone under her" the same query as "everyone under her" with `depth > 0` added, and they let the maintenance statements below run without special cases for the moved node itself. Leaving them out is the usual bug in a hand-built closure table, and it shows up as a manager missing from their own headcount.


<br>

### Storage grows with depth

A node at depth d contributes d + 1 rows, so the table holds the node count times the average depth plus 1. Wide, shallow trees are cheap: a company of 50,000 employees whose people sit 6 levels down on average stays well under a million rows. Long chains are expensive, because a hierarchy shaped as a single line of n nodes stores n(n + 1)/2 rows. That is why closure tables suit org charts and product categories and suit reply threads badly, where a single argument can nest thousands of replies deep.

- **350,000** — closure rows for the 50,000-person org
- **50M** — closure rows for a 10,000-reply chain


<br>

### Upkeep on hire and on reorg

A new hire, employee 7 under Dee, copies Dee's ancestor rows 1 level deeper and adds a depth-0 row: `INSERT INTO org_closure SELECT ancestor_id, 7, depth + 1 FROM org_closure WHERE descendant_id = 4`, followed by `(7, 7, 0)`. Moving a subtree is the case to rehearse, because it is a self-join on the closure table. Suppose the next reorg moves Cal, with Dee and Eli, under Ben.

```sql
DELETE FROM org_closure
WHERE descendant_id IN (SELECT descendant_id FROM org_closure
                        WHERE ancestor_id = 3)
  AND ancestor_id NOT IN (SELECT descendant_id FROM org_closure
                          WHERE ancestor_id = 3);

INSERT INTO org_closure (ancestor_id, descendant_id, depth)
SELECT up.ancestor_id, down.descendant_id,
       up.depth + down.depth + 1
FROM org_closure up
CROSS JOIN org_closure down
WHERE up.descendant_id = 2
  AND down.ancestor_id = 3;
```

The delete removes every path that enters the subtree from outside it: Fay and Ana to each of Cal, Dee and Eli. The insert crosses Ben's ancestors (Ben at 0, Ana at 1) with Cal's subtree (Cal at 0, Dee at 1, Eli at 2), adding 1 for the new edge, so Eli lands 4 below Ana. Rows written equal the subtree size times the new parent's depth plus 1: a 3,000-person department moved under a manager 3 levels down writes 12,000 rows and deletes a similar number. Both statements run in 1 transaction, or readers see an org that is half moved.

| ✓ Recursive walk on each read | ✗ Closure table |
| --- | --- |
| • No extra table; always reflects the latest change<br><br>• Each read pays 1 join per level of depth<br><br>• Read latency grows as the org deepens<br><br>• Fits hierarchies that change constantly or are read rarely | • Storage grows with node count times depth<br><br>• Each read is 1 indexed join, whatever the depth<br><br>• Every reorg rewrites paths as a batch<br><br>• Fits hierarchies read far more often than they change |

Incremental upkeep is optional more often than people expect. Rebuilding the whole table from a recursive walk of the stints and swapping it in atomically is a few hundred thousand inserts for this org, finishes in seconds, and has no half-moved state to get wrong. Incremental maintenance is worth its complexity only when readers cannot wait for the next rebuild, or when the hierarchy is large enough that a full rebuild competes with the reads it serves.

> **TIP**
>
> A closure table answers today's questions. For "Fay's org as of last June", build it per snapshot date from the effective-dated stints and put `snapshot_date` in the key. Quarter-end snapshots for 5 years are 20 copies, around 7 million rows for this org.


<br>

---

## Large Self-Joins and Indexing

A self-join's output size is set by its key, and both sides carry the same skew. For an equality self-join, a key with c rows produces c times c pairs, so the result is the sum of the squared key counts. A modest table can therefore have an enormous self-join if a single key is hot, and the question usually reaches the room as "this job ran fine for a year and now never finishes."


<br>

### The placeholder manager

Take "list every pair of employees who share a manager". The query is a self-join on `manager_id` with `a.employee_id < b.employee_id` to keep each pair once, and it is correct. On a real HR table, 40,000 contractors sit under a placeholder `manager_id` of 0 because the source system demands a value there. That key alone produces more pairs than every real team combined. A NULL would have been harmless, since `NULL = NULL` is unknown and NULL keys pair with nothing; the sentinel is what does the damage.

- **800M** — sibling pairs under manager_id 0

Diagnose before fixing. Counting rows per key and squaring the count predicts the self-join's size before it runs, and it is the first thing to offer when the interviewer says the job hangs:

```sql
SELECT
  manager_id,
  COUNT(*) AS n,
  COUNT(*) * (
    COUNT(*) - 1
  ) / 2 AS distinct_pairs
FROM employees
WHERE manager_id IS NOT NULL
GROUP BY manager_id
ORDER BY distinct_pairs DESC
LIMIT 10
```


<br>

### What an index contains, and what it cannot

An index bounds the work of finding partners. With a B-tree on `employees(manager_id)`, each pass of a recursive walk, or each level of a fixed chain, becomes a lookup that touches only matching rows. Without it, the engine typically hash-joins the current pass against a full scan of the table, so a 2-million-row table walked 8 levels deep is read 8 times to return a subtree of a few thousand rows. A closure table's reads stay point lookups only while both of its id columns are indexed.

An index cannot shrink the output. When the answer itself is a quadratic number of pairs, an index makes them faster to produce and nothing more. The fix is to change what is computed: count pairs per manager as `n * (n - 1) / 2` from a `GROUP BY`, exclude or route the sentinel key separately, or ask who actually consumes the pairs. Adding an index to the placeholder query and stopping there answers a different question from the one asked.

> **TIP**
>
> Name the operator you expect in the plan: "Without the index this is a Hash Join scanning employees on every pass; with it, a Nested Loop driving an Index Scan on manager_id." Reading EXPLAIN aloud for a self-join is the follow-up that tells someone who has tuned one from someone who has read about it.


<br>

### Range self-joins need an equality key

Inequality self-joins are where tables of ordinary size fail. A join whose only conditions are time comparisons, such as "pair each payment with any payment in the next 10 minutes", gives the engine no equality key, so it cannot hash-join and falls back to a nested loop: 1 million rows means up to 1 trillion comparisons. Most real questions carry an equality the query must state anyway. "Pair each login with the same user's logins in the next 10 minutes" needs `b.user_id = a.user_id` to be correct, and that condition also lets the engine group candidates by user first. A composite index on `(user_id, login_ts)` then turns each probe into a short range scan bounded at both ends.

```sql
CREATE INDEX idx_logins_user_ts ON logins (user_id, login_ts);

SELECT a.login_id,
       b.login_id AS next_login_id
FROM logins a
JOIN logins b
  ON b.user_id  = a.user_id
 AND b.login_ts >  a.login_ts
 AND b.login_ts <= a.login_ts + INTERVAL '10' MINUTE;
```


<br>

### Warehouses have no B-tree

Columnar warehouses and Spark generally offer no B-tree to probe on their standard tables, so the follow-up arrives as "this is on Snowflake, now what?" What those engines offer instead is clustering and sort order, which let the engine skip files or micro-partitions when the key is selective, and bucketing, which manufactures an equality key for a range join. Assign each login a 10-minute bucket, join on `user_id` and on a bucket equal to or 1 after the left row's, then apply the exact 10-minute range as a filter. The range check now runs only inside matching buckets.

Distribution adds a cost of its own. A hot key lands on a single task, so the placeholder manager becomes 1 task running for an hour while the other 199 finish in seconds. The diagnosis is the same per-key count, and so is the fix, because no join hint or extra parallelism helps when the output of that task is itself too large.

| ✓ An index contains the work | ✗ Change the query instead |
| --- | --- |
| • Equality self-join on a selective key<br><br>• Recursive walk down or up a hierarchy<br><br>• Range self-join with an equality key and a bounded window<br><br>• Subtree and chain lookups in a closure table | • A single hot key whose pairs are the output<br><br>• Range join with no equality key and no window bound<br><br>• Peak concurrency over millions of intervals<br><br>• Any question that counts can answer without pairs |


<br>

---

## Peak Concurrency With a Self-Join

The question never says interval. It says "how many licences do we need?", "what was the most simultaneous calls our support line handled yesterday?", or "enforce a limit of 4 concurrent streams per account". Underneath, each hands over rows with a start and an end and asks for the instant covered by the most of them.


<br>

### Count open intervals at each start

The self-join depends on a single fact, and saying it first is part of the answer: the number of open intervals rises only at a start, so the maximum is always reached at some interval's start. Checking every start is therefore enough. For each session `a`, count the sessions `b` already open at `a.start_ts`, meaning started at or before it and not yet ended. The count includes `a` itself.

https://github.com/user-attachments/assets/bf3055fa-b643-473e-8ace-0d4d6d779df3

The peak is 2, reached at 09:20 and again at 09:30. The comparison that decides it is s1 against s3's start: s1 ends at 09:30, s3 starts at 09:30, and `b.end_ts > a.start_ts` says s1 has already left. Write `>=` instead and s1 still counts at 09:30, the peak becomes 3, and the licence order grows by half. Neither comparison is wrong in general. Half-open intervals, where a session ending at 09:30 frees its seat for one starting at 09:30, match how most seat-counting systems reuse a seat, and stating the rule before writing the comparison is what the interviewer is listening for.


<br>

### Where the self-join is the wrong tool

Every start probes every earlier interval, and `b.start_ts <= a.start_ts` has no lower bound, so an index on `start_ts` still scans everything that began before each start. That is about n squared over 2 comparisons: harmless for 5,000 sessions, hopeless for 2 million calls in a day, which is 2 trillion comparisons. The sweep line does it with a single sort. Each interval becomes 2 events, +1 at its start and -1 at its end, and a running sum in time order is the concurrency at every instant.

```sql
WITH events AS (
  SELECT
    start_ts AS ts,
    1 AS delta
  FROM sessions

  UNION ALL

  SELECT
    end_ts AS ts,
    - 1 AS delta
  FROM sessions
),
running AS (
  SELECT
    ts,
    SUM(delta) OVER (
      ORDER BY ts, delta
      ROWS UNBOUNDED PRECEDING
    ) AS open_sessions
  FROM events
)

SELECT
  MAX(open_sessions) AS peak_sessions
FROM running
```

In the sweep, tie order makes the same decision that the < versus <= comparison made in the self-join. The 2 events at 09:30 produce different running sums depending on which comes first:

| tie order | event at 09:30 | running sum |
| --- | --- | --- |
| ends first | s1 ends (-1) | 1 |
| ends first | s3 starts (+1) | 2 |
| starts first | s3 starts (+1) | 3 |
| starts first | s1 ends (-1) | 2 |

Sorting starts first touches 3 for a single event and reproduces the closed-interval answer by accident, and an engine left to order ties itself can return 2 on one run and 3 on the next. The explicit `ROWS UNBOUNDED PRECEDING` frame keeps the sum row by row instead of grouping tied rows the way the default `RANGE` frame does.


<br>

### The follow-up: how long was the peak?

Once the peak is known, the next question is often its duration, and the sweep answers it with 1 more window function. `LEAD(ts) OVER (ORDER BY ts, delta)` gives each event the timestamp of the next one, so every row describes a segment with a constant count. Summing segment lengths where the count equals the peak gives the time spent there: 09:20 to 09:30 and 09:30 to 09:50, 30 minutes in total.

The self-join still wins in 3 cases. The question wants the sessions themselves, as in "which calls were on hold together at the peak?", which a running sum cannot name. The data is small enough that clarity beats speed. Or a known maximum duration bounds the range: if no call lasts over 4 hours, adding `b.start_ts >= a.start_ts - INTERVAL '4' HOUR` gives the index a window, and each probe reads only 4 hours of calls. Per-tenant peaks add `b.tenant_id = a.tenant_id` to the join, or `PARTITION BY tenant_id` to the sweep.

| ✓ Do | ✗ Don't |
| --- | --- |
| • State the depth a question needs before choosing a chain, a recursive CTE or a closure table<br><br>• Put a half-open as-of predicate on every alias, inside ON for the outer side<br><br>• Ship every recursive CTE with a cycle guard and a depth bound you chose<br><br>• Count rows per key and square them before self-joining a large table<br><br>• Say whether intervals are half-open before writing the comparison | • Don't trust a fixed join chain on a hierarchy with no enforced maximum depth<br><br>• Don't use BETWEEN on valid_from and valid_to; change dates match 2 stints<br><br>• Don't expect an index to shrink a self-join whose output is quadratic<br><br>• Don't run a pairwise self-join for peak concurrency over millions of intervals |


<br>

---

## Putting It All Together

A 50,000-person company's people-analytics team owns a dashboard that refreshes hourly: headcount for every VP's org, the approval chain behind each flagged expense, and peak concurrent seats on the HR system to size next year's licence renewal. Last quarter's headcount disagreed with Finance's published figures by a few hundred people, and the overnight job that lists teammates for a 'shared skip-level' panel stopped finishing.

- VP headcount reads a closure table rebuilt for each quarter-end snapshot, so the hourly refresh is a single indexed join instead of a recursive walk per tile.
- The snapshot comes from effective-dated stints with half-open predicates on every alias; an undated skip-level alias was double-counting reorganised teams, and matching Finance also needed the recorded-at filter.
- The recursive build carries a path guard and a depth bound, because the HR import has already produced a reporting loop once.
- The teammate panel stalled on the placeholder manager_id, and counting pairs per manager with n(n-1)/2 replaced materialising them.
- Seat sizing runs a sweep with ends sorted before starts, because login sessions number in the millions per quarter and the licence server frees a seat the moment a session ends.


<br>

---

## Key Takeaways

- A chain of N self-joins sees N levels and is silently wrong below them; unbounded depth needs a recursive walk with cycle and depth guards.
- As-of reporting lines need a half-open date predicate on every alias, inside ON for the outer side, or a manager's history fans out the result.
- A closure table turns any subtree or chain-of-command query into a single join, paid for in rows per depth and subtree-sized writes on each reorg.
- A self-join's size is the sum of squared key counts; an index speeds up finding partners and never shrinks an output that is itself quadratic.
- Peak concurrency is always reached at a start: a self-join counts open intervals per start, and a sweep with ends sorted first does it in a single sort.
