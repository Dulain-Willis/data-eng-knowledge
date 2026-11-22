# NULL Handling: Intermediate

Twenty minutes into a SQL round at a marketplace company, the interviewer pastes 2 tables into the shared editor.
"Revenue and average order value by region, then our top 3 customers by revenue. We run on Snowflake."
Half the region cells are blank. So are half the order amounts, because partner orders settle at month end. Neither fact is mentioned. The query most candidates type, a `GROUP BY region` with `AVG(amount)` and an `ORDER BY revenue DESC LIMIT 3`, runs without a single error and makes 3 decisions nobody signed off on: a blank region row with no label, an average taken over half the orders, and a top 3 made entirely of customers with no revenue.
What she is grading is whether you ask what each blank means before you group, average, bucket or sort a single row.


<br>

### What you will be able to do

Explain why GROUP BY puts NULLs in a single group, as DISTINCT and PARTITION BY do, while a join on the same column drops them

Predict COUNT(\*), COUNT(col), SUM and AVG over a nullable column, and choose the average the business question needs

Write a CASE that sends NULL rows to a branch you chose instead of whatever the ELSE holds

Pin NULL placement in a sort on any engine, including those without NULLS FIRST and NULLS LAST

Build a COALESCE chain in trust order, then defend each fallback and the default value, including its type


<br>

---

## Why NULLs Share One Group

This part of the question rarely arrives as "how does GROUP BY treat NULL?" It arrives as a symptom: "the regional report has a blank row at the bottom", or "region counts add up to 6 customers, but after the join to targets only 3 are left". Both symptoms come from a single column behaving 2 ways, and the interviewer wants both ways named before anyone edits the query.


<br>

### Distinctness groups, equality compares

SQL asks 2 different questions about a pair of values. A predicate, such as a join's ON clause or a WHERE, asks whether they are **equal**, and NULL = NULL is unknown, so the pair is rejected. A grouping operation asks whether they are **distinct**, and the SQL standard defines 2 NULLs as not distinct from each other. GROUP BY and SELECT DISTINCT use distinctness. So do UNION and INTERSECT, along with EXCEPT and PARTITION BY, which is why every NULL lands in a single bucket.

The reason is bookkeeping. A grouping has to place every row in exactly 1 group. If NULLs were dropped, the group counts would stop adding up to the table's row count. If each NULL were its own group, 3 unassigned customers would produce 3 identical `NULL, 1` rows that nothing downstream could tell apart or join back to, and `SELECT DISTINCT` would stop removing duplicates. So the standard treats NULLs as not distinct, and "grouping uses distinctness, predicates use equality" is the sentence that tells the interviewer you know there are 2 rules.

```sql
SELECT
  region,
  COUNT(*) AS customers
FROM customers
GROUP BY region
```

| region | customers |
| --- | --- |
| EU | 2 |
| US | 1 |
| NULL | 3 |

The query returns 3 groups, and the counts sum to 6. The NULL row is real output: a BI tool renders it as an empty label or the word "(null)", and it is the blank row from the first symptom above.


<br>

### The join that loses 3 customers

Now join the same customers to `region_targets`, a table of monthly targets per region. Someone anticipated the gap and added a row with a NULL region and a target of 40 for unassigned customers. Watch what the `ON` clause does with that row.

https://github.com/user-attachments/assets/d662270a-8760-48a0-8d15-c599eb4d6a9e

Customer 2 is compared against all 3 target rows, and so are customers 5 and 7. Every comparison comes back unknown, including the one against the NULL row added for them. The join takes in 6 customers and returns 3 rows: customers 1 and 4 pick up EU's 120, customer 3 picks up 90, and the 40 is never used. The inner join raises no error and no warning, and the result looks complete.

| ✓ Distinctness: NULLs gather | ✗ Equality: NULLs never match |
| --- | --- |
| • GROUP BY region puts all 3 NULLs in a single group<br><br>• SELECT DISTINCT region returns a single NULL row<br><br>• UNION treats 2 rows with NULL in the same column as duplicates<br><br>• PARTITION BY region gives every NULL row a shared window | • JOIN ... ON c.region = t.region drops every NULL key<br><br>• WHERE region = 'EU' and WHERE region <> 'EU' both exclude NULL rows<br><br>• A self-join on region pairs no NULL row, not even with itself<br><br>• region IN (SELECT region FROM region_targets) never finds a NULL |

