# Top N Per Group: Intermediate

You are 20 minutes into the SQL round at a logistics company. The interviewer shares a screen with 1 table on it, `shipments`: shipment_id, carrier_id, region, delivered_at, cost.
"For each region, give me the 3 carriers with the highest total cost last quarter."
Then he stops talking. Most candidates have ROW_NUMBER typed within 15 seconds, partitioned by region and ordered by cost descending, which numbers shipments when the sentence asked about carriers, and 1 carrier with 3 expensive shipments takes all 3 slots. Nobody has said what happens when 2 carriers tie for third, whether "last quarter" removes shipments before the ranking or carriers after it, or what the top 3 of a region served by 2 carriers looks like.
He is testing whether you settle those 3 things before you write SELECT, because each one changes which rows come back.


<br>

### What you will be able to do

State the grain the question ranks and shape the input to it before any window function runs

Place a condition where it decides who competes rather than where it hides rows that already won

Read the consumer's sentence for the words that decide between ROW_NUMBER and the tie-aware pair, RANK and DENSE_RANK, and say which words forced the choice

Write a window ORDER BY that ends in a unique column so exactly N rows return the same way every run

Turn a percentage cutoff into an explicit rounding rule and say what the smallest group receives


<br>

---

## Ranking at the Right Grain

The question names an entity and a grain. 'The 3 highest-paid employees per department' ranks employees at 1 row each. The table on the interviewer's screen rarely sits at that grain. It is `salary_history` with a row per employee per pay change, or `employees` joined to `project_assignments` with a row per project, and a window function numbers whatever rows reach it. Rank history rows and an employee with 2 raises in 3 years can fill all 3 positions in her department by herself: a correct ranking of pay changes and a wrong answer about people.


<br>

### Say the grain before the syntax

Open by stating what 1 row of the ranked set represents: 'I need 1 row per employee carrying the salary that should count, then I rank those rows inside each department.' That sentence does 2 jobs in the room. It shows the interviewer you compared the input's grain with the question's, and it commits you to a shaping step before the window function. The ranking itself is 2 lines; getting the right rows to it is the rest of the query.

Here is department 10 as it arrives. Employee 103 has 3 pay-change rows, and her current salary is the 150000 row effective 2023-01-01. Employee 105 has held 120000 since 2017.

| employee_id | department_id | salary | effective_date |
| --- | --- | --- | --- |
| 103 | 10 | 110000 | 2018-09-03 |
| 103 | 10 | 135000 | 2020-01-01 |
| 103 | 10 | 150000 | 2023-01-01 |
| 101 | 10 | 180000 | 2019-03-01 |
| 105 | 10 | 120000 | 2017-05-20 |

```sql
WITH ranked AS (
  SELECT
    employee_id,
    department_id,
    salary,
    ROW_NUMBER() OVER (
      PARTITION BY department_id
      ORDER BY salary DESC
    ) AS rn
  FROM salary_history
)

SELECT
  employee_id,
  salary,
  rn
FROM ranked
WHERE rn <= 3
```

ROW_NUMBER numbers the 5 rows it receives. Employee 101 takes 1, 103's current 150000 takes 2 and her 2020 salary of 135000 takes 3, so `rn <= 3` returns 101 followed by 103 twice. Employee 105, the department's real third at 120000, never appears. Nothing in the output looks off, since salaries descend across 3 rows, and nobody questions it until a department head counts 2 names where 3 were promised and asks where the third person went.


<br>

### 2 windows at 2 grains

```sql
WITH current_pay AS (
  SELECT
    employee_id,
    department_id,
    salary,
    ROW_NUMBER() OVER (
      PARTITION BY employee_id
      ORDER BY effective_date DESC
    ) AS latest
  FROM salary_history
),
ranked AS (
  SELECT
    employee_id,
    department_id,
    salary,
    ROW_NUMBER() OVER (
      PARTITION BY department_id
      ORDER BY salary DESC
    ) AS rn
  FROM current_pay
  WHERE latest = 1
)

SELECT
  employee_id,
  salary,
  rn
FROM ranked
WHERE rn <= 3
```

The first window works at the employee grain: `PARTITION BY employee_id` with `ORDER BY effective_date DESC`, and `latest = 1` keeps 1 row per person. The second works at the department grain over those survivors. Read aloud, the plan is 'collapse to the entity, then rank the entity', and the interviewer hears both grains named. The result has 101 at 180000 and 103 at 150000. Third is 105 at 120000, which answers the question that was asked.

