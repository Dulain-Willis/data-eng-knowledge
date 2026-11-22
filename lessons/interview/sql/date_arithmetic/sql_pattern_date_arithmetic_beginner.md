# Date Arithmetic: Beginner

You are 20 minutes into a SQL screen at an online grocery company. The interviewer pastes 1 table, `orders(order_id, customer_id, ordered_at, amount)`, and reads from her notes.
"Finance wants January revenue next to the January before it. Growth wants to know how many new customers came back for a second order within 30 days. Use whatever SQL you like."
Nobody has said that `ordered_at` is a timestamp, and that detail decides the first answer. A filter that stops at '2024-01-31' keeps the stroke of midnight on the 31st and drops every order after it. The usual first move is a GROUP BY on month plus a BETWEEN, which returns believable totals that are short by most of a day.
What she is testing is whether you hear the date math hiding in plain business words, and draw every boundary so each row lands in exactly 1 period.


<br>

### What you will be able to do

Translate phrases like "monthly", "within 30 days", "on Mondays" and "in January" into the date operation each one needs

Group events into calendar buckets with DATE_TRUNC and anchor rolling windows on CURRENT_DATE

Shift dates with interval arithmetic and measure gaps with DATE_DIFF, including a separate window for every row

Tell when grouping by a repeating date part pools periods that a trend needs kept apart

Write half-open ranges that keep every timestamp on the last day of a period


<br>

---

## Dates Hide in Business Questions

Business questions arrive in business words. A product manager says "monthly", "since signup", "within a week", "last quarter" or "on weekends", and the translation into date math is the candidate's job. Each of those words resolves to 1 of 5 operations: bucket a timestamp onto its calendar period, shift a date by a fixed span, measure the gap between 2 dates, pull out a repeating part such as the weekday, or bound a range with a start and an end. Naming the operation behind each word before writing SQL is most of what this question is graded on. Once the operation is chosen, the SQL for it is 1 or 2 lines, and the remaining points go to where you put the boundaries.


<br>

### Translating the request

| The request says | The date math underneath | Tool |
| --- | --- | --- |
| "Revenue by month for the past year" | Put each sale on its month, keep 12 calendar months | DATE_TRUNC plus a range |
| "Trial ends 14 days after signup" | Move signup_date forward 14 days | + INTERVAL or DATE_ADD |
| "Came back within 7 days" | Count the days from first visit to the next visit | DATE_DIFF |
| "Are Mondays our slowest day?" | Pull the weekday, pool every Monday together | EXTRACT |
| "January revenue" | Every row from Jan 1 00:00 up to, not including, Feb 1 00:00 | Half-open range |
| "Active in the last 30 days" | Shift back from today, decide whether today counts | CURRENT_DATE - INTERVAL |

Real requests stack several of these. "Weekly signups over the last quarter, split by whether the account ordered within 14 days" needs a bucket (signups per week), a range (the quarter), and a measured gap (signup to first order) evaluated per account. Breaking the request apart out loud, phrase by phrase, gives the interviewer your plan before your query. It also catches the piece a candidate who starts typing at the first noun tends to drop, which is usually the gap, because it lives on a different table from the thing being counted.


<br>

### What the wording leaves open

> Settle these before the first line of SQL
>
> - Calendar or rolling: on 2024-03-15, "last month" is February 1 to 29, or the 30 days ending today. They return different rows.
> - Does today count: a job running at 09:00 sees 9 hours of today, so any window that includes today carries a partial day.
> - DATE or TIMESTAMP: the column type decides whether '2024-01-31' as an upper bound means the whole day or 1 instant at midnight.
> - Which day is day 0: "within 7 days of signup" can count the signup day as day 0 or day 1, and the threshold moves by a day.

Every relative window gets written against CURRENT_DATE (or CURRENT_TIMESTAMP when the comparison needs a time of day), never against a typed-in date. A literal such as '2024-02-14' is correct on the afternoon you type it and wrong the next morning, and a dashboard query keeps running every day after the one it was written on. In this lesson today is 2024-03-15, so CURRENT_DATE - INTERVAL '30 days' evaluates to 2024-02-14, and tomorrow it evaluates to 2024-02-15 without anyone editing it. Interviewers notice a hardcoded date because it is the line that turns a correct answer into a report that silently freezes.


