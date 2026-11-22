# CTEs (Common Table Expressions): Intermediate

You are 40 minutes into a SQL round at a payments company. The interviewer pastes a query into the shared editor: 4 CTEs, a refunds join in the middle, an assertion at the end.
'This runs every night. Last night the check fired. SMB shows minus 120 dollars of net revenue for February 2024, and SMB had a single refund that month. Where is it wrong?'
She doesn't say which step to suspect or whether the query was ever right. The usual opening is to reread the final SELECT for 5 minutes, because that is where the bad number surfaced. The cause sits 2 steps upstream.
Behind the bug she has follow-ups queued: what each CTE costs, whether the engine runs it once, and whether 2 reads of it could ever disagree.


<br>

### What you will be able to do

Find the CTE that produced a wrong final number by checking its grain, then reconciling it against the source

Decide when a temp table beats a CTE or a subquery, and name what each option costs

Say whether a given engine inlines or materializes a CTE, and read the answer off a query plan

Explain why 2 references to one CTE can return different rows, and make them agree

Refactor a nested query into a CTE chain and prove the result did not change


<br>

---

## Debugging a Multi-CTE Query

A bug-hunt question hands you a chain and a symptom, never a line number. Reading SQL is assumed. What gets scored is method: whether you probe the chain one CTE at a time with a hypothesis behind each probe, or reread it top to bottom waiting for the mistake to stand out. Here is the chain, with each step's intended grain written as a comment. Adding those comments is the first move worth making if the original lacks them.

```sql
WITH seg_txns AS (
  -- one row per transaction
  SELECT
    t.txn_id,
    t.customer_id,
    c.segment,
    DATE_TRUNC('month', t.txn_date) AS month_start,
    t.amount
  FROM transactions AS t
  JOIN customers AS c
    ON c.customer_id = t.customer_id
),
txn_refunds AS (
  -- intended: one row per transaction
  SELECT
    s.segment,
    s.month_start,
    s.txn_id,
    s.amount,
    r.refund_id,
    r.refund_amount
  FROM seg_txns AS s
  LEFT JOIN refunds AS r
    ON r.customer_id = s.customer_id
),
net_revenue AS (
  -- one row per segment and month
  SELECT
    segment AS customer_segment,
    month_start,
    SUM(amount) - SUM(COALESCE(refund_amount, 0)) AS net_revenue
  FROM txn_refunds
  GROUP BY segment, month_start
),
quality_violations AS (
  -- returns zero rows on clean data
  SELECT
    *
  FROM net_revenue
  WHERE net_revenue < 0
)

SELECT
  *
FROM quality_violations
```


<br>

### Start from the alarm

The last CTE is an assertion: on clean data it returns nothing. Played over the net_revenue rows, it keeps one.

https://github.com/user-attachments/assets/7fbe08bd-d224-468f-be44-8e2d2dee8f08

The flagged row is SMB, 2024-02-01, -120. From here the trace follows that single key upstream and ignores every other segment and month, which keeps each probe small enough to read at a glance.


<br>

### Probe each step for grain and totals

At each CTE, replace the final SELECT with a probe of that step, filtered to the bad key. The trace uses 2 measurements. A grain check compares `COUNT(*)` with `COUNT(DISTINCT ...)` for every key the step holds, including keys that arrived through a join. A reconciliation compares the step's sums with the same sums taken straight from the source tables.

```sql
-- In place of the final SELECT: probe txn_refunds for the bad key
SELECT
  COUNT(*) AS row_count,
  COUNT(DISTINCT txn_id) AS distinct_txns,
  COUNT(refund_id) AS refund_rows,
  COUNT(DISTINCT refund_id) AS distinct_refunds,
  SUM(amount) AS gross,
  SUM(refund_amount) AS refunds
FROM txn_refunds
WHERE segment = 'SMB'
  AND month_start = DATE '2024-02-01'
```

| Step | Rows | Distinct txns | Refund rows (distinct) | Gross / refunds |
| --- | --- | --- | --- | --- |
| transactions, refunds (source) | 3 | 3 | 1 (1) | 300 / 140 |
| seg_txns | 3 | 3 | n/a | 300 / n/a |
| txn_refunds | 3 | 3 | 3 (1) | 300 / 420 |
| net_revenue | 1 | n/a | n/a | net -120 |

