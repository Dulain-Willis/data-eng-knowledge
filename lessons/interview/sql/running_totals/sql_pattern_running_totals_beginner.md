# Running Totals: Beginner

You are 12 minutes into a SQL screen at a neobank. The interviewer pastes 5 rows into the shared editor: `txn_id`, `txn_date`, `amount`. A deposit of 500 on March 1, then 4 more movements through March 14.
"Show me the balance after each of these."
That is the whole prompt. Nothing in it says total, cumulative or running, and nothing says how many rows the answer should have. The first move most candidates make is `SUM(amount)`, which returns 250 on 1 row, the balance today. The interviewer nods and waits, because the question said after each, and 1 number cannot sit after 5 things.
What he is listening for is whether you hear that the answer has 5 rows, each carrying the sum of the rows above it, before you type the first keyword.


<br>

### What you will be able to do

Recognize a running total when the prompt says balance after each or so far, or asks for a figure as of a date or to date, and state the grain before writing a line

Write SUM(amount) OVER (ORDER BY ...) with an explicit ROWS frame and explain what each word of the frame gathers

Tell a request for the grand total beside each row from a request for the total so far, and produce both in 1 SELECT

Verify a running total by hand and with a LAG-based step check, and name which check fails for each common mistake


<br>

---

## "Show Me the Running Balance"

The question comes in the vocabulary of whoever owns the dashboard. A payments team wants the balance after each transaction posts. For a fundraising team it is how much a campaign had raised after every gift, for a warehouse the stock on hand after each receipt and each pick, and for a growth team the number of people signed up as of each day since launch. Every one of these asks for a row plus the sum of the rows before it, and the interviewer is checking whether you hear that shape underneath the nouns before you commit to a query.

- "balance after each transaction" or "running balance": the plainest form, 1 output row per movement
- "raised so far after every donation": the same shape on a gifts table, with a campaign in place of an account
- "as of each day", "to date", "since launch": a date names the moment the total is taken, and a moment is a row
- "stock on hand after each movement": receipts positive, picks negative, and the arithmetic is unchanged
- "how many had signed up by each week": a running count, COUNT with the same window or SUM over a column of 1s


<br>

### The grain is the whole question

`SUM(amount)` with `GROUP BY account_id` collapses the statement to 1 row holding 250, the balance today. A running balance keeps all 5 transaction rows and attaches to each one the sum of every amount dated at or before it. The output has as many rows as the input, and each value depends on the rows above it in date order. So the row count does not change, and the order decides the arithmetic. Say both out loud, because a candidate who writes a correct `GROUP BY` has answered a different question, and the interviewer scores it as not having listened.

SUM with GROUP BY: 1 row

Running balance: 5 rows

The left result answers what account 4471 holds today. The right result answers what it held after each of the 5 transactions, which is what the statement page prints and what the interviewer asked for. The last row on the right carries 250, the same figure as the single row on the left, and that equality is the first check the final section of this lesson runs.

```sql
SELECT
  account_id,
  SUM(amount) AS balance
FROM transactions
GROUP BY account_id
-- account_id | balance
-- 4471       | 250
```


<br>

### What to say before you type

Open with the shape. "This is a running total, so 5 rows come back, and each one shows its own amount plus every amount dated before it." That sentence commits you to the right grain and names the column being added and the order it accumulates along. It also tells the interviewer you have met the pattern before. From there the query is 4 lines, and a working version should be on the screen within a minute or 2. Candidates who type `GROUP BY` first and only rewrite after 1 row comes back lose 3 or 4 minutes of a 25-minute screen, and the follow-ups about the frame and about the grand total, where the grade is decided, arrive with no time left to answer them well.

