# Running Totals: Intermediate

You are 20 minutes into the SQL round at a payments company. The interviewer shares a `transactions` table: `account_id`, `txn_date`, `amount`, about 3 million rows a month. "Finance wants to know which accounts make up the top 80% of volume this quarter. While you are in there, give me a 7-day trailing total per account, and tell me how many distinct accounts had transacted as of each day." She stops typing. All 3 questions are running totals in different coats. Nobody has said what happens when 2 transactions share a date, whether "7-day" means 7 rows or 7 calendar days, or whether "as of each day" starts over at the quarter. The usual move is to write `SUM(amount) OVER (ORDER BY txn_date)` 3 times with small edits, and the first one already carries a bug she can see in the sample. What she is scoring is whether you name the frame, the grain and the reset before you write any of them.


<br>

### What you will be able to do

Compute a running share of a grand total in one scan and return the rows up to the point where the share crosses a threshold

Explain why a window with ORDER BY and no frame collapses tied rows, and write the ROWS frame plus tiebreaker that fixes it

Build a 7-day trailing window at daily grain and say what a missing day does to it, with a spine or a RANGE interval as the fix

Restart a running total per account, per month, or at each event row using only the partition clause

Produce an exact cumulative distinct-user count from first-seen dates, and name the join or sketch a trailing distinct count needs


<br>

---

## Running Share of the Total

The question rarely contains the word running. It arrives as "which merchants account for 80% of our volume", "how many accounts do I need to call before I have covered half the revenue", or "at what point does the cumulative share cross 95%". Each one is a running total divided by a grand total, read down a list sorted from largest to smallest. The interviewer is listening for 2 things in the first minute: that you sort before you accumulate, and that you compute both totals in the same pass instead of running a second query to fetch the denominator.

Start with the grain. One row per account with its quarterly revenue, so the running total walks accounts rather than transactions. If the table is at transaction grain, collapse it first with a GROUP BY and say so, because a share computed over raw transactions answers a question nobody asked.


<br>

### Both totals from 1 scan

```sql
WITH account_revenue AS (
  SELECT
    account_id,
    SUM(amount) AS revenue
  FROM transactions
  WHERE txn_date >= DATE '2025-01-01'
    AND txn_date < DATE '2025-04-01'
  GROUP BY account_id
)

SELECT
  account_id,
  revenue,
  SUM(revenue) OVER (
    ORDER BY revenue DESC, account_id
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS running_revenue,
  SUM(revenue) OVER () AS grand_total,
  ROUND(
    100.0 * SUM(revenue) OVER (
      ORDER BY revenue DESC, account_id
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) / SUM(revenue) OVER (),
    1
  ) AS running_pct
FROM account_revenue
ORDER BY revenue DESC, account_id
```

`SUM(revenue) OVER ()` with nothing inside the parentheses is the grand total stamped onto every row. With no partition and no ordering, its frame is the whole result set. The ordered window beside it grows one account at a time. Say out loud that both come out of the same sorted scan: a scalar subquery for the denominator reads the table a second time, and a CROSS JOIN to a one-row total does the same with more syntax.

https://github.com/user-attachments/assets/bda5a77e-d061-41b7-bdb5-97b715abc6fe

On the 5 accounts in the animation the grand total is 1,000 and the running column climbs 500, 800, 920, 980, 1,000. Divide each by 1,000 and the shares read 50%, 80%, 92%, 98%, 100%. The cumulative share reaches 80% at the second row, so 2 accounts out of 5 carry 80% of the revenue, which is the sentence finance wanted in the first place.

| account_id | revenue | running_revenue | running_pct |
| --- | --- | --- | --- |
| C1 | 500 | 500 | 50.0 |
| C2 | 300 | 800 | 80.0 |
| C3 | 120 | 920 | 92.0 |
| C4 | 60 | 980 | 98.0 |
| C5 | 20 | 1000 | 100.0 |


<br>

### Returning the rows up to the crossing

