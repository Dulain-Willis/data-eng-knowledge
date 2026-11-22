# Period-over-Period: Intermediate

A candidate sits across from a data engineer at Shopify, the commerce platform whose merchants post their biggest sales of the year across the Black Friday Cyber Monday weekend each November. The interviewer shares a table of orders and asks for each merchant category's revenue growth by month, then adds: 'November will look like a boom and January like a collapse. How do you report growth so the calendar doesn't pose as a trend, and what happens to a category with a month of no sales?' The candidate aggregates into months, pairs each month with the right earlier one, and then has to decide which earlier one, what a gap in the rows does to the division, and whether a change in conversion rate is a percent or a percentage point. This lesson walks that reasoning in the order the question demands it.


<br>

### What you will be able to do

Write a self-join on truncated dates that pairs each group's period with exactly 1 earlier period, and explain each condition in the ON clause

Replace the self-join with LAG, name what PARTITION BY and ORDER BY stand in for, and list the assumptions LAG makes

Choose year-over-year for a metric with a yearly cycle, and read a month-over-month and a year-over-year column against each other

Predict what a missing period does to LAG and to the self-join, and add a date_diff guard or a calendar fill that exposes it

Report a change in a rate in percentage points and a change in an amount in percent, with the unit carried in the column name


<br>

---

## Self-Join on Truncated Dates

An interviewer hands you an orders table, 1 row per order with its region, date and amount, and asks for each region's revenue change from the previous month. Orders land on scattered days, so the first step collapses them into 1 row per region per month, and only then does the query look for the earlier period. The self-join is the longer way to do that second step, and it comes first here because every assumption LAG makes later is written out in its ON clause.


<br>

### Truncate first, then aggregate

```sql
SELECT
  region,
  DATE_TRUNC('month', order_date) AS month_start,
  SUM(amount) AS revenue
FROM orders
GROUP BY region, DATE_TRUNC('month', order_date)
```

| region | month_start | revenue |
| --- | --- | --- |
| North | 2024-01-01 | 1500 |
| North | 2024-02-01 | 1800 |
| North | 2024-03-01 | 1350 |
| South | 2024-01-01 | 2000 |
| South | 2024-02-01 | 1600 |
| South | 2024-03-01 | 1200 |

date_trunc('month', DATE '2024-02-14') returns 2024-02-01, and so does every other February date, which is what lets GROUP BY fold a whole month of orders together. After this step each pair of region and month_start appears exactly once, and that uniqueness is the property the self-join depends on: when February asks for January, there is exactly 1 January row in its region to find. Joining the raw orders to themselves would instead pair February 14 with January 14 and miss every order placed on another day, and a region with 40 orders in a month would produce 40 candidate rows where 1 was wanted.


<br>

### The join condition names the earlier period

```sql
WITH monthly AS (
  SELECT
    region,
    DATE_TRUNC('month', order_date) AS month_start,
    SUM(amount) AS revenue
  FROM orders
  GROUP BY region, DATE_TRUNC('month', order_date)
)

SELECT
  cur.region,
  cur.month_start,
  cur.revenue,
  prev.revenue AS prior_revenue,
  cur.revenue - prev.revenue AS change,
  ROUND(
    (
      cur.revenue - prev.revenue
    ) * 100.0 / prev.revenue,
    1
  ) AS pct_change
FROM monthly AS cur
LEFT JOIN monthly AS prev
  ON prev.region = cur.region
    AND prev.month_start = cur.month_start - INTERVAL '1' MONTH
ORDER BY cur.region, cur.month_start
```

The CTE is listed twice under 2 aliases. cur holds the period being reported and prev holds the candidate earlier periods, and the ON clause does the pairing: prev must be in the same region, and its month_start must equal cur's month_start minus 1 month. Because both columns were truncated, 2024-02-01 minus INTERVAL '1' MONTH lands on 2024-01-01 and the equality finds the row. Apply the same arithmetic to an untruncated date and 2024-03-31 minus 1 month is 2024-02-29, which equals no row's month_start, so the arithmetic belongs on the truncated column.