| ✓ Opens with GROUP BY | ✗ Names the shape first |
| --- | --- |
| • Gets 1 row back and has to be told the question wanted 5<br><br>• Rewrites under time pressure and forgets the ORDER BY inside the window<br><br>• Reaches the frame follow-up with 8 minutes left instead of 15<br><br>• Never gets asked how to prove the numbers, which is the part that shows understanding | • Says "running total, 1 row per transaction, summed in date order" inside 20 seconds<br><br>• Says which column gets summed in which order before touching the keyboard, frame included<br><br>• Has 5 correct balances on screen inside 2 minutes<br><br>• Spends the saved time on the frame and the grand total, where the score is set |

> Say these 4 things before the first keyword
>
> - Grain: 1 output row per transaction, so the row count matches the input
> - Column: amount, which already stores withdrawals as negative numbers, so a plain SUM is the balance
> - Order: txn_date, since a balance after March 7 means every amount dated March 7 or earlier
> - Start: the account opened on March 1 at 0, so no opening balance has to be added to each row

Interviewers pick this question because the table fits on 1 screen, a correct answer is short, and the follow-ups give the rest of the slot somewhere to go: which rows the sum sees on a given row, what changes if the `ORDER BY` is removed, how you would prove the 5 numbers.

The pull toward `GROUP BY` comes from the word total, since most earlier SQL practice used total to mean collapse the rows. Listen instead for the word that names a moment: after, so far, as of, to date, since launch. A moment is a row, and a total taken at a row is a running total. The signature reads the same on a transactions table as on a donations table or an inventory ledger.


<br>

---

## SUM OVER (ORDER BY ...) Basics

Start from the aggregate you would type without thinking. `SUM(amount)` returns 1 row, 250. Append `OVER ()` and the same 250 appears on each of the 5 rows, because a window with nothing inside the parentheses spans the whole table. Put `ORDER BY txn_date` inside them and the value begins to grow: 500 on March 1, 380 on March 3, 630 on March 7. The ordering is the entire change. It tells the engine which rows count as earlier than the row being computed, and a sum taken over the earlier rows and this one is a total so far.

```sql
-- Balance after each transaction, accumulated in date order
SELECT
  txn_id,
  txn_date,
  amount,
  SUM(amount) OVER (
    ORDER BY txn_date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS running_balance
FROM transactions
ORDER BY txn_date
```

SUM(amount) is the quantity being added up. OVER turns the aggregate into a per-row calculation that keeps every input row instead of collapsing them. ORDER BY txn_date sorts the rows inside the window so the engine knows which ones precede the current one. ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW states the span of rows added for each row, from the first through this one, and the next section takes it apart word by word. AS running_balance names the column after what the number means, which is part of the answer: a column called sum tells the dashboard reader nothing.

https://github.com/user-attachments/assets/dade47b3-79b3-4178-bcb1-ef42b6991c04

The rows are stored out of date order, with transaction 3 first and transaction 5 third, and the first thing the engine does is sort them by `txn_date`. Then it walks down the sorted list: 500, then 500 plus negative 120 gives 380, then plus 250 gives 630, then minus 80 gives 550, then minus 300 gives 250. The last value matches the plain `SUM(amount)`, as it must, since the last row's span is every row in the table. Narrate it in those words while the interviewer watches: the engine sorts before it accumulates. The first row's balance is its own amount because nothing precedes it.


<br>

### Each ORDER BY has its own job

The query has 2 `ORDER BY` clauses, and they do different work. The one inside `OVER` decides the arithmetic: which rows are earlier, and therefore which amounts each sum includes. The one at the end decides display order only. Delete the last line and every `running_balance` value stays the same, but the rows can come back in whatever order the engine found convenient, which on a dashboard looks like a broken running total even though every number is right. "What happens if I remove the final ORDER BY" is a common probe, and the complete answer is: the values do not change, the row order becomes undefined, so I keep it for the reader's sake.


<br>

### The query the window replaces

```sql
-- The pre-window way: every row joined to every row at or before it
SELECT
  t.txn_date,
  t.amount,
  SUM(e.amount) AS running_balance
FROM transactions AS t
JOIN transactions AS e
  ON e.txn_date <= t.txn_date
GROUP BY t.txn_id, t.txn_date, t.amount
ORDER BY t.txn_date
```

