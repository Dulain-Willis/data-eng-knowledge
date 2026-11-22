# Gaps and Islands: Beginner

You are 20 minutes into a SQL screen at a fitness app. The interviewer shares a table on screen: `user_id`, `workout_date`, roughly 3 million rows.
"Find each user's longest run of consecutive workout days."
Then he waits. The sample shows one user with dates March 1, 2, 3, 5 and 6, and it reads like a sorting problem. Most candidates start typing a self-join that matches each row to the day before it, then stall on turning those matches into groups, or a recursive CTE that walks forward 1 day at a time. Both look fine on 5 rows, and the cost only appears at 3 million. What the question never says is that SQL has no operator for "consecutive", so a run has to be turned into a column that a `GROUP BY` can see. He is listening for whether you can name that column before you write a line.


<br>

### What you will be able to do

Hear a question about streaks or contiguous ranges, however it is worded, and name it as gaps and islands within 10 seconds

Before writing SQL, state which column is the sequence and what step it should advance by, and decide whether a 1-row island counts

Number rows with ROW_NUMBER() partitioned by entity and ordered by the sequence, and say why the partition is mandatory

Explain in 2 sentences why value minus row number is constant along a run and changes at every gap

Trace a 9-row sketch by hand to find the islands and the awkward cases before touching the keyboard


<br>

---

## Spotting a Question About Runs

The question rarely contains the word "island". It arrives as "find the longest streak of login days per user", or "show me each stretch of nights the room was booked", or "which invoice numbers are present in contiguous ranges". The data is 1 row per event or per value, and the answer is 1 row per unbroken stretch, which means the query has to collapse many rows into 1 without any column that says which rows belong together.

- "longest streak of consecutive days"
- "contiguous ranges of ids"
- "unbroken sequence of readings"
- "start and end of each run of"
- "how many separate periods was the account active"
- "stretches where the signal never dropped"


<br>

### Every phrasing depends on the neighbouring rows

Each of these phrasings asks about a group of rows that is defined by what the rows next to it look like. A user's 3-day streak is a streak because the 3 dates sit side by side with nothing missing between them. Remove the middle date and the same 2 remaining rows become 2 streaks of 1. That dependence on neighbours is the mark of the pattern: no single row carries enough information to say which group it belongs to, so a `WHERE` clause cannot find the group and a plain `GROUP BY` has nothing to group on.


<br>

### The operator SQL does not have

SQL has no keyword for "consecutive". `GROUP BY` collapses rows that share a value in a column, and a table of dates has no column whose value is shared along a streak. The database sees 1, 2, 3, 7, 8, 12 as 6 numbers with no idea that the first 3 belong together. The whole pattern is the work of inventing that column: a value that is identical for every row in a run and different for rows in other runs, computed from the order of the rows, so that an ordinary `GROUP BY` can finish the job.

That is why the self-join and the recursive CTE feel natural and go wrong. Joining each login to the same user's previous day is an equi-join, which the engine runs as a hash or merge join in close to linear time, but it only flags the rows where a streak starts or stops. Turning those flags into groups needs a second step: an inequality self-join that compares each row with every earlier row of the same user, around 500,000 comparisons for a user with 1,000 logins, or a recursive walk that takes 1 iteration per day of the longest streak. Both return the right answer on the 5-row sample, and the sample never shows you the cost.


<br>

### The sentence to say before typing

Say 1 sentence before you touch the keyboard, because the interviewer is scoring recognition first and syntax second. It names the pattern and the tool along with why the tool works, and it takes roughly 10 seconds to say:

> The 10-second opening
>
> - "This is a gaps-and-islands question: the rows form runs, and I need a group key that is shared by every row in a run."
> - "I will number each user's rows with `ROW_NUMBER()` ordered by the date."
> - "Then I subtract the row number from the date, which gives a value that holds still inside a run."
> - "Inside a run both climb by 1 per row, so the difference holds; at a gap the date jumps and the difference changes."

