# Deduplication: Beginner

The interviewer shares her screen: an `orders` table, 5 columns, a few thousand rows.
'This feed double-writes sometimes. Give me one row per customer per order date.'
She has not named the columns that decide whether 2 rows match, and she has not said which copy to keep when 3 rows agree on customer and date but carry different amounts. `SELECT DISTINCT *` is the move most people make in the first 10 seconds, and it returns every row untouched, because the rows differ in `order_id` and `created_at`. The next move is a `GROUP BY` that returns the right number of rows and none of the columns she asked for.
What she is scoring is whether you define the duplicate before you remove it: name the key, measure the repeats, then keep one whole row for each key with a rule for which copy it is.


<br>

### What you will be able to do

State the key that makes 2 rows the same, and the grain of the result, before writing a line of SQL

Choose between DISTINCT and GROUP BY for exact copies and say out loud why they return the same rows

Count the repeating keys and the extra rows they carry, and use those numbers to verify the removal

Keep one whole row per key with ROW_NUMBER over the key, filtered to 1 in an outer query

Explain why DISTINCT leaves by-key copies and near-matches in place, and build a key that removes them


<br>

---

## What Counts as a Duplicate

The question rarely contains the word key. It arrives as 'this feed double-writes sometimes, clean it up', as 'the daily order count runs 3% above what finance reports', or as 'every join off this table fans out'. All 3 describe the same table, and none says which columns make 2 rows the same. A row in `orders` has 5 columns, and 2 rows can agree on all 5, on 2 of them, or on 2 of them only after a string is trimmed, so the word duplicate means nothing until a column list goes with it.

| order_id | customer_id | order_date | amount | created_at |
| --- | --- | --- | --- | --- |
| 1001 | 1 | 2024-01-01 | 100 | 2024-01-01 09:00:00 |
| 1002 | 1 | 2024-01-01 | 140 | 2024-01-01 10:00:00 |
| 1003 | 1 | 2024-01-01 | 110 | 2024-01-01 11:00:00 |
| 1004 | 1 | 2024-01-02 | 60 | 2024-01-02 08:15:00 |
| 1005 | 2 | 2024-01-01 | 75 | 2024-01-01 12:45:00 |

Match on every column and no 2 of these rows are the same: 5 distinct rows, nothing to remove. If `customer_id` and `order_date` decide the match, rows 1001 to 1003 are copies of one key, which leaves 3 rows. On `customer_id` alone, customer 1's 4 rows fold into 1, which leaves 2. The same table gives a different answer under each definition, and the interviewer has handed you none of them. The first thing you produce is the definition, because every query after it is scored against that choice.


<br>

### Exact duplicates and duplicates by key

An exact duplicate agrees with another row in every column. It comes from a file loaded twice, a `UNION ALL` that should have been `UNION`, or a lookup table someone appended to instead of replacing. Nothing in the row tells the copies apart, so any copy can survive, and one keyword removes the rest. The question is answered in a line and the interviewer learns nothing from it.

A duplicate by key agrees in the columns that identify the entity and differs somewhere else. Rows 1001 to 1003 share a customer and a date, but `order_id` differs on each one, as do `amount` and `created_at`, because the feed wrote the order 3 times and stamped each write. Retries, change-data-capture replays after a failover, and corrections written as fresh rows all produce this shape. Removing these means deciding on a key and then on which copy survives, and almost every interview version of the question is this case, because it tests judgement rather than vocabulary.


<br>

### The grain is the definition

The sentence worth saying out loud is the grain: what one row of the finished table stands for. 'I'll treat `customer_id` plus `order_date` as the key, so the result holds a single row for each customer on each date' takes 2 seconds for the interviewer to confirm or correct, and either response hands you the column list. If she answers that `order_id` is the business key, this table has no duplicates at all and the 3% overcount comes from a join downstream. That is a different problem, and you caught it before writing a line. Candidates who skip the sentence commit to a definition inside their SQL and discover it was the wrong one when the row count comes back.

> 2 questions before any SQL
>
> - Which columns make 2 rows the same? The answer is the dedup key, and it picks the tool: a keyword for exact copies, a window function for copies by key.
> - When 2 rows are the same, which copy survives? The answer is a sort order, and it becomes the ORDER BY of the query that keeps one row.
> - Ask both before touching the keyboard; the second has no answer until the first does.


<br>

### Where the copies come from

