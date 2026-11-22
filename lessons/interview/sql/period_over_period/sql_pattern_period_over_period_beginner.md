# Period-over-Period: Beginner

You are 20 minutes into the SQL screen at a furniture retailer. The analyst across the table shares her screen: a `transactions` table with `txn_date`, `region`, `product` and `amount`, about 40,000 rows a month.
"Is revenue growing? I want to see how each region is trending month over month."
She stops there. Nothing in that sentence says what a single row of the answer looks like, and most candidates start typing before deciding. One row per transaction? Per month? Per region per month? The query that joins `transactions` to itself to find "last month's revenue" returns a number for every pair of sales, and the totals it prints are thousands of times too large while looking entirely plausible.
What she is listening for is whether you say, before writing anything, that trend means 2 figures sitting together: this month's total and last month's total for that region.


<br>

### What you will be able to do

Recognize a period-over-period question behind words like growth, trend, lift, delta and month-over-month

State the grain of the answer and aggregate sales to a single row for each group and period before comparing anything

Bring the previous period's value onto each row with LAG, partitioned by group and ordered by the truncated date

Compute percent change against the earlier period, guarded against zero and integer division, and read the sign correctly

Sketch the row and its prior before writing the window clause, so a wrong pairing is caught before the query runs


<br>

---

## The Growth Question in Disguise

The question almost never arrives with the words 'period-over-period' in it. It arrives as 'is revenue growing', 'how is the East region trending', 'what did sign-ups do last quarter' or 'show me the lift since the redesign'. Every one of those reduces to the same calculation: take a figure for one period, take the same figure for the period before it, and put the 2 numbers on one row so they can be subtracted. The interviewer knows this. The first thing being scored is whether you know it too, and whether you say so before writing a line.

- 'growth', 'trend', 'trajectory', 'momentum': a value over consecutive periods, each compared with the one before
- 'month-over-month', 'week-over-week', 'quarter-over-quarter': the period length named for you
- 'change', 'delta', 'lift', 'drop': a difference between 2 periods, usually wanted as a percent
- 'is X up or down': the sign of that difference, with the size expected as a follow-up
- 'how did we do versus last month': the same question with the 2 periods named in plain words
- 'show me the numbers over time, with how much each moved': the output described rather than the calculation


<br>

### Two Numbers on One Row

Say the shape of the answer out loud before touching the keyboard, because the shape settles half the design. For 'month-over-month revenue per region' one row of the answer is one region in one month, and that row carries 2 revenue figures: the month's own total and the previous month's total for the same region. Everything else, the difference and the percent, is arithmetic between those 2 columns. State it as 'one row per region per month, with this month's revenue and last month's revenue side by side', and the interviewer can relax, because you have named the grain and the comparison in 1 sentence.

| region | month_start | revenue | prior_revenue | pct_change |
| --- | --- | --- | --- | --- |
| East | 2024-01-01 | 1000 | NULL | NULL |
| East | 2024-02-01 | 1550 | 1000 | 55.0% |
| East | 2024-03-01 | 1100 | 1550 | -29.0% |

Read the East rows and the question answers itself: revenue rose 55% from January to February, then fell 29% in March. The table holds 3 rows because East had 3 months of sales, and the first row's `prior_revenue` is empty because January has no month before it in the data. Those 2 observations, the row count and the empty first cell, are what the interviewer will ask about later, so notice them now.


<br>

### Roll Up Before You Compare

The trap in this round is working from the raw table. `transactions` holds 1 row per sale, so 'last month's revenue' does not exist in it as a value; it exists as hundreds of rows waiting to be added. A candidate who reaches straight for a comparison, joining the table to itself on 'the month before' or running `LAG` directly over sales rows, is comparing single sales with single sales. Joined, every January sale pairs with every February sale and the totals multiply; windowed, each row's 'prior' is the previous sale, often from the same afternoon. Both outputs print numbers that look like money and mean nothing.