| employee_id | salary | rn |
| --- | --- | --- |
| 101 | 180000 | 1 |
| 103 | 150000 | 2 |
| 105 | 120000 | 3 |

A different interviewer hands over the same question with `employees` already at 1 row per person, and then the shaping step is nothing. Say so anyway: 'this table is 1 row per employee, so I can rank it directly.' It costs 5 seconds, and it removes the most common way this question goes wrong when the table happens to be the other kind.


<br>

### When the shaping step is an aggregate

A sum is the other common shaping step. 'Top 5 products per category by revenue' handed `order_items` at the line-item grain needs `SUM(amount)` grouped by product before any window runs; ranking lines returns the 5 largest single lines, which may all belong to 1 product. A join that fans out does the same damage from the other side. 'Top 3 customers per segment by lifetime value, with their city' joins `customers` to `addresses`, which repeats a customer once per saved address, so 1 customer with 3 addresses can fill all 3 slots. The test is the same each time: if the entity the question ranks can appear on more than 1 row of the input, shape first.

> Questions that settle the grain
>
> - What does 1 row of the input represent? A pay change, a line item, an employee-project pair.
> - What does 1 row of the answer represent? One employee, one product, one carrier.
> - Which step moves between them: a dedup window, a GROUP BY, or nothing because they already match?

> **TIP**
>
> The follow-up is 'why 2 CTEs?' Answer with grains: the first picks 1 row per employee, the second ranks employees within departments, and 1 window cannot do both because they partition by different columns.


<br>

---

## Which Rows Compete for the Top N

These 2 requests sound alike and return different rows. 'The 3 highest-paid active employees per department' sets a condition on who competes. 'The 3 highest-paid per department, and show me the active ones' ranks everyone and then hides rows. In the first, a terminated employee holding the department's top salary never enters the ranking, and 3 active people come back. In the second, she takes position 1, the filter removes her afterwards, and the department returns 2 rows. An interviewer who adds 'only active' or 'from last quarter' to the question is checking which of the 2 you build.


<br>

### Where the condition sits

A window function runs over the rows that survive FROM and WHERE, before the outer query sees anything, so a predicate inside the CTE shapes what gets numbered and a predicate in the outer query trims what was already numbered. `WHERE status = 'active'` beside the window removes the terminated row before ROW_NUMBER counts it. The same text written as `AND status = 'active'` next to `rn <= 3` acts on a finished numbering in which she holds rank 1. The predicate is character for character the same in both places, and only 1 of the 2 result sets matches what the interviewer asked for.

```sql
WITH ranked AS (
  SELECT
    employee_id,
    department_id,
    salary,
    status,
    ROW_NUMBER() OVER (
      PARTITION BY department_id
      ORDER BY salary DESC
    ) AS rn
  FROM employees
  WHERE status = 'active'
)

SELECT
  employee_id,
  salary,
  rn
FROM ranked
WHERE rn <= 3
```

https://github.com/user-attachments/assets/a58a7c73-a724-49a5-a1b2-962e92da566e

The animation plays this over department 10, where employee 106 holds the top salary at 210000 and a terminated status. WHERE tests each of the 4 rows and only 106 fails. ROW_NUMBER numbers the survivors in salary order: 101 at 180000 takes 1, 103 at 150000 takes 2 and 105 at 120000 takes 3. The cutoff keeps all of them, every one active, as the question asked.

Condition before ranking

Condition after ranking

Move the predicate to the outer query and 106 is numbered 1, 101 becomes 2, 103 becomes 3, 105 becomes 4. `WHERE rn <= 3 AND status = 'active'` keeps 101 and 103 and drops 106, so department 10 returns 2 rows. The query runs without an error, so the report owner reads it as a department with 2 people, and the real third-highest active earner, 105, is on nobody's screen.


<br>

### Answer in execution order

If the interviewer asks why the position matters, answer in evaluation order. FROM and WHERE run first, GROUP BY and HAVING next, then the SELECT list where window functions compute, and the outer query last. ROW_NUMBER sits in step 4 and sees the output of steps 1 to 3. A predicate in step 2 shapes its input; a predicate in the outer query shapes its output. 'Because the CTE runs first' describes the same fact, and the evaluation-order version shows you can reason about any clause the interviewer adds next.


<br>

### Nulls compete unless you remove them