- A client that retries on a timeout sends the same event twice, and the second copy arrives with a later receipt time
- A change-data-capture stream replays committed rows after a database failover
- A nightly file loaded twice because the first load's success message was lost
- A join on a column that was never unique, fanning each left row into several
- UNION ALL written where UNION was intended, keeping copies from both branches
- A correction written as a new row instead of an update, so old and new versions coexist



| ✓ Opens with the keyword | ✗ Opens with the definition |
| --- | --- |
| • Types SELECT DISTINCT \* before asking a single question and gets every row back<br><br>• Switches to GROUP BY and loses the columns the interviewer asked to keep<br><br>• Spends the next 5 minutes recovering from a definition nobody agreed on<br><br>• Hears 'why did the count not change?' before saying anything scorable | • Names the key and the grain in one sentence and waits for a nod<br><br>• Asks which copy survives when 3 rows share a key<br><br>• Counts what repeats before removing anything<br><br>• Writes the keep-one query once, with the right columns and no rewrite |

> **TIP**
>
> Say the grain as a sentence with the word per in it, such as 'one row per ticket' or 'one row per device per hour'. If you cannot say it, you have not defined the duplicate, and the interviewer knows it before you do.


<br>

---

## DISTINCT vs GROUP BY

Start with the case where the copies agree in every column. A customer file was assembled from 2 regional exports that overlapped, so `imported_customers` holds 6 rows for 3 customers. The ask is one copy of each row, and the whole answer is one keyword. Watch what the keyword actually compares, because the rows it keeps are the ones that trip people in the next question.

https://github.com/user-attachments/assets/7d380099-fc5c-4f87-81bb-723e9132c872

Of the 6 rows that go in, 4 come out. Customer 101's 2 rows agree on `customer_id` and `email` and carry the same `segment`, so they fold into 1, and so do customer 102's. Customer 103 keeps both rows, because one says retail and the other wholesale, and `DISTINCT` compares the entire selected row: a difference in any 1 of the 3 columns keeps a row alive. Drop `segment` from the select list and the same query returns 3 rows. The columns you list are the definition from the previous section, written into the query.

`DISTINCT` runs after the select list is computed, so it compares the expressions you wrote rather than the stored columns. Postgres compares case-sensitively by default, as do Snowflake and BigQuery, so there `SELECT DISTINCT email` keeps Ana@shopmail.com and ana@shopmail.com as 2 values; the MySQL and SQL Server defaults compare case-insensitively and fold them. `SELECT DISTINCT LOWER(email)` folds them on every engine, which is why the normalised expression is the one to write. The same rule makes `SELECT DISTINCT *` compare every stored column, including the ones that were never part of the key, which is the mistake the last section of this lesson takes apart.


<br>

### GROUP BY folds the same rows

```sql
SELECT
  customer_id,
  email,
  segment,
  COUNT(*) AS copies
FROM imported_customers
GROUP BY customer_id, email, segment
```

| customer_id | email | segment | copies |
| --- | --- | --- | --- |
| 101 | ana@shopmail.com | retail | 2 |
| 102 | ben@shopmail.com | wholesale | 2 |
| 103 | cara@shopmail.com | retail | 1 |
| 103 | cara@shopmail.com | wholesale | 1 |

The 4 rows are the ones `DISTINCT` returned, because both constructs do the same work: every column in the list becomes part of a group key, and rows with equal keys fold into 1. Most optimizers produce the same hash aggregate plan for either form, so no performance argument separates them on exact copies. What `GROUP BY` adds is the aggregate column: `copies` shows that 101 and 102 arrived twice and 103 once per segment, which is the first evidence of how the overlap happened. If the import had also stamped a `loaded_at` on each row, `GROUP BY` could carry `MIN(loaded_at)` beside each survivor, a column outside the key that `DISTINCT` has no way to express.

One constraint follows from that. Under `DISTINCT`, an `ORDER BY` column has to appear in the select list, because the engine holds no single value of an unselected column for a folded row. `GROUP BY` lifts the limit for aggregates, so `ORDER BY MIN(loaded_at)` is legal after a group and has no equivalent under `DISTINCT`. When the interviewer asks for the earliest copy's load time beside each surviving row, only the second form can produce it.


<br>

### 3 forms that return the same rows

- SELECT DISTINCT customer_id, email, segment: reads as deduplication, which is what you are doing
- SELECT customer_id, email, segment ... GROUP BY customer_id, email, segment: the same rows, reads as aggregation
- SELECT ... UNION SELECT ...: UNION without ALL removes copies across both branches and within each one