| ✓ The answer that stalls | ✗ The answer that gets scored |
| --- | --- |
| • Writes a recursive CTE that walks the table 1 row at a time<br><br>• Writes a correlated subquery comparing each row to its neighbours<br><br>• Looks for a built-in consecutive-run function that does not exist<br><br>• Spends 10 minutes unable to express the grouping and runs out of time | • Names the pattern out loud before the first keystroke<br><br>• Numbers each user's rows with ROW_NUMBER(), restarting per user and sorted by date<br><br>• Computes value minus row number and groups by that difference<br><br>• Gives the 2-sentence proof: lockstep inside a run, divergence at a gap |


<br>

### Where the same question lives at work

Gaps-and-islands queries sit under every product dashboard that touches sequential events: engagement streaks (consecutive days a user logged in), retention (unbroken weeks of activity), billing (contiguous months of an active subscription), inventory (continuous nights a room could be sold), fleet operations (consecutive days a vehicle was in service) and monitoring (unbroken stretches of a passing health check). That spread is why the pattern appears in entry-level data engineering loops even though the technique feels advanced: an engineer who cannot write it is locked out of a whole class of business questions.


<br>

---

## What Counts as a Gap vs an Island

An island is a maximal stretch of rows with no break between any 2 neighbours. A gap is the empty space between 2 islands: the values that would have continued the sequence and are missing. In the sequence 1, 2, 3, 7, 8, 12 there are 3 islands and 2 gaps, and the gaps are made of values that appear in no row at all, which is the part that trips people up. You cannot `SELECT` a gap, because the gap has no rows; the only thing the query can do is find where each island stops.

| n | next value present | what sits between | verdict |
| --- | --- | --- | --- |
| 1 | 2 | nothing | island continues |
| 2 | 3 | nothing | island continues |
| 3 | 7 | 4, 5, 6 missing | island ends, gap of 3 |
| 7 | 8 | nothing | island continues |
| 8 | 12 | 9, 10, 11 missing | island ends, gap of 3 |
| 12 | none | end of data | island of 1 row |


<br>

### The question defines the break

What counts as a break is set by the question, and the first job is to pull that definition out of the wording. "Consecutive days" means the expected step is 1 day and anything larger is a break. "Contiguous invoice numbers" means the step is 1. "Consecutive hours of readings" means 1 hour. The difference trick in section 3 works for any sequence that is supposed to step by a fixed amount, because it subtracts the position from the value, and a fixed step is what makes that subtraction land on the same number row after row.

| question wording | sequence column | expected step | a break is |
| --- | --- | --- | --- |
| longest login streak | login_date | 1 day | a calendar day with no login |
| contiguous invoice ranges | invoice_no | 1 | a missing number |
| unbroken hourly readings | reading_hour | 1 hour | an hour with no reading |
| consecutive booked nights | night | 1 day | an unbooked night |

Some questions define a break by something other than a missing value: a status that changes from active to cancelled, or 2 events more than 30 minutes apart counting as separate sessions. Those are the same family and need a different way of building the island key, which later lessons in this track cover. Here, say the step back to the interviewer as a question: "so 2 logins on the same day collapse to 1 day, and a day with no login breaks the streak?" That question costs 5 seconds and prevents the most common wrong answer, which is a correct query built on a definition the interviewer never gave.


<br>

### Counting what is missing

Count what the question asks for. An island's length is the number of rows in it, so the island from 7 to 8 has length 2. A gap's size is the number of values skipped, which is the next value minus the current value minus 1, so the gap between 3 and 7 is 3 missing values and not 4. Candidates who report the gap as 4 have counted the fence posts instead of the fence, and an interviewer who put a gap of 3 in the sample is checking for exactly that.


<br>

### Islands of 1 and the edges of the data

A row with no neighbour on either side is an island of its own, with length 1. The value 12 in the sequence above is one, and a user who logged in once has a streak of 1. Whether the question wants those rows depends on who is asking: a leaderboard of streaks includes them, a report of "streaks worth celebrating" may set a minimum of 2 or 3. The edges of the data are not gaps. Nothing is missing before the first row or after the last one, because there is no island on the far side for a gap to sit between, so a sequence that starts at 7 has no gap from 1 to 6 and a user whose last login was in March has no gap running up to today.