A NULL salary is a row, and a row competes unless something removes it. PostgreSQL treats NULL as larger than every value, so under `ORDER BY salary DESC` a record with no salary takes rank 1 in its department; MySQL and SQL Server treat NULL as smallest, so the same row lands last. Before anything else, ask whether a row with no salary belongs in the ranking at all. If the answer is no, which it usually is, `WHERE salary IS NOT NULL` inside the CTE takes it out of competition. If it must remain, `NULLS LAST` on the ORDER BY stops it from winning, and section 3 shows that clause in the full query.


<br>

### Time filters are competition filters

'Top 3 carriers by cost last quarter' is the same decision wearing a date. A predicate on `delivered_at` in WHERE restricts the shipments the sum and the ranking are built from, so the ranking reflects last quarter. Applied after the ranking, it filters finished rows by whatever date the final row happens to carry, and when the ranked row is a carrier total there is no shipment date left to filter on. When the ranked rows are totals built by GROUP BY, a condition on the total, `HAVING SUM(cost) > 0`, also runs before the window and also changes who competes.

> Say which rows compete
>
> - 'I filter to active employees first, so only they compete for the 3 slots.'
> - 'I rank everyone, then show status as a column, so a terminated top earner still appears.'
> - 'Last quarter is a competition filter: the sums are built from that period only.'

> **TIP**
>
> The follow-up reverses the request: 'now give me the all-time top 3 and tell me who is still active.' That is the after form, with `status` as an output column rather than a predicate anywhere. Say 'that changes who competes, so the filter moves out of the CTE' and the point is yours.


<br>

---

## How Ranking Functions Treat Ties

The 3 ranking functions take the same OVER clause and agree on every row until 2 rows share a value in the ORDER BY. ROW_NUMBER gives tied rows consecutive numbers in an order the engine chooses. RANK gives them the same number and skips the numbers they consumed. DENSE_RANK gives them the same number and skips nothing. The interviewer is scoring whether you pick from the consumer's sentence rather than from habit, because all 3 produce plausible output on the same data and only 1 matches the request.

Everything else is shared: PARTITION BY, ORDER BY, the frame, the position in evaluation order. A candidate who describes them as 3 different tools has missed that. They are 1 tool with 3 settings for the moment 2 rows compare equal, and that setting is the whole decision.

| employee_id | salary | ROW_NUMBER | RANK | DENSE_RANK |
| --- | --- | --- | --- | --- |
| 101 | 180000 | 1 | 1 | 1 |
| 102 | 150000 | 2 | 2 | 2 |
| 103 | 150000 | 3 | 2 | 2 |
| 104 | 150000 | 4 | 2 | 2 |
| 105 | 120000 | 5 | 5 | 3 |

The table breaks ROW_NUMBER's tie by employee_id so it has fixed values. Without that, which tied row from 102 through 104 receives 2 is the engine's call, which section 3 takes up. RANK counts the rows ahead of a row: 105 has 4 rows above it and gets 5. DENSE_RANK counts the distinct values ahead: 105 is behind 2 salary levels and gets 3.

https://github.com/user-attachments/assets/eb21ad51-3a99-4fa9-ba12-f7b2a2e039eb

The animation runs all 3 over the same 5 rows with the same ORDER BY and nothing else. Watch the 150000 rows: RANK stamps 2 on all 3 and DENSE_RANK does the same, while ROW_NUMBER hands them 2 through 4 in whatever order the engine holds them. Then watch 105: RANK jumps to 5, DENSE_RANK steps to 3, ROW_NUMBER reaches 5. Everything that differs between the 3 columns happens at the tie and in the row after it.


<br>

### What rn <= 3 returns under each

| Function | Rows returned | Who |
| --- | --- | --- |
| ROW_NUMBER | 3 | 101 plus 2 of the 3 tied at 150000, engine's choice |
| RANK | 4 | 101, 102, 103, 104 |
| DENSE_RANK | 5 | every row: 120000 is the third distinct level |

ROW_NUMBER returns exactly N and decides the tie for you. RANK returns at least N: everyone tied at the boundary comes through, so 'top 3' delivers 4. DENSE_RANK returns the rows at the top N distinct values, which here is the whole department, and in a department where 40 people share 3 pay bands it returns 40. Each is the correct answer to a different sentence, and the interviewer's sentence is the spec.


<br>

### The words that pick the function