The transaction-grain check on txn_refunds passes: 3 rows, 3 distinct transactions. A candidate who only verifies the grain written in the comment calls the step clean and moves on. The refund key tells another story: 1 distinct refund occupies 3 rows, and the refund total is exactly 3 times the 140 in the source. A total that lands on a whole multiple of the true figure is the fingerprint of a fan-out, and the multiplier is the number of rows each refund matched.


<br>

### Watching the fan-out happen

The join key is `customer_id`, so the refund attaches to every order customer 7 placed, including the 2 it never touched. The query below isolates that join, one output row per matched pair.

https://github.com/user-attachments/assets/75baa819-1ff5-4ddd-8796-eda3c6a654cf

Customer 7's 3 orders still total 300, but the single 140 refund is copied onto each of the 3 rows, so any SUM over the refund column reads 420. Customer 8 has no refund, so the LEFT JOIN keeps its one row with a NULL refund, and its numbers come out correct by accident. That's why this bug survives review: any spot check run on customers without refunds passes.


<br>

### The fix that holds

Switching the join to `txn_id` repairs this data and leaves a second trap: a transaction with 2 partial refunds would match twice and double its own amount. The fix that handles both cases brings refunds to the join's grain first, in a CTE of their own.

```sql
refunds_per_txn AS (          -- one row per refunded transaction
  SELECT txn_id,
         SUM(refund_amount) AS refund_amount
  FROM refunds
  GROUP BY txn_id
),
txn_refunds AS (              -- one row per transaction, by construction
  SELECT s.segment, s.month_start, s.txn_id, s.amount,
         r.refund_amount
  FROM seg_txns s
  LEFT JOIN refunds_per_txn r ON r.txn_id = s.txn_id
),
```

With the 140 taken off 300, SMB February now nets 160 and the gate returns no rows. Expect the follow-up 'how do you stop this happening again?' The strongest answer is a reconciliation assertion: the refund total entering net_revenue must equal `SUM(refund_amount)` from refunds for the same months. Say explicitly that a grain assertion on `txn_id` alone would have passed this bug, because that sentence shows you understood why it slipped through.

> Searching a long chain
>
> - On a chain of 6 or more CTEs, probe the middle step first; whether its totals reconcile tells you which half holds the bug.
> - Filter every probe to the one bad key, so each result is a handful of rows.
> - Check grain on every key a step carries, including keys that arrived by join.
> - Reconcile sums against the source tables, since row counts can pass while totals drift.

> **TIP**
>
> Narrate each probe before running it: 'I'll count rows and distinct refund ids in txn_refunds for SMB February, because if refunds fanned out, those 2 numbers split.' The interviewer scores the hypothesis as much as the finding.


<br>

---

## CTE vs Subquery vs Temp Table

This one arrives as a challenge to code you have already written: 'Why a CTE there? Wouldn't a subquery be faster?' or 'Would you stage that in a temp table?' An answer about style loses the point. The strong answer prices each option on 4 axes: how long the intermediate result lives, how many times it can be read, whether the optimizer can see through it, and whether the planner has trustworthy statistics for it.

|  | Subquery | CTE | Temp table |
| --- | --- | --- | --- |
| Lives for | One clause | One statement | The session |
| Read more than once | No, copy it | Yes, by name | Yes, across statements |
| Optimizer sees through it | Yes | When inlined | No, it is a table |
| Statistics | Derived from sources | Derived from sources | Its own, once analyzed |
| Can be indexed | No | No | Yes |
| Inspectable after a run | No | No | Yes, query it directly |
| Write cost | None | None, or a spool if materialized | A full write of the result |


<br>

### Subquery and CTE usually share a plan

Postgres 12 and later generally compile a CTE read once to the same plan as the equivalent derived table in FROM. So do SQL Server and BigQuery, and Snowflake as well. So 'wouldn't a subquery be faster' has a factual answer, which is no for a single reference, and the proof is running EXPLAIN on both forms side by side. The CTE's advantages are all about the reader: a name that states its grain, steps that read in the order data flows, and a second reference that costs no copied logic.