The follow-up is "now give me only those accounts". A window result cannot be filtered in the same SELECT, because WHERE runs before window functions are computed, so the running share goes into a CTE and the filter sits outside it. The inequality is where candidates slip: `WHERE running_pct <= 80` drops the account that pushes the share over the line, and on real data no account lands on exactly 80.0, so the list comes back 1 account short of the threshold. The predicate that keeps the crossing row looks at the share before this account, which is the running share minus the account's own share.

```sql
WITH account_revenue AS (
  SELECT
    account_id,
    SUM(amount) AS revenue
  FROM transactions
  GROUP BY account_id
),
shares AS (
  SELECT
    account_id,
    revenue,
    100.0 * revenue / SUM(revenue) OVER (
    ) AS share_pct,
    100.0 * SUM(revenue) OVER (
      ORDER BY revenue DESC, account_id
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) / SUM(revenue) OVER () AS running_pct
  FROM account_revenue
)

SELECT
  account_id,
  revenue,
  ROUND(running_pct, 1) AS running_pct
FROM shares
WHERE running_pct - share_pct < 80
ORDER BY revenue DESC, account_id
```

Read the result against the 5-row example: C1 has a prior share of 0, C2 of 50, C3 of 80, so C1 and C2 pass and C3 fails. The `LAG` version is equivalent but needs 1 more CTE, since it is a new window over `shares`: compute `LAG(running_pct, 1, 0) OVER (ORDER BY revenue DESC, account_id) AS prior_pct` there, then filter `WHERE prior_pct < 80` outside it. Some interviewers prefer it because it says "the previous row had not crossed yet" in the query's own words.

> What the interviewer asks next
>
> - Why DESC? The share is read from the largest account down. ASC gives the share covered by the smallest accounts, a different and rarely wanted answer.
> - What if 2 accounts tie on revenue? The account_id tiebreaker pins the order. Without it the crossing row can change between runs.
> - Does the crossing account count? State it as a business choice, then write the predicate that matches the choice you named.
> - Per region? Add PARTITION BY region to both windows, including the empty one, and the denominator becomes the regional total.

> **TIP**
>
> Name the partition decision before the first window: 'the share is across all accounts, so neither window is partitioned'.


<br>

---

## The Silent ROWS vs RANGE Bug

The question is the plain running balance, and the interviewer has put 3 transactions on the same date in the sample. Most candidates write `SUM(amount) OVER (ORDER BY txn_date)` and move on. The query runs, returns 1 row per input row, and the 3 same-day rows all carry the same cumulative figure. Nobody spots it in a 4-row result unless they read the numbers, and the interviewer is waiting to see whether you read them.

The cause is the default frame. When a window has an ORDER BY and no frame clause, the standard fills in `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`, and Postgres, SQL Server, Snowflake and BigQuery all follow it. Under RANGE, CURRENT ROW means every row whose ordering value equals the current row's, so the 3 Jan 1 transactions are peers and the frame for each of them ends after the last peer. Each receives the sum through the end of Jan 1, which is 180.

```sql
-- What you wrote
SUM(amount) OVER (ORDER BY txn_date)

-- What the engine runs
SUM(amount) OVER (
  ORDER BY txn_date
  RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
)
```

https://github.com/user-attachments/assets/2ead8ee3-327d-4d17-bb52-67ab8bb46e84

Watch the frames in the animation. The 4 rows are 100, 50 and 30 on Jan 1 and 20 on Jan 2. `bad_running` reads 180, 180, 180, 200: the RANGE frame for each Jan 1 row reaches to the last Jan 1 peer. `good_running` with the ROWS frame reads 100, 150, 180, 200, stepping 1 row at a time. Both columns agree on Jan 2, because Jan 2 has 1 row and a single row is its own peer group. That agreement is what makes the bug silent: on any date with 1 transaction the 2 frames produce the same number, and a spot check on quiet data passes.

| txn_date | amount | bad_running (RANGE) | good_running (ROWS) |
| --- | --- | --- | --- |
| 2025-01-01 | 100 | 180 | 100 |
| 2025-01-01 | 50 | 180 | 150 |
| 2025-01-01 | 30 | 180 | 180 |
| 2025-01-02 | 20 | 200 | 200 |