The distinctness side has a practical payoff. `EXCEPT` treats NULLs as matching, so `SELECT * FROM snapshot_today EXCEPT SELECT * FROM snapshot_yesterday` returns the rows that are new or changed today, and the reverse direction returns the old versions plus the deletions. A join on every column instead reports each row holding a NULL as deleted and re-added, because those rows can never match themselves.


<br>

### The same rule inside OVER

Window partitions are groupings, so they follow distinctness too. Below, `ROW_NUMBER` restarts in each partition, and the 3 NULL-region customers share a single numbering.

https://github.com/user-attachments/assets/e844d024-23d1-466f-a451-8eb1fab2ad2d

Customer 2 gets row number 1, and customers 5 and 7 follow with 2 and 3 in signup order, exactly as if NULL were a region name. That is the right behaviour for a running count of unassigned signups and the wrong one for a per-region "first customer" flag, which would crown customer 2 as the first customer of a region that does not exist.

> Follow-ups that test whether you have hit this
>
> - "Why doesn't the NULL target row match?" Because `ON` tests equality, and no NULL equals anything, itself included.
> - "How do you keep the 3 customers?" A `LEFT JOIN` keeps them with a NULL target; mapping NULL to a real key on both sides makes them match, at a cost covered under COALESCE.
> - "Is the NULL group a bug?" Only if its consumer did not expect it. Say whether it stays in the output with a label or gets filtered out, and whether a data-quality check should see it.
> - "Does `COUNT(DISTINCT region)` include it?" No. That is an aggregate, and aggregates follow their own rule.

> **TIP**
>
> Compare `COUNT(*)` before and after any join to a dimension. A grouped report whose counts sum to the source count has kept its NULLs; an inner join that shrank the count has dropped them, and the difference is the number of rows with a NULL or unmatched key.


<br>

---

## NULLs in Aggregates and COUNT

This part arrives as a number that moved with no change to the logic: "the dashboard shows 3 priced orders and the table has 6", or "average order value is 40 on the dashboard and 20 in my spreadsheet". Both are aggregates skipping NULLs exactly as specified. The strong answer names the rule and then asks what the NULL means, because the rule is fixed and the meaning decides which number is correct.


<br>

### Every aggregate skips NULL except COUNT(\*)

COUNT(\*) counts rows. COUNT(amount) and SUM first discard the rows where their argument is NULL and then work on what is left. So do AVG and MIN, and MAX and COUNT(DISTINCT ...) behave the same way. COUNT returns 0 when no rows survive, but the others return NULL, which is why an empty group shows a blank revenue cell rather than a zero.

The `orders` table below holds 6 orders across 3 channels. Partner orders are invoiced monthly, so their `amount` stays NULL until the invoice posts, and app order 102 is still waiting on payment capture.

https://github.com/user-attachments/assets/e749704a-1da2-43f5-80c7-f6277dbcb98a

Web keeps both rows in every aggregate: 2 orders, 100 in revenue, an average of 50. App loses order 102 from everything except `COUNT(*)`, so its average is 20 over a single priced order. Partner counts 2 orders with none priced, so `SUM` and `AVG` have no rows left to work on and its revenue and average come back empty.


<br>

### 2 averages, both defensible

Across all 6 orders, `AVG(amount)` is 40: 120 divided by the 3 priced orders. `SUM(amount) / COUNT(*)` is 20: the same 120 over all 6. Neither is a bug. The first is the average price of an order whose price is known; the second treats every unpriced order as worth zero. If partner orders will be invoiced next week, 20 understates revenue per order by half and 40 is the honest figure. If NULL meant a free sample, 20 would be the right one.

```sql
SELECT
  AVG(amount) AS avg_known, -- 40
  AVG(COALESCE(amount, 0)) AS avg_zero_filled, -- 20
  COALESCE(AVG(amount), 0) AS avg_or_zero -- 40
FROM orders
```