<br>

### How the answer gets scored

| ✓ Costs points | ✗ Earns points |
| --- | --- |
| • Starts typing at the first noun, before settling calendar versus rolling<br><br>• Builds the month with LEFT(CAST(txn_date AS VARCHAR), 7), a string where a date belonged<br><br>• Hardcodes '2024-02-01' into a query meant to run daily<br><br>• Puts BETWEEN on a timestamp column and never checks the last day | • Restates each phrase as an operation: "monthly" is a bucket, "within 30 days" is a gap<br><br>• Groups with DATE_TRUNC, so the bucket stays a date and date arithmetic still works on it<br><br>• Anchors every relative window on CURRENT_DATE<br><br>• Says which end of each range is inclusive before being asked |

The strongest openings fit in a single breath. For "monthly revenue by region for the past year" it sounds like: "Monthly means I bucket txn_date to the first of its month with DATE_TRUNC. Past year I'll read as the 12 complete calendar months before this one, as a range that includes its start and excludes its end. I'm assuming txn_date is a DATE; tell me if it's a timestamp." That takes around 15 seconds and settles the grain of the output and the window. If the interviewer meant a rolling 365 days, you find out before writing the query instead of after, and the same goes for the column type.

> **TIP**
>
> When a clarifying question gets the reply "your call", pick one and write it as a comment on the line it affects, saying it aloud as you type. A stated assumption reads as judgement. An unstated one reads as a bug the moment your number differs from the one on the interviewer's sheet.


<br>

---

## DATE_TRUNC for Calendar Buckets

`DATE_TRUNC` takes a unit and a date or timestamp and returns the start of the period that value falls in. `DATE_TRUNC('month', DATE '2024-03-15')` returns 2024-03-01, and so does every other date from March 1 through March 31. That many-to-1 mapping is the whole job: 31 different dates become 1 value, so a GROUP BY on that value produces 1 row per month. The unit sets the bucket size, and the table below shows what each unit does to the same timestamp, this lesson's 2024-03-15 14:30:45.

| Unit | DATE_TRUNC(unit, TIMESTAMP '2024-03-15 14:30:45') |
| --- | --- |
| 'minute' | 2024-03-15 14:30:00 |
| 'hour' | 2024-03-15 14:00:00 |
| 'day' | 2024-03-15 00:00:00 |
| 'week' | 2024-03-11 00:00:00 |
| 'month' | 2024-03-01 00:00:00 |
| 'quarter' | 2024-01-01 00:00:00 |
| 'year' | 2024-01-01 00:00:00 |

*The week row assumes weeks start on Monday, as they do in Postgres and DuckDB, so Friday 2024-03-15 lands in the week of Monday 2024-03-11. If the business counts weeks from Sunday, say so out loud, because every weekly bucket moves by a day.*


<br>

### The monthly rollup

The request is "revenue per region per month for the past year", over a `transactions` table with 1 row per sale and a DATE column `txn_date`. Here is the query a strong answer writes, with DATE_TRUNC doing 2 different jobs.

```sql
-- One row per (region, month_start), from March 2023 to today
SELECT
  region,
  DATE_TRUNC('month', txn_date) AS month_start,
  SUM(amount) AS monthly_revenue
FROM transactions
WHERE txn_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '12 months'
GROUP BY region, DATE_TRUNC('month', txn_date)
ORDER BY region, month_start
```

In the SELECT and the GROUP BY, DATE_TRUNC is the bucket: it turns each sale's date into its month. In the WHERE clause it is the anchor: `DATE_TRUNC('month', CURRENT_DATE)` is 2024-03-01, and subtracting 12 months gives 2023-03-01, so the window opens on the first day of a month. The animation runs the bucketing part over 6 sales from 2 regions, leaving out the WHERE so every row stays in play.

https://github.com/user-attachments/assets/9113a6ca-377d-48e6-b146-43f932821751