| region | month_start | revenue | prior_revenue | change | pct_change |
| --- | --- | --- | --- | --- | --- |
| North | 2024-01-01 | 1500 | NULL | NULL | NULL |
| North | 2024-02-01 | 1800 | 1500 | 300 | 20.0 |
| North | 2024-03-01 | 1350 | 1800 | -450 | -25.0 |
| South | 2024-01-01 | 2000 | NULL | NULL | NULL |
| South | 2024-02-01 | 1600 | 2000 | -400 | -20.0 |
| South | 2024-03-01 | 1200 | 1600 | -400 | -25.0 |

Read North's February row: cur.revenue is 1800, prior_revenue is North's January 1500, the change is 300 and pct_change is 300 over 1500, which rounds to 20.0. North's March row carries prior_revenue 1800 and a change of minus 450, so minus 25.0. South's March also falls by 400, but from 1600 rather than from 2000, so its pct_change is minus 25.0 where February's was minus 20.0. The same absolute drop reads differently against a different denominator, and the self-join puts the 2 denominators on adjacent rows where the difference can be seen.


<br>

### Both conditions, or the pairs multiply

Drop the region condition and the query still runs, but North's February now matches every January in the table: North's and South's. The output gains a second North February row whose prior_revenue is South's 2000, with a pct_change of minus 10.0 that describes no real region, and a SUM over the result would count North's February revenue twice.

| region | month_start | revenue | prior_revenue | pct_change |
| --- | --- | --- | --- | --- |
| North | 2024-02-01 | 1800 | 1500 | 20.0 |
| North | 2024-02-01 | 1800 | 2000 | -10.0 |
| South | 2024-02-01 | 1600 | 1500 | 6.7 |
| South | 2024-02-01 | 1600 | 2000 | -20.0 |

The symptom is a row count that grows. Under a LEFT JOIN with both conditions, 6 monthly rows produce 6 output rows, and they produce 10 when the region condition is missing: the 2 January rows still match nothing, and the 4 later rows each match 2 Januaries or 2 Februaries. Comparing output rows to input rows takes 1 query and catches the problem before anyone reads a percentage.

The join is a `LEFT JOIN` so that January, which has no earlier month in the table, stays in the output with a NULL prior_revenue and a NULL pct_change. An `INNER JOIN` would drop both January rows, and a chart built on the result would begin in February. Either choice is defensible, and the answer should name it: the first period is shown without a comparison, or the first period is omitted.

The same shape serves any grain, with truncation and interval changing together: `date_trunc('week', order_date)` pairs with `INTERVAL '7' DAY`, and `date_trunc('quarter', order_date)` with `INTERVAL '3' MONTH`. The 2 must agree. A week start minus 1 month usually lands on a date no week starts on and goes unmatched, but from March into a 28-day February it lands on the week 4 weeks earlier, so the output mixes NULLs with a few wrong comparisons.

> **TIP**
>
> Say the pairing aloud before writing it: 'each region's month joins to the same region's month exactly 1 month earlier'. Each phrase becomes a line of the query: same region is an equality, same table is the second alias, 1 month earlier is month_start minus INTERVAL '1' MONTH. A phrase with no line behind it means the join is incomplete.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Aggregate to the period grain before joining, so each group and period has 1 row<br><br>• Put the date arithmetic on the truncated column, never on the raw date<br><br>• Match the interval to the truncation: month with 1 month, week with 7 days<br><br>• Compare output row count with input row count after the join | • Join raw order rows to themselves and expect 1 prior per period<br><br>• Leave the group key out of the ON clause<br><br>• Switch to INNER JOIN without saying the first period will vanish<br><br>• Round before dividing, since the denominator loses precision |


<br>

---

## LAG as the Cleaner Alternative

The self-join spells the pairing out in its ON clause. LAG performs the same pairing by position: within a partition, sorted by period, each row receives the value from the row before it. The query shrinks from 2 aliases and 2 join conditions to 1 window clause, and each piece has a counterpart: PARTITION BY region stands where the region equality stood, and ORDER BY month_start stands where the date subtraction stood. Play the animation and watch which row each value comes from.

https://github.com/user-attachments/assets/1f97b46f-043e-4ecc-8777-ce08d485ea5c

North's 3 rows sort by month_start, and each receives the revenue from the row above it: February receives 1500 and March receives 1800. South opens a new partition, so its January receives NULL rather than North's March 1350, and the window never reaches across the boundary. That NULL on each partition's first row is the same NULL the LEFT JOIN produced, reached without listing the table twice.


<br>

### Finishing the growth rate