`COALESCE` inside the aggregate rewrites the data before `AVG` sees it, which moves the answer from 40 to 20. `COALESCE` outside the aggregate replaces only a NULL result, so it would turn the partner channel's empty average into 0 without touching any other number. State which position you mean out loud; the interviewer is listening for whether you know the 2 positions answer different questions.


<br>

### DISTINCT keeps the NULL that COUNT(DISTINCT) drops

On the customers table, `SELECT DISTINCT region` returns 3 rows because `DISTINCT` is a grouping, and the third row after EU and US is NULL. `COUNT(DISTINCT region)` returns 2, because it is an aggregate and discards NULL first. A check that compares a distinct-count with the rows of a `SELECT DISTINCT` is off by 1 whenever the column is nullable, so "how many regions do we operate in?" has 2 answers depending on which query produced it.


<br>

### Conditional aggregates lean on the skip

```sql
SELECT
  COUNT(
    CASE
      WHEN amount >= 50 THEN 1
    END
  ) AS large_orders, -- 1
  SUM(
    CASE
      WHEN amount >= 50 THEN 1
      ELSE 0
    END
  ) AS large_flagged, -- 1
  COUNT(
    CASE
      WHEN amount IS NULL THEN 1
    END
  ) AS unpriced -- 3
FROM orders
```

The `COUNT(CASE ...)` form works because a `CASE` with no `ELSE` yields NULL for rows that fail its test, and `COUNT` skips those NULLs. Every pivot you write depends on that skip. It also means a NULL `amount` lands in neither a large count nor a small one unless a branch tests for it. In a group where no row passes the test, `SUM(CASE ... ELSE 0 END)` returns 0, while `SUM(CASE WHEN ... THEN amount END)` returns NULL.

The same rule decides a rate. `AVG(CASE WHEN amount >= 50 THEN 1.0 ELSE 0 END)` is 1 large order in 6, around 17%. Drop the `ELSE` and add `WHEN amount < 50 THEN 0`, and the 3 unpriced orders become NULL and leave the denominator: 1 in 3, roughly 33%. The data did not change; the rate doubled because a `CASE` let different rows through as NULL.


<br>

### Numbers that move when the data fills in

Because NULLs are skipped, every aggregate here changes when the missing values arrive, with no change to the query. Web's share of revenue is 100 of 120 today, around 83%. When the 2 partner invoices post, the numerator stays at 100 and the denominator grows, so the share drops. Say this before the stakeholder sees it, and report `COUNT(*) - COUNT(amount)` as unpriced orders next to the revenue, so a moving number arrives with its explanation.

> When the interviewer pushes
>
> - "Is `COUNT(1)` faster than `COUNT(*)`?" No. Current optimizers plan them identically; both count rows.
> - "Why is `COUNT(amount)` 3?" It counts non-NULL values, which makes it a completeness metric with no extra code.
> - "Can `MIN(amount)` return an unpriced order?" No. `MIN` ignores NULL, so the cheapest order is order 105 at 20.
> - "Divide by `COUNT(*)` or `COUNT(amount)`?" Ask what an unpriced order means, then pick. Here the denominators differ by 3 orders.
> - "Why did `SUM` return NULL instead of 0?" Every input was NULL. Wrap the result, `COALESCE(SUM(amount), 0)`, if the report needs a zero.
> - "Does `AVG` over a window skip NULLs too?" Yes. `SUM` skips NULLs inside `OVER` just as it does in `GROUP BY`, and so do `AVG` and `COUNT(col)`.


<br>

---

## NULLs Falling Through a CASE

The `CASE` version of this question hides inside a segmentation request: "split customers into EU and rest of world for the GDPR register". NULL is never mentioned. The query most people write negates the condition, and without any error it sends every customer with an unknown region into the EU bucket.

A searched CASE checks its WHEN conditions top to bottom and returns the first branch whose condition is TRUE. A comparison against NULL is unknown, and unknown is not TRUE, so the row skips that branch exactly as a FALSE row would. If no branch is TRUE, the row takes the ELSE, and with no ELSE the result is NULL. Every NULL row therefore ends up in whichever branch nobody tested it against.

https://github.com/user-attachments/assets/9fdc6e14-2106-42a7-96ee-c58c2f93301e