The fix is an aggregation step before any comparison. `DATE_TRUNC('month', txn_date)` turns every date into the first day of its month, `GROUP BY` that and the region, and `SUM(amount)` collapses the sales into 1 row per region per month. Only once each period is a single row does 'the previous period' mean a single value. This step belongs in a CTE of its own, usually named `monthly`, so that the comparison that follows reads from a table where the grain is already right.

```sql
WITH monthly AS (
  SELECT
    region,
    DATE_TRUNC('month', txn_date) AS month_start,
    SUM(amount) AS revenue
  FROM transactions
  GROUP BY region, DATE_TRUNC('month', txn_date)
)

SELECT
  *
FROM monthly
ORDER BY region, month_start
```

The sentence that signals you parsed the prompt: *'This is a period-over-period question. I will roll transactions up to 1 row per region per month, use* LAG *to bring the previous month's total onto each row, then compute the change as the difference divided by the previous month.'* The plan has 3 steps, named in order, and each maps to a CTE or a column in the query you are about to write.

| ✓ Opening that loses time | ✗ Opening that scores |
| --- | --- |
| • Starts typing a join of transactions to transactions on the date<br><br>• Discovers the row count is in the millions when asked<br><br>• Backs out and re-plans with the clock running<br><br>• Never states what 1 row of the answer is | • Names the pattern in the first sentence<br><br>• States the grain: 1 row per region per month<br><br>• Writes the rollup CTE before any comparison<br><br>• Has the comparison column on screen within 2 minutes |

> **TIP**
>
> If the question names a period ('weekly', 'by quarter'), the rollup uses it: `DATE_TRUNC('week', ...)` or `DATE_TRUNC('quarter', ...)`. If it does not, ask. 'Monthly, or do you want weekly?' is a question interviewers like, because the period is a decision they have deliberately left out.


<br>

---

## Each Group Against Its Own Past

'Per region' changes the question from 1 trend to 1 trend for each region, and each of those trends is measured against that region's own history. East in February is compared with East in January, never with West in January and never with the company's January total. That sounds too plain to need saying, and yet the most common wrong output in this round is a table where the first West row shows a prior value that belongs to East. It happens because the rollup produced 1 list of rows, and 'the previous row' in 1 list crosses from the end of one region into the start of the next.

| region | month_start | revenue |
| --- | --- | --- |
| East | 2024-01-01 | 1000 |
| East | 2024-02-01 | 1550 |
| East | 2024-03-01 | 1100 |
| West | 2024-01-01 | 1000 |
| West | 2024-02-01 | 850 |
| West | 2024-03-01 | 600 |

Six rows, 2 regions. Read down the list and the row above West's January is East's March at 1100. A window with no partition hands that 1100 to West's January as its prior, and the report says West fell from 1100 to 1000 in a month where West had no earlier month at all.


<br>

### What PARTITION BY Draws

`PARTITION BY region` inside the `OVER` clause splits that 1 list into 1 list per region, and the window function runs separately inside each. `LAG` looking back from West's January finds nothing, because nothing in West's list comes before it, and returns NULL. Looking back from West's February it finds West's January, 1000, which is the figure the question wants. The partition is the SQL spelling of 'against its own past', and saying that sentence as you type the clause tells the interviewer that the clause is deliberate.

```sql
SELECT
  region,
  month_start,
  revenue,
  LAG(revenue, 1) OVER (
    PARTITION BY region
    ORDER BY month_start
  ) AS prior_revenue
FROM monthly
```

| region | month_start | revenue | prior_revenue |
| --- | --- | --- | --- |
| East | 2024-01-01 | 1000 | NULL |
| East | 2024-02-01 | 1550 | 1000 |
| East | 2024-03-01 | 1100 | 1550 |
| West | 2024-01-01 | 1000 | NULL |
| West | 2024-02-01 | 850 | 1000 |
| West | 2024-03-01 | 600 | 850 |

Two NULLs now, 1 at the top of each region, where the unpartitioned version had 1. That second NULL is the tell: when the interviewer asks 'how many rows have no prior', the answer is 'one per group, because each group's first period has nothing before it', and the number of groups in the data is the number of blanks.


<br>

### The Grain Follows the Question