```sql
WITH monthly AS (
  SELECT
    region,
    DATE_TRUNC('month', order_date) AS month_start,
    SUM(amount) AS revenue
  FROM orders
  GROUP BY region, DATE_TRUNC('month', order_date)
),
with_prior AS (
  SELECT
    region,
    month_start,
    revenue,
    LAG(revenue, 1) OVER (
      PARTITION BY region
      ORDER BY month_start
    ) AS prior_revenue
  FROM monthly
)

SELECT
  region,
  month_start,
  revenue,
  prior_revenue,
  ROUND(
    (
      revenue - prior_revenue
    ) * 100.0 / prior_revenue,
    1
  ) AS pct_change
FROM with_prior
WHERE prior_revenue IS NOT NULL
ORDER BY region, month_start
```

The window sits in a CTE because a window function cannot be referenced in the WHERE clause of the same query: filtering happens before windows are computed, so the filter that removes the first rows must run in an outer query. The CTE also lets pct_change use prior_revenue by name instead of repeating the OVER clause a second time. The 4 rows that survive carry the self-join's values exactly: 20.0, minus 25.0, minus 20.0, minus 25.0, and a result that agrees across both methods is the check an interviewer likes to hear you propose.

| region | month_start | revenue | prior_revenue | pct_change |
| --- | --- | --- | --- | --- |
| North | 2024-02-01 | 1800 | 1500 | 20.0 |
| North | 2024-03-01 | 1350 | 1800 | -25.0 |
| South | 2024-02-01 | 1600 | 2000 | -20.0 |
| South | 2024-03-01 | 1200 | 1600 | -25.0 |


<br>

### The partition is the group the question names

Interviewers often widen the grouping partway through: 'now break it out by region and product'. The self-join gains an equality in ON, and LAG gains a column in PARTITION BY. Leave product out and North's 2 January rows tie on month_start, so whichever sorts second receives the other's revenue: North Monitor's January can receive Laptop's 2000. Each February row receives the row sorted just before it, possibly the other product's February, and the pairs can change between runs.

https://github.com/user-attachments/assets/9954ef3e-e89a-4f9f-975b-aa9dbd48c632

Each of the 3 region and product pairs starts a partition of its own: North Laptop February receives 2000, North Monitor February receives 800, South Laptop February receives 1500, and all 3 January rows receive NULL. So every column the question uses to define 'the same group' goes into PARTITION BY, and the period column alone goes into ORDER BY. A column in the wrong clause changes which row counts as previous.


<br>

### What LAG assumes

> LAG's 3 assumptions
>
> - One row per period in each partition, so 'the previous row' means the previous period rather than another row from the same one.
> - Adjacent rows are adjacent periods, so no period between them is missing from the table.
> - ORDER BY sorts on the truncated period column, so ties and raw dates never reorder the rows.

The first assumption bites when the aggregation step is skipped. Run LAG over raw orders partitioned by region and the previous row is the previous order, which may have been placed the same day: 2 orders on 2024-02-14 give February a prior that is also February. The self-join needs the aggregation for the same reason, but with LAG the mistake is quieter, because the query still returns exactly 1 prior per row and no row count grows to give it away. The second assumption, that no period is missing, has a section of its own later in this lesson.

LAG accepts a third argument as the value to return when no previous row exists, as in LAG(revenue, 1, 0). A default of 0 removes the NULLs, and it also turns every first month into a division by zero in pct_change or into a reported change equal to the whole month's revenue. NULL states the truth, that there is no earlier period, and the outer `WHERE` removes it when the report should start at the second period.

| ✓ Self-join | ✗ LAG |
| --- | --- |
| • Pairs by date arithmetic: month_start minus an interval<br><br>• Group match is an explicit equality in ON<br><br>• A missing period returns NULL for the prior<br><br>• Any offset is an interval change: 1 month, 3 months, 1 year<br><br>• Longer to write, every assumption visible | • Pairs by position: the row before, in sort order<br><br>• Group match is PARTITION BY<br><br>• A missing period returns the wrong prior<br><br>• Any offset is a row count: LAG(revenue, 12)<br><br>• Shorter to write, assumptions implied by the data |


<br>

---

## Year-over-Year for Seasonal Metrics

A toy retailer's monthly revenue, in thousands, rises every December and falls every January, and has done so every year the company has existed. Month-over-month growth on that series reports a boom each December and a collapse each January, and both numbers are accurate about the calendar while saying almost nothing about the business. The table below carries 2 Novembers, 2 Decembers and 2 Januaries for the Toys category, with both comparisons computed, so the 2 columns can be read against each other.