Customer 3 is the only row where `region <> 'EU'` is TRUE. Customers 1 and 4 are FALSE and reach the `ELSE` as intended. Customers 2 and 5 evaluate to unknown, as does customer 7, and all 3 reach the same `ELSE`, so the `eu` market holds 5 customers when 2 are in the EU. For a GDPR register that is 3 customers whose data residency nobody knows, recorded as settled.

Every negation behaves this way. `WHEN region NOT IN ('EU', 'UK')` and `WHEN NOT (region = 'EU')` send NULL rows to the `ELSE` too, and rewriting the test with De Morgan's laws changes nothing, because `NOT` applied to unknown is still unknown.


<br>

### 2 branches that can never fire

```sql
-- Searched CASE: '=' against NULL is unknown on every row
CASE WHEN region = NULL THEN 'unassigned' ELSE region END

-- Simple CASE: shorthand for region = NULL, same result
CASE region WHEN NULL THEN 'unassigned' ELSE region END

-- The test that works
CASE WHEN region IS NULL THEN 'unassigned' ELSE region END
```

The simple form `CASE region WHEN x` is shorthand for `region = x`, so a `WHEN NULL` written there is dead code on every engine. Both broken versions return the original NULL for all 3 unassigned customers, which makes them look as if they ran. `IS NULL` is the test that returns TRUE for a NULL.


<br>

### Which branch the NULL rows reach

| CASE shape | Where NULL rows land | What it costs |
| --- | --- | --- |
| `WHEN region = 'EU' THEN ... ELSE ...` | The ELSE branch | Unknowns join the catch-all bucket |
| `WHEN region <> 'EU' THEN ... ELSE ...` | The ELSE branch | Unknowns join the bucket you negated, here EU |
| `WHEN amount >= 50` and `WHEN amount < 50`, no ELSE | NULL output | Ranges that look exhaustive still miss 3 orders |
| The same ranges with `ELSE 'small'` | The ELSE branch | Unpriced orders are counted as small |

The third row is the one interviewers like, because the 2 ranges cover every number and the candidate concludes the `CASE` is exhaustive. Order 102 has no number at all, and neither do 104 and 106. All 3 come out with a NULL size and then form a group of their own when the result is grouped, which is the grouping rule from earlier meeting this one.


<br>

### The fix: test NULL by name

```sql
SELECT
  customer_id,
  CASE
    WHEN region IS NULL THEN 'unassigned'
    WHEN region = 'EU' THEN 'eu'
    ELSE 'rest_of_world'
  END AS market
FROM customers
-- eu: 2   rest_of_world: 1   unassigned: 3
```

Because no comparison is TRUE for a NULL, the `IS NULL` branch could sit anywhere before the `ELSE` and still catch all 3 rows. Put it first anyway, so a reader sees the NULL decision before the business logic. The rewrite also turns the test positive, `region = 'EU'`, so the `ELSE` now holds only known non-EU values instead of everything nobody tested.

A shorter patch, `WHEN COALESCE(region, '') <> 'EU'`, moves the 3 NULL customers into `rest_of_world` instead. It runs, and it is a data-residency decision made inside a string literal. If you write it, say that you are classifying unknown as non-EU and ask whether the register owner agrees; an explicit `unassigned` bucket leaves that call with the people who own it.

> **TIP**
>
> Make the `ELSE` an alarm. A branch like `ELSE 'UNMAPPED'`, plus a data test that fails when any row carries that label, turns the next unexpected value or NULL into a failed build instead of a quietly wrong segment.

> What the interviewer is listening for
>
> - That you ask what an unknown region should mean for this register before writing the CASE.
> - That you name the bucket the NULL rows fall into under the query as written.
> - That the counts after the fix sum to the input: 2 + 1 + 3 = 6 customers.
> - That `CASE x WHEN NULL` is recognised as dead code rather than a NULL check.
> - That a NULL output from a CASE is expected to form its own group downstream.


<br>

---

## Where NULLs Land in a Sort

The sort version arrives as a ranking request, "top 3 customers by revenue" or "most recent login per account", or as a migration bug: "the leaderboard was right on MySQL and broke on Snowflake". The query text contains no NULL anywhere. The NULLs come from the data, and where they land is a property of the engine.