The partition list is whatever the question says 'per' or 'by'. 'Per region and product' means `PARTITION BY region, product`, and the rollup's `GROUP BY` carries the same 2 columns, because the rollup and the comparison have to agree on what 1 row is. A rollup grouped by region alone and a window partitioned by region and product would hand the window rows where product does not exist, so the pair is always written together: the columns after `GROUP BY` in the rollup are the columns after `PARTITION BY` in the window, with the period column left out of the partition and placed in `ORDER BY`.

https://github.com/user-attachments/assets/ee31131e-b44e-4cfb-a34f-3d96a302db17

The animation's `monthly` table carries 3 rows for East: Desk in January at 1000, Desk in February at 1250, and Lamp in February at 300. With `PARTITION BY region, product`, Desk's February row receives 1000 as its prior, because Desk's January is the row before it inside the Desk sequence. Lamp's February row receives NULL, because Lamp has no January row at all. A partition on region alone would have handed Lamp whichever East row the tie on 2024-02-01 happens to place before it, Desk's February at 1250 or Desk's January at 1000. Both are another product's revenue, so the 76% or 70% collapse it reports is fiction either way.

A different follow-up probes whether you understand that the window does not reduce rows. `GROUP BY` collapses many rows into 1; `PARTITION BY` keeps every row and only decides which neighbours a row can see. The output of the comparison step has the same 6 rows as `monthly`, 1 new column wider. Candidates who expect the partition to produce 1 row per region have confused the 2 clauses, and the interviewer will ask for the row count to find out.

| ✓ GROUP BY region | ✗ PARTITION BY region |
| --- | --- |
| • Collapses rows: 1 output row per region<br><br>• Columns outside the group list must be aggregated<br><br>• Lives in the rollup step | • Keeps rows: output has as many rows as input<br><br>• Every column stays available on each row<br><br>• Lives in the comparison step |

> The follow-up: 'and the company total?'
>
> - A total across regions is a different grain: 1 row per month, with no region column
> - Write it as a second rollup grouped by month alone, with LAG over ORDER BY month_start and no partition
> - Adding a region named 'All' inside the per-region table mixes 2 grains in 1 partition column
> - If asked for both, say 'two rollups, each with its own LAG, stacked with UNION ALL if one table is wanted'

> **TIP**
>
> Name the partition as you write it: 'partition by region, so each region compares only with itself'. The interviewer is listening for the word 'itself'.


<br>

---

## Comparing This Period to the Last

SQL evaluates 1 row at a time. An expression in a `SELECT` can read any column on the row it is evaluating and none from the row above, which is the whole difficulty of this question: the subtraction `revenue - prior_revenue` needs 2 months on 1 row, and the rollup put them on 2. Something has to copy the earlier value across. `LAG` is the function that does it: for each row, it looks at the row 1 position earlier in the window's order and returns that row's value of whatever column you name.


<br>

### Reading the LAG Clause

> Anatomy of the LAG clause
>
> - `LAG(revenue)`: the column to fetch from the earlier row; the default offset is 1 row back, written in full as `LAG(revenue, 1)`
> - `OVER`: marks this as a window function, computed for each row without collapsing rows
> - `PARTITION BY region`: the earlier row has to be in the same region
> - `ORDER BY month_start`: 'earlier' means an earlier month; without an order, 'previous row' has no meaning
> - Result: the previous month's revenue copied onto the current row, or NULL when there is none


<br>

### The Query, Stage by Stage

```sql
WITH monthly AS (
  SELECT
    region,
    DATE_TRUNC('month', txn_date) AS month_start,
    SUM(amount) AS revenue
  FROM transactions
  GROUP BY region, DATE_TRUNC('month', txn_date)
),
compared AS (
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
  revenue - prior_revenue AS revenue_change
FROM compared
ORDER BY region, month_start
```

The `monthly` CTE is the rollup from the opening: 1 row per region per month. The `compared` CTE adds 1 column and no rows: `prior_revenue`, filled by `LAG` from the row above inside each region. The final `SELECT` does arithmetic between 2 columns that now sit on the same row. Writing it in 3 stages costs a few lines and buys 2 things the interviewer values: every intermediate table can be run on its own to check its row count, and the subtraction reads as plain column arithmetic with no window syntax around it.