Pick the form that names the intent and say why: 'I'm using `DISTINCT` because it reads as deduplication; `GROUP BY` would read as aggregation, and I reach for it when I want a count beside each surviving row.' That sentence tells the interviewer you know the forms are equivalent and chose on purpose. Writing `GROUP BY` with no aggregate and no comment reads as not knowing `DISTINCT` exists, and writing `UNION` against a single source reads as an accident.


<br>

### NULL collapses with NULL

Both forms treat 2 NULLs in the same column as equal for grouping, even though `NULL = NULL` evaluates to UNKNOWN in a `WHERE` or a join. 2 rows with a NULL `email` and the same `customer_id` and `segment` fold into 1 under `DISTINCT` and under `GROUP BY`. That is the behaviour you want for a cleanup, and it deserves one sentence out loud, because the same 2 rows would refuse to match in a self-join written to find them. The interviewer hears that you know where NULL behaves one way and where it behaves the other.

| ✓ DISTINCT is the right reach when | ✗ GROUP BY is the better fit when |
| --- | --- |
| • The copies agree in every selected column<br><br>• Any copy can survive, so no ordering is needed<br><br>• The cleanup is a one-off on a file or an ad-hoc query<br><br>• You want the query to read as what it does | • You want a count of copies beside each surviving row<br><br>• A column outside the key needs an aggregate, such as the earliest load time<br><br>• The result feeds a HAVING filter on the count<br><br>• Deduplication is one step of a larger aggregation anyway |

> **TIP**
>
> The phrasing that marks this case: 'the file was loaded twice', 'we ran the backfill twice', or a sample where 2 rows are identical on screen. Any visible difference between the sample rows moves you to the key-based pattern, and the keyword will hand back the count it was given.


<br>

---

## Finding Duplicates Before Removal

The interviewer's second question, whichever query you wrote first, is 'how do you know it worked?'. A candidate who removed rows without counting them has no answer, and the habit that separates the 2 answers is measuring the duplicates before touching them. 3 numbers describe the problem: how many rows the table holds, how many distinct keys it holds, and the difference, which is the number of rows any correct dedup must remove.


<br>

### 3 numbers before anything is removed

```sql
WITH per_key AS (
  SELECT
    customer_id,
    order_date,
    COUNT(*) AS copies
  FROM orders
  GROUP BY customer_id, order_date
)

SELECT
  COUNT(*) AS distinct_keys,
  SUM(copies) AS total_rows,
  SUM(copies) - COUNT(*) AS extra_rows,
  SUM(
    CASE
      WHEN copies > 1 THEN 1
      ELSE 0
    END
  ) AS repeating_keys
FROM per_key
```

| distinct_keys | total_rows | extra_rows | repeating_keys |
| --- | --- | --- | --- |
| 3 | 5 | 2 | 1 |

The inner query folds `orders` to one row per key with its copy count; the outer one counts those rows and sums the copies, so `total_rows` is 5 and `distinct_keys` is 3 without a second scan of the table. `extra_rows` is 2: the dedup must delete 2 rows and return exactly 3, and if it returns 5 or 4 or 2 you know before the interviewer does. `repeating_keys` is 1, which says the problem is concentrated, a single key with 3 copies, rather than spread across the table. Postgres accepts `COUNT(DISTINCT (customer_id, order_date))` as a one-line shortcut for the key count; most other engines reject the tuple, so the CTE form is the one to write when the dialect is unstated.

Interviewers read these counts as production experience, because the failure they have seen is a dedup that silently dropped 10% of a table nobody measured, with the loss surfacing weeks later as a revenue gap. The 3 numbers take one query and give you the sentence 'this will remove 2 rows out of 5' before anyone asks for it.


<br>

### Which keys repeat

https://github.com/user-attachments/assets/0900e57f-c008-4eed-ac07-a78e81bd8f39

`GROUP BY` folds the 5 rows into 3 groups and counts each; `HAVING` then drops every group with a count of 1, leaving the key (1, 2024-01-01) with its count of 3. The filter has to be `HAVING` because `WHERE` runs before the fold and cannot see a count that does not exist yet; `WHERE COUNT(*) > 1` is a syntax error on every engine and a common one under time pressure. Say the order as you write it: 'I group first, then filter on the count with `HAVING`, because `WHERE` cannot reference an aggregate.'


<br>

### Look at the copies themselves