Subqueries keep 2 jobs. A correlated `EXISTS` in WHERE, such as keeping transactions that have at least one refund, states a per-row test that a CTE would have to restate as a join plus a DISTINCT. A one-value scalar subquery, like a threshold read from a config table, is clearer inline than lifted into a named step nobody else reads.

Said in full, an answer to 'why not a subquery?' runs about 3 sentences: 'For one reference the plans are identical on this engine, and EXPLAIN on both forms shows it. I used the CTE because its name states its grain and the steps read in the order the data flows. If several statements needed this intermediate, or the planner misjudged its size, I'd stage it in a temp table instead.'


<br>

### When a temp table is worth the write

A temp table pays for writing its whole result and gets 3 things back. It survives across statements, so a stored procedure that builds a staging set and reads it from 4 later statements computes it once. It can carry an index, so a 2-million-row intermediate joined repeatedly on `customer_id` can be probed instead of hashed each time. And it gets statistics of its own, which fixes the failure that pushes most production queries out of a long CTE chain: row estimates compounding through 6 joins and filters until the planner is wrong by orders of magnitude and picks a nested loop over millions of rows.

```sql
CREATE TEMP TABLE txn_refunds_stage AS
SELECT t.txn_id, t.customer_id,
       DATE_TRUNC('month', t.txn_date) AS month_start,
       t.amount,
       COALESCE(r.refunded, 0) AS refunded
FROM transactions t
LEFT JOIN (SELECT txn_id, SUM(refund_amount) AS refunded
           FROM refunds
           GROUP BY txn_id) r
  ON r.txn_id = t.txn_id;

CREATE INDEX ON txn_refunds_stage (customer_id);
ANALYZE txn_refunds_stage;
```

> **TIP**
>
> Postgres autovacuum never processes temporary tables, so a temp table there has no column statistics until your session runs ANALYZE on it. The planner still estimates its size from the page count. Selectivity estimates for filters and joins on it fall back to defaults, and that's where the bad join choices come from.

There is a debugging argument as well. If a chain in a nightly job fails intermittently, land its 2 or 3 riskiest steps in temp tables. The probes from the previous section can then run after the failure against the exact rows the job saw, not against a rerun on data that has since changed.

The follow-up 'what does the temp table cost you?' separates people who have run this from people who have read about it. Name the write itself, the pressure on tempdb or the temp tablespace when many sessions do it at once, and cleanup. On a pooled connection the session can outlive the job that created the table, so drop it explicitly or, on Postgres, create it with `ON COMMIT DROP` inside a transaction.

> The choice in one breath
>
> - Read once, inside one statement: a CTE. Same plan as the subquery, plus a name.
> - A per-row existence test: a correlated subquery with EXISTS.
> - Read by several statements, or worth an index: a temp table.
> - Planner misestimates deep in a chain: a temp table plus ANALYZE at the step where estimates go wrong.


<br>

---

## Inlining vs Materializing a CTE

Inlining substitutes a CTE's body into the outer query as though it were a derived table, and the optimizer plans the statement as one piece: outer filters move inside, joins reorder across the boundary, unread columns are never fetched. Materializing runs the body once into a work table and points every reference at that. The question arrives as 'what happens when this CTE is referenced 3 times?' or 'does the filter on segment reach the transactions scan?' The answer opens with 'it depends on the engine' and moves straight to what it depends on.

| Engine | Read once | Read 2 or more times | Override |
| --- | --- | --- | --- |
| Postgres 11 and earlier | Materialized | Materialized | None |
| Postgres 12 and later | Inlined | Materialized | `AS MATERIALIZED`, `AS NOT MATERIALIZED` |
| SQL Server | Inlined | Inlined, body runs per reference | Stage in a temp table |
| BigQuery | Inlined | Inlined, body runs per reference | Temp table in a script |
| Snowflake | Optimizer decides | Often computed once and shared | No direct hint |

*Whatever its reference count, Postgres 12 and later also materialize a recursive CTE or one that modifies data. A CTE that calls a volatile function such as random() is materialized too.*