https://github.com/user-attachments/assets/3a2820dc-172b-4b5a-8858-a4d3b4e93cea

The animation drops the region to keep the stage small and plays the same 2 stages over 4 sales. January's 2 sales, 1200 and 800, fold into 1 row at 2000; February's single sale becomes 2400; March's becomes 1700. Then `LAG` walks the 3 monthly rows in date order: January looks back and finds nothing, so its `prior_revenue` is NULL; February looks back and copies 2000; March looks back and copies 2400. Watch which row each copied cell flies out of, because that motion is what you will describe in the room: 'each row reaches back 1 month and brings that month's total forward'.

| month_start | revenue | prior_revenue | revenue_change |
| --- | --- | --- | --- |
| 2024-01-01 | 2000 | NULL | NULL |
| 2024-02-01 | 2400 | 2000 | 400 |
| 2024-03-01 | 1700 | 2400 | -700 |


<br>

### The First Row Has No Partner

January's `prior_revenue` is NULL, and so is its change, because NULL minus anything is NULL. This is correct and the interviewer will test whether you think so. The weak answer is 'I'd filter that row out' or 'I'd treat it as zero'. Zero would report January as 2000 of growth from nothing, which is a claim about December that the data does not support. The strong answer: 'the first month of each region has no comparison, so it stays in the output with a blank change, and the report shows a dash'. Keeping the row also keeps the row count equal to `monthly`, which is the check you promised.

A common follow-up is 'what if I wanted next month on the row instead'. `LEAD(revenue)` with the same `OVER` clause looks 1 row forward rather than back, so the last month of each region becomes the NULL. The arithmetic flips: `LEAD` answers 'how much did next month move from this one', which is the same change attributed to a different row. For a trend report the convention is to attach the change to the later month, which is `LAG`, and saying 'the change belongs to the month it happened in' is the reason to give.

> **TIP**
>
> Alias the window column `prior_revenue` or `prev_month_revenue`, never `lag` or `x`. The final `SELECT` then reads as English, and the interviewer scanning your screen sees the pairing without decoding the clause.


<br>

---

## Which Period Is the Denominator

Once the 2 values share a row the change is 1 subtraction, and the percent is that subtraction divided by 1 of the 2 values. Which one is the question this section exists for, because both divisions produce a believable number and only 1 is the growth rate. Growth is measured against where you started: February's growth over January is February minus January, divided by January. The earlier period is the denominator, every time, and 'divided by the prior period' is a phrase to say aloud as you type it.

```sql
SELECT
  region,
  month_start,
  revenue,
  prior_revenue,
  revenue - prior_revenue AS revenue_change,
  (
    revenue - prior_revenue
  ) * 1.0 / NULLIF(prior_revenue, 0) AS pct_change
FROM compared
ORDER BY region, month_start
```

| month_start | revenue | prior_revenue | over prior (correct) | over current (wrong) |
| --- | --- | --- | --- | --- |
| 2024-02-01 | 2400 | 2000 | +20.0% | +16.7% |
| 2024-03-01 | 1700 | 2400 | -29.2% | -41.2% |

Over the earlier month, February is up 20%: 400 more on a base of 2000. Divided by the current month instead, the same 400 reads as 16.7%, and March's fall of 700 reads as 41.2% instead of 29.2%. Neither wrong figure is absurd, which is what lets the error survive review; a dashboard built on the wrong denominator reports every rise too small and every fall too large, and nobody notices until a finance team recomputes a number by hand.


<br>

### Reading What Comes Back

The expression returns a fraction: 0.20 for February, with 0 meaning flat, a positive value meaning the period grew and a negative value meaning it shrank. If the interviewer wants a percent column, multiply by 100 and round, `ROUND((revenue - prior_revenue) * 100.0 / NULLIF(prior_revenue, 0), 1)`, and say which you are producing, because 'growth of 0.2' and 'growth of 20' are both plausible on a screen and only the column name tells them apart. Read a negative value as 'down by', so -0.292 in March is 'revenue down 29.2% from February', with the base month named in the sentence.

