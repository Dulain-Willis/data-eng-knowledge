# Conditional Aggregation: Beginner

You are 15 minutes into a SQL screen at an online retailer.
"Here is our customers table: customer_id, region, status, signup_date. Status is active, inactive or churned. Give me one row per region showing how many customers are active, how many are inactive, and how many there are in total."
She turns the laptop toward you. The table is long, one row per customer, and the answer is wide, 3 numbers beside a region name. Nobody has said the word pivot. The first move most candidates make is a `WHERE status = 'active'` query, which produces 1 of the 3 numbers and leaves 2 more queries to write and glue together.
What she is listening for is whether you see that all 3 numbers come from the same grouped rows, and whether the query that produces them appears on the screen inside a minute.


<br>

### What you will be able to do

Spot when a request wants one row per group with a column per category, whether it says so in words or shows you sample output

Write SUM(CASE WHEN ...) and COUNT(CASE WHEN ...) columns that count or sum only the rows meeting a condition

Put a total beside its subsets in one grouped query and compute the rate from the same row

Check that columns meant to split a total count every row exactly once, and catch the NULL that escapes every bucket

Count the distinct users who qualify rather than the rows that do, and say which one the question asked for


<br>

---

## When the Output Looks Like a Pivot

The question never says pivot. It says 'a column for active customers and a column for inactive ones per region', or 'revenue split into premium and standard', or 'signups and converters per cohort'. Each phrasing describes an output that is wider than the input: the table has one row per customer and a single status column, and the answer has one row per region and a column for every status value the asker cares about. Wider output from a long table is the signal.

- Per region, I need separate columns for active and inactive customers
- Break revenue down by tier, premium and standard side by side
- Show signups and the number who converted, per cohort month
- Turn this long table of status rows into a wide summary
- How many orders were over 100 dollars, and how many in total, per store


<br>

### Long in, wide out

A `WHERE` clause keeps or drops whole rows, so a query with `WHERE status = 'active'` can produce the active count and nothing else: the inactive rows left the query before `GROUP BY` ever saw them. The output the interviewer described needs the active count and the inactive count in the same row, which means both sets of rows have to reach the group, and each column has to decide for itself which of the grouped rows it counts. So the condition goes inside the aggregate and is checked against each row.

customers, one row per customer

The answer, one row per region

Read the answer table column by column and the query follows from it. The column that labels each row, `region`, is the `GROUP BY` column. Every other column is an aggregate over that region's rows. A column named after a value in the data is an aggregate that counts only the rows carrying that value. `active` is one; `premium` and `converted` work the same way. The way to say 'only these rows' inside an aggregate is a `CASE` that returns something for a matching row and `NULL` or 0 for the rest. The `total` column is the same aggregate with no condition, and North's 0 under `inactive` is a region with no matching rows still getting its row.

| As asked | Group by | Categories come from | Aggregate |
| --- | --- | --- | --- |
| Active and inactive customers per region | region | status | COUNT |
| Revenue by tier, per region | region | tier | SUM(amount) |
| Signups and converters per cohort month | cohort_month | completed_onboarding | COUNT |
| Orders over 100 dollars and total orders per store | store_id | amount > 100 | COUNT |
| Purchases, refunds and net per day | order_date | order_type | SUM(amount) |

The request also arrives from the other direction. The interviewer pastes a 3-row sample of the dashboard tile they want filled and asks for the query behind it. The same reading applies: find the column whose values are labels, treat it as the group, and treat every numeric column as an aggregate whose name tells you its condition. A tile headed `premium_revenue` is `SUM` over amount where tier is premium; one headed `orders` with no qualifier is `COUNT(*)`.


<br>

### The sentence to say before writing

State the plan in one sentence before typing: 'I'll group by region and use conditional aggregates, a `CASE` inside each `COUNT` or `SUM`, to get one column per status.' That sentence shows the interviewer you recognized the shape and know the technique by name, and it commits you to a single query, so the next 60 seconds are typing rather than deciding. A candidate who opens with `SELECT region, COUNT(*) FROM customers WHERE status = 'active'` is answering a third of the question and will throw the query away when asked where the other columns are.