> **TIP**
>
> Ask "does a single day count as a streak of 1?" before writing. The answer decides whether you add `HAVING COUNT(*) > 1`, and an interviewer hears the question as evidence that you know the output row count depends on it.


<br>

### Saying the definition out loud

A strong answer states the 3 facts the definition pins down before any SQL: what the sequence column is, what the expected step is, and whether islands of 1 belong in the output. "The sequence is `login_date`, the step is 1 day, and a single login is a streak of 1 unless you tell me otherwise." Every later choice, including the exact arithmetic of the group key and the aggregates at the end, follows from those 3 facts, so stating them first lets the interviewer check your plan before you commit to it.

> Island or gap: the 3 facts to pin down
>
> - Sequence column: which column the rows are in order by (a date, an id, an hour).
> - Expected step: the distance between neighbours when nothing is missing (1, 1 day, 1 hour).
> - Minimum island: whether 1 row alone counts, which decides if the output needs a `HAVING` filter.


<br>

---

## Ordering Rows Before Grouping

A table has no order. The rows of `logins` come back in whatever order the storage engine finds convenient, and 2 runs of the same query can return them differently. A run is a statement about which row comes after which, so until the query has imposed an order on the rows inside each user there are no runs to find: there is a bag of dates. `ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY login_date)` is the step that turns the bag into a sequence, and every later step depends on it being right.

| user_id | login_date |
| --- | --- |
| bob | 2024-03-02 |
| alice | 2024-03-05 |
| alice | 2024-03-01 |
| bob | 2024-03-03 |
| alice | 2024-03-03 |
| alice | 2024-03-02 |

Alice logged in from March 1 to March 3 and again on March 5, and Bob on March 2 and 3. Read as stored, nothing about these 6 rows says that Alice's first 3 dates belong together, and a row number handed out in storage order would mean nothing. The pattern needs the rows ordered by date within each user, and the query has to build that order itself.


<br>

### Numbering across users is the bug

```sql
-- Wrong: 1 numbering across everyone
SELECT
  user_id,
  login_date,
  ROW_NUMBER() OVER (ORDER BY login_date) AS rn
FROM logins;

-- Right: numbering restarts for each user
SELECT
  user_id,
  login_date,
  ROW_NUMBER() OVER (
    PARTITION BY user_id
    ORDER BY login_date
  ) AS rn
FROM logins;
```

One numbering across users

Numbering restarts per user

On the left, Alice's March 3 login carries row number 4 because Bob's March 2 login took number 3. Her dates go up by 1 each time, but her row numbers skip from 2 to 4, so when section 3 subtracts one from the other the difference changes in the middle of a real streak, splitting it in 2. The query runs without an error and returns a wrong answer, which is the worst kind of bug in an interview because nothing prompts you to look for it. On the right, each user's numbering starts at 1 and climbs by 1 per login, which is the property the trick needs.

> **TIP**
>
> Say "the `PARTITION BY` is mandatory" as you write it. An interviewer who has watched this query fail knows the missing partition is the number 1 cause, and hearing you name it closes that rubric line.


<br>

### What ORDER BY inside OVER promises

The `ORDER BY` inside the `OVER` clause is the only one that matters to the run. It tells the engine the sequence the row numbers follow, within each partition, independent of how the rows are stored and of any `ORDER BY` at the end of the query. The final `ORDER BY` arranges the output for a human and has no effect on the numbering. Two different orders can appear in 1 query without conflict: number by `login_date`, then sort the result by `streak_length DESC`.

The direction matters too. Number ascending by the sequence column, so that the row number and the value climb together. Numbering descending while the value climbs makes the difference change on every row, and every row becomes its own island. If a question asks for streaks that are still running today, keep the ascending numbering and pick out the island whose end is today's date afterwards, rather than reversing the window.

The window runs after the `WHERE` clause, so a filter such as only mobile logins is applied before the numbering and the row numbers count only the kept rows. Apply the same filter in an outer query after the numbering and the removed rows take their row numbers with them: if Alice's March 2 login came from a laptop, March 1 keeps row number 1 and March 3 keeps row number 3, both give the same difference, and 2 days that are not consecutive merge into 1 streak. The row number skips exactly where the date skips, which hides the gap, so every filter on which rows take part belongs before the window, in the same ranked stage.