The Postgres 12 change is why so much CTE advice online is backwards. Before it, every Postgres CTE was an optimization fence, and rewriting CTEs as subqueries was a real performance fix. A candidate who repeats that advice for a modern engine signals that their knowledge stopped in 2019, the year Postgres 12 shipped.


<br>

### Reading the choice off a plan

Take the aggregation from the running example at production scale: monthly_gross, a segment-by-month sum over 4.8 million transactions joined to customers, read once, with the outer query filtering to `customer_segment = 'SMB'`. Materialized, as Postgres 11 always did it, the plan aggregates every segment and month before the filter discards most of the result.

```sql
CTE Scan on monthly_gross  (rows=24)
  Filter: (customer_segment = 'SMB'::text)
  CTE monthly_gross
    ->  HashAggregate  (rows=96)
          Group Key: c.segment, date_trunc('month', t.txn_date)
          ->  Hash Join  (rows=4800000)
                Hash Cond: (t.customer_id = c.customer_id)
                ->  Seq Scan on transactions t  (rows=4800000)
                ->  Hash  (rows=1200)
                      ->  Seq Scan on customers c  (rows=1200)
```

Inlined on Postgres 12, the same query plans like this:

```sql
HashAggregate  (rows=24)
  Group Key: c.segment, date_trunc('month', t.txn_date)
  ->  Hash Join  (rows=1200000)
        Hash Cond: (t.customer_id = c.customer_id)
        ->  Seq Scan on transactions t  (rows=4800000)
        ->  Hash  (rows=300)
              ->  Seq Scan on customers c  (rows=300)
                    Filter: (segment = 'SMB'::text)
```

The tell is the node names. A materialized CTE appears as a CTE subplan read through a CTE Scan, with the outer filter sitting on the scan above the aggregation. An inlined CTE leaves no trace of its name; here the segment filter sits on the customers scan itself, so only SMB rows ever reach the join or the aggregate above it. That move is legal because segment is a grouping column: a filter on the summed revenue couldn't go below the GROUP BY under either strategy. Snowflake's query profile shows the shared form as a WithClause operator feeding WithReference operators.

Postgres 12's default has a sharp edge worth naming unprompted. Add a second reference to a CTE and it flips from inlined to materialized, so a query whose outer filter used to reach the base scan stops pushing it down after an edit that read the CTE one more time. Nothing in the SQL warns you; the plan is the only place it shows.


<br>

### What each strategy costs

| ✓ Inlined | ✗ Materialized |
| --- | --- |
| • Outer filters on grouping columns push into the body and shrink the scan<br><br>• Joins reorder across the CTE boundary<br><br>• Read N times, the body runs N times<br><br>• Nondeterministic expressions are evaluated once per reference | • The body runs once, however many references read it<br><br>• Outer filters apply only after the whole body has run<br><br>• The work table has no index, so joins to it hash or loop<br><br>• Every reference reads the identical stored rows |

The arithmetic worth saying out loud: a CTE body that takes 30 seconds and is read 3 times costs roughly 90 seconds on SQL Server or BigQuery, and roughly 30 seconds plus 3 cheap work-table scans on Postgres 12. Reverse the shape, one read behind a selective filter, and the old Postgres fence aggregates all 4.8 million transactions to hand back the 24 SMB rows the outer query wanted.

> **TIP**
>
> When asked which strategy your engine uses, answer with the check: 'I'd run EXPLAIN and look for a CTE Scan. If it's there, the body ran once and my outer filter never reached it.' Overriding the engine with a hint is its own decision with its own failure modes, and an interviewer who wants that conversation will open it.


<br>

---

## When Two Reads of a CTE Differ

The mental model most people carry treats a CTE like a variable: computed once, read wherever it's named. Materialization makes that true. Inlining makes each reference its own evaluation of the body, and 2 evaluations of the same SQL return different rows whenever the body's output is not fully determined by its input. The question arrives sideways: 'cohort sizes change between runs on unchanged data', or 'a customer's first order shows a refund bigger than the order'.


<br>

### Ties in a ranking

Customer 7 placed orders 101 and 102 on the same day, 2024-02-03. This query picks each customer's first order and reads the result twice: directly for the order amount, and inside first_txn_refunds to find refunds on that order.