> What the output tells you about the query
>
> - The column that labels each row is the GROUP BY column; everything else is an aggregate
> - A column named after a data value counts or sums only the rows holding that value
> - A total column is the same aggregate with no condition, even when it is headed all or overall
> - The number of category columns equals the number of distinct values the asker cares about

| ✓ 3 filtered queries | ✗ One grouped query |
| --- | --- |
| • SELECT region, COUNT(\*) ... WHERE status = 'active', then the same again for inactive and churned<br><br>• 3 result sets that someone then stitches together in application code, if not by hand<br><br>• A change to the grouping has to be made in 3 places<br><br>• Reads to the interviewer as not having seen the shape | • One GROUP BY region over the whole table<br><br>• Each status column is an aggregate with its own CASE condition<br><br>• Every region appears once, with 0 in a column where it has no rows<br><br>• On the screen within a minute, with the total beside the slices |


<br>

---

## SUM(CASE WHEN ...) as a Count

`CASE` runs once per row, before any aggregate sees the row. `CASE WHEN tier = 'premium' THEN 1 ELSE 0 END` looks at one order and produces a 1 if the tier is premium and a 0 otherwise. `SUM` then adds those 1s and 0s across the group, and because every 0 adds nothing, the result is the number of premium orders. The row stayed in the group the whole time; the condition decided its contribution. That is the difference between this and a `WHERE`, and the interviewer will ask you to state it.

```sql
SELECT
  region,
  SUM(
    CASE
      WHEN tier = 'premium' THEN 1
      ELSE 0
    END
  ) AS premium_orders,
  COUNT(*) AS all_orders
FROM orders
GROUP BY region
```


<br>

### Watching a row become 1 or 0

The orders table below has 3 rows in North and 1 in South. The query adds a second conditional column that uses the same condition with `amount` in place of 1, so you can watch each row resolve to 1 or 0 for the count and to its amount or 0 for the revenue before the groups fold.

https://github.com/user-attachments/assets/3ebae206-9666-4e2d-9046-758f87988a5d

North holds orders 1 to 3. Order 1 is premium and becomes 1 and 100; order 2 is standard and becomes 0 and 0; order 3 is premium and becomes 1 and 200. The sums are 2 premium orders, 300 in premium revenue, and 350 in total revenue from the unconditional `SUM(amount)`. South holds only order 4, a standard order at 300, so both of its `CASE` results are 0 and only the total column shows 300: a region with no premium orders still gets its row, with 0 in the premium columns. The standard orders contributed 0 to the premium columns, which is why the total column still sees their 50 and 300.


<br>

### Same shape, a different value

The count form and the sum form are one pattern with the `THEN` swapped. `THEN 1` counts matching rows; `THEN amount` sums their amounts; `THEN amount * 0.1` would sum a derived value. When the interviewer adds 'and premium revenue' to a question about premium order counts, the new column is the same `CASE` with a different `THEN`. Saying so, 'same condition, the value changes from 1 to amount', shows you see one pattern rather than 2 separate tricks.

| Expression | What the column holds |
| --- | --- |
| SUM(CASE WHEN cond THEN 1 ELSE 0 END) | How many rows match |
| SUM(CASE WHEN cond THEN amount ELSE 0 END) | Total amount across the matching rows |
| SUM(CASE WHEN cond THEN 1 END) | How many rows match; non-matching rows give NULL, which SUM skips |
| SUM(amount) | Total across every row, the column the slices reconcile against |


<br>

### ELSE 0 or no ELSE

Dropping the `ELSE` makes non-matching rows produce `NULL`, and `SUM` skips `NULL`, so the count comes out the same on any group that has a match. The 2 forms differ in one case the interviewer likes to ask about: a region with no premium orders at all. With `ELSE 0` that region's column is 0. With no `ELSE`, every row in the group produced `NULL`, and a `SUM` over nothing but `NULL` returns `NULL`. A dashboard tile showing a blank where the reader expects 0, or a downstream subtraction that turns into `NULL`, is what the follow-up is about. Write `ELSE 0` inside `SUM` unless you have a reason to want the `NULL`, and say that reason.