Watch the 2 North sales from January. Transaction 1 on 2024-01-05 and transaction 2 on 2024-01-28 both truncate to 2024-01-01, so they land in the same group and sum to 150. North's single February sale gives 75. South's January is 1 row of 200, and its 2 February sales, 40 on the 3rd and 60 on the 21st, fold into 100. The 6 rows that go in come out as 4, 1 per region per month. When the interviewer asks for the grain of the output, the answer is the GROUP BY list read aloud: a row for each region and month_start.


<br>

### Group by the truncated value

A frequent slip is truncating in the SELECT but grouping by the raw column: GROUP BY region, txn_date. The query still runs, because a function of a grouped column is allowed in the SELECT, and it returns 1 row per region per distinct day, each labelled with its month. March can come back as 31 rows that all read 2024-03-01, and a chart drawn from them stacks 31 bars on a single tick. The other slip is building the bucket from text, as in TO_CHAR(txn_date, 'YYYY-MM'). That groups correctly, and 'YYYY-MM' strings happen to sort in date order, but the result is a string, so you can no longer subtract a month from it or compare it with a date. Name formats are worse: TO_CHAR(txn_date, 'Mon YYYY') sorts alphabetically, with 'Apr 2024' ahead of 'Mar 2024'. Keep the bucket a date and format it at the very end, if at all.


<br>

### Truncate first, then shift

The anchor matters because of what the first bucket contains. Written as `txn_date >= CURRENT_DATE - INTERVAL '12 months'`, the window opens on 2023-03-15, so the March 2023 bucket holds 17 days of sales and plots as a dip that never happened. Truncating first opens the window on 2023-03-01, and every past bucket is a complete month. The last bucket still holds only March 2024 to date, 15 days on 2024-03-15. If the chart should show complete months only, add `AND txn_date < DATE_TRUNC('month', CURRENT_DATE)`, which closes the range at the start of the current month and leaves exactly 12 buckets, March 2023 through February 2024.

> Follow-ups this query draws
>
> - "Why truncate inside the WHERE?" So the oldest bucket is a whole month and its bar compares fairly with the rest.
> - "Should this month be on the chart?" Ask. A finance report usually wants complete months; an operations screen usually wants month to date.
> - "Why repeat the expression in GROUP BY?" Some engines accept GROUP BY month_start; the repeated expression works in all of them.
> - "What if txn_date were a timestamp?" DATE_TRUNC returns midnight on the 1st, and the monthly buckets come out the same.

> **TIP**
>
> Units smaller than a day only make sense on timestamps. Truncating a DATE to 'hour' returns midnight for every row, so an hourly chart built from a DATE column shows 1 bar per day at 00:00. If the request says "by hour", check that the column carries a time.


<br>

---

## DATE_ADD and DATE_DIFF Basics

Most relative-time questions reduce to 2 moves. A shift takes a date and a span and returns another date: the trial end, the start of a window, the same day last year. A measure takes 2 dates and returns a number: days to first order, age of an open ticket, tenure. Requests ask "when" for the first and "how long" for the second, and naming which one you are answering keeps the result type straight, since a shift returns a date you can filter on and a measure returns an integer you can compare with a threshold.

Some engines spell the shift with the operator signup_date + INTERVAL '14 days' and others with a function such as DATE_ADD; this lesson writes the operator form. A negative span moves backwards, so on 2024-03-15 CURRENT_DATE - INTERVAL '30 days' is 2024-02-14. A day span moves by exact days. A month or year span moves along the calendar: 2024-03-01 minus 1 month is 2024-02-01, whatever the length of February. Pick the unit the request names. "30 days" is a day span and "last month" is a month span, and on 2024-03-15 they start the window on different dates.

```sql
-- Filters on events.event_date; today is 2024-03-15

-- Last 7 days including today: 2024-03-09 through 2024-03-15
WHERE event_date >= CURRENT_DATE - INTERVAL '6 days'

-- Last 7 complete days, today excluded: 2024-03-08 through 2024-03-14
WHERE event_date >= CURRENT_DATE - INTERVAL '7 days'
  AND event_date <  CURRENT_DATE

-- Last full calendar month: February 2024
WHERE event_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month'
  AND event_date <  DATE_TRUNC('month', CURRENT_DATE)

-- The same month a year ago: March 2023
WHERE event_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 year'
  AND event_date <  DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '11 months'
```