```sql
SELECT
  o.order_id,
  o.customer_id,
  o.order_date,
  o.amount,
  o.created_at
FROM orders AS o
JOIN (
  SELECT
    customer_id,
    order_date
  FROM orders
  GROUP BY customer_id, order_date
  HAVING COUNT(*) > 1
) AS d
  ON d.customer_id = o.customer_id
    AND d.order_date = o.order_date
ORDER BY o.customer_id, o.order_date, o.created_at
```

The repeating-keys list says which keys, and this join shows the rows behind them, in the order they were written. For (1, 2024-01-01) that is 1001 at 09:00 with amount 100, 1002 at 10:00 with 140 and 1003 at 11:00 with 110. The amounts differ, so these are 3 writes of one order carrying different values, and whichever copy survives moves a revenue figure by up to 40. That observation is the point of looking: a double load produces identical copies and any survivor is fine, while differing copies mean the survivor rule is a business decision you now have to ask for. Candidates who skip this step choose the rule by accident.

A window form shows the same rows without the join: `COUNT(*) OVER (PARTITION BY customer_id, order_date) AS copies` beside every column of `orders`, filtered to `copies > 1` in an outer query. It reads shorter and introduces the partition clause the next section builds on; either form is accepted, and naming both marks you as someone who has done this more than once.

- **40%** — of this table is extra copies

> The verification you say out loud
>
> - Count rows and distinct keys before removal; the difference is the number of rows to remove
> - List the repeating keys with `HAVING COUNT(*) > 1` and look at a few of their rows
> - Run the removal and count its output; it must equal the distinct key count, 3 here
> - Group the output by key and confirm `HAVING COUNT(*) > 1` returns no rows
> - A removal rate above a few percent is an upstream bug worth naming, beyond a cleanup

> **TIP**
>
> A dedup that removes 2% of rows looks like retries; one that removes half the table looks like a load that ran twice. Say which you think it is before you remove anything, because the interviewer wants the diagnosis as much as the query.


<br>

---

## Keeping One Row Per Key

With the key agreed and the copies counted, the next mistake is a query that collapses the key alone. `SELECT customer_id, order_date FROM orders GROUP BY customer_id, order_date` returns the right 3 rows but has no `order_id` in them, and `amount` and `created_at` are gone as well. The interviewer asked for one row per key, and a row has 5 columns. The 3 columns that were never part of the key have to come from somewhere, and where they come from is the whole question.


<br>

### Aggregating the other columns invents a row

The first instinct is to aggregate them. For this example, `orders` gains `email` as a sixth column, which the 10:00 write left NULL. Take the 4 rows dated 2024-01-01: customer 1's 3 writes, 100 at 09:00, 140 at 10:00 and 110 at 11:00, and customer 2's single write of 75 at 12:45. With one date in play, grouping by `customer_id` alone is the same as grouping by the agreed key. Wrap every non-key column in `MAX` and the query runs without complaint.

https://github.com/user-attachments/assets/f0b858ab-f892-41fc-a009-52f4ed76de23

Customer 1 comes out at 11:00 with an amount of 140 and the email ana@shopmail.com. No source row carries that combination: the time belongs to the 11:00 write, the amount to the 10:00 write, and the email to whichever write had one, since `MAX` skips NULL and so hides that a write lost it. The latest write of this order says 110, and the revenue report built on this result will say 140. Aggregating column by column assembles a record from pieces of different rows, and the record it assembles never existed. This is what the question tests: whether you know that keeping one row per key means keeping a row, with its columns travelling together, rather than a key with the best value of each column stapled on.


<br>

### Rank the copies, keep rank 1

```sql
WITH ranked AS (
  SELECT
    order_id,
    customer_id,
    order_date,
    amount,
    created_at,
    ROW_NUMBER() OVER (
      PARTITION BY customer_id, order_date
      ORDER BY created_at DESC
    ) AS rn
  FROM orders
)

SELECT
  order_id,
  customer_id,
  order_date,
  amount,
  created_at
FROM ranked
WHERE rn = 1
```

https://github.com/user-attachments/assets/d042af07-3356-4946-9c15-2a51027ea6ea

`PARTITION BY customer_id, order_date` is the key from the first section written into the query: rows that share both columns form one partition and are numbered apart from every other partition. `ORDER BY created_at DESC` decides the numbering inside each one, newest first, so the 11:00 write of (1, 2024-01-01) gets `rn` 1 and the 09:00 write gets 3, with the 10:00 write between them at 2. Rows 1004 and 1005 sit alone in their partitions and get 1. The outer `WHERE rn = 1` keeps 1003 along with those 2 singletons: 3 rows, the count the previous section said to expect, and row 1003 arrives whole, amount 110 beside its 11:00 timestamp. Change the 2 clauses and the same shape answers any key and any survivor rule.