"Could you do this without window functions" is the follow-up for a candidate who typed the window too quickly, and the self-join is the answer. Each row joins to every row dated at or before it and sums the matches. However the engine finds those matches, it has to produce and add every one of them: 15 pairs for 5 rows, about 500,000 for a 1,000-row statement, growing with the square of the row count. The window produces the same 5 balances from 1 sort and 1 pass. Naming the cost is what the interviewer wants to hear, because it shows you know why the window exists rather than only how to spell it.

- "Remove ORDER BY from inside OVER?" Every row reads 250, the whole-table sum, since nothing marks rows as earlier
- "What if I remove the ORDER BY at the end?" Values unchanged, display order undefined
- "Can I use COUNT or AVG?" Same window: COUNT(\*) in place of SUM(amount) gives 1, 2, 3, 4, 5
- "Does the window run before or after WHERE?" After: a filtered row never enters any sum, as the last section shows

*SUM ... OVER (ORDER BY ...) with these frame keywords runs unchanged on PostgreSQL, MySQL 8, SQL Server, BigQuery, Snowflake and Spark SQL, which covers every major engine, so the query you practise here is the one you will type in the room.*

> **TIP**
>
> Type the window as 1 motion the moment you type OVER: the ordering, then the frame, then the closing parenthesis. Candidates who plan to add the frame later forget it under time pressure, and the query that ships depends on a default the next section describes.


<br>

---

## What a Window Frame Actually Is

The frame is the set of rows the `SUM` adds together to produce the value on 1 output row, and the engine assembles a fresh one for every row it computes. On the March 7 row the frame holds 3 rows, March 7 and the 2 dated before it, so the value is 500 minus 120 plus 250, which is 630. On the March 10 row the frame has grown by 1 row and the value is 550. Nothing else about the query changes from row to row: the column and the sort stay fixed while the frame gets 1 row longer each time. A candidate who can list the rows in the frame for any row the interviewer points at has understood running totals, and the rest is spelling.

| Current row | Rows in the frame | Amounts added | running_balance |
| --- | --- | --- | --- |
| 2024-03-01 | March 1 | 500 | 500 |
| 2024-03-03 | March 1, 3 | 500 - 120 | 380 |
| 2024-03-07 | March 1, 3, 7 | 500 - 120 + 250 | 630 |
| 2024-03-10 | March 1, 3, 7, 10 | 500 - 120 + 250 - 80 | 550 |
| 2024-03-14 | March 1, 3, 7, 10, 14 | 500 - 120 + 250 - 80 - 300 | 250 |


<br>

### Reading the frame clause word by word

> ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
>
> - ROWS: count the frame by position in the sorted order, 1 row at a time
> - UNBOUNDED PRECEDING: the frame starts at the first row of the ordered set, however far back that is
> - CURRENT ROW: the frame stops at the row being computed, and includes it
> - BETWEEN ... AND: the 2 edges, start then end, both inclusive

`PRECEDING` and `FOLLOWING` measure from the current row outward, and `UNBOUNDED` means as far as the sorted data reaches in that direction. A frame of `ROWS BETWEEN 1 PRECEDING AND CURRENT ROW` would hold only the current row and the one before it. That column is a 2-row moving sum, 380 on March 3 and then 130 on March 7, which answers a different question. For a balance after each transaction the start edge sits at the first row no matter how far down the table you are, so `UNBOUNDED PRECEDING` is the only correct start.


<br>

### 3 ways to write the window, 3 results

| OVER clause | Frame on the March 7 row | Value on March 7 |
| --- | --- | --- |
| OVER () | all 5 rows | 250, the grand total |
| OVER (ORDER BY txn_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) | March 1, March 3, March 7 | 630, the total so far |
| OVER (ORDER BY txn_date) | default frame: every row whose date is at or before March 7 | 630 here, because no 2 rows share a date |