The first 2 patterns differ by 1 in the interval and by a whole day in the result. "Last 7 days" on a dashboard refreshed every morning usually means 7 complete days ending yesterday, because today is partial. On a live operations screen it usually means today plus the 6 days before. Both readings are common, and the mistake is choosing between them without saying so. "I'm counting 7 full days and excluding today" turns the off-by-one into a stated decision the interviewer can agree with or redirect.


<br>

### Measuring the gap

DATE_DIFF('day', start_date, end_date) returns end minus start as a whole number of days, and in Postgres, end_date - start_date on 2 DATE values gives the same integer. Signup on 2024-01-10 and first order on 2024-01-17 is 7. An order on the signup day is 0. A negative result means the arguments are reversed or the data has an order before its signup, and either is worth a sentence to the interviewer. The query below measures days from signup to first order and flags customers who ordered within 7 days.

```sql
WITH first_orders AS (
  SELECT
    customer_id,
    MIN(CAST(ordered_at AS DATE)) AS first_order_date
  FROM orders
  GROUP BY customer_id
)

SELECT
  c.customer_id,
  c.signup_date,
  f.first_order_date,
  DATE_DIFF('day', c.signup_date, f.first_order_date) AS days_to_first_order,
  CASE
    WHEN DATE_DIFF('day', c.signup_date, f.first_order_date) <= 7 THEN 1
    ELSE 0
  END AS activated_in_7_days
FROM customers AS c
LEFT JOIN first_orders AS f
  ON f.customer_id = c.customer_id
```

| customer_id | signup_date | first_order_date | days_to_first_order | activated_in_7_days |
| --- | --- | --- | --- | --- |
| C1 | 2024-01-01 | 2024-01-01 | 0 | 1 |
| C2 | 2024-01-10 | 2024-01-17 | 7 | 1 |
| C3 | 2024-01-20 | 2024-02-05 | 16 | 0 |
| C4 | 2024-02-02 | NULL | NULL | 0 |

Read the result row by row. C1 ordered on signup day, so the gap is 0. C2's gap of exactly 7 passes because the test is `<= 7`; with `< 7` it would fail, and that single character is the "which day is day 0" question in code form. C4 never ordered: the LEFT JOIN keeps the customer, DATE_DIFF of a NULL date is NULL, the comparison is unknown, and the CASE falls through to 0. An inner join would have dropped C4 entirely and lifted the activation rate from 2 of 4 to 2 of 3.

Measure thresholds in days. DATE_DIFF('month', a, b) in Snowflake and BigQuery counts the month boundaries crossed between the 2 dates, and DuckDB does the same, so 2024-01-31 to 2024-02-01 is 1 month and 2024-02-01 to 2024-02-29 is 0. A filter like DATE_DIFF('month', signup_date, CURRENT_DATE) >= 1 therefore calls a customer who joined on 2024-02-29 a month old on 2024-03-01. "Customers older than 30 days" is DATE_DIFF('day', signup_date, CURRENT_DATE) > 30, which counts what it says.


<br>

### A window for every row

The shift gets more useful when its starting date comes from the row. "Day-90 retention" asks, for each customer, whether they were active roughly 90 days after their own signup. There is no shared window: C1's sits at the end of March, C3's in mid-April. Adding the interval to `signup_date` inside the query computes a separate window per customer, and EXISTS checks for an event inside it.

```sql
-- Day-90 retention for customers who signed up in January 2024
SELECT
  c.customer_id,
  c.signup_date + INTERVAL '90 days' AS check_date,
  CASE
    WHEN EXISTS (
      SELECT
        1
      FROM events AS e
      WHERE e.customer_id = c.customer_id
        AND e.event_date >= c.signup_date + INTERVAL '89 days'
        AND e.event_date < c.signup_date + INTERVAL '91 days'
    ) THEN 'retained'
    ELSE 'churned'
  END AS day_90_status
FROM customers AS c
WHERE c.signup_date >= '2024-01-01'
  AND c.signup_date < '2024-02-01'
```