| month_start | revenue | mom_pct | yoy_pct |
| --- | --- | --- | --- |
| 2022-10-01 | 370 | (prior month not shown) | (no prior year) |
| 2022-11-01 | 400 | 8.1 | (no prior year) |
| 2022-12-01 | 640 | 60.0 | (no prior year) |
| 2023-01-01 | 300 | -53.1 | (no prior year) |
| 2023-10-01 | 380 | (prior month not shown) | 2.7 |
| 2023-11-01 | 420 | 10.5 | 5.0 |
| 2023-12-01 | 650 | 54.8 | 1.6 |
| 2024-01-01 | 290 | -55.4 | -3.3 |

December 2023 against November 2023 reads 54.8 percent growth. December 2023 against December 2022 reads 1.6 percent growth. Both are correct divisions, and they answer different questions. The month-over-month figure measures how much December rose from November, which is mostly the holiday rising above an ordinary month, and that rise happened in 2022 as well, at 60.0 percent. The year-over-year figure holds the holiday constant by putting a December against a December, and what remains is 10 thousand of growth on a base of 640, which describes a business that barely moved. A manager reading only the first column plans for a surge that the second column shows did not happen.


<br>

### Hold the season fixed

A metric has a yearly cycle when its level depends on where in the calendar the period falls: retail in November and December, tax software in April, travel in summer, textbooks in September, heating in winter. For such a metric, the earlier period that shares its position in the cycle is the same month 1 year earlier, so the self-join subtracts a year rather than a month, and everything else about the query stays as it was in the first section.

```sql
SELECT
  cur.category,
  cur.month_start,
  cur.revenue,
  prev.revenue AS revenue_last_year,
  ROUND(
    (
      cur.revenue - prev.revenue
    ) * 100.0 / prev.revenue,
    1
  ) AS yoy_pct
FROM monthly AS cur
LEFT JOIN monthly AS prev
  ON prev.category = cur.category
    AND prev.month_start = cur.month_start - INTERVAL '1' YEAR
ORDER BY cur.category, cur.month_start
```

cur.month_start minus INTERVAL '1' YEAR takes 2023-12-01 to 2022-12-01, and because both sides were truncated to the first of the month the equality finds exactly 1 row. The column is named revenue_last_year rather than prior_revenue so that a reader of the output knows which comparison was made without opening the query. Every 2022 row comes back with a NULL yoy_pct, since the table holds no 2021, and that NULL is 12 months wide where the month-over-month version's was 1 month wide.

| category | month_start | revenue | revenue_last_year | yoy_pct |
| --- | --- | --- | --- | --- |
| Toys | 2023-10-01 | 380 | 370 | 2.7 |
| Toys | 2023-11-01 | 420 | 400 | 5.0 |
| Toys | 2023-12-01 | 650 | 640 | 1.6 |
| Toys | 2024-01-01 | 290 | 300 | -3.3 |

The window version is LAG(revenue, 12) OVER (PARTITION BY category ORDER BY month_start), which returns the value from the row 12 positions back. It counts rows rather than months, so if a single month is missing, the row 12 back is 13 months earlier and the column labelled last year holds a November against a December. The interval version still pairs December with December across that gap, and returns NULL only when the year-ago month itself has no row, a failure the next section examines.


<br>

### Other cycles, same reasoning

The yearly cycle is one case of a general rule: compare a period with the earlier period that shares its position in whatever cycle drives the metric. Daily orders for most consumer businesses move with the weekday, so a Tuesday compared with the Tuesday 7 days earlier, INTERVAL '7' DAY, shares the cycle, while a Tuesday compared with Monday mostly measures the day of the week. Quarterly figures with a yearly cycle compare Q4 against the previous Q4 with date_trunc('quarter') and INTERVAL '1' YEAR. Deciding which cycle applies is part of the answer, and stating it aloud is how the interviewer hears that you understood the metric as well as the syntax.

> Which comparison answers which question
>
> - Month-over-month: did momentum change in the last few weeks? Fits a metric without a cycle, or reads beside last year's same move.
> - Year-over-year: is the business bigger than a year ago at this point in the cycle? Fits any metric with a yearly rhythm.
> - Both columns side by side: the seasonal rise and the underlying growth can be told apart in 1 glance.