> Order checklist
>
> - `PARTITION BY` the entity whose runs you want: user, room, sensor, account.
> - `ORDER BY` the sequence column ascending inside `OVER`.
> - Treat the outer `ORDER BY` as display only; it cannot repair a wrong window order.
> - Put every row filter before the window so the numbering has no holes.

When the interviewer asks "what if 2 users log in on the same date", the answer is that the partition keeps them apart: Alice's March 2 and Bob's March 2 each take the number their own sequence gives them. The trouble starts when a single user has 2 rows on the same date, which the next lesson in this track covers in full. Here, say that you would use `SELECT DISTINCT user_id, login_date` to reduce the table to 1 row per user per day before numbering, then move on.


<br>

---

## Why the Difference Trick Works

With the rows numbered inside each entity, the island key is 1 subtraction. Take the sequence value and subtract the row number. Along an unbroken run the value climbs by 1 per row and the row number climbs by 1 per row, so the 2 move in lockstep and their difference holds still. At a gap the value jumps by more than 1 while the row number still climbs by 1, so the difference jumps by the size of the gap and never returns to its old value, because both columns only ever increase.

https://github.com/user-attachments/assets/a97928c6-19bf-4ae7-9360-2cb55a2fbfb3

Watch the 6 rows of `sequence_data`, which hold 1 through 3, then jump to 7 and 8, then to 12. Row numbers land as 1 through 6. `n - rn` gives 0 on each of the first 3 rows and 3 on the rows for 7 and 8; the row for 12 gets 6. That is 3 distinct differences and 3 islands. The gap from 3 to 7 skipped 3 values and the difference moved from 0 to 3; the gap from 8 to 12 skipped 3 more and it moved from 3 to 6. The size of each jump in the key equals the number of missing values, which is a useful check when you trace by hand.


<br>

### The proof in 2 sentences

> Say this when asked why it works
>
> Inside a run, each row's value is exactly 1 more than the previous row's, and its row number is also exactly 1 more, so the difference between them does not change. At a gap, the value increases by more than 1 while the row number increases by exactly 1, so the difference increases and stays increased, because neither column ever goes down.

That paragraph is the rubric item. An interviewer asks "why does subtracting the row number group the runs?" on almost every loop where this pattern appears, and candidates who memorised the query without the argument stall here. The second sentence matters most: the difference can never come back to an earlier value, so 2 different runs never share a key within the same partition.


<br>

### The whole query

```sql
-- Find runs of consecutive integers in a single column
WITH ranked AS (
  SELECT
    n,
    ROW_NUMBER() OVER (ORDER BY n) AS rn
  FROM sequence_data
),
grouped AS (
  SELECT
    n,
    n - rn AS island_id
  FROM ranked
)

SELECT
  island_id,
  MIN(n) AS island_start,
  MAX(n) AS island_end,
  COUNT(*) AS island_length
FROM grouped
GROUP BY island_id
ORDER BY island_start
```

| island_id | island_start | island_end | island_length |
| --- | --- | --- | --- |
| 0 | 1 | 3 | 3 |
| 3 | 7 | 8 | 2 |
| 6 | 12 | 12 | 1 |

Read the CTEs top down and they name the steps: `ranked` numbers the rows, `grouped` computes the key, and the final `SELECT` collapses each key into 1 row with `MIN` for the start, `MAX` for the end and `COUNT(*)` for the length. Point at `island_id` when you trace it and say "this column is identical for every row in a run, which is what lets `GROUP BY` fold the run into 1 row". The output has as many rows as there are islands, 3 here, never as many as the input.

`COUNT(*)` and `MAX(n) - MIN(n) + 1` both give 3 for the first island, and the interviewer may ask which you would use. On clean data they always agree, so pick `COUNT(*)` because it reads as "rows in the run". Neither one catches a duplicated value: in 1, 2, 2, 3 the second 2 takes its own row number, the differences come out 0, 0, -1, -1, and the run splits in 2, with an island from 1 to 2 overlapping one from 2 to 3. Count and span both say 2 for each. The defence is the `SELECT DISTINCT` from section 2, which leaves 1 row per value before the numbering starts.