https://github.com/user-attachments/assets/c934d768-2388-42f3-b745-2f20c04801af

C1 signed up on 2024-01-01, so day 90 is 2024-03-31 and the window runs from 2024-03-30 up to, not including, 2024-04-01. Its event on 2024-03-31 falls inside: retained. C2 has 2 events. The one on 2024-01-12 is day 2 and sits far outside the window, while the one on 2024-04-09 is exactly day 90: retained. C3's window covers 2024-04-18 and 2024-04-19, and its only event, 2024-04-25, is day 96: churned. EXISTS answers yes or no per customer, so C2's 2 events produce 1 output row. Joining every event instead would have produced 2 rows for C2 and double-counted it in any retention rate built on top.

> **TIP**
>
> Say the tolerance out loud. This query counts activity on day 89 or day 90; some teams mean exactly day 90, others any day from 90 onward. The interval bounds encode the definition, so once the definition is stated, changing it is a matter of editing 1 number.


<br>

---

## Date Parts vs Date Buckets

`EXTRACT(part FROM value)` pulls a single field out of a date or timestamp and returns it as a number. For 2024-03-15 14:30:45 the year is 2024, the month 3 and the day of the month 15. The hour is 14, and the day of week is 5, because Postgres and DuckDB number the days of the week from Sunday as 0 and this date is a Friday. What separates a part from a bucket is repetition. Month 3 recurs every year, and EXTRACT gives every March the same value. DATE_TRUNC gives each March its own date on the timeline, 2023-03-01 or 2024-03-01. Group by a part and every occurrence of it pools into 1 group; group by a bucket and each period keeps a row of its own.

| Unit | EXTRACT returns | DATE_TRUNC returns |
| --- | --- | --- |
| year | 2024 | 2024-01-01 00:00:00 |
| month | 3 | 2024-03-01 00:00:00 |
| day | 15 | 2024-03-15 00:00:00 |
| hour | 14 | 2024-03-15 14:00:00 |
| day of week (DOW) | 5 | no equivalent: a weekday has no single place on the timeline |


<br>

### 2 Januaries in 1 row

The trap appears when a trend spans more than 12 months. North's sales now reach back to January 2023, and the request is "North's monthly revenue since January 2023". A candidate who reaches for the month number writes the query in the animation below. The 3 North sales of 2024 from the monthly rollup are still here, joined by 2 sales from early 2023.

https://github.com/user-attachments/assets/69da5308-48a1-44e4-8255-67b0a7938645

Transaction 7 on 2023-01-12 extracts to month 1, and so do transactions 1 and 2 from January 2024. The 3 sales fold into a group worth 450. February does the same: 150 from 2023 and 75 from 2024 become 225. The query returns 2 rows where the timeline holds 4 months, and the row reading 450 for January hides the fact the business cares about, that January revenue halved from 300 to 150. Grouping the same rows by `DATE_TRUNC('month', txn_date)` keeps the years apart:

| month_start | revenue |
| --- | --- |
| 2023-01-01 | 300 |
| 2023-02-01 | 150 |
| 2024-01-01 | 150 |
| 2024-02-01 | 75 |

The fix is to group by DATE_TRUNC('month', txn_date), or by both EXTRACT(YEAR FROM txn_date) and EXTRACT(MONTH FROM txn_date). The 2-column version returns the right rows but hands the consumer 2 integers to recombine before they can sort or plot, and filtering on them takes 2 conditions. The truncated date carries both parts in a single sortable value. The same pooling happens with day of month: grouping by EXTRACT(DAY FROM txn_date) puts the 15th of every month in 1 row, which answers a payday question and nothing else.


<br>

### When pooling is the point

Parts are the correct tool when the question is about a cycle. "Are Mondays our slowest day?", "What hour do support tickets peak?" and "Which month of the year is typically busiest?" all want every Monday, every 14:00 or every March stacked together, because the cycle is the subject. The query groups by the part, and the care goes into making the comparison fair.