> **TIP**
>
> When a question says 'growth' about a seasonal metric, present year-over-year as the headline, keep month-over-month as a second column with its label visible, and say out loud which column answers which question.


<br>

---

## Missing Periods in Growth Rates

Every method so far assumed that the row before a period is the period before it. This animation's table breaks it: West has a January row and a March row and no February, either because the pipeline skipped West's February load or because West had no orders. Watch where LAG looks for March's prior.

https://github.com/user-attachments/assets/fb61b724-0a9c-4a13-b409-fc1366008ce8

LAG never consults the calendar. Within West's partition the row above 2024-03-01 is 2024-01-01, so prior_month is January and prior_revenue is 1000. The growth rate that follows is 3000 minus 1000 over 1000, 200.0 percent, and it sits in a column named month-over-month even though 2 months separate the rows. Nothing in the output marks the row as different from North's, where the same column holds honest 1 month figures.


<br>

### The self-join goes empty instead

| method | West March prior_revenue | West March pct_change |
| --- | --- | --- |
| LAG(revenue) | 1000 | 200.0 |
| Self-join on INTERVAL '1' MONTH | NULL | NULL |

The self-join asks a different question. For West's March it looks for a West row whose month_start equals 2024-02-01, finds none, and the LEFT JOIN returns NULL for prior_revenue and therefore for pct_change. That is the better failure, since a NULL in a growth column prompts someone to ask why, whereas 200.0 prompts someone to send congratulations. Both methods, though, leave the gap for the reader to discover, and the next 2 queries make the gap announce itself.


<br>

### Noticing the gap

```sql
WITH with_prior AS (
  SELECT
    region,
    month_start,
    revenue,
    LAG(month_start, 1) OVER (
      PARTITION BY region
      ORDER BY month_start
    ) AS prior_month,
    LAG(revenue, 1) OVER (
      PARTITION BY region
      ORDER BY month_start
    ) AS prior_revenue
  FROM monthly
)

SELECT
  region,
  month_start,
  revenue,
  DATE_DIFF('month', prior_month, month_start) AS months_between,
  CASE
    WHEN DATE_DIFF('month', prior_month, month_start) = 1 THEN ROUND(
      (
        revenue - prior_revenue
      ) * 100.0 / prior_revenue,
      1
    )
  END AS pct_change
FROM with_prior
ORDER BY region, month_start
```

| region | month_start | revenue | months_between | pct_change |
| --- | --- | --- | --- | --- |
| North | 2024-01-01 | 1500 | NULL | NULL |
| North | 2024-02-01 | 1800 | 1 | 20.0 |
| North | 2024-03-01 | 1350 | 1 | -25.0 |
| West | 2024-01-01 | 1000 | NULL | NULL |
| West | 2024-03-01 | 3000 | 2 | NULL |

LAG(month_start) returns the period that LAG(revenue) came from, and date_diff('month', prior_month, month_start) counts how many months lie between them. For every honest pair that count is 1. West's March returns 2, the CASE expression declines to compute a percent, and months_between stays in the output as the reason. January rows have no prior_month, so date_diff returns NULL and the CASE returns NULL for them as well. Wrap this check around any LAG-based growth rate and a gap turns from a wrong number into a visible blank with its cause beside it.

A coarser check works before any window runs: count rows per region and compare the count with the number of months the report covers. With 3 months and 2 regions there should be 6 rows, and when North has 3 and West has 2 the shortfall names the region to inspect. This takes 1 GROUP BY and belongs at the top of the answer, since it decides whether LAG can be trusted at all.


<br>

### Filling the calendar

To make the gap a row rather than an absence, build the full grid of regions and months and LEFT JOIN the aggregate onto it. A calendar table with 1 row per month start and a table of regions give the grid through a CROSS JOIN, and monthly below is the aggregate CTE from the first section.

```sql
WITH grid AS (
  SELECT
    r.region,
    c.month_start
  FROM regions AS r
  CROSS JOIN calendar_months AS c
),
filled AS (
  SELECT
    g.region,
    g.month_start,
    COALESCE(m.revenue, 0) AS revenue
  FROM grid AS g
  LEFT JOIN monthly AS m
    ON m.region = g.region
      AND m.month_start = g.month_start
),
with_prior AS (
  SELECT
    region,
    month_start,
    revenue,
    LAG(revenue, 1) OVER (
      PARTITION BY region
      ORDER BY month_start
    ) AS prior_revenue
  FROM filled
)

SELECT
  region,
  month_start,
  revenue,
  prior_revenue,
  CASE
    WHEN prior_revenue > 0 THEN ROUND(
      (
        revenue - prior_revenue
      ) * 100.0 / prior_revenue,
      1
    )
  END AS pct_change
FROM with_prior
ORDER BY region, month_start
```