```sql
WITH first_txn AS (
  -- one row per customer
  SELECT
    customer_id,
    txn_id,
    amount
  FROM (
    SELECT
      customer_id,
      txn_id,
      amount,
      ROW_NUMBER() OVER (
        PARTITION BY customer_id
        ORDER BY txn_date
      ) AS rn
    FROM transactions
  ) AS ranked
  WHERE rn = 1
),
first_txn_refunds AS (
  -- second read of first_txn
  SELECT
    f.customer_id,
    r.refund_amount
  FROM first_txn AS f
  JOIN refunds AS r
    ON r.txn_id = f.txn_id
)

SELECT
  f.customer_id,
  f.amount AS first_order_amount,
  fr.refund_amount AS first_order_refund
FROM first_txn AS f -- first read of first_txn
LEFT JOIN first_txn_refunds AS fr
  ON fr.customer_id = f.customer_id
```

`ORDER BY txn_date` leaves 101 and 102 tied, and ROW_NUMBER must still hand exactly one of them a 1. The SQL standard leaves that choice to the engine, which in practice means physical arrival order. Whichever parallel worker finishes first can decide it, and so can the hash bucket a row lands in or a sort that is not stable. Inlined, each read of first_txn makes the choice again, independently.

Read 1: first_txn in the final SELECT

Read 2: first_txn inside first_txn_refunds

| customer_id | first_order_amount | first_order_refund |
| --- | --- | --- |
| 7 | 100 | 140 |

The output claims customer 7's first order was 100 and was refunded 140, a row no consistent reading of the data could produce. On Postgres 12 the 2 reads always agree within a run, because a CTE read twice is materialized, though which order counts as first can still change from one run to the next. The same SQL on SQL Server or BigQuery evaluates the window twice and can disagree with itself under parallelism. On a 10-row test sample it agrees every time, which is how it reaches production.

The fix is a unique tiebreaker: `ORDER BY txn_date, txn_id`. With it, the ranking is a function of the data, and every evaluation on every engine picks order 101.


<br>

### Randomness and clocks

The second source is any expression whose value isn't a function of the row. Sampling with BigQuery's `RAND()` or Postgres's `random()` is the common case. Ids from `GENERATE_UUID()` or `NEWID()` behave the same way, as do wall-clock reads such as Postgres's `clock_timestamp()`. Each evaluation draws a fresh value. SQL Server's `RAND()` is the exception: it's constant for the whole query, so `RAND() < 0.1` there keeps every row or none, and per-row randomness comes from `NEWID()`. An experiment-assignment CTE that buckets users with `RAND()` and is read once for exposures and once for conversions assigns each user independently on each read, so the conversion rate it reports is noise. BigQuery's documentation states the rule directly: a non-recursive CTE referenced in several places is executed once for each reference.

```sql
-- BigQuery: a hash of the user id replaces RAND()
WITH assignment AS (
  SELECT user_id,
         CASE WHEN MOD(ABS(FARM_FINGERPRINT(CAST(user_id AS STRING))), 100) < 50
              THEN 'control' ELSE 'treatment' END AS arm
  FROM users
)
```


<br>

### Concurrent and same-statement writes

The third source is the table changing underneath the statement. Postgres reads every reference in one statement from a single snapshot, so a concurrent commit cannot split them, and Snowflake and BigQuery behave the same way. SQL Server's default READ COMMITTED takes and releases shared locks as each scan proceeds unless the READ_COMMITTED_SNAPSHOT database option is on. Without it, 2 scans of transactions inside one inlined statement can straddle another session's commit and count different rows. A NOLOCK hint widens the gap to uncommitted rows.

One Postgres case runs the other way. In `WITH moved AS (INSERT INTO refunds_archive SELECT ... RETURNING *) SELECT COUNT(*) FROM refunds_archive`, the outer read does not see the rows the CTE inserted, because every part of the statement shares a snapshot taken before any of it ran. Count from `moved` instead; RETURNING is the only view of those rows inside that statement.