```sql
-- Average daily revenue by day of week, last 84 complete days (12 of each weekday)
WITH daily AS (
  SELECT
    txn_date,
    SUM(amount) AS day_revenue
  FROM transactions
  WHERE txn_date >= CURRENT_DATE - INTERVAL '84 days'
    AND txn_date < CURRENT_DATE
  GROUP BY txn_date
)

SELECT
  EXTRACT(DOW FROM txn_date) AS day_of_week,
  COUNT(*) AS days_counted,
  AVG(day_revenue) AS avg_daily_revenue
FROM daily
GROUP BY EXTRACT(DOW FROM txn_date)
ORDER BY day_of_week
```

A window of 84 days is 12 weeks exactly, so each weekday appears 12 times in the window and the averages compare like with like. A 30-day window would give 2 weekdays 5 appearances and the other 5 weekdays only 4, and a SUM by weekday would crown whichever days got the extra turn. Averaging the daily totals removes that bias. The `days_counted` column is the check: it should read 12 on every row. A row reading 11 means a day with no sales at all, which is worth flagging to the interviewer as a gap in the data.

| ✓ Group by a part (EXTRACT) | ✗ Group by a bucket (DATE_TRUNC) |
| --- | --- |
| • Answers questions about a cycle: weekday, hour of day, month of year<br><br>• Pools every occurrence across weeks and years into 1 group<br><br>• Returns 7 rows by weekday at most, and no more than 24 by hour or 12 by month, however long the data runs<br><br>• Misleads on any trend over time | • Answers questions about a trend: this month against last<br><br>• Keeps each period separate on the timeline<br><br>• Adds a row for every new period as the data grows<br><br>• Cannot say on its own which weekday is busiest |

> **TIP**
>
> The request's own words usually pick the tool. "Over time", "trend", "month over month" and "since" point to a bucket. "Typically", "which day", "seasonal" and "by hour of day" point to a part. "Is December always our biggest month" needs both: a bucket for each December's total, then a comparison across the years.


<br>

---

## Half-Open Intervals vs BETWEEN

`x BETWEEN a AND b` means `x >= a AND x <= b`, both ends included. On a DATE column that matches the request: `txn_date BETWEEN '2024-01-01' AND '2024-01-31'` holds every January day. On a TIMESTAMP column the same literal '2024-01-31' becomes the instant 2024-01-31 00:00:00, so the range ends at the first moment of January 31 and everything ordered later that day falls outside. Nothing errors and the total looks reasonable, which is why this bug survives code review.

- **23h 59m 59.999999s** — of Jan 31 that BETWEEN skips

The animation tests 6 orders against both filters at once, a CASE for each form, so every row shows its 2 verdicts side by side. The orders sit on the edges of January, where the forms disagree.

https://github.com/user-attachments/assets/46f5db46-1c63-41cc-901e-31244d47b87f

Order 101 at 2023-12-31 23:59:00 is out under both forms, and order 102 at 2024-01-01 00:00:00 is in under both, since each includes its start. Order 103 in mid-January agrees too. The split is on January 31: order 104 at 09:15 and order 105 at 18:45 are in under the half-open range and out under BETWEEN. Order 106 at 2024-02-01 00:00:00 is out under both, because the half-open range excludes exactly the instant February begins. Summed, the BETWEEN version reports January revenue of 165 and the half-open version 425. The gap is the 260 ordered on the last day of the month, the kind of last-day spike a month-end promotion produces.


<br>

### Why the patches fall short

```sql
-- Patch 1: end at the last second of the month
WHERE ordered_at BETWEEN '2024-01-01 00:00:00' AND '2024-01-31 23:59:59'
-- misses an order at 2024-01-31 23:59:59.400

-- Patch 2: cast the column to a date first
WHERE CAST(ordered_at AS DATE) BETWEEN '2024-01-01' AND '2024-01-31'
-- correct rows, but the column is wrapped in a cast

-- The form that needs no patch
WHERE ordered_at >= '2024-01-01'
  AND ordered_at <  '2024-02-01'
```