| ✓ RANGE, the default | ✗ ROWS, written explicitly |
| --- | --- |
| • CURRENT ROW extends to the last row with the same ORDER BY value<br><br>• Tied rows share 1 cumulative value, the sum through the end of the tie<br><br>• Correct for 'balance as of end of day' shown per transaction<br><br>• Measures distance in the ordering column's units, not in rows | • CURRENT ROW is this physical row and nothing after it<br><br>• Every row gets its own step, even inside a tie<br><br>• Correct for 'balance after each transaction', which is what running balance usually means<br><br>• Needs a tiebreaker in ORDER BY to be deterministic |


<br>

### When RANGE is the right frame

RANGE is correct when the question is "balance as of the end of each day" and the result is still shown per transaction: 3 same-day rows sharing 1 end-of-day balance is the right answer there, and the ties are the point. RANGE is also the frame that measures distance in units of the ordering column rather than in rows, which the trailing-window section uses for calendar-day windows. Say which semantics the question wants, then pick the frame that matches, and the interviewer hears a decision instead of a habit.


<br>

### Ties are a sort problem too

ROWS fixes the collapse and leaves a second problem in place. With ties on txn_date and nothing else in the ORDER BY, the engine is free to put the 100, 50 and 30 in any order, so the intermediate balances 100 and 150 can come back as 50 and 80 on the next run. The fix is a tiebreaker that reflects real order: `ORDER BY txn_date, txn_id` if ids are assigned in sequence, or a timestamp column if the table has one. Intermediate values on tied rows mean something only once the order within the tie is pinned, and saying that unprompted answers the follow-up before it lands.

```sql
SELECT
  account_id,
  txn_date,
  txn_id,
  amount,
  SUM(amount) OVER (
    PARTITION BY account_id
    ORDER BY txn_date, txn_id
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS running_balance
FROM transactions
ORDER BY account_id, txn_date, txn_id
```

> The recovery when she says 'walk me through your output'
>
> - Read the same-date rows first and use the words peer group, which tells her you know the mechanism and not only the symptom.
> - Name the default out loud: an ORDER BY without a frame means RANGE on every engine she is likely to name back.
> - Add ROWS and the tiebreaker column in the same edit, because a ROWS frame on an ambiguous order is a different bug.
> - Point at the single-row date and explain why both versions agree there. That date is why the bug survives a spot check.

> **TIP**
>
> Read the frame as a sentence while typing it: 'rows between unbounded preceding and current row'. Saying it keeps the word ROWS from dropping out of the query, and ROWS is the word the interviewer is waiting for.


<br>

---

## Rolling Windows (7-Day Trailing)

The phrasing is "7-day rolling volume", "trailing 30-day spend" or "a moving average of daily transactions". The shape under all 3 is a window whose lower edge moves with the row instead of staying pinned at the start. The first thing to say is the difference from the running total you have already written: `UNBOUNDED PRECEDING` becomes `6 PRECEDING`, the frame stops growing at 7 rows, and every other clause stays where it was.

| ✓ Running total | ✗ Trailing window |
| --- | --- |
| • Frame: UNBOUNDED PRECEDING to CURRENT ROW<br><br>• Grows by 1 row at each output and never shrinks<br><br>• The last row holds the grand total<br><br>• Answers 'how much so far' | • Frame: 6 PRECEDING to CURRENT ROW<br><br>• Holds 7 rows once it fills, then slides<br><br>• The last row holds only the latest week<br><br>• Answers 'how much lately' |


<br>

### 7 rows and 7 days are different windows

The frame counts rows, and the table is at transaction grain. `ROWS BETWEEN 6 PRECEDING AND CURRENT ROW` over raw transactions sums this transaction and the 6 before it, which on a busy account covers an hour and on a quiet one covers 2 months. The interviewer puts an account with 20 transactions on 1 day into the sample for this reason. The query below is the one that gets written first, and it's wrong for a daily rolling figure.