| region | month_start | revenue | prior_revenue | pct_change |
| --- | --- | --- | --- | --- |
| West | 2024-01-01 | 1000 | NULL | NULL |
| West | 2024-02-01 | 0 | 1000 | -100.0 |
| West | 2024-03-01 | 3000 | 0 | NULL |

West now has a February row with revenue 0, and LAG is honest again: February compares with January at minus 100.0 percent, and March compares with February. March's prior is 0, so the CASE returns NULL for its percent rather than dividing by 0, which would fail the query. COALESCE to 0 is the right fill when the gap means no orders happened. When the gap means the pipeline skipped West's February load, the revenue is unknown rather than 0, and the fill is NULL, so February's own percent goes blank too. The numbers can't say which of the 2 the gap is: knowing how the table was loaded can, and saying so belongs in the answer.

> Signs a group is missing periods
>
> - Row counts per group fall short of the number of periods in the range.
> - date_diff between a row's period and LAG of its period comes back greater than 1.
> - After a calendar fill, a period appears with revenue 0 or NULL where the source had no row.

> **TIP**
>
> Ask the interviewer whether every group has a row for every period before choosing LAG. If the answer is uncertain, add the date_diff guard, and name the fill you chose for gaps: 0 for a real month of no activity, NULL for data that never arrived.


<br>

---

## Percentage Points vs Percent

The same month-over-month machinery applies to a rate, and the reporting changes. A store's conversion rate is orders divided by visits. In January 2,000 orders came from 50,000 visits, so the rate was 4.0 percent, and in February 2,400 orders came from 48,000 visits, so the rate was 5.0 percent. Conversion rose. By how much depends on which of 2 numbers is meant.

| month_start | visits | orders | conv_rate |
| --- | --- | --- | --- |
| 2024-01-01 | 50000 | 2000 | 4.0 |
| 2024-02-01 | 48000 | 2400 | 5.0 |
| 2024-03-01 | 52000 | 2340 | 4.5 |

The difference between the 2 rates is 5.0 minus 4.0, which is 1.0 percentage point. The relative change of the rate is that difference divided by the earlier rate, 1.0 over 4.0, which is 25 percent. Both describe February. A percentage point is a unit of the rate itself, a hundredth of the whole, and a change in percentage points says how many more of each hundred visits converted. A percent change treats the rate as any other quantity and says how much bigger it became in proportion to what it was. Saying 'conversion rose 1 percent' names neither, and a listener who hears the relative meaning pictures a rate of 4.04 percent.

```sql
WITH monthly AS (
  SELECT
    DATE_TRUNC('month', visit_date) AS month_start,
    COUNT(*) AS visits,
    SUM(
      CASE
        WHEN converted THEN 1
        ELSE 0
      END
    ) AS orders
  FROM visits
  GROUP BY DATE_TRUNC('month', visit_date)
),
rates AS (
  SELECT
    month_start,
    orders * 100.0 / visits AS conv_rate
  FROM monthly
),
with_prior AS (
  SELECT
    month_start,
    conv_rate,
    LAG(conv_rate, 1) OVER (
      ORDER BY month_start
    ) AS prior_rate
  FROM rates
)

SELECT
  month_start,
  ROUND(conv_rate, 1) AS conv_rate,
  ROUND(conv_rate - prior_rate, 1) AS change_pp,
  ROUND(
    (
      conv_rate - prior_rate
    ) * 100.0 / prior_rate,
    1
  ) AS change_pct
FROM with_prior
ORDER BY month_start
```

| month_start | conv_rate | change_pp | change_pct |
| --- | --- | --- | --- |
| 2024-01-01 | 4.0 | NULL | NULL |
| 2024-02-01 | 5.0 | 1.0 | 25.0 |
| 2024-03-01 | 4.5 | -0.5 | -10.0 |