When `ORDER BY` is present and no frame is written, the SQL standard supplies one: `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`. `RANGE` gathers rows by the value of the ordering column, so every row carrying the current row's date is inside the frame at once. On this statement no 2 rows share a date, so the `RANGE` column and the `ROWS` column read identically, 500 through 250. The day the table gains 2 transactions on 1 date they disagree, and that disagreement gets a section of its own in the intermediate lesson. Writing `ROWS` out stops tied rows sharing 1 value, but it does not decide which tied row comes first, so end the ordering on a unique column: `ORDER BY txn_date, txn_id`. Saying "ROWS, written explicitly, with txn_id as the tiebreaker" tells the interviewer you know the default exists and that a sort on dates alone is not unique.




<br>

### The frame questions the interviewer asks

"Which rows does the sum see on the fourth row?" Answer with the rows and the arithmetic: all 4 from March 1 through March 10, so 500 minus 120 plus 250 minus 80, which is 550. "Why UNBOUNDED?" Because the balance after any transaction depends on every earlier one back to the account's opening, so the frame can never start later than row 1. "Why end at CURRENT ROW?" Because the question says after, and after includes the transaction itself; an end edge of `1 PRECEDING` would give the balance before each transaction, NULL on the first row since its frame is empty, then 500, 380, 630, 550, which is a legitimate column and a different question. Every one of these answers names specific rows.

The engine sorts the rows once, then walks them holding an accumulator and adds each new row into it as the frame's end edge advances, so a running total over 1 million rows costs 1 sort and 1 pass. The frame's start edge never moves, which is what makes that single pass possible; a frame whose start edge slides needs the engine to subtract rows as well, a cost the intermediate lesson's rolling windows pay. The self-join of the previous section examines every pair instead, which is why the window scales and the join does not.

> **TIP**
>
> When asked what a frame is, point at a row and list the rows it gathers, with their amounts. An abstract definition is scored lower than "on March 10 the frame is these 4 rows and they add to 550".


<br>

---

## Cumulative vs Grand Total

These 2 requests sound alike and want different columns. "Show each transaction with the balance after it" wants a number that changes down the page. "Show each transaction with the month's net change beside it" wants the same number, 250, on all 5 rows, so a reader can see how large each movement is against the month. Both are `SUM(amount) OVER`, both keep 5 rows, and the only difference in the SQL is whether `ORDER BY txn_date` appears inside the `OVER`. With it the frame grows row by row; without it the frame is the whole table every time, and the whole table summed is the grand total.

```sql
-- Both columns in 1 SELECT: the constant and the one that grows
SELECT
  txn_date,
  amount,
  SUM(amount) OVER () AS grand_total,
  SUM(amount) OVER (
    ORDER BY txn_date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS balance_so_far
FROM transactions
ORDER BY txn_date
```

https://github.com/user-attachments/assets/729898a3-b7cb-471f-b1d5-41b454c8e450

Watch the 2 columns fill. `grand_total` reads 250 on every row because its window has no ordering and so no notion of earlier, and the frame it gathers is all 5 rows each time. `balance_so_far` reads 500, 380, 630, 550, 250, growing with each row's frame. The 2 columns meet on the last row, where the total so far has caught up with everything, and that meeting point is a property you can state in the room: the final value of a running total always equals the grand total of the same rows.


<br>

### Hearing which one the question wants

| ✓ Words that want the grand total | ✗ Words that want the total so far |
| --- | --- |
| • "beside each row", "next to each gift"<br><br>• "the month's total", "the campaign total", "overall"<br><br>• "compared with the whole period"<br><br>• "what share of the total is this row" | • "after each", "following each"<br><br>• "so far", "to date", "as of"<br><br>• "accumulated since", "since launch"<br><br>• "the first day it passed 10,000" |

| Request as the interviewer says it | Column wanted | ORDER BY inside OVER? |
| --- | --- | --- |
| balance after each transaction | total so far | yes |
| each gift next to the campaign total | grand total | no |
| stock on hand as of each movement | total so far | yes |
| each day's signups with the launch total beside it | grand total | no |
| revenue to date on each row | total so far | yes |