<br>

### The label means nothing on its own

The keys in the example (0, 3, 6) are neither run lengths nor run starts, and no consumer should ever see them: they only happen to stay constant along a run. Drop `island_id` from the final `SELECT` in production and keep it only while debugging. Two users can produce the same label for unrelated runs, since each user's row numbers restart at 1, which is why the `GROUP BY` always carries the entity column beside the key; the next lesson in this track works through that pairing, and here the rule is to never group by the key alone when there is more than 1 entity.

*Volunteer the caveat about the label unprompted: it tells the interviewer you derived the trick rather than copied it.*


<br>

### The same trick on dates

```sql
SELECT
  user_id,
  MIN(login_date) AS streak_start,
  MAX(login_date) AS streak_end,
  COUNT(*) AS streak_length
FROM (
  SELECT
    user_id,
    login_date,
    login_date - ROW_NUMBER() OVER (
      PARTITION BY user_id
      ORDER BY login_date
    ) * INTERVAL '1 day' AS island_key
  FROM logins
) AS keyed
GROUP BY user_id, island_key
ORDER BY user_id, streak_start
```

A date minus an integer needs the integer turned into days, so the subtraction becomes `login_date - rn * INTERVAL '1 day'`, and the key is a date that stays the same along a streak. Alice's logins from March 1 to March 3 carry row numbers 1 to 3, so every one of them gives February 29, while her March 5 with row number 4 gives March 1, a different key. The query returns a 3-day streak and a 1-day streak for her and a 2-day streak for Bob. Everything else about the query is identical, and the calendar details of the date form are the next lesson's subject.

The follow-up is always "now give me the longest one per user". Wrap the streaks in a CTE and take `MAX(streak_length)` grouped by `user_id` for the number alone; returning the dates of that streak means picking a row, and the tie between 2 equal streaks is the awkward case the next section sketches.


<br>

---

## Sketching the Sequence by Hand

Before writing the query in the room, draw the sequence. Put the value in the first column and the row number in the second; the third holds their difference and the fourth a letter naming the island. With 9 rows this takes roughly 60 seconds. The sketch catches every mistake this pattern produces, because a wrong partition shows up as a letter that changes where it should not, and a wrong direction or a misread step does the same. It also gives you and the interviewer one picture to point at while you explain.

| n | rn | n - rn | island |
| --- | --- | --- | --- |
| 1 | 1 | 0 | A |
| 2 | 2 | 0 | A |
| 3 | 3 | 0 | A |
| 7 | 4 | 3 | B |
| 8 | 5 | 3 | B |
| 12 | 6 | 6 | C |
| 13 | 7 | 6 | C |
| 14 | 8 | 6 | C |
| 20 | 9 | 11 | D |

Read down the third column. It changes 3 times, so there are 4 islands: A from 1 to 3 with 3 rows, B from 7 to 8 with 2, C from 12 to 14 with 3, and D holding 20 alone. Two islands share the longest length, and the sketch has already answered a question the interviewer has not asked yet. Check the jumps as well: 0 to 3 for 3 missing values, 3 to 6 for 3 more, 6 to 11 for the 5 values between 14 and 20.


<br>

### The awkward cases the sketch shows

- An island of 1 row: D above, and the first thing to look for when the output seems to have too many rows.
- A tie for longest: A and C both have 3 rows, so "the longest streak" has 2 answers.
- Every row alone: the difference changes on every row and the result returns 1 row per input row.
- An empty table: no rows in, 0 rows out, with no error, which is the correct result and worth saying.
- Numbering in the wrong direction: the difference changes on every row even though runs exist.

The tie is the one that costs offers. `ORDER BY island_length DESC LIMIT 1` returns A or C depending on which the engine happens to place first, and an interviewer who built the example put the tie in on purpose. Ask "should ties at the longest length both come back, or do you want exactly 1 row?" If both, filter the runs to the ones whose length equals the maximum, as the query below does; if 1, add a deterministic tiebreak such as the earliest start to the `ORDER BY` before the `LIMIT`.