```sql
WITH customer_revenue AS (
  SELECT
    customer_id,
    SUM(amount) AS revenue
  FROM orders
  GROUP BY customer_id
)

SELECT
  customer_id,
  revenue
FROM customer_revenue
ORDER BY revenue DESC
LIMIT 3
```

NULL sorts high (PostgreSQL, Snowflake)

NULL sorts low (MySQL, BigQuery)

The SQL standard says NULLs sort together and must come before every non-NULL value or after all of them, and it leaves the choice to the implementation. Most engines picked whether NULL behaves as the largest value or the smallest; Trino and Presto instead put NULLs last in both directions. Largest means last in ASC and first in DESC, which is why a descending top 3 on PostgreSQL fills with NULLs before it reaches a real number.

| Engine | ASC default | DESC default | NULLS FIRST / LAST syntax |
| --- | --- | --- | --- |
| PostgreSQL, Oracle, Redshift, Snowflake | NULLs last | NULLs first | Yes |
| BigQuery, Spark SQL | NULLs first | NULLs last | Yes |
| MySQL, SQL Server | NULLs first | NULLs last | No |
| Trino, Presto | NULLs last | NULLs last | Yes |

*Snowflake's placement comes from the DEFAULT_NULL_ORDERING parameter. Its default is LAST, but the parameter can be set at the account level or per session, so a query that never states its own placement can have it changed underneath it.*


<br>

### Pinning the position

```sql
-- PostgreSQL, Snowflake, BigQuery, Oracle: state it every time
ORDER BY revenue DESC NULLS LAST

-- MySQL and SQL Server have no NULLS LAST: sort on a NULL flag first
ORDER BY CASE WHEN revenue IS NULL THEN 1 ELSE 0 END,
         revenue DESC
```

The flag version runs on every engine: 0 sorts before 1, so the priced customers come first in descending revenue and the 3 NULL customers trail them. Write explicit placement whenever the sort column is nullable, even where the default happens to suit you, because the next engineer may port the query and the default does not travel with it.

The same defaults apply to `ORDER BY` inside `OVER`. A `ROW_NUMBER` meant to pick each account's latest login, ordered by `last_login_at DESC`, picks the account's NULL login row on PostgreSQL and Snowflake. Pin the placement there as well.


<br>

### MAX skips NULLs, ORDER BY does not

`MAX(revenue)` over the same CTE returns 60, because aggregates discard NULL. `ORDER BY revenue DESC LIMIT 1` returns customer 2 with a NULL on PostgreSQL. The 2 are often treated as interchangeable ways to find the top value, and they agree only where a descending sort puts NULLs last (MySQL, SQL Server, BigQuery, Spark, Trino) or when the column has no NULLs. Raising this unprompted signals that you have debugged it.


<br>

### COALESCE in the sort key changes the ranking

`ORDER BY COALESCE(revenue, 0) DESC` also pushes the NULLs down, but it ranks an unpriced customer level with one who genuinely spent 0, and under a tie-breaker the 2 kinds interleave. `NULLS LAST` keeps them apart. The choice affects plans too: in PostgreSQL a B-tree index on `revenue` serves `ORDER BY revenue DESC NULLS FIRST` by scanning backwards. `DESC NULLS LAST` or a `COALESCE` expression gets no such help and needs an index built to match. Without one, the engine falls back to a full sort.


<br>

### Paging past the NULLs

Keyset pagination adds a comparison to the sort, and the comparison drops NULLs. With 2 rows a page, page 1 of `ORDER BY revenue DESC NULLS LAST` ends at customer 1 with 40, page 2 asks for `WHERE revenue < 40`, and the 3 NULL-revenue customers never appear on any page because `NULL < 40` is unknown. Page through them with a separate `WHERE revenue IS NULL` query, or sort on a key that holds no NULLs.


<br>

### The sentence to say