The test is whether the number should change as you read down the rows. A request that describes a moment, after this row, as of this date, so far, wants a figure that moves, and that figure needs an ordering. A request that describes the whole period, the month's total, the campaign total, the overall figure, wants 1 number repeated, and an ordering would be a mistake because it turns the constant into a staircase. Ask when the wording leaves it open: "Do you want the balance as of each row, or this month's total shown beside each row?" The question costs 5 seconds and prevents the wrong column.


<br>

### The grand total beside each row without a join

```sql
-- The pre-window way: a scalar subquery evaluated once, copied onto every row
SELECT
  txn_date,
  amount,
  (
    SELECT
      SUM(amount)
    FROM transactions
  ) AS grand_total
FROM transactions
ORDER BY txn_date
```

Before window functions the grand total beside each row came from a scalar subquery or a join back to a `GROUP BY` result, and both still work. The subquery runs once and its single value is copied onto each row; the join needs a grouping key and loses rows if any key fails to match. `SUM(amount) OVER ()` does the same work in 1 pass with no second scan and no join condition to get wrong, and it sits in the same `SELECT` as the growing column, as the earlier code shows. In the room, write the window form and offer the subquery form if asked for an alternative; naming both shows you know what the window replaced.

> **TIP**
>
> Name the aliases after what they hold: grand_total for the constant and balance_so_far for the growing one. A column called total that changes on every row sends the dashboard reader back to the query to find out which it is.

*The follow-up that usually comes next divides the growing column by the constant one to get the share of the month reached after each row, and the intermediate lesson opens with it; everything that query needs is already on the row.*


<br>

---

## Checking the Total Row by Row

"How do you know that is right?" arrives the moment the 5 balances appear, and the answer is a check you perform out loud on the rows in front of you. Start at 0. Add 500: 500, matches row 1. Subtract 120: 380, matches row 2. Add 250: 630, matches. Subtract 80: 550, matches. Subtract 300: 250, matches. That 250 is also what `SUM(amount)` returns for the whole table. The 5 rows take 30 seconds, and the interviewer hears you verify the numbers instead of hoping. On a real statement with thousands of rows the same check becomes a query, and both forms are worth knowing.

| txn_date | balance before | amount | balance after, by hand | running_balance from query |
| --- | --- | --- | --- | --- |
| 2024-03-01 | 0 | 500 | 500 | 500 |
| 2024-03-03 | 500 | -120 | 380 | 380 |
| 2024-03-07 | 380 | 250 | 630 | 630 |
| 2024-03-10 | 630 | -80 | 550 | 550 |
| 2024-03-14 | 550 | -300 | 250 | 250 |


<br>

### 4 checks, in the order to run them

- Row count: the output has 5 rows because the input has 5. A different count means a filter or a join changed the grain
- First row: its balance equals its own amount, 500, because nothing precedes it
- Last row: its balance equals SUM(amount) over the whole table, 250
- Every step: each balance minus the one before equals that row's amount, which catches a missing ORDER BY

```sql
WITH balances AS (
  SELECT
    txn_date,
    amount,
    SUM(amount) OVER (
      ORDER BY txn_date
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_balance
  FROM transactions
),
steps AS (
  SELECT
    txn_date,
    amount,
    running_balance,
    running_balance - LAG(running_balance, 1, 0) OVER (
      ORDER BY txn_date
    ) AS step
  FROM balances
)

SELECT
  txn_date,
  amount,
  running_balance,
  step
FROM steps
WHERE step <> amount
```

The step check is the strongest of the 4 because it fails on the most common mistake. Remove `ORDER BY txn_date` from the window and every row reads 250; the first step is then 250 against an amount of 500, and the check query returns 5 rows instead of 0. It also fails when the sort key is wrong: order the window by `txn_id` descending and the balances come out as 250, negative 250, negative 130, negative 380, negative 300 read in date order, and the steps disagree with the amounts on every row. A join that fans out fails 2 checks at once: the output has more than 5 rows, and the last row moves away from the closing 250 in the direction of the duplicated amounts, up for a doubled deposit and down for a doubled withdrawal. The row-count check also catches a filter that removed a transaction.