https://github.com/user-attachments/assets/2c0b2702-d64a-409d-a4cd-ce6710a75666

`runs` here is the output of section 3's query over the 9 values above, 1 row per island. The scalar subquery finds that the largest length is 3, and `WHERE` keeps every run that long, so the runs starting at 1 and at 12 both come back while 7 to 8 and 20 drop out. With 1 run alone at the top, the same query returns 1 row, so it is correct in both cases without changing anything.


<br>

### A 60-second routine

> Trace before you type
>
> - Write the sequence values in order, 6 to 9 of them, including 1 gap of more than 1 value and 1 island of 1 row.
> - Number them 1 to N and write the difference beside each.
> - Letter the islands where the difference holds, and count them.
> - Check the letters against the question's definition of a break.
> - Name the awkward case your example contains, and say it to the interviewer before they ask.

When the interviewer hands you a sample with 2 users, sketch each user separately, because the partition is what the sketch is checking. A sketch that numbers both users in 1 column reproduces the missing-partition bug by hand, and watching a letter change in the middle of a real streak on the whiteboard is the fastest way to show why the query needs `PARTITION BY`. If the sample has a user with 1 login, trace that user too: an island of 1 row is where most "too many rows" complaints come from, and it takes 1 line to show that the query is right and the question was underspecified.

The sketch also tells you what to type last. Once the letters are down, the aggregates write themselves: the smallest value under each letter is the start, the largest is the end, and the count of rows is the length. If the question asked for a minimum streak of 2, cross out D on the sketch and add the `HAVING` that does the same in the query. Everything the interviewer sees on the board matches a line in the SQL, which is what makes the trace convincing.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Say "gaps and islands" and the subtraction sentence before writing a line<br><br>• Pin down the sequence column and its step, and ask whether an island of 1 counts<br><br>• Number with ROW_NUMBER() partitioned by entity, ordered ascending by the sequence<br><br>• Trace a 6-to-9 row sketch by hand that includes a gap and a 1-row island<br><br>• Ask how ties for the longest run should be returned | • Reach for a self-join or recursive CTE to walk neighbouring rows<br><br>• Number across all entities with 1 window and trust the result<br><br>• Show the n - rn label in the output as if it meant something<br><br>• Use LIMIT 1 for the longest run without a tiebreak or a question |


<br>

---

## Putting It All Together

A subscription software company bills monthly, and the finance team keeps 1 row per customer per month in which an invoice was paid. The CFO asks for each customer's longest unbroken stretch of paid months, to report tenure to the board, and flags that customers who paused and returned must show their stretches separately, while a customer who paid for 1 month still counts.

- The wording "unbroken stretch of paid months" is the recognition cue from section 0, and the opening sentence names the pattern and the row-number subtraction before any SQL.
- Section 1's 3 facts decide the design: the sequence is the billing month, the step is 1 month, and a 1-month stretch is an island of 1 that the CFO wants kept.
- Section 2's partition by customer is what keeps a customer's paid months in their own sequence while thousands of customers paid in the same months.
- Section 3's key, the month minus the row number in months, stays constant across a paid stretch and changes at the paused month, so GROUP BY customer and key yields 1 row per stretch.
- Section 4's sketch of 1 paused customer shows the 2 separate stretches and a tie between them, which decides whether the board report lists both or picks the earlier one.


<br>

---

## Key Takeaways

- Any question about streaks or contiguous ranges is gaps and islands, and your first sentence should name the pattern along with the subtraction that answers it.
- The question defines the break: before writing SQL, pin down the sequence column and its expected step, and settle whether a 1-row island counts.
- Runs exist only after ROW_NUMBER() is partitioned by the entity and ordered ascending by the sequence; a missing PARTITION BY fails silently.
- Value minus row number holds still along a run and jumps by the gap size at every break, and it never returns to an earlier value.
- Before the query is typed, a 9-row hand sketch shows any 1-row islands and ties for longest, and it catches wrong numbering.