```sql
SUM(CASE WHEN tier = 'premium' AND amount >= 100 THEN 1 ELSE 0 END)    AS big_premium_orders,
SUM(CASE WHEN region IN ('North', 'West') THEN amount ELSE 0 END)      AS northern_revenue,
SUM(CASE WHEN order_date >= DATE '2024-03-01' THEN 1 ELSE 0 END)       AS march_orders
```

The condition can use `AND` and `OR` to combine comparisons, and `IN` lists and date ranges work too, because `CASE` evaluates a boolean and nothing about `SUM` cares how that boolean was built. The slice gets narrower; the structure stays one column per slice, and a follow-up such as 'now only premium orders from this quarter' is an `AND` added to a condition rather than a new query.

> 3 things to say while typing it
>
> - 'The CASE runs per row, so each order is a 1 or a 0 before SUM touches it'
> - 'ELSE 0, so a region with no premium orders shows 0 rather than NULL'
> - 'SUM(amount) beside it is the total, so the slices can be checked against the whole'

> **TIP**
>
> When asked what the CASE does, narrate one row: 'this order is standard, so the CASE returns 0, so it adds nothing to premium_orders, but its 50 still lands in total_revenue.' Narrating a single row proves you understand the per-row evaluation.


<br>

---

## Counting Subsets in One Query

`COUNT` has its own version of the same move, and it depends on a rule to say aloud: `COUNT(*)` counts every row in the group, while `COUNT(expression)` counts the rows where the expression is not `NULL`. So `COUNT(CASE WHEN status = 'active' THEN 1 END)` counts the rows where the `CASE` produced a 1, and because there is no `ELSE`, every non-active row produced `NULL` and was skipped. The 1 carries no meaning beyond being not `NULL`; `THEN 'x'` or `THEN customer_id` would count the same rows.

```sql
SELECT
  region,
  COUNT(*) AS total_customers,
  COUNT(
    CASE
      WHEN status = 'active' THEN 1
    END
  ) AS active_count,
  COUNT(
    CASE
      WHEN status = 'inactive' THEN 1
    END
  ) AS inactive_count,
  COUNT(
    CASE
      WHEN status = 'churned' THEN 1
    END
  ) AS churned_count
FROM customers
GROUP BY region
```

The run below keeps only the total and active-count columns and runs them over the 6 customers from the first section, so each `CASE` result and each skipped `NULL` is visible.

https://github.com/user-attachments/assets/833bd7c1-64cf-44c7-8fd4-36152aff611d

North has customers 1 to 3, and only customer 2 has churned: `COUNT(*)` is 3, and the `CASE` produced 1, `NULL`, 1, so `active_count` is 2. In South only customer 5 is active, so the row has 3 in total and 1 active; customer 4 is inactive and customer 6 has churned. The full query from the code block fills in the rest of the row. North has no inactive customers and 1 churned, South has 1 of each, and each of those columns ran over the same 3 rows the total did.

> The ELSE that breaks COUNT
>
> - COUNT(CASE WHEN cond THEN 1 ELSE 0 END) counts every row, because 0 isn't NULL
> - Every conditional column then equals COUNT(\*), and nothing looks wrong until someone compares a slice with the total
> - Rule: SUM gets ELSE 0, COUNT gets no ELSE
> - Say it as you type: 'no ELSE, so non-matching rows are NULL and COUNT skips them'


<br>

### The total and its subsets in one row

The reason to keep `COUNT(*)` beside the conditional counts is that the question nearly always wants a rate, and a rate is a subset over a total. Signups and converters per cohort month is the standard form: `COUNT(*)` is the denominator, the conditional count is the numerator, and the rate is their ratio computed in the same row. Both numbers came from the same grouped rows, so they cannot disagree about which cohort a signup belongs to or which day the data was pulled.

https://github.com/user-attachments/assets/0417f830-9792-4ea8-abd3-7d9084b8f195

The 2024-01 cohort has 4 signups, of which 3 completed onboarding, a rate of 0.75. The 2024-02 cohort converted 1 of its 2 signups, for 0.5. The numerator expression is written twice, once as its own column and once inside the ratio, and that repetition is deliberate: the interviewer wants to see the absolute counts next to the rate, because a rate of 1.0 on 1 signup and a rate of 1.0 on 10,000 signups mean different things to the person reading the dashboard.