| Symptom | Check that fails | Likely cause |
| --- | --- | --- |
| Every row shows 250 | every step | ORDER BY missing from inside OVER |
| Last row off the closing 250, more rows than transactions | row count, last row | a join fanned rows out, so some amounts were added twice |
| 4 rows back instead of 5 | row count | a WHERE removed a transaction before the sum ran |
| Values right, rows in random order | none | display ORDER BY missing; the numbers are correct |


<br>

### Where the filter sits

```sql
SELECT
  txn_date,
  amount,
  SUM(amount) OVER (
    ORDER BY txn_date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS running_balance
FROM transactions
WHERE amount < 0
-- 2024-03-03 | -120 | -120
-- 2024-03-10 |  -80 | -200
-- 2024-03-14 | -300 | -500
```

`WHERE` runs before the window, so a row the filter removes never enters anyone's frame. Asked for the balance after each withdrawal, a candidate who filters to `amount < 0` gets negative 120 on the first withdrawal and negative 200 on the second, then negative 500 on the last, because the deposits that fund the account were removed before the sum ran. The true balances after those withdrawals are 380 and 550, then 250 after the last one. The fix is a CTE that computes the running total over every row; filter its result afterward. The row-count check and the last-row check both catch the wrong version: 3 rows instead of 5, and a closing figure of negative 500 against a statement that closes at 250.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Say the grain first: 1 row out per row in, each carrying the sum of the rows at or before it<br><br>• Type the ordering and an explicit ROWS frame together with OVER, ending the ordering on a unique column<br><br>• Name the alias after the meaning: running_balance, balance_so_far, grand_total<br><br>• Check the last row against the plain SUM before the interviewer asks<br><br>• Compute the running total over all rows in a CTE, then filter the result | • Open with GROUP BY when the question names a moment: after, so far, as of<br><br>• Leave the frame to the default, or order by date alone when 2 rows can share a date<br><br>• Put a WHERE on the same query as the window when the filtered rows belong in the sum<br><br>• Call a column total when it changes on every row<br><br>• Present 5 numbers without saying how you know they are right |

Say the check before you are asked. "The last row is 250, which matches the plain sum, and each step matches its amount, so the ordering is right." That sentence closes the question, and in a screen it is usually where the conversation turns from whether you can write SQL to what else you can be asked.


<br>

---

## Putting It All Together

A neobank's mobile app shows a statement page for each account: every card swipe and deposit of the month, the balance after each one, and a header that reads the month's net change. A customer reports that the balance column shows 250 on every line of March, and the ticket lands with the data engineer who owns the query.

- The statement page is a running total by definition: 1 row per transaction, each carrying the sum of the amounts at or before it, which is the shape section 0 taught you to hear.
- A column reading 250 on every line is the grand total, which means the window has lost its ORDER BY, the single clause section 1 named as what makes a total grow.
- The header's net change is SUM(amount) OVER () and belongs on every row unchanged, so the same SELECT carries both the constant and the growing column, as section 3 showed.
- The repaired query writes the frame as ROWS from the first row through the current one, so section 2's rows-gathered-per-row reasoning explains each printed balance.
- Before the fix ships, the step check from section 4 runs over the account: 0 rows back means every balance moves by exactly its transaction's amount.


<br>

---

## Key Takeaways

- A balance after each row is a running total: the output keeps every input row, and each value is the sum of the rows at or before it.
- ORDER BY inside OVER is what makes a total grow; without it the frame is the whole table and every row shows the grand total.
- Write the frame out: ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW gathers from the first row through this one, by position.
- Moment words (after, so far, as of, to date) want the total so far; period words (the month's total, the overall figure) want the constant.
- Prove it: first row equals its amount, last row equals the plain SUM, each step equals its row's amount, row count unchanged.