| Phrase in the request | Function | What comes back |
| --- | --- | --- |
| 'exactly 3, we have 3 bonus slots' | ROW_NUMBER with a tiebreak | 3 rows, no more |
| 'top 3, and if people tie include them all' | RANK | 3 or more rows |
| 'everyone at the top 3 salary levels' | DENSE_RANK | all rows at 3 distinct values |
| 'the 3 most recent orders per customer' | ROW_NUMBER | 3 rows; add order_id as the tiebreak |

The clarifying question, asked before SELECT, is 'If 2 people tie at position 3, do both appear? And is the report about 3 people or 3 pay levels?' The answer maps straight to a row of that table. Asked after the query is written, the same words mean 'fix the bug'. Asked before, they mean 'define the contract', and the rest of the conversation is about requirements, which is the conversation the interviewer wants to have.


<br>

### Ties happen in every ranking column

'The 3 most recent orders per customer' ties whenever a batch import stamps 200 orders with the same `created_at`, and a top 3 by order count per store ties constantly because counts are small integers. The habit worth building is to ask 'can 2 rows share this value?' for every ORDER BY column. The answer is yes for any count or rating out of 5, and for dates without a time and rounded amounts. Saying 'ratings tie heavily, so this is a RANK question unless the carousel has fixed slots' is the kind of sentence that gets written in the interviewer's notes.


<br>

### Probes after the query lands

Expect 1 of 3 probes after the query lands. 'What if 2 employees tie for third?' Answer with the consumer: RANK if both should appear, ROW_NUMBER with a stated tiebreak if the report needs 3. 'What if I want the top 3 salary levels?' DENSE_RANK, and say out loud that the row count is now unbounded. 'Why did you pick ROW_NUMBER?' is the probe that catches habit; the strong answer names the words in the request that forced it, such as 'exactly 3 bonus slots'. An answer that cites what the function does rather than what the consumer asked is the one that loses the point.

> **TIP**
>
> Say 'exactly', 'including ties' and 'distinct levels' as you choose. Those 3 phrases are the vocabulary the interviewer uses when scoring, and hearing them from you removes any doubt about whether the choice was deliberate.


<br>

---

## Deterministic Tiebreaks for N Rows

`ORDER BY salary DESC` alone leaves 3 rows at 150000 with no instruction about their order, and the SQL standard says nothing about how peers are sequenced. The engine takes whatever physical order its plan produced: a hash join's bucket order, a parallel scan's merge order, the heap's layout after yesterday's VACUUM. Tuesday's refresh shows 102 as third-highest, Wednesday's shows 104, the data has not changed, and the dashboard owner files a bug that nobody can reproduce because the dev database runs with 1 fewer parallel worker. ROW_NUMBER without a total order is that bug waiting for a plan change.

```sql
WITH ranked AS (
  SELECT
    employee_id,
    department_id,
    salary,
    hire_date,
    ROW_NUMBER() OVER (
      PARTITION BY department_id
      ORDER BY salary DESC NULLS LAST, hire_date, employee_id
    ) AS rn
  FROM employees
  WHERE status = 'active'
)

SELECT
  department_id,
  employee_id,
  salary,
  hire_date
FROM ranked
WHERE rn <= 3
```

https://github.com/user-attachments/assets/7d4d9d9b-9a6b-4859-8e50-45954b0c7451

The animation plays the window over department 10's 5 rows with the full ORDER BY. 101 at 180000 takes 1 alone. The 3 rows at 150000 are sorted by `hire_date ASC`: 103, hired 2018-09-03, takes 2. 102 and 104 share 2021-06-14 as well, and `employee_id ASC` puts 102 at 3 and 104 at 4. 105 at 120000 takes 5. Run it on any engine with the rows in any physical order and the same numbers land on the same employees, which is what a top 3 that feeds a bonus list requires.


<br>

### Each column is a rule

- salary DESC: the metric. Highest pay wins. This column is the question.
- hire_date ASC: the business tiebreak. On equal pay, longer tenure wins. The consumer chose it.
- employee_id ASC: the guarantee. Unique per row, so no 2 rows can remain tied.

The middle column is a policy decision, so say that out loud. `hire_date ASC` encodes 'tenure breaks ties'. `performance_rating DESC` would encode 'rating breaks ties', and `employee_id ASC` on its own encodes 'the older record wins', which no HR team would choose if asked. Ask: 'when 2 people are tied at the cutoff, who does the business want in the 3?' The answer becomes the second ORDER BY column, and the query documents the rule. The last column is different in kind: it exists so the ORDER BY is a total order, and it should be the primary key or something equally unique.


<br>

### Why exactly N needs this and RANK does not