Before writing `ORDER BY` on a nullable column, say where the NULLs will go and whether they belong in the answer at all. Something like: "revenue is NULL for customers whose orders are all unpriced. Snowflake sorts NULL high, so a descending top 3 would be 3 NULLs. I'll exclude them, and if the business wants them listed, I'll add `NULLS LAST`." Those 3 sentences explain how the engine places NULLs and then make a call on them, which is what this part of the round scores.

> Follow-ups on a sorted answer
>
> - "Should unpriced customers be in the top 3 at all?" Usually no. Filter `WHERE revenue IS NOT NULL` and say so, rather than relying on placement.
> - "What order do the NULL rows come back in?" Arbitrary. Add `customer_id` as a tie-breaker so repeated runs and pages agree.
> - "Does an `ORDER BY` inside the CTE fix the order?" No. Only the outermost `ORDER BY` is guaranteed, so placement belongs there.


<br>

---

## COALESCE Fallback Chains

The chain question arrives as a modelling request: "we have a region from the shipping and billing addresses, plus one from IP geolocation; give me one region per customer". The `customers.region` column used throughout this lesson was loaded from shipping address alone, which is why 3 of the 6 customers have none. A fallback chain fills them from the other sources.

COALESCE(a, b, c, ...) returns its first argument that is not NULL, reading left to right, and returns NULL only if every argument is NULL. The argument order is a **trust ranking**: the first source with a value wins, even when a later source disagrees. PostgreSQL documents that arguments after the first non-NULL one are not evaluated; SQL Server expands COALESCE into a CASE, so a subquery passed as an argument can run more than once.

https://github.com/user-attachments/assets/28bffa03-7981-4678-8c26-8d8d912fb2c6

Customer 2 falls through to billing and becomes US, customer 4 keeps shipping's EU, and customer 7 exhausts every source and takes the literal. Customer 5's billing region is an empty string from a web form, an empty string is a value, and `COALESCE` stops there and returns it. The APAC in `ip_region` is never read, and the customer is grouped under a blank region that `IS NULL` cannot find.


<br>

### Normalise blanks before the chain

```sql
SELECT
  customer_id,
  COALESCE(
    NULLIF(TRIM(shipping_region), ''),
    NULLIF(TRIM(billing_region), ''),
    NULLIF(TRIM(ip_region), ''),
    'UNKNOWN'
  ) AS region,
  CASE
    WHEN NULLIF(TRIM(shipping_region), '') IS NOT NULL THEN 'shipping'
    WHEN NULLIF(TRIM(billing_region), '') IS NOT NULL THEN 'billing'
    WHEN NULLIF(TRIM(ip_region), '') IS NOT NULL THEN 'ip'
    ELSE 'default'
  END AS region_source
FROM customer_geo
```

| customer_id | region | region_source |
| --- | --- | --- |
| 1 | EU | shipping |
| 2 | US | billing |
| 3 | US | shipping |
| 4 | EU | shipping |
| 5 | APAC | ip |
| 7 | UNKNOWN | default |

`NULLIF(x, '')` turns the blank into NULL so the chain moves on, and `TRIM` catches the single-space version of the same problem. The `region_source` column records which link won. It costs a single `CASE`, and it answers the first question anyone asks after a fallback ships: how many of these regions are guesses? Here 3 of 6 came from a fallback, and each link after shipping supplied exactly 1, the default included.


<br>

### Order is a business decision

Shipping goes first because it records where goods were delivered, which is the region tax and logistics care about. Billing comes second because the customer declared it, though it can be a corporate head office. IP comes last because VPNs and travel move it. Reorder the chain and the same rows give different answers: with `ip_region` first, every customer behind a VPN takes the VPN's exit country, and shipping fills only the rows where geolocation failed. In the room, justify each position in a single clause; an unjustified order reads as a guess.


<br>

### The default goes last

A literal default belongs in the last position, because every argument after it is unreachable. Whether to have one at all is a separate decision. `'UNKNOWN'` gives a dashboard a labelled group instead of a blank row, and it also hides customer 7 from any later `WHERE region IS NULL` check meant to find unresolved customers. Many teams keep the NULL in the cleaned table and apply the label in the reporting layer, where nobody filters on it.


<br>

### Types and the 2-argument cousins