The `* 1.0` in the ratio turns the integer numerator into a decimal before the division, because Postgres truncates an integer divided by an integer, as do SQL Server and SQLite, and 3 / 4 comes back as 0; MySQL's `/` already returns a decimal, so there the `* 1.0` is harmless. The denominator is `COUNT(*)` of a group that exists, and a group exists only because at least 1 row fell into it, so this particular division can't hit zero.

| ✓ 2 queries plus application code | ✗ One grouped query |
| --- | --- |
| • One query for signups per cohort, another for converters per cohort<br><br>• The ratio computed in Python after matching the 2 result sets by cohort<br><br>• A cohort present in one result and absent from the other has to be handled by hand<br><br>• The 2 queries can drift apart the next time someone edits one of them | • The rate sits in the same row as the signups and converters it came from<br><br>• Every cohort appears exactly once, with converters at 0 where nobody converted<br><br>• The ratio is computed where its inputs are<br><br>• The consumer can check the rate against the counts beside it |

*SUM(CASE WHEN cond THEN 1 ELSE 0 END) and COUNT(CASE WHEN cond THEN 1 END) return the same count; pick one and use it for every column in the query, because mixing them reads as not knowing they are equivalent.*


<br>

### Reading it back to the interviewer

Once the query is on the screen, read one output row back: 'for January, 4 people signed up, 3 of them finished onboarding, so the rate is 0.75; the 3 and the 4 came from the same group, which is why I put them side by side.' Reading a row back catches your own mistakes, a wrong column name or a swapped condition, before the interviewer does, and it is the moment the question moves from 'can you write it' to 'do you understand what it returns'.


<br>

---

## Columns That Add Up to the Total

A question that asks for active and inactive customers per region, plus the total, carries an unstated requirement: active plus inactive should equal the total. Columns built to split a total need 2 properties. Every row has to land in some column, so the conditions are exhaustive, and no row can land in 2 columns, so the conditions are exclusive. A `CASE` per column gives you neither for free, and the interviewer who asks 'do these add up?' is checking whether you know that.


<br>

### The row that lands nowhere

A customer whose status is `NULL` breaks the first property. The comparison `status = 'active'` evaluates to `NULL` rather than false, `CASE` treats anything other than true as not matching, and with no `ELSE` the row produces `NULL` for every status column. `COUNT(*)` counts the row anyway. The same happens to a value nobody wrote a column for: a `churned` customer in a query with only active and inactive columns is in the total and in no slice. The run below has 1 of each.

https://github.com/user-attachments/assets/5ca8edbd-f929-4690-b127-6c4494028eb2

In North, customer 1 is active, customer 2 has no status at all and customer 3 is inactive. The total is 3, the active count is 1 and the inactive count is 1, so the slices sum to 2 and a row is missing. In South, customer 4 is active and customer 6 inactive, but customer 5 has churned, so the slices again sum to 2 against a total of 3, with a different cause: the churned customer had nowhere to go. A reader of the dashboard would see the gap and ask where the third customer went, and the answer in production is usually a status that was never set or a value added after the query was written.

```sql
SELECT
  region,
  COUNT(*) AS total_customers,
  COUNT(
    CASE
      WHEN status = 'active' THEN 1
    END
  ) AS active_count,
  COUNT(
    CASE
      WHEN status = 'inactive' THEN 1
    END
  ) AS inactive_count,
  COUNT(
    CASE
      WHEN status IS NULL
        OR status NOT IN ('active', 'inactive') THEN 1
    END
  ) AS other_count
FROM customers
GROUP BY region
```

The `other_count` condition needs both halves. `status NOT IN ('active', 'inactive')` is `NULL` when status is `NULL`, so on its own it would skip the very row it exists to catch; the `IS NULL` test is what picks that row up. With the catch-all in place, both regions show a total of 3 and a 1 in each slice column, so the slices add back up to the total.


<br>

### The row that lands twice

Overlapping conditions break the second property. Buckets such as 'under 100', '100 or more' and 'over 500' look like a partition, but a 600-dollar order satisfies both of the last 2 conditions and is counted in each, so the columns sum to more than the total. The same thing happens when one column counts premium orders and another counts North orders. Those columns slice on different attributes, so they're segments rather than a split and should never be expected to add up.