```sql
SELECT
  account_id,
  txn_date,
  amount,
  SUM(amount) OVER (
    PARTITION BY account_id
    ORDER BY txn_date, txn_id
    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
  ) AS rolling_7d -- 7 rows, not 7 days
FROM transactions
```

The repair is to change the grain before the window: collapse to 1 row per day with GROUP BY, then run the window over days. Each row is now a day, so 6 PRECEDING reaches back 6 rows, and 6 rows are 6 days for as long as every day has a row. The next question tests that last clause.

https://github.com/user-attachments/assets/3b2961b3-15c8-43cc-8253-07b11710a7dc

The animation folds 5 transactions into 4 daily rows and runs a 3-day frame so the arithmetic fits in your head. The 2 Jan 1 rows collapse to 150, then the trailing column reads 150, 120, 320 as the frame fills. Jan 4 has no row, so the Jan 5 frame reaches back to Jan 2 and reads 210 across 4 calendar days. The true 3 calendar days, Jan 3 to Jan 5, sum to 240: Jan 2's -30 dragged the figure low. A missing day pulls in an older day of either sign, so the error runs either way; on mostly positive volume data it usually inflates.

| txn_date | daily_net | trailing_3d | calendar days covered |
| --- | --- | --- | --- |
| 2025-01-01 | 150 | 150 | 1 |
| 2025-01-02 | -30 | 120 | 2 |
| 2025-01-03 | 200 | 320 | 3 |
| 2025-01-05 | 40 | 210 | 4 |


<br>

### Making the frame count days

There are 2 fixes, and the interviewer wants to hear you pick 1 with its cost attached. The first is a date spine: generate every calendar day in the range, LEFT JOIN the daily totals onto it, COALESCE the missing days to 0, and keep the ROWS frame. Every day now has a row, so 6 PRECEDING is 6 calendar days, and the output shows the quiet days as rows, which is usually what the dashboard wanted anyway. The cost is a per-account cross with the calendar: 10,000 accounts over a 90-day quarter is 900,000 rows before the window runs, most of them zeros.

```sql
WITH daily AS (
  SELECT
    account_id,
    txn_date,
    SUM(amount) AS daily_net
  FROM transactions
  GROUP BY account_id, txn_date
),
spine AS (
  SELECT
    a.account_id,
    c.cal_date
  FROM (
    SELECT DISTINCT
      account_id
    FROM transactions
  ) AS a
  CROSS JOIN calendar AS c
  WHERE c.cal_date BETWEEN DATE '2025-01-01'
  AND DATE '2025-03-31'
)

SELECT
  s.account_id,
  s.cal_date,
  COALESCE(d.daily_net, 0) AS daily_net,
  SUM(COALESCE(d.daily_net, 0)) OVER (
    PARTITION BY s.account_id
    ORDER BY s.cal_date
    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
  ) AS trailing_7d
FROM spine AS s
LEFT JOIN daily AS d
  ON d.account_id = s.account_id
    AND d.txn_date = s.cal_date
```

The other fix is a RANGE frame measured in the ordering column's own units. Postgres accepts `RANGE BETWEEN INTERVAL '6 days' PRECEDING AND CURRENT ROW` over a date column, and BigQuery takes the same idea with a numeric ordering such as `UNIX_DATE(txn_date)` and `RANGE BETWEEN 6 PRECEDING AND CURRENT ROW`. The frame reaches back by calendar distance, so a missing day stays missing instead of dragging in an older one, and you need neither a spine nor zero rows. The cost is that quiet days produce no output row, and the syntax differs by engine, so name the engine when you offer it.

> Questions to settle before writing the frame
>
> - Calendar days or business days? A business-day window needs a spine of business days; a RANGE interval can't express it.
> - Does today count? 6 PRECEDING AND CURRENT ROW includes today. 7 PRECEDING AND 1 PRECEDING is the week ending yesterday.
> - What do the first 6 days show? A partial frame. COUNT(\*) OVER with the same frame flags rows with fewer than 7 contributing days.
> - Sum or average? AVG over a spine divides by 7 including zero days; AVG over sparse rows divides by however many rows existed.