Every argument must resolve to a single data type. COALESCE(customer_id, 'none') on an integer column fails on PostgreSQL and Snowflake; cast the column to text or choose a default of the same type. The 2-argument shortcuts differ: IFNULL (MySQL, BigQuery) and NVL (Oracle, Snowflake) behave like a 2-argument COALESCE, while SQL Server's ISNULL returns the type of its first argument, so ISNULL(region_code, 'UNKNOWN') on a VARCHAR(2) column returns 'UN'.

A chain whose fallback rule is something other than missing needs a `CASE` instead. Skipping shipping regions that come from PO boxes, or preferring billing when the order was digital, are conditions on other columns, and `COALESCE` can only test for NULL. The `region_source` column above is already that ladder written out, which is also its risk: the 2 expressions stay in step only if every edit touches both.


<br>

### Rescuing the join from earlier

```sql
SELECT
  c.customer_id,
  t.monthly_target
FROM customers AS c
JOIN region_targets AS t
  ON COALESCE(c.region, 'UNASSIGNED') = COALESCE(t.region, 'UNASSIGNED')
```

With this, the unassigned customers match the 40 target. Name the 2 costs as you write it: wrapping a join key in a function stops the engine from using an index or partition pruning on that column, and the literal must never be a real region value, or the join merges 2 groups and raises no error. Resolving `region` upstream with the fallback chain is usually the better fix, because fewer rows reach the join with a NULL at all.

> Follow-ups on a fallback chain
>
> - "What if shipping and billing disagree?" The chain hides it. Count customers where both are present and differ, and report that number.
> - "Why not `NVL`?" It takes only 2 arguments, so a 3-source chain becomes nested calls, and `COALESCE` is the standard form every engine reads.
> - "Where should the chain run?" Once, in the model that produces `region`, so every report resolves a customer to the same answer.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Ask what a NULL means for this report before you write any query over it<br><br>• Write NULLS FIRST or NULLS LAST, or sort on a NULL flag, for every nullable sort key<br><br>• Put WHEN x IS NULL as the first branch of any CASE over a nullable column<br><br>• Wrap blank-prone inputs in NULLIF(TRIM(x), '') before they enter a COALESCE chain<br><br>• Reconcile grouped and post-join counts against COUNT(\*) of the source | • Don't divide by COUNT(\*) or COUNT(col) without saying what the denominator counts<br><br>• Don't negate a CASE condition and leave the NULL rows to the ELSE<br><br>• Don't place a literal default anywhere but the last argument of COALESCE<br><br>• Don't treat MAX(x) and ORDER BY x DESC LIMIT 1 as the same query on a nullable column |


<br>

---

## Putting It All Together

A marketplace's finance team asks for a monthly regional pack on Snowflake: revenue and average order value per region, a top-10 customer list and an EU versus rest-of-world split for the GDPR register. Many customers have no region on file, and partner orders stay unpriced until month-end invoicing.

- Resolve region with a shipping, billing, IP COALESCE chain over NULLIF-cleaned inputs, so fewer customers reach the NULL group at all.
- Group by the resolved region, confirm the group counts sum to COUNT(\*), and join to targets with a LEFT JOIN so unresolved customers stay visible.
- Report AVG(amount) as average known order value, with COUNT(\*) minus COUNT(amount) beside it as unpriced orders.
- Build the GDPR split with an IS NULL branch first, so customers with no region sit in an unassigned bucket the register owner can review.
- Rank customers with ORDER BY revenue DESC NULLS LAST and a customer_id tie-breaker, or filter unpriced customers out and say so.


<br>

---

## Key Takeaways

- Grouping operations treat NULLs as not distinct and gather them, but a comparison with NULL returns unknown, which is why a join or a WHERE clause drops those rows.
- Every aggregate but COUNT(\*) skips NULLs; an all-NULL group gives COUNT 0 and NULL from SUM, AVG, MIN and MAX.
- A CASE row whose test is unknown falls to the ELSE, or to NULL without one; give NULL its own IS NULL branch, first.
- PostgreSQL and Snowflake sort NULL high where MySQL and BigQuery sort it low, so write the placement into every nullable sort.
- COALESCE returns the first non-NULL argument, so its order is a trust ranking, and an empty string stops the chain.