| amount | under_100 | at_least_100 | over_500 |
| --- | --- | --- | --- |
| 50 | 1 | 0 | 0 |
| 120 | 0 | 1 | 0 |
| 600 | 0 | 1 | 1 |
| 90 | 1 | 0 | 0 |
| column sums | 2 | 2 | 1 |

The run has 4 orders, and the 3 columns sum to 5. The fix is to make the ranges disjoint, `amount >= 100 AND amount <= 500` for the middle bucket, or to assign each row one label first and count the labels.


<br>

### One CASE, one label per row

```sql
WITH labeled AS (
  SELECT
    region,
    CASE
      WHEN status = 'active' THEN 'active'
      WHEN status = 'inactive' THEN 'inactive'
      ELSE 'other'
    END AS bucket
  FROM customers
)

SELECT
  region,
  COUNT(*) AS total_customers,
  COUNT(
    CASE
      WHEN bucket = 'active' THEN 1
    END
  ) AS active_count,
  COUNT(
    CASE
      WHEN bucket = 'inactive' THEN 1
    END
  ) AS inactive_count,
  COUNT(
    CASE
      WHEN bucket = 'other' THEN 1
    END
  ) AS other_count
FROM labeled
GROUP BY region
```

A `CASE` with several `WHEN` branches evaluates them in order and stops at the first true one, and the `ELSE` catches whatever remains, including the `NULL` status. That gives every row exactly one label by construction, so the counts over the labels are exhaustive and exclusive without any further checking. The 2-step shape costs a CTE, and it pays for itself the moment a fourth status value appears in the data: the new value falls into `other` and the total still reconciles, rather than vanishing from a dashboard.

> The reconciliation check to say out loud
>
> - 'These 3 columns are meant to split the total, so they should sum to COUNT(\*)'
> - 'A NULL status fails every equality test and lands in no column, so I add an other bucket'
> - 'My ranges are disjoint, so no order is counted twice'
> - 'Premium and North are segments, not a split, so I would not expect them to add up'


<br>

---

## Counting Distinct Users Who Qualify

The question shifts from a customers table to an events table and the wording barely changes: 'how many users made a purchase, per region'. The events table has one row per event, so a user who bought 3 times has 3 purchase rows. `COUNT(CASE WHEN event_type = 'purchase' THEN 1 END)` counts purchases, and a candidate who reports that number as the number of buyers has answered a different question. The grain of the input decides which aggregate the question needs, and saying the grain out loud is the first thing the interviewer listens for.

Counting the users rather than the rows puts DISTINCT inside the aggregate and the user id in the THEN: COUNT(DISTINCT CASE WHEN event_type = 'purchase' THEN user_id END).

The `CASE` returns the `user_id` for a purchase row and `NULL` for every other row. `DISTINCT` collapses the repeated ids into one each, `COUNT` skips the `NULL`, and what remains is the set of users with at least 1 purchase in the group. The run below has 6 events across 2 regions, with user 101 buying twice in North and user 202 buying twice in South, so the 2 counts come apart in both rows.

https://github.com/user-attachments/assets/a16b29d8-8e61-4515-a6b2-92c8b6bee890

North holds events 1 to 4: user 101 purchases twice, user 102 views, user 103 purchases. The purchase count is 3; the `CASE` produced 101 twice, then `NULL`, then 103, and after `DISTINCT` that leaves 2 buyers. South holds events 5 and 6, both purchases by user 202, which makes 2 purchases from a single buyer. On a real table that gap is a repeat customer, 3 purchases from 2 buyers, and a dashboard that showed 3 under 'buyers' would overstate the customer base by half.


<br>

### Which number the question wants

| The question says | The aggregate |
| --- | --- |
| How many purchases, per region | COUNT(CASE WHEN event_type = 'purchase' THEN 1 END) |
| How many customers bought, per region | COUNT(DISTINCT CASE WHEN event_type = 'purchase' THEN user_id END) |
| How much was spent on purchases, per region | SUM(CASE WHEN event_type = 'purchase' THEN amount ELSE 0 END) |
| How many customers did anything, per region | COUNT(DISTINCT user_id) |