The rate is computed per month in its own CTE before LAG runs, so a single conv_rate column feeds both changes and they read as 2 views of 1 quantity. change_pp is a plain subtraction. change_pct divides that subtraction by prior_rate and multiplies by 100, the same formula the revenue sections used, applied to a quantity that already carries a percent sign. March shows the 2 units moving together in the other direction: the rate fell 0.5 percentage points from 5.0 to 4.5, which is a 10 percent relative drop. The column suffixes carry the unit, so a chart built from the output cannot mislabel it.


<br>

### Which unit the question wants

| ✓ Percentage points when | ✗ Percent when |
| --- | --- |
| • The metric is itself a rate: conversion, churn, margin, share, uptime<br><br>• The audience needs the absolute movement of the rate<br><br>• Rates at different levels are compared across segments<br><br>• The earlier rate is small and a percent would exaggerate | • The metric is a count or an amount: revenue, orders, users<br><br>• The question asks how much bigger something became in proportion<br><br>• The base is far from 0 and relative scale carries meaning<br><br>• The reader will compare growth across metrics of different sizes |

Rates get percentage points because a percent change of a rate stacks 2 ratios and leaves the reader unsure of the base. A churn rate that moves from 2.0 to 2.5 percent is up 0.5 percentage points and up 25 percent, and a message saying 'churn is up 25 percent' will be read by someone as a quarter of customers leaving. Amounts get percent, since 'revenue up 300' means little without the base and 'revenue up 20 percent' carries it. When the interviewer's question asks 'how did conversion change month over month', answer in percentage points, and offer the percent change as a second number with its own label.




<br>

### Small rates make percent explode

| prior_rate | conv_rate | change_pp | change_pct |
| --- | --- | --- | --- |
| 0.5 | 1.0 | 0.5 | 100.0 |
| 2.0 | 2.5 | 0.5 | 25.0 |
| 20.0 | 20.5 | 0.5 | 2.5 |

The same 0.5 percentage point move reads as 100 percent growth from a 0.5 percent base, 25 percent from a 2.0 percent base and 2.5 percent from a 20.0 percent base. The percentage point column tells 1 story in all 3 rows: half a visitor more in every hundred. For a metric such as fraud rate or click-through rate that lives below 1 percent, the percent change will always be the dramatic number, and presenting it alone invites the reader to overreact. The advanced tier of this track treats tiny baselines for amounts. For rates, percentage points sidestep the problem by never dividing at all.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Suffix columns _pp and _pct so the unit travels with the number<br><br>• Compute the rate per period first, then LAG the rate<br><br>• State the base when quoting a percent change of a rate<br><br>• Ask which unit is meant when someone says conversion 'rose 1 percent' | • Report a percent change of a rate without its percentage point change<br><br>• Call a 1 point rise in conversion a 1 percent rise<br><br>• Let percent and percentage points share a column<br><br>• Divide when the earlier rate is 0 |


<br>

---

## Putting It All Together

An online marketplace holds its January business review. The analytics engineer presents gross merchandise value by seller category for December, conversion rate by device, and a flag on 2 categories whose December row is missing because their payments feed failed over the holiday weekend.

- GMV by category is aggregated to months with date_trunc, then paired with December a year earlier through a self-join on INTERVAL '1' YEAR, so the holiday peak is compared with the previous holiday peak.
- The month-over-month column sits beside year-over-year, and the 55 percent jump from November is read as seasonal because the year-over-year column shows 2 percent.
- The 2 categories with no December row are absent from the December year-over-year output altogether, which a row count per category exposes, and a date_diff guard on the LAG version keeps their January from comparing against November as if it were December.
- Device conversion moved from 3.2 to 3.6 percent, reported as 0.4 percentage points, with the 12.5 percent relative change in a second labelled column.


<br>

---

## Key Takeaways

- Aggregate to the period grain first, so each group and period appears once, then pair each row with its earlier one.
- A self-join pairs by date arithmetic on the truncated column and needs both the group equality and the interval in its ON clause.
- LAG pairs by position inside PARTITION BY and ORDER BY, and assumes 1 row per period with no gaps between rows.
- A metric with a yearly cycle is compared with the same period 1 year earlier, so the season is held fixed and growth is what remains.
- A missing period makes LAG wrong and the self-join empty, and date_diff on LAG(month_start) turns either into a visible blank with its cause.
- A change in a rate is reported in percentage points, a change in an amount in percent, and the column name carries the unit.