- **29 PRECEDING** — frame for a 30-day trailing window

> **TIP**
>
> Count the frame out loud: '6 preceding through current, 7 rows'. Writing 7 PRECEDING for a 7-day window returns 8 days, and that off-by-one is the most common arithmetic slip in this question.


<br>

---

## Resetting Totals with PARTITION BY

"Year-to-date", "month-to-date", "per account", "since the last statement": each is a running total that starts over somewhere. The reset is a partition decision. The frame decides how far back a row can see; the partition decides where the table is cut so that seeing back stops. Nothing in the frame changes when a lifetime balance becomes a monthly one. Say that early, because candidates who believe the reset lives in the frame start writing CASE expressions inside the SUM.

```sql
SELECT
  account_id,
  txn_date,
  amount,
  SUM(amount) OVER (
    PARTITION BY account_id
    ORDER BY txn_date, txn_id
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS lifetime_balance
FROM transactions
```

To restart each month, add the month to the partition and nothing else: `PARTITION BY account_id, DATE_TRUNC('month', txn_date)`. DATE_TRUNC produces 1 value per month, so the engine groups each account's rows by month, sorts each group by date, and runs a fresh running sum inside it. `EXTRACT(YEAR FROM txn_date), EXTRACT(MONTH FROM txn_date)` does the same with 2 columns; the truncated date is shorter and keeps December and January of different years apart without a second key.

https://github.com/user-attachments/assets/ee9a44dd-04fd-4b82-8a99-d2346b8b3332

The animation holds 2 accounts across 2 months. Account A in January reads 500, 380, 460 across Jan 20, Jan 28 and Jan 31; on Feb 1 the partition key changes and the balance restarts at 200, falling to 150 on Feb 5. Account B carries 300 through January, restarts at 150 on Feb 2 and reaches 250 on Feb 10. Nothing from A reaches B and nothing from January reaches February: A's Jan 31 balance of 460 doesn't carry into Feb 1. That's what month-to-date means, and it's also the thing to confirm, because "monthly balance" sometimes means an opening balance carried forward.

| account_id | txn_date | amount | mtd_balance |
| --- | --- | --- | --- |
| A | 2025-01-20 | 500 | 500 |
| A | 2025-01-28 | -120 | 380 |
| A | 2025-01-31 | 80 | 460 |
| A | 2025-02-01 | 200 | 200 |
| A | 2025-02-05 | -50 | 150 |
| B | 2025-01-15 | 300 | 300 |
| B | 2025-02-02 | 150 | 150 |
| B | 2025-02-10 | 100 | 250 |


<br>

### Carrying the opening balance forward

If the business wants each month to open with the previous month's close, the reset is wrong and the lifetime query is the right one, with the month added as a display column rather than a partition key. Ask the single question, "does February start from zero or from where January ended", and write whichever the answer calls for. The 2 queries differ by 1 clause, which is the structural point to make out loud: the partition is the only moving part.


<br>

### Resetting on an event instead of a calendar

The harder variant is "running balance since the last deposit" or "stock on hand since the last stocktake": the reset point is a row in the data rather than a date boundary. There is no column to partition by yet, so build one. A running count of reset events, computed with its own window, gives every row the number of resets seen so far, and that count is the partition key for the balance.

```sql
WITH flagged AS (
  SELECT
    account_id,
    txn_date,
    txn_id,
    amount,
    txn_type,
    SUM(
      CASE
        WHEN txn_type = 'deposit' THEN 1
        ELSE 0
      END
    ) OVER (
      PARTITION BY account_id
      ORDER BY txn_date, txn_id
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS deposit_seq
  FROM transactions
)

SELECT
  account_id,
  txn_date,
  amount,
  deposit_seq,
  SUM(amount) OVER (
    PARTITION BY account_id, deposit_seq
    ORDER BY txn_date, txn_id
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS balance_since_deposit
FROM flagged
```