The disguise is in the noun. 'Purchases' and 'orders' and 'events' are rows; 'users', 'customers', 'accounts' and 'sessions' are distinct ids. The interviewer often asks for both in one breath, 'purchases and buyers per region', and wants to see the pair as 2 columns from the same group rather than 1 column with the wrong name. A `WHERE event_type = 'purchase'` with `COUNT(DISTINCT user_id)` gets the buyers right but loses the viewers, which is the same shape problem as the opening question: the condition belongs inside each aggregate so that buyers and viewers can sit in one row beside the overall count.

```sql
SELECT
  region,
  COUNT(DISTINCT user_id) AS all_users,
  COUNT(DISTINCT
    CASE
      WHEN event_type = 'purchase' THEN user_id
    END
  ) AS buyers,
  COUNT(DISTINCT
    CASE
      WHEN event_type = 'view' THEN user_id
    END
  ) AS viewers
FROM events
GROUP BY region
```

Each `DISTINCT` is computed inside its own aggregate, independently of the others. A user who viewed and then bought is in both `buyers` and `viewers`, so those 2 columns can sum to more than `all_users`. The previous section's reconciliation check does not apply here, and saying so unprompted, 'these are overlapping sets of users, so they won't add up to all_users', is the sentence that separates someone who has built this from someone who has only read the syntax. If the question needs non-overlapping groups of users, label each user once first, by their highest action, and count the labels.

> **TIP**
>
> Say the grain before the aggregate: 'one row per event, and the question counts people, so I need DISTINCT user_id inside the condition.' Stating it first means the interviewer never has to ask whether 3 purchases is 3 customers.


<br>

### Habits that survive the follow-up

| ✓ Do | ✗ Don't |
| --- | --- |
| • Say the grain of the input and the grain of the output before writing a line<br><br>• Put COUNT(\*) or SUM(amount) beside the conditional columns so the slices reconcile<br><br>• Write ELSE 0 inside SUM and no ELSE inside COUNT, and say why as you type it<br><br>• Add an other bucket, or one labelling CASE, when columns are meant to partition the total<br><br>• Reach for COUNT(DISTINCT CASE ...) when the question counts people and the table holds events | • Don't open with a WHERE on one category; it answers a third of the question<br><br>• Don't write ELSE 0 inside COUNT; every column becomes COUNT(\*)<br><br>• Don't assume category columns sum to the total; a NULL or an unlisted value lands in none<br><br>• Don't report a row count as a user count when a user can appear in many rows<br><br>• Don't expect distinct-user columns to add up; one user can qualify for several |


<br>

---

## Putting It All Together

The retailer's head of operations wants a single Monday-morning tile per region: orders placed last week, premium orders, premium revenue, total revenue, the number of customers who bought, and the share of orders that shipped late, all from the orders table (one row per order, with a customer_id, a tier, an amount and a shipped_on_time flag that is NULL for orders still in the warehouse).

- The tile is wider than the orders table, so the first sentence is 'group by region, with a CASE inside each aggregate', and the whole tile is one query
- Premium orders and premium revenue are the same condition with THEN 1 and THEN amount, written with ELSE 0 so a region with no premium orders shows 0
- Late shipments are a COUNT with no ELSE beside COUNT(\*), and the late rate is their ratio in the same row
- On-time and late look like a split of the total, but the NULL flag on unshipped orders lands in neither slice, so the tile needs an unshipped column for the numbers to reconcile
- Customers who bought is COUNT(DISTINCT CASE WHEN ... THEN customer_id END), because a repeat buyer has several order rows and the question counts people


<br>

---

## Key Takeaways

- An output with one row per group and a column per category is conditional aggregation: one GROUP BY, a CASE inside each aggregate
- SUM(CASE WHEN cond THEN 1 ELSE 0 END) counts matching rows; swap the 1 for amount and the same column sums them
- COUNT(CASE WHEN cond THEN 1 END) takes no ELSE, because the NULL from non-matching rows is what COUNT skips
- Keep COUNT(\*) or SUM(amount) beside the slices so a rate and its reconciliation live in the same row
- Columns meant to split a total need an other bucket and disjoint conditions; distinct-user columns overlap and will not add up