> Making 2 reads agree
>
> - Add a unique tiebreaker to every ROW_NUMBER and every ORDER BY with LIMIT.
> - Replace RAND() sampling and bucketing with a hash of a stable key.
> - Compute volatile values once: stage them in a temp table and read that.
> - On SQL Server, read under snapshot isolation when one statement scans a table twice.

> **TIP**
>
> When the interviewer asks 'does this CTE run once or twice?', add the second sentence nobody volunteers: 'and if twice, would both runs return the same rows?' Every bug in this section hides behind that second question.


<br>

---

## Refactoring Subqueries into CTEs

The prompt is usually a paste: 'This is from the finance reporting job. Nobody wants to touch it. Clean it up.' Below it sit 3 levels of derived tables and 2 correlated subqueries in a SELECT list. The grade has 2 halves: a chain a reviewer can follow, and evidence that the result did not move. Deliver only the first and the next question is 'how do you know it's the same?', where 'I compared a few rows' ends the conversation.

```sql
SELECT
  seg.segment,
  seg.month_start,
  seg.gross - seg.refunded AS net_revenue,
  seg.refunds_issued
FROM (
  SELECT
    x.segment,
    x.month_start,
    SUM(x.amount) AS gross,
    SUM(x.refunded) AS refunded,
    SUM(x.n_refunds) AS refunds_issued
  FROM (
    SELECT
      c.segment,
      DATE_TRUNC('month', t.txn_date) AS month_start,
      t.amount,
      (
        SELECT
          COALESCE(SUM(r.refund_amount), 0)
        FROM refunds AS r
        WHERE r.txn_id = t.txn_id
      ) AS refunded,
      (
        SELECT
          COUNT(*)
        FROM refunds AS r
        WHERE r.txn_id = t.txn_id
      ) AS n_refunds
    FROM transactions AS t
    JOIN customers AS c
      ON c.customer_id = t.customer_id
  ) AS x
  GROUP BY x.segment, x.month_start
) AS seg
WHERE seg.gross > 0
```


<br>

### Work from the innermost query out

- Find the innermost derived table; it becomes the first CTE, named for one row of its output.
- Lift each enclosing level into the next CTE, keeping its column names and aliases unchanged.
- Turn each correlated subquery in SELECT into a grouped CTE joined with LEFT JOIN at the same grain.
- Keep the outermost SELECT as the final query, its WHERE and ORDER BY untouched.
- Prove the 2 versions match before renaming or optimizing anything.

```sql
WITH refunds_per_txn AS (
  -- one row per refunded transaction
  SELECT
    txn_id,
    SUM(refund_amount) AS refunded,
    COUNT(*) AS n_refunds
  FROM refunds
  GROUP BY txn_id
),
seg_txns AS (
  -- one row per transaction
  SELECT
    c.segment,
    DATE_TRUNC('month', t.txn_date) AS month_start,
    t.amount,
    COALESCE(r.refunded, 0) AS refunded,
    COALESCE(r.n_refunds, 0) AS n_refunds
  FROM transactions AS t
  JOIN customers AS c
    ON c.customer_id = t.customer_id
  LEFT JOIN refunds_per_txn AS r
    ON r.txn_id = t.txn_id
),
seg_month AS (
  -- one row per segment and month
  SELECT
    segment,
    month_start,
    SUM(amount) AS gross,
    SUM(refunded) AS refunded,
    SUM(n_refunds) AS refunds_issued
  FROM seg_txns
  GROUP BY segment, month_start
)

SELECT
  segment,
  month_start,
  gross - refunded AS net_revenue,
  refunds_issued
FROM seg_month
WHERE gross > 0
```


<br>

### The COALESCE calls are the refactor

A correlated `COUNT(*)` returns 0 for a transaction with no refunds, because an aggregate without GROUP BY always produces one row. The LEFT JOIN to refunds_per_txn returns NULL for the same transaction. Drop the COALESCE and most months still match, because SUM skips NULLs. Then comes a segment-month with no refunds at all: `SUM(refunded)` and `SUM(n_refunds)` are both NULL. The row survives the `gross > 0` filter, but net_revenue reads NULL instead of its gross and refunds_issued reads NULL instead of 0, so the check below reports it on both sides as a changed row. That is the most common way a refactor sold as readability-only changes a result.