Two windows over the same ordering, and the second cannot be folded into the first because its partition key is the first window's output. Name the cost: each account's rows are sorted for the first window and, unless the optimizer sees the order carries over, sorted again for the second. The deposit row lands in the new group, so the balance since the deposit includes it. If the deposit should close the previous group instead, the counter takes `ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING` wrapped in `COALESCE(..., 0)`: the first row's frame is empty, its SUM is NULL, and unwrapped it forms a partition of its own.

> Which clause owns which question
>
> - Where does the total restart? PARTITION BY. Lifetime to year-to-date is 1 added partition column.
> - How far back can a row see? The frame. Running to trailing is 1 changed bound.
> - What does 'so far' mean? ORDER BY, with a tiebreaker when the date repeats.
> - Reset on an event? A first window counts the events, and its output becomes the second window's partition key.

> **TIP**
>
> When you switch the partition, say what did not change: 'the frame stays unbounded preceding to current row, the order stays by date, only the partition gained a month'. Listing the constants is how the interviewer hears that you see the structure rather than the syntax.


<br>

---

## Running Count of Distinct Users

"How many distinct users had transacted as of each day" sounds like a running total over a column that already exists. The daily report has a `distinct_users` column, and the move most candidates make is `SUM(distinct_users) OVER (ORDER BY event_date)`. A user who shows up on Monday and again on Tuesday is counted on both days, so the running figure climbs faster than the user base and never stops climbing. Distinct counts are not additive across days, and the interviewer chose this question to hear you say so before any query exists.

| event_date | users seen | daily_distinct | summed daily | true cumulative |
| --- | --- | --- | --- | --- |
| 2024-03-11 | u1, u2 | 2 | 2 | 2 |
| 2024-03-12 | u1, u3 | 2 | 4 | 3 |
| 2024-03-13 | u2, u3, u4 | 3 | 7 | 4 |

By Wednesday the sum reads 7 and the truth is 4. The gap is every repeat visit, and it widens with engagement, so the product that retains its users best is the one whose chart lies hardest. The direct fix, `COUNT(DISTINCT user_id) OVER (ORDER BY event_date)`, doesn't run: Postgres and SQL Server reject DISTINCT inside a window function, and engines that allow DISTINCT in a window do not combine it with an ORDER BY frame. A cumulative distinct count has to be built from a quantity that is additive.


<br>

### Count each user once, on the day they first appeared

A user joins the cumulative count exactly once, on their first day, and never leaves it. So the additive quantity is new users per day: the number of users whose earliest event falls on that date. Take MIN(event_date) per user, count users per first date, and run an ordinary running sum over those counts. Each of the 3 steps is a plain GROUP BY or window, and the result is exact.

```sql
WITH first_seen AS (
  SELECT
    user_id,
    MIN(event_date) AS first_date
  FROM events
  GROUP BY user_id
),
daily_new AS (
  SELECT
    first_date,
    COUNT(*) AS new_users
  FROM first_seen
  GROUP BY first_date
)

SELECT
  first_date,
  new_users,
  SUM(new_users) OVER (
    ORDER BY first_date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS cumulative_users
FROM daily_new
ORDER BY first_date
```

| first_date | new_users | cumulative_users |
| --- | --- | --- |
| 2024-03-11 | 2 | 2 |
| 2024-03-12 | 1 | 3 |
| 2024-03-13 | 1 | 4 |

Walk the sample: u1 and u2 first appear on Monday, u3 on Tuesday, u4 on Wednesday, so new users are 2, 1, 1 and the running count is 2, 3, 4, matching the true column from the first table. Say the invariant out loud, "each user contributes 1 on 1 day only", because it's the sentence that proves the method rather than the syntax, and it is the sentence that lets you answer the follow-ups without a query.


<br>

### 2 follow-ups that test whether you have run this

The first: "a day with no new users is missing from your output". True, and the fix is the date spine from the trailing-window section: LEFT JOIN daily_new onto the calendar, COALESCE new_users to 0, and the running count holds flat across the quiet day instead of skipping it. The second is harder: "now give me distinct users over a trailing 7 days". The first-seen trick doesn't survive this, because a user who was new 10 days ago and active yesterday belongs in today's window, and their first date says nothing about yesterday.