The denominator also explains a fact worth stating when asked to interpret a result: a fall and the rise that undoes it are different percents. March fell 29.2% from 2400 to 1700. Climbing back to 2400 next month would be a change of 700 on a base of 1700, a larger percent than the fall, because the base shrank. Candidates who say 'it would need to grow 29% to recover' have divided by the wrong month in their head.

- **+41.2%** — to climb from 1700 back to 2400


<br>

### Two Guards on the Division

`NULLIF(prior_revenue, 0)` returns NULL when the prior is 0 and the prior otherwise. Dividing by NULL yields NULL, which is the honest result: growth from a month that earned nothing has no percent, and reporting NULL lets the dashboard show a dash. Without it, the month after one where refunds cancelled out every sale, so `SUM(amount)` came to exactly 0, raises a division-by-zero error on PostgreSQL and most warehouses, and the whole report fails on 1 row. A month with no sales at all is a different case: it has no row in `monthly`, so `LAG` reaches past it to an older month, which is the gap problem the sketch catches and NULLIF cannot. The interviewer who asks 'what if last month was zero' is checking for this 1 function, and 'I would NULLIF the denominator' is the complete answer.

`* 1.0` guards against integer division. If `amount` is an integer column, `SUM(amount)` is an integer, and on PostgreSQL an integer divided by an integer truncates toward zero: 400 / 2000 becomes 0, March's -700 / 2400 also becomes 0, and so does every change smaller than the prior month, rises and falls alike. Only a change of at least the whole prior survives, so a doubling shows as 1. Nearly every rate in the report reads 0, and nothing errors. Multiplying the numerator by 1.0 promotes the arithmetic to decimal before the division. A `CAST(revenue - prior_revenue AS DECIMAL(18, 4))` does the same more verbosely; either is fine, and mentioning the hazard unprompted is a point in your favour.

> When the interviewer probes the formula
>
> - 'Why divide by the prior month?': 'Growth is measured against the starting point; the earlier period is the base'
> - 'What if the prior month is zero?': 'NULLIF turns the zero into NULL, the percent becomes NULL, and the report shows no comparison'
> - 'Why is every rate showing 0?': 'Integer division; multiply by 1.0 or cast before dividing'
> - 'Is 0.2 the same as 20%?': 'Yes, and the column name should say which unit the column is in'


<br>

---

## Sketching the Rows You Subtract

Everything that goes wrong in this query goes wrong in the pairing: the row `LAG` hands you is a row from the wrong region, from a month that is not the previous one, or from a different position than you pictured. The defence is a habit you can perform in the room in under a minute: before writing the window clause, write out 2 rows by hand, the row you are computing and the row its prior should come from, with every column filled in. If you cannot write the second row, you do not yet know what the clause should say.

| which row | region | month_start | revenue |
| --- | --- | --- | --- |
| this row | East | 2024-03-01 | 1100 |
| its prior | East | 2024-02-01 | 1550 |

The sketch forces 3 answers out of you. The prior row shares the region, so `PARTITION BY region`. The prior row is the month immediately before, so `ORDER BY month_start` with an offset of 1. The expected result for East in March is 1100 against 1550, a fall, so when the query runs and that row shows a positive change, you know the pairing is wrong before the interviewer does.

- Same group: every column in the partition matches between the 2 rows
- Adjacent period: the prior row's month is 1 period before, with nothing between
- Date order: the ORDER BY column is a date or timestamp, never a label or a measure
- Direction: the prior is earlier, so LAG; a later row would be LEAD
- Expected sign: you know whether this row should read as up or down before running


<br>

### The Partition Left Out

https://github.com/user-attachments/assets/93828dbd-34e9-4079-9380-9b5b2868e809

The animation orders the 4 rows by region and then month, with no partition. East's February correctly receives East's January, 1000. West's January, with nothing of West's before it, receives 1550: East's February, the row above it in the single ordered list. West's February then receives 1000 from West's January, which is right, so the output has 1 wrong cell in 4 and 3 right ones. The sketch catches it: the prior row you drew for West's January was blank, and the query gave it a number.