<br>

### Why the filter sits in an outer query

`WHERE` is evaluated before window functions, so in the `SELECT` that defines `rn` the column does not exist yet, and `WHERE rn = 1` fails with an unknown column error. The CTE computes `rn` first, and the outer query filters a result in which `rn` is an ordinary column. Say it as you type the `WITH`: 'I'm wrapping the `ROW_NUMBER` in a CTE because the outer `WHERE` can't filter on a window function in the same select.' Interviewers hear that sentence as evidence you have written this against a real engine, because the error it avoids is the one everybody hits the first time.

```sql
-- Snowflake, BigQuery, Databricks
SELECT
  order_id,
  customer_id,
  order_date,
  amount,
  created_at
FROM orders
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY customer_id, order_date
  ORDER BY created_at DESC
) = 1
```

`QUALIFY` is to window functions what `HAVING` is to aggregates: a filter that runs after the function has been computed. Postgres offers `DISTINCT ON (customer_id, order_date)` with an `ORDER BY customer_id, order_date, created_at DESC`, which keeps the first row of each key in that order. Both are shortcuts for one dialect. The CTE form runs everywhere, so write it unless the interviewer has named the engine, and name the shortcut as you skip it: 'on Snowflake this is a `QUALIFY`, on Postgres a `DISTINCT ON`, and this form is portable.'

> ROW_NUMBER gives exactly one row per key
>
> - `ROW_NUMBER` numbers every row apart, so each partition has exactly one `rn` of 1 and the row count equals the key count
> - Ties are broken arbitrarily, so 2 writes with the same `created_at` can swap survivors between runs; end with a unique column: `ORDER BY created_at DESC, order_id DESC`
> - `RANK` gives tied rows the same rank, so 2 writes with the same `created_at` both pass a `= 1` filter and the duplicate survives
> - The `ORDER BY` is a business rule, latest here; ask which copy should survive and write that column in
> - Verify by counting the output rows against the distinct key count from the previous section

> **TIP**
>
> Write the ranked CTE from memory in under a minute; it is the one shape in this lesson that appears in nearly every dirty-data interview, and stumbling on its syntax costs more than any single mistake in the answer.


<br>

---

## Why DISTINCT Alone Often Fails

Return to the move most candidates make first. `SELECT DISTINCT * FROM orders` compares all 5 columns, and `order_id` differs on every row, so 5 rows go in and 5 come out. The interviewer sees the unchanged count and asks what the query did, and the answer is nothing. Narrowing the select list helps only until a non-key column differs: drop `order_id` and `created_at` and the 3 copies of (1, 2024-01-01) still survive, because the 09:00 copy says 100 and the other 2 say 140 and 110.

| Select list under DISTINCT | Rows returned | What happened |
| --- | --- | --- |
| \* | 5 | `order_id` differs on every row, so nothing folds |
| customer_id, order_date, amount | 5 | the 3 copies carry 3 amounts, so all 3 stay |
| customer_id, order_date | 3 | the key folds, and `amount` is gone |

The table shows the bind. `DISTINCT` collapses the key if you select only the key and keeps the other columns if you select them. It can't do both, because a difference in any selected column keeps the row. That is the rule to state when the interviewer asks why the first attempt failed: '`DISTINCT` compares the whole selected row, and these rows differ in columns outside the key, so the keyword sees 5 different rows.' The fix is the ranked CTE, which collapses on the key and carries the other columns of the chosen row along with it.


<br>

### Differences you cannot see on the screen

A second family of failures hides inside values that look equal. Postgres compares strings case-sensitively and without padding, and so do Snowflake and BigQuery. On those engines 'Alice@Example.com ' with a trailing space and 'alice@example.com' are different strings, and on every engine a NULL address and an empty one differ. `DISTINCT` on a `customers` table with these rows returns every one of them there, and a reader looking at the sample sees 2 copies of Alice and cannot work out why the count did not drop. SQL Server and older MySQL collations ignore case and trailing spaces and may fold the emails, so an explicit `LOWER(TRIM(...))` is what makes the key behave the same everywhere. The duplicate is real; the equality test is too strict.

https://github.com/user-attachments/assets/384db255-4f3c-471a-8854-709df6dd0852