```sql
SELECT
  c.cal_date,
  COUNT(DISTINCT e.user_id) AS distinct_7d
FROM calendar AS c
JOIN events AS e
  ON e.event_date BETWEEN c.cal_date - 6
  AND c.cal_date
WHERE c.cal_date BETWEEN DATE '2024-03-01'
AND DATE '2024-03-31'
GROUP BY c.cal_date
ORDER BY c.cal_date
```

The exact answer is that join: every event lands in 7 daily groups, so the events table is expanded 7-fold before the GROUP BY, exact, and comfortable at tens of millions of rows. Past that, name the approximate route. HyperLogLog sketches of each day's users can be merged across any window, which BigQuery exposes as `HLL_COUNT.MERGE` and Snowflake as `HLL_COMBINE`, with error under 2% at default precision in exchange for a count that is additive again. Offering the exact join first and the sketch second, with the volume at which you would switch, is the shape of the answer that gets scored as experience.

> The sentences that score on this question
>
> - 'Distinct isn't additive across days, so I cannot sum the daily column.'
> - 'Each user contributes 1 on their first day, so new users per day is the additive quantity.'
> - 'A day with no new users needs a spine row, otherwise the chart skips it.'
> - 'A trailing distinct count needs a 7-fold expansion join or a mergeable sketch, and the volume decides which.'

| ✓ Do | ✗ Don't |
| --- | --- |
| • Write the ROWS frame and a tiebreaker column every time, even when the sample has no ties<br><br>• Collapse to daily grain before any window described in days<br><br>• Compute the grand total with an empty OVER () in the same scan as the running total<br><br>• Put resets in PARTITION BY and leave the frame alone<br><br>• Build cumulative distinct counts from first-seen dates, never from summed daily distincts | • Rely on the default frame when the ORDER BY column can repeat<br><br>• Filter a window result in the same SELECT that computes it<br><br>• Write 7 PRECEDING for a 7-day window<br><br>• Treat a missing day as harmless in a ROWS frame<br><br>• Offer COUNT(DISTINCT) OVER (ORDER BY ...) as a fix; the engines reject it |


<br>

---

## Putting It All Together

Quarter-end at a payments company: finance asks for the accounts that carry 80% of settled volume this quarter, a 7-day trailing settlement chart per account for the board deck, month-to-date balances for the reconciliation team, and a cumulative count of distinct accounts that have settled since the quarter opened. All 4 come out of the same transactions table, which has thousands of rows per day sharing a settlement date and whole days where small accounts settle nothing.

- The 80% list sorts accounts by quarterly volume, runs the ordered window beside SUM OVER (), and keeps every row whose predecessor had not crossed 80%, with account_id as the tiebreaker so the list is the same tomorrow.
- Every window in the deck carries an explicit ROWS frame and a txn_id tiebreaker, because thousands of settlements share each date and the RANGE default would hand them 1 shared balance.
- The trailing chart collapses settlements to daily grain and joins each account onto the calendar before the 6 PRECEDING frame, so a quiet day shows as 0 instead of pulling last week into this one.
- Month-to-date balances reuse the lifetime query with DATE_TRUNC('month') added to the partition and nothing else changed, and reconciliation is told that February opens at 0, not at January's close.
- The distinct-account count takes MIN(txn_date) per account within the quarter, counts first dates per day, and runs a running sum over that, so an account settling daily is counted once.


<br>

---

## Key Takeaways

- A running share is a running total divided by an empty-OVER grand total from the same scan; the crossing row stays in when you filter on the share before it.
- ORDER BY without a frame means RANGE, which gives tied rows 1 shared value; write ROWS plus a tiebreaker column every time.
- A trailing window counts rows, so collapse to daily grain first and fill missing days with a spine, or use a RANGE interval that counts calendar distance.
- Resets live in PARTITION BY: the month for month-to-date, a running count of events for 'since the last deposit'; the frame does not move.
- Cumulative distinct users come from first-seen dates summed as new users per day, never from adding daily distinct counts.