The first patch fails as soon as the column stores fractions of a second. Timestamp columns in Postgres do, to the microsecond or finer, and so do the ones in Snowflake and BigQuery. An order at 23:59:59.4 is later than 23:59:59 and outside the range. The second patch returns the right rows, but the filter now compares a computed value instead of the stored one, and it only works for whole days. The half-open form needs neither fix: it names the start of the period and the start of the next, and every instant of January, at any precision, sits between them.

Half-open ranges also tile. `[2024-01-01, 2024-02-01)` and `[2024-02-01, 2024-03-01)` share a boundary, and every instant falls in exactly 1 of them. Closed ranges cannot do that on timestamps: `BETWEEN '2024-01-01' AND '2024-02-01'` counts the midnight that opens February in both January and February, and stopping at 23:59:59 leaves a sliver unclaimed. The tiling is the same rule DATE_TRUNC follows, which is why the 2 tools fit together: a row belongs to month bucket M exactly when M is at or before the row's time and M plus 1 month is after it.

So the upper bound of a calendar range is always the start of the next period, and it comes from the same truncate-then-shift move as the rollup's anchor. The last-full-month filter from the list of windows already has this shape: it opens at DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' and closes, exclusive, at the truncated start of this month. February 2024 has 29 days, and that number never appears in the query.


<br>

### Saying it while you write it

Write the filter and narrate it in the same sentence: "Greater than or equal to January 1, strictly less than February 1, so it holds whether ordered_at is a date or a timestamp at any precision." The common follow-up is "isn't BETWEEN fine here?" The answer that scores is specific: on a DATE column, yes, a BETWEEN that runs to January 31 covers January; on a timestamp it ends at midnight on the 31st; the half-open form is right on both, so it stays right if the column type changes later. Then offer the check that proves it: count the rows on January 31 after 00:00:00, and that count is exactly what BETWEEN would have lost.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Restate each time phrase as one of the 5 operations before touching SQL<br><br>• Group trends on DATE_TRUNC and keep the bucket a date until the final display<br><br>• Anchor relative windows on CURRENT_DATE, truncated first for calendar-month windows<br><br>• Close every range with a strict less-than on the start of the next period<br><br>• Say out loud which day is day 0, and whether today and the last day of the range are included | • Ending a BETWEEN on a timestamp column at a bare date like '2024-01-31'<br><br>• Grouping a multi-year trend by EXTRACT(MONTH ...) alone<br><br>• Hardcoding dates into a query that runs on a schedule<br><br>• Testing a 30-day threshold with DATE_DIFF in month units<br><br>• Using an inner join when customers with no orders belong in the rate |


<br>

---

## Putting It All Together

On the first Monday of February 2024, the online grocery company from the opening asks for a finance report: January 2024 revenue by region against January 2023, the share of January's new customers who placed a second order within 30 days of their first, and a note on whether weekends outsell weekdays. The orders table stores ordered_at as a timestamp, and the report will run every month from now on.

- "January" and "January 2023" are 2 half-open ranges, each from the 1st up to the 1st of February, built by truncating CURRENT_DATE to the month and shifting back 1 month and 13 months.
- Revenue by region per month groups on DATE_TRUNC, so the 2 Januaries stay separate rows instead of pooling under month number 1.
- The second-order question is a measure per customer: DATE_DIFF in days from first order to second, with the threshold <= 30 and day 0 stated out loud.
- The weekend question is the one place pooling is wanted: EXTRACT(DOW) over a window of whole weeks, averaged per day so every weekday counts equally.
- Because ordered_at is a timestamp, every range closes with a strict less-than, so the evening orders of January 31 count toward January.


<br>

---

## Key Takeaways

- Business words hide 5 date operations. 2 of them, bucket and shift, return a date, and 2 more, measure and part, return a number. The fifth is the range that filters rows. Name the one behind each phrase before writing SQL.
- DATE_TRUNC turns many dates into 1 period start; group on it, and truncate before shifting so the oldest bucket is a full month.
- Shift with + INTERVAL to get a date, measure with DATE_DIFF in days to get a number, and say whether today and day 0 count.
- A date part repeats and pools every year together; use it for cycles like weekday, and a bucket for anything that trends.
- Write ranges as >= start AND < start of the next period; BETWEEN on a timestamp stops at midnight on the last day.