RANK and DENSE_RANK are deterministic without a tiebreak because tied rows receive the same number and all come through or all stay out; the row count varies, the set does not. ROW_NUMBER promises exactly N, and the only way to keep that promise and return the same N every run is an ORDER BY in which no 2 rows compare equal. The follow-up 'does RANK need the tiebreak too?' tests that distinction. The answer is no for which rows return, and yes if the output is also displayed in order, since the display order of tied rows is otherwise arbitrary.


<br>

### The tiebreak goes inside OVER

The tiebreak belongs in the window's ORDER BY. A candidate who adds `ORDER BY salary DESC, employee_id` to the outer query has ordered the 3 rows the window already chose and has done nothing about which 3 it chose. The numbering happened inside OVER, and only the ORDER BY inside OVER can change it. The same applies to the dedup window from section 0: `PARTITION BY employee_id ORDER BY effective_date DESC` keeps an arbitrary row when 2 pay changes share a date, and `effective_date DESC, change_id DESC` fixes it. Any 'keep 1 row per group' is a top 1 per group with the same requirement.


<br>

### Nulls at the top of a descending sort

`NULLS LAST` is the other clause in that ORDER BY, and section 1 covered why it is there: engines disagree on where NULL sorts. The clause itself does not travel. PostgreSQL and Oracle accept it, and both need it, because their DESC puts NULL first. MySQL and SQL Server reject it as a syntax error, although their DESC already puts NULL last. The spelling that runs on all 4 is `ORDER BY CASE WHEN salary IS NULL THEN 1 ELSE 0 END, salary DESC`. Naming that difference tells the interviewer you have watched a query break after a migration.

> The determinism check
>
> - Run the query twice and diff the outputs. Any difference on unchanged data is a missing tiebreak.
> - Read the window's ORDER BY and ask whether its columns together are unique per row.
> - Check every ROW_NUMBER in the query, including the dedup ones, and the final ranking last.

> **TIP**
>
> Narrate the ORDER BY as you type it: 'salary descending is the metric, hire date ascending is the tenure rule the business wants, employee id makes it total.' That is 3 sentences, and the interviewer has heard you treat an ORDER BY as a design decision.


<br>

---

## Top N Percent of Each Group

'The top 10% of earners in each department' sounds like the same question with a different cutoff, and the cutoff is where it changes. In a 100-person department, 10% is 10 people. In a 25-person department it is 2.5 people, and in a 3-person department it is 0.3 of a person. Someone decides how 2.5 and 0.3 become row counts, and if you do not, the function you reach for decides silently and differently from the function the last analyst used. The interviewer is listening for whether you name the rounding rule before the smallest department forces it on you.


<br>

### Count the group, then cut

```sql
WITH ranked AS (
  SELECT
    employee_id,
    department_id,
    salary,
    ROW_NUMBER() OVER (
      PARTITION BY department_id
      ORDER BY salary DESC, hire_date, employee_id
    ) AS rn,
    COUNT(*) OVER (
      PARTITION BY department_id
    ) AS dept_size
  FROM employees
  WHERE status = 'active'
)

SELECT
  department_id,
  employee_id,
  salary
FROM ranked
WHERE rn <= CEIL(0.10 * dept_size)
```

`COUNT(*) OVER (PARTITION BY department_id)` puts each department's active headcount on every row, and the cutoff `rn <= CEIL(0.10 * dept_size)` turns the percentage into an integer the reader can check by hand. With CEIL, a department of 3 returns 1 person and a department of 25 returns 3. Swap in FLOOR and the department of 3 returns nobody and 25 returns 2. Both are defensible policies. The query makes the policy visible in 1 expression, and that visibility is why this form wins in the room over the shorter ones below.


<br>

### What NTILE and PERCENT_RANK decide for you

`NTILE(10) OVER (PARTITION BY department_id ORDER BY salary DESC) = 1` reads like 'top decile' and distributes rows as evenly as integers allow, with the remainder going to the first buckets. A 25-person department splits into buckets of 3, 3, 3, 3, 3, 2, 2, 2, 2, 2, so bucket 1 holds 3 people, 12% of the department. A 3-person department fills buckets 1 to 3 with 1 person each, so bucket 1 is 33% of it. `PERCENT_RANK()` is (rank - 1) / (rows - 1): the top row is always 0, so `<= 0.10` always admits at least 1 person, and for a 1-person department the division is defined as 0 rather than failing. `CUME_DIST()` is rows at or above this one divided by all rows, so the top earner of a 3-person department scores 0.33 and `<= 0.10` admits nobody.