<br>

### Ordering by the Wrong Column

The second wrong pairing comes from the `ORDER BY`. A rollup that produced a month label with `TO_CHAR(txn_date, 'Month')`, or stored the month as text, sorts alphabetically, and April, February, January, March is the order the window walks. February's 'prior' becomes April. Ordering by `revenue` instead of the date is the other variant, usually a slip when the `ORDER BY` from the final query is pasted into the window. In both cases the sketch's prior row has the wrong month on it, which is visible the moment you compare it against the row you drew.

| month_label | month_start | revenue | prior by label order |
| --- | --- | --- | --- |
| April | 2024-04-01 | 1400 | NULL |
| February | 2024-02-01 | 1550 | 1400 |
| January | 2024-01-01 | 1000 | 1550 |
| March | 2024-03-01 | 1100 | 1000 |

East's February now reads as a change from 1400 to 1550, a rise that pairs it with a month 2 months later. Keep the truncated date in the rollup even when the report wants a label. `DATE_TRUNC` gives a value that sorts as time, and a label column formatted from it can sit beside it for display. The window always orders by the date.


<br>

### When the Sketch Shows a Hole

Sometimes the sketch itself is the warning. You draw East's March and reach for East's February, and the `monthly` table has no February row for East because the region sold nothing that month. `LAG` will hand March the January row without complaint, and the change will be labelled month-over-month while spanning 2 months. The expectation here is to notice: 'the previous row is not the previous month, so this growth rate is comparing across a gap'. Say that, and the interviewer hears someone who checks the rows rather than trusting the clause. How to fill the gap is a longer conversation, and naming it is what is scored.

*The sketch costs 30 seconds and the interviewer sees you doing it, which reads as method rather than hesitation.*

| ✓ Do | ✗ Don't |
| --- | --- |
| • Roll up to 1 row per group per period in a CTE before any LAG<br><br>• Say the grain aloud: 1 row per region per month, with this month and last month side by side<br><br>• Partition by every 'per' column and order by the truncated date<br><br>• Divide the change by the prior period, wrapped in NULLIF, multiplied by 1.0<br><br>• Sketch the 2 rows for 1 group before writing the OVER clause | • Don't run LAG or a self-join over raw transaction rows<br><br>• Don't replace the first period's NULL with 0 or filter the row away<br><br>• Don't order the window by a month label or by the measure<br><br>• Don't divide by the current period; the result looks right and is wrong<br><br>• Don't report a fraction and call it a percent without saying which |


<br>

---

## Putting It All Together

The finance team at a 2-region furniture retailer closes each month by sending the board a chart of revenue by region with month-over-month change. The analyst builds it from transactions: a monthly rollup via DATE_TRUNC and SUM, a compared CTE with LAG partitioned by region and ordered by month_start, and a final SELECT with the percent over the prior month through NULLIF and \* 1.0. In the first run East's and West's January rows show a blank change, which the dashboard draws as dashes. One East row shows +200%, and a sketch of that row and its prior shows the prior is January rather than February, because East sold nothing in February, so the analyst flags the figure before the deck goes out.

- The board's question 'how are the regions trending' is the growth question in disguise, and the chart is 2 figures per region per month
- The rollup to 1 row per region per month is what makes 'last month' a single value LAG can copy
- PARTITION BY region keeps West's January from reading East's March as its past, and produces exactly 1 blank per region
- Dividing by the prior month gives West's February -15% against January; the January dashes come from LAG's NULL, and NULLIF only covers a base of 0
- Sketching the +200% row against its prior exposes a 2-month gap labelled as 1 month, before anyone on the board reads it


<br>

---

## Key Takeaways

- Every growth or trend question is 2 numbers on 1 row: a period's value and the previous period's, for the same group
- Aggregate to the period grain first; comparisons over raw rows multiply or misalign
- PARTITION BY the group columns and ORDER BY the truncated date; the first row of each group carries a NULL prior
- Percent change divides the difference by the earlier period, guarded by NULLIF and \* 1.0
- Sketch the row and its prior before writing the clause, and check the sign of the result against the sketch