`LOWER(TRIM(email))` maps both of Alice's spellings and both of Bob's to one value each, and `COALESCE(address, '')` replaces the NULL with a blank that can be compared. Bob's 2 rows now agree in every column, and `DISTINCT` over this result folds them. Alice's do not: one still says 12 Oak St and the other says blank, so `DISTINCT` keeps both even though the normalised email proves they describe one person. Normalisation builds a key out of messy columns, and the key-based pattern from the previous section is what removes the copies.

```sql
WITH normalized AS (
  SELECT
    customer_id,
    LOWER(TRIM(email)) AS email_normalized,
    COALESCE(address, '') AS address_normalized,
    ROW_NUMBER() OVER (
      PARTITION BY customer_id, LOWER(TRIM(email))
      ORDER BY CASE
  WHEN address IS NULL THEN 1
  ELSE 0
END
    ) AS rn
  FROM customers
)

SELECT
  customer_id,
  email_normalized,
  address_normalized
FROM normalized
WHERE rn = 1
```

Alice's 2 rows share the partition, the `ORDER BY` puts the row with an address first, and the result has 2 rows, one per person, with Alice's carrying 12 Oak St. It is the same shape as before with the key built from expressions instead of stored columns. Say that as you write it: 'the key is an expression, so I partition on the expression and keep the most complete copy.'


<br>

### The diagnosis the interviewer wants to hear

When a dedup returns the same count it was given, 3 diagnoses are possible, and naming the right one in a sentence is what scores. The rows differ in a column outside the key, so the fix is partition-and-rank. The rows differ in formatting, so the fix is to normalise into a key first. Or the rows are not duplicates under the agreed key at all, so the overcount comes from a join downstream and the table is fine. Running through those 3 out loud, in that order, shows the interviewer a method rather than a guess.

> **TIP**
>
> If the sample shows 2 rows that look identical and your `DISTINCT` kept both, ask for `LENGTH(email)` on each before changing the query: a trailing space shows up as 18 against 17 and settles the diagnosis in one line.

| ✓ Do | ✗ Don't |
| --- | --- |
| • State the key and the grain in one sentence before writing SQL<br><br>• Count rows and distinct keys first; the difference is what you must remove<br><br>• Use DISTINCT only when the copies agree in every selected column<br><br>• Keep whole rows with ROW_NUMBER over the key, filtered in an outer query<br><br>• Lowercase and trim text keys, and map NULL to a comparable value, before comparing | • Run SELECT DISTINCT \* and read an unchanged count as 'no duplicates'<br><br>• Aggregate non-key columns with MAX and call the result a row<br><br>• Filter rn = 1 in the same SELECT that defines it<br><br>• Use RANK where exactly one survivor per key is required<br><br>• Remove rows without a number for how many should disappear |


<br>

---

## Putting It All Together

A retailer's order feed, consumed from Kafka with at-least-once delivery, double-writes a few hundred orders a day after broker restarts, and finance reports a daily order count 3% above the warehouse's. The platform team is asked to make the orders table safe to sum.

- The grain comes first. Each row is one order keyed on order_id . If the feed assigns a fresh order_id to each write, the key moves to customer_id with order_date , and the team says so before writing anything.
- The count query runs on a day of data: 5 rows and 3 keys on a sample means 2 extra rows, and the repeating-keys query shows whether copies are identical retries or writes carrying different amounts.
- DISTINCT on the key alone gives the right count and loses the amounts, so the removal is a ranked CTE partitioned by the key and ordered by created_at DESC , with its output counted against the key count.
- Emails that differ only in case or trailing whitespace are normalised with LOWER and TRIM before the key is built. DISTINCT compares strings exactly, and so does the partition.
- The 3% gap closes when the deduplicated table sums to finance's figure, and the rate of removal is reported upstream as the measure of the retry problem.


<br>

---

## Key Takeaways

- A duplicate has no meaning until a column list defines it; state the key and the grain before writing SQL.
- DISTINCT and GROUP BY fold rows that agree in every listed column; GROUP BY can add a count or an aggregate beside each survivor.
- Count rows and distinct keys before removing anything; the difference is what the removal must delete, and its output must equal the key count.
- Keeping one whole row per key is ROW_NUMBER over the key, filtered to 1 in an outer query; aggregating columns assembles a row that never existed.
- DISTINCT keeps any row that differs in any selected column, so by-key copies and near-matches survive it until a key is built and ranked.