| Group size | CEIL(0.10 \* n) | NTILE(10) = 1 | PERCENT_RANK <= 0.10 | CUME_DIST <= 0.10 |
| --- | --- | --- | --- | --- |
| 3 | 1 | 1 | 1 | 0 |
| 10 | 1 | 1 | 1 | 1 |
| 25 | 3 | 3 | 3 | 2 |
| 100 | 10 | 10 | 10 | 10 |

At 100 rows the 4 methods agree, which is why they look interchangeable on a demo dataset. Everything interesting happens below 25, and the 3-person department is the row to point at in the room: 3 methods return its top earner and 1 returns nobody. That is the question to ask before writing: 'a department of 3 people, does its top 10% have 0 people in it or 1?' The answer picks the rounding, and the rounding picks the SQL.


<br>

### Ties against a percentage cutoff

A percentage cutoff still lands on a tie. PERCENT_RANK and CUME_DIST are built on RANK, so tied salaries share a value and all cross the line together or none do, which makes them RANK-flavoured by construction. The count form uses ROW_NUMBER, so it needs the total ordering from section 3 to return the same people each month, or `RANK()` in place of `ROW_NUMBER()` if tied people at the boundary should all receive the bonus. Say which you chose: 'the cutoff is a headcount, so I break ties by tenure and employee id' is a sentence that settles it.

The question arrives dressed as 'top decile', 'the 90th percentile and above' or 'the top 5% of accounts by spend in each region'. Each of those is a percentage of a group whose size varies, and each needs the same 2 answers before any function is typed: how a fraction of a person becomes a count, and what the smallest group gets. Decile and percentile wording pulls candidates toward NTILE and PERCENT_RANK, and the strong move is to translate the wording into a count rule first and pick the function second.

> **TIP**
>
> Lead with the smallest group. 'What happens to a department of 2?' asked by you, before the interviewer asks it, converts the hardest follow-up into evidence that you have seen a percentage report misbehave.

| ✓ Do | ✗ Don't |
| --- | --- |
| • State the grain of the ranked rows before writing any window function<br><br>• Put competition filters in the CTE's WHERE, output filters in the outer query<br><br>• Ask whether ties at position N appear, then choose the function from the answer<br><br>• End every ROW_NUMBER ORDER BY with a unique column<br><br>• Make percentage cutoffs an explicit CEIL or FLOOR of the group count | • Rank a table whose rows repeat the entity the question is about<br><br>• Trust the engine's default NULL placement in a DESC sort<br><br>• Add the tiebreak to the outer ORDER BY and expect it to change which rows win<br><br>• Use NTILE to mean a fixed percentage on groups smaller than the bucket count<br><br>• Call the 3 ranking functions separate tools when only their tie rule differs |


<br>

---

## Putting It All Together

An HR analytics team at a 4,000-person software company builds the quarterly compensation pack for the board. For each of 60 departments, sized from 2 to 400 people, the pack lists the 3 highest-paid active employees and everyone in the top 10% by pay, built from salary_history, which carries 1 row per employee per pay change and includes contractors with NULL salaries.

- salary_history is at the pay-change grain, so a first window keeps the latest row per employee before any department ranking runs; without it, 1 person with recent raises fills all 3 slots.
- Active status and salary IS NOT NULL go in the CTE's WHERE, which keeps contractors and departed staff out of the competition. If those filters sat in the outer query, departments would show 2 names.
- The board wants exactly 3 names per department, so the function is ROW_NUMBER. When 2 directors tie on pay, the tenure rule the CHRO chose becomes the second ORDER BY column, with employee_id closing the order.
- The top 10% list uses CEIL ( 0.10 \* dept_size ) so the 2-person department returns its top earner, and the pack's footnote states that rounding so finance can reproduce the counts.
- Running the pack twice produces identical files, which is the check the team runs before the pack leaves the building.


<br>

---

## Key Takeaways

- Rank rows at the grain the question names: collapse or aggregate to the entity first, then number.
- A condition in the CTE's WHERE decides who competes; the same condition in the outer query hides rows that already won.
- The 3 ranking functions share everything except what they do when 2 rows are equal, and that rule is the whole choice.
- Exactly N rows that come back the same every run require an ORDER BY ending in a unique column, inside the window.
- A percentage cutoff is a rounding decision per group; CEIL or FLOOR of COUNT(\*) OVER makes it explicit, and the smallest group reveals it.