The other half is grain. The correlated subqueries couldn't fan out, since each returned one value per transaction. The LEFT JOIN is only as safe because refunds_per_txn groups by `txn_id` first; joining raw refunds instead reproduces the duplication from the first section's chain.

Nested originals carry 2 habits that are safe to drop on the way through. An ORDER BY inside a derived table without LIMIT carries no guarantee in any engine, so removing it changes nothing a caller can rely on. A `SELECT *` in an intermediate step is worth replacing with named columns, because the equivalence check below compares by position and a reordered column list fails it for no real reason.


<br>

### Prove it did not change

```sql
WITH old_result AS (
  /* the original nested query, pasted unchanged */
),
new_result AS (
  /* the CTE version, its WITH steps folded into this one */
)
SELECT 'only_in_old' AS side, d.*
FROM (SELECT * FROM old_result
      EXCEPT ALL
      SELECT * FROM new_result) d
UNION ALL
SELECT 'only_in_new' AS side, d.*
FROM (SELECT * FROM new_result
      EXCEPT ALL
      SELECT * FROM old_result) d;
```

Zero rows back means the 2 results are the same multiset. The ALL matters: plain EXCEPT deduplicates, so a refactor that doubled every row would pass it. EXCEPT also treats 2 NULLs as matching, which is the comparison you want here and the one `=` in a join gets wrong. BigQuery and SQL Server lack EXCEPT ALL; there, group each side by every column with `COUNT(*)` and compare those. Run it over a full month of real data, because empty groups and duplicate keys break refactors and are rare by nature. If amounts are stored as FLOAT, a reordered sum can differ in its last digits; compare on ROUND, or store money as DECIMAL.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Comment each CTE with its grain: one row per what<br><br>• Probe a broken chain one CTE at a time, filtered to the single bad key<br><br>• Aggregate the many side of a join to the join's grain before joining it<br><br>• Break ties in ROW_NUMBER and in ORDER BY plus LIMIT with a unique key like txn_id<br><br>• Prove a refactor with a symmetric EXCEPT ALL over a full month of real data | • Don't trust a grain check that skips the keys a join brought in<br><br>• Don't assume a CTE named twice runs once; read the plan on your engine<br><br>• Don't sample or bucket with RAND() inside a CTE that is read twice<br><br>• Don't drop the COALESCE when a correlated COUNT becomes a LEFT JOIN |


<br>

---

## Putting It All Together

A subscription software company closes its books from a nightly Postgres 15 job: a 9-CTE chain that turns invoices, credit notes and account segments into net recurring revenue per segment, ending in an assertion CTE that fails the run when any segment goes negative. The night before the board pack is due, the assertion fires for the mid-market segment, and the on-call engineer has to find the cause, fix it, and show finance the corrected report can be trusted.

- Following the flagged mid-market month upstream, a probe of each CTE shows credit notes joined on account_id instead of invoice_id: invoice grain passes, but each credit note appears once per invoice on the account.
- EXPLAIN shows the invoice aggregate, read in 3 places, as one CTE Scan, so Postgres already runs it once; the segment filter never reaches it, and staging it in a temp table with ANALYZE gives the later joins real row counts.
- A first_invoice CTE ranked by invoice_date alone had picked different same-day invoices on different nights; invoice_id as a tiebreaker makes the cohort stable.
- The legacy nested query feeding the chain becomes CTEs with COALESCE kept on its correlated counts, and a symmetric EXCEPT ALL over February returns zero rows before the fix ships.


<br>

---

## Key Takeaways

- Trace a wrong total by following its key upstream: check grain on every key a CTE carries and reconcile its sums to the source.
- A CTE read once plans like a subquery; a temp table costs a write but can be indexed and analyzed, and later statements can reuse it.
- Postgres 12+ inlines a CTE read once and materializes one read twice; SQL Server and BigQuery rerun the body for each reference.
- Inlined reads can disagree: ties without a unique tiebreaker, RAND(), wall clocks and lock-based reads each give a read its own rows.
- A faithful refactor keeps a correlated COUNT's zero with COALESCE and proves itself with a symmetric EXCEPT ALL on real data.
