# Self-Join: Beginner

You are 10 minutes into a SQL screen at a logistics company, and the interviewer shares one table.
"Here is `employees`: employee_id, name, manager_id, salary. Give me everyone who earns more than their manager."
She stops there. There is no managers table, and nobody has said what to do with the CEO, whose manager_id is NULL. The first move most candidates make is to scan the column list for a manager_salary that does not exist, then start a WHERE clause that compares `salary` to something the row does not hold. The manager's salary sits on another employee's row, and a WHERE clause only ever sees one row at a time.
What she is listening for is whether you say, before typing anything, that the table has to appear twice.


<br>

### What you will be able to do

Recognize a question that compares 2 rows of one table, whatever vocabulary it arrives in

Write FROM employees e JOIN employees m with aliases that name the 2 roles

Build the join condition in the right direction and say what happens to the row with a NULL pointer

Finish the earns-more-than-manager query, trace it row by row and handle the follow-ups

Explain when a correlated subquery is enough and the exact point where it stops working


<br>

---

## Two Rows Playing Different Roles

The question rarely arrives with the word 'join' in it. It arrives as a comparison: 'who out-earns their boss', 'which employees sit in Carol's department', 'find pairs of accounts registered with one email'. Each one asks about a relationship between 2 rows, and both rows live in the same table. The interviewer is checking whether you notice that fact before you start typing, because a candidate who treats it as a single-row filter writes a WHERE clause that cannot be finished.


<br>

### The question in its disguises

- 'Which employees earn more than the person they report to?'
- 'Show me every employee alongside their manager's name.'
- 'Which tickets were escalated from a ticket that is still open?'
- 'Find every product variant priced below its parent product.'
- 'List each store with the quarterly revenue of the hub it belongs to.'

Every one of these has a column on one row that points at another row of the same table: manager_id points at an employee_id, escalated_from_ticket_id points at a ticket_id, parent_product_id points at a product_id. The word 'their' or 'its' in the question is the tell. 'Their manager' means a second row, found by following the pointer, and the answer needs a value from that second row sitting beside a value from the first.


<br>

### One row, 2 roles

| employee_id | name | manager_id | salary |
| --- | --- | --- | --- |
| 1 | Alice | NULL | 200000 |
| 2 | Bob | 1 | 180000 |
| 3 | Carol | 1 | 220000 |
| 4 | Dave | 2 | 150000 |

Read Bob's row twice. In the question 'does Bob earn more than his manager', Bob is the employee: his manager_id is 1, which points at Alice, and the comparison is 180000 against 200000. In the question 'does Dave earn more than his manager', Bob is the manager: Dave's manager_id is 2, which points at Bob, and the comparison is 150000 against 180000. The same physical row plays the employee role in one comparison and the manager role in another. Nothing in the table marks a row as a manager; the role comes from which side of the pointer the row sits on.

A `WHERE` clause evaluates one row at a time, so when it is looking at Carol's row it can see salary = 220000 and manager_id = 1, and nothing else. The number it needs, Alice's 200000, is 2 rows away. No expression over Carol's own columns can reach it. That is the wall candidates hit when they try a `CASE` expression or a plain filter: the manager's pay sits on a second row of the same table, and the row being tested does not contain the value it is being compared to.

The shape, in 4 facts

- One table is listed twice in the FROM clause, under 2 different aliases
- Each alias plays one role: one alias is the employee, the other is the manager
- The join condition is the pointer on one role matched to the key on the other
- A single stored row can be the employee in one output row and the manager in another


<br>

### What the interviewer scores in your first sentence

The score at this point is for pattern recognition, and it is awarded in the first sentence you say. The sentence that clears it: 'The manager's pay is on a different row, so I will join employees to itself, one alias for the employee and one for the manager.' That names the shape, names the 2 roles and tells the interviewer the join condition is coming. Candidates who skip this sentence and start typing force the interviewer to reverse-engineer the plan from the syntax, and a typo in the ON clause then reads as confusion about the approach rather than a slip of the fingers.

| ✓ The answer that stalls | ✗ The answer that clears the bar |
| --- | --- |
| • Scans the column list for manager_salary and finds nothing<br><br>• Asks whether there is a managers table (there is not)<br><br>• Tries a CASE expression or a filter over a single row<br><br>• Loses 2 minutes before the second copy of the table appears | • Says 'self-join' within the first 10 seconds<br><br>• Names the roles: one alias is the employee, the other the manager<br><br>• States that manager_id on one side matches employee_id on the other<br><br>• Has a running query on the screen inside 90 seconds |

> Signals that the comparison crosses rows
>
> - 'Their' or 'its' attached to a role: their manager, its parent, its hub
> - A column named like the key with a prefix: manager_id, parent_id, referrer_id, escalated_from_id
> - A comparison between 2 things that share a column name: price below the parent's price
> - 'Same X as another' or 'pairs of': also a self-join, matched on a shared value rather than a pointer, and it needs `a.id < b.id` to drop self-pairs and repeats

Outside the interview, org charts and bill-of-materials trees have the same shape, as do ticket escalation chains and referral programs. So do product variants, and so does any table with a column that points back into itself. An engineer who cannot write a self-join cannot answer questions about any of those, which is why the question is asked early. It screens whether you can hold one table in 2 roles in your head, and it does so with 1 table and 4 rows.

> **TIP**
>
> Say the phrase 'join the table to itself' before writing FROM. It costs nothing, and hearing it is when the interviewer marks pattern recognition as done, so what follows is graded as syntax.


<br>

---

## Aliasing the Table Twice (e and m)

The FROM clause is where the second copy comes from. Writing `FROM employees e JOIN employees m` tells the database to read the employees table twice and to call one reading e and the other m. From that point every column reference in the query has to say which reading it means: e.salary is the salary on the employee's row, m.salary is the salary on the manager's row. The aliases are the mechanism, and without them the query cannot be written at all.

```sql
-- Pair each employee with their manager's row
SELECT
  e.employee_id,
  e.name AS employee_name,
  m.name AS manager_name,
  e.salary AS employee_salary,
  m.salary AS manager_salary
FROM employees AS e
JOIN employees AS m
  ON e.manager_id = m.employee_id
```

| employee_id | employee_name | manager_name | employee_salary | manager_salary |
| --- | --- | --- | --- | --- |
| 2 | Bob | Alice | 180000 | 200000 |
| 3 | Carol | Alice | 220000 | 200000 |
| 4 | Dave | Bob | 150000 | 180000 |

The query returns 3 rows, one per employee who has a manager. Alice's manager_name and manager_salary show up twice, once on Bob's row and once on Carol's, because 2 employees point at her. Alice does not appear as employee_name at all, since her manager_id is NULL and matches nothing; the next section covers that row. Look at what each output row now holds: a salary from the employee role and a salary from the manager role, side by side. The comparison the question asked for is one WHERE clause away.

It helps to know what the engine considered before it kept those 3. Joining 2 copies of a 4-row table gives 16 candidate pairings, every e row against every m row. The ON condition tests each pairing and keeps only those where the pointer on the e side lands on the employee_id of the m side: Bob with Alice, Carol with Alice, Dave with Bob. None of the other 13 pairings reach the output; they fail the test, and that includes each row paired with itself. Because employee_id is unique, no e row can pass against 2 different m rows, so the join never multiplies an employee into several output rows.


<br>

### Unqualified columns fail as ambiguous

Drop the prefix and write SELECT name, salary FROM employees e JOIN employees m ON ... and the database refuses: column reference "salary" is ambiguous. Both copies have a salary column, and the engine has no way to know whether you mean the employee's or the manager's. In an ordinary 2-table join the ambiguity only arises for columns that happen to share a name. In a self-join every column shares a name with its twin, so every reference needs its alias. Interviewers watch for this: a candidate who prefixes every column has internalised that there are 2 rows in play.

*Postgres rejects an unqualified column in a self-join with an ambiguity error, and so do MySQL and SQLite. The loud error helps, because a version of this bug that ran silently would be far harder to catch.*


<br>

### Aliases that name the role

The convention for this question is e for the employee row and m for the manager row. The engine would run the query identically with t1 and t2, since it does not care what the aliases are called. The interviewer does, because they are reading the query as you type it and the aliases are the only words on the screen that say which copy is which. With e and m, the line `WHERE e.salary > m.salary` reads as 'employee salary exceeds manager salary' with no translation. With t1 and t2 the reader has to scroll back to the ON clause to work out which copy holds the pointer, and so do you when the follow-up arrives.

| ✓ e and m | ✗ t1 and t2 |
| --- | --- |
| • e.manager_id = m.employee_id reads as a sentence<br><br>• A reversed condition is visible the moment it is typed<br><br>• The follow-up 'add the manager's hire date' is m.hire_date, no lookup needed<br><br>• Shows the interviewer you separated the 2 roles before writing | • t1.manager_id = t2.employee_id needs the ON clause reread to decode<br><br>• A reversed condition looks identical to a correct one<br><br>• Every added column starts with 'which one was the manager again?'<br><br>• Reads as aliasing done to satisfy the parser |

> Aliases that name the role, by question
>
> - Employee and manager: `e` and `m`
> - Product variant and parent product: `v` and `p`
> - Escalated ticket and original ticket: `esc` and `orig`
> - Store and its regional hub: `s` and `hub`
> - Course and its prerequisite: `c` and `pre`

Aliases of 2 or 3 letters are fine when a single letter would be ambiguous: `esc` and `orig` say more than `t` and `t2`, and they are still short enough to type 10 times without slowing down. The test is whether someone reading the SELECT list alone, without the FROM clause, can tell which role each column came from.


<br>

### Narrating the FROM clause

Say the aliases as you type them. 'I am reading employees twice: e is the employee, m is the manager. The join condition will connect e's manager_id to m's employee_id.' That is 2 sentences, and by the time you finish them the FROM clause is on the screen and the interviewer has heard the whole plan. If the ON clause then comes out backwards, the interviewer already knows what you meant, and the fix is a 5-second swap rather than a conversation about whether you understood the question.

> **TIP**
>
> Write the alias on the FROM line and on the JOIN line before writing a single SELECT column. Starting from SELECT forces you to invent names for columns whose source you have not yet declared, which is where `salary` without a prefix sneaks in.


<br>

---

## Writing the Self-Join Condition

The join condition is the sentence that says how a row in one role finds its partner in the other. For an org chart the pointer is manager_id: it sits on the employee's row and holds the employee_id of the manager's row. So the condition is `e.manager_id = m.employee_id`, read as 'the employee's manager_id equals the manager's employee_id'. Every self-join over a self-referencing column has this shape: the foreign key on the alias playing the child role, the primary key on the alias playing the parent role.


<br>

### Which side holds the pointer

Before typing the ON clause, answer one question: which column is the pointer, and which row does it live on? In employees, the pointer is manager_id and it lives on every row that has a boss. The alias whose manager_id you read is therefore the employee, and the alias whose employee_id you compare it to is the manager. Carol's row has manager_id 1; the m row with employee_id 1 is Alice; the condition pairs Carol with Alice. Trace exactly one row like this out loud and the direction is settled before any syntax exists.


<br>

### The reversed condition

The mistake that costs the most here is writing the condition backwards: `e.employee_id = m.manager_id`. It compiles and returns rows, but they are the wrong rows, and the column labels misstate what they hold.

```sql
-- Reversed: pairs each person with the people who report to them
SELECT
  e.name AS employee_name,
  m.name AS manager_name
FROM employees AS e
JOIN employees AS m
  ON e.employee_id = m.manager_id
```

| employee_name | manager_name |
| --- | --- |
| Alice | Bob |
| Alice | Carol |
| Bob | Dave |

The output says Alice's manager is Bob, and also Carol, which is nonsense, since Alice has no manager at all. What the reversed condition computed is 'for each person e, every m whose manager_id points back at e', which is the list of each person's direct reports with the labels swapped. The row count is 3 in both the correct and the reversed version, so counting rows will not catch it. The only check that works is picking one output row and asking whether it is true: 'is Bob Alice's manager?' No. Swap the sides.

> A 10-second check for the ON clause
>
> - Name the pointer column and the row it lives on: manager_id, on the employee's row
> - Put the pointer on the alias that plays the child role: `e.manager_id`
> - Match it to the key on the alias that plays the parent role: `m.employee_id`
> - Trace one row: Carol has manager_id 1, the m row with employee_id 1 is Alice, so Carol's manager is Alice
> - Read one output row back as a sentence and confirm it is true of the data


<br>

### The row with nothing to match

Alice's manager_id is `NULL`. When the join compares her row against each of the 4 m rows, NULL = 1 comes back unknown rather than true. The same happens with NULL = 2 and NULL = 3, and again with NULL = 4, so an inner join finds no partner and drops her. For 'who earns more than their manager' that is the correct behaviour: the CEO has no manager to compare against. For 'show me every employee with their manager's name' it is a bug, and the fix is `LEFT JOIN`, which keeps every e row and fills the m columns with NULL where no partner exists.

https://github.com/user-attachments/assets/4746c7e9-cb10-4ee7-ae80-8d4d40624e7c

Watch Alice's row in the run. Each of her 4 comparisons resolves to unknown, no m row attaches, and the LEFT JOIN emits her with manager NULL. The 3 other employees each pick up the same single manager they got from the inner join in section 1, so switching to LEFT JOIN changes only what happens to the row that finds nothing.

A pointer that lands nowhere fails the match the same way. If Bob's row were deleted while Dave's manager_id still said 2, the inner join would drop Dave, and the LEFT JOIN would emit him with NULL in every m column, exactly as it emits Alice. The m columns look alike; e.manager_id does not. Alice's is NULL because she has no manager, and Dave's is still 2 because his manager's row is gone. Filtering on both columns after the LEFT JOIN separates them, and it is the query to have ready when the interviewer asks about deleted managers.

```sql
-- Employees whose manager_id points at no existing row
SELECT
  e.employee_id,
  e.name,
  e.manager_id
FROM employees AS e
LEFT JOIN employees AS m
  ON e.manager_id = m.employee_id
WHERE e.manager_id IS NOT NULL
  AND m.employee_id IS NULL
```

> **TIP**
>
> Ask about the top of the hierarchy before writing the join: 'The CEO has a NULL manager_id. Should they appear?' The interviewer hears you anticipating the NULL, and whichever answer comes back tells you INNER or LEFT before you have typed either.


<br>

---

## "Earns More Than Their Manager"

Once the join has put e.salary and m.salary on the same output row, the question collapses into a single comparison. The relationship goes in the ON clause, the question's filter goes in WHERE, and the SELECT names both roles so the interviewer can verify each row by eye. The hard part was already done in the FROM clause.

https://github.com/user-attachments/assets/5b006649-6d3e-4c2f-a99d-0d37ce52db9e

The run uses only the first 3 rows of the table, Alice and her 2 direct reports, and puts the salary test inside ON next to the pointer; for an inner join that keeps exactly the rows the WHERE version keeps, a point the follow-ups below come back to. Bob against Alice: the pointer matches, but 180000 > 200000 is false, so the pair is dropped. Carol against Alice: 220000 > 200000 is true, kept. Alice finds no partner at all. One row comes back: Carol, manager Alice. On the full 4-row table, Dave against Bob adds one more test; 150000 > 180000 is false, and the answer is still Carol alone. Narrate the trace row by row in the room, because the interviewer cannot see it unless you say it.

| employee | employee_salary | manager | manager_salary | kept |
| --- | --- | --- | --- | --- |
| Bob | 180000 | Alice | 200000 | no |
| Carol | 220000 | Alice | 200000 | yes |
| Dave | 150000 | Bob | 180000 | no |


<br>

### The version worth writing in full

```sql
SELECT
  e.employee_id,
  e.name AS employee_name,
  e.salary AS employee_salary,
  m.name AS manager_name,
  m.salary AS manager_salary,
  e.salary - m.salary AS gap
FROM employees AS e
JOIN employees AS m
  ON e.manager_id = m.employee_id
WHERE e.salary > m.salary
ORDER BY gap DESC
```

The question asked only for names, and the names-only query is a complete answer. The fuller version is what you write when the interviewer says 'good, now show me the manager too' or 'by how much?', and it is worth having ready because those follow-ups come in that order nearly every time. The gap column is one subtraction across the 2 roles, and ORDER BY on it puts the biggest inversion at the top, which is what a compensation analyst actually wants from this query.


<br>

### Which way the comparison points

`e.salary > m.salary` and `m.salary > e.salary` are both valid SQL and answer opposite questions. The first finds employees out-earning their manager. The second finds employees paid less than their manager, which on most org charts is nearly everybody. Read the comparison back as a sentence with the roles substituted in: 'employee salary greater than manager salary'. If the sentence matches the question, the direction is right. On the 4-row table the first returns Carol and the second returns Bob and Dave, so even the row count tells you which one you wrote.


<br>

### Saying the CEO line unprompted

Alice's absence from the result is correct, and the interviewer wants to hear you say so without being asked. The sentence: 'Alice has no manager, so the inner join drops her, which is right for this question; if the question wanted every employee listed, I would switch to a LEFT JOIN and the manager columns would be NULL for her.' That one sentence names the NULL and the join type, and it says the choice depends on the question. Candidates who stay silent about the CEO are usually asked about it, and answering under questioning scores lower than volunteering it.


<br>

### The follow-ups and their answers

Questions that arrive after the first query works

- 'Two people report to Alice. Does that break anything?' No: Alice's m row is reused for Bob and for Carol, and each employee still gets exactly 1 output row.
- 'What if a manager_id points at an employee who was deleted?' The inner join drops that employee, exactly as it drops the CEO; a LEFT JOIN shows them with a NULL manager, which exposes the dirty data.
- 'What about someone paid the same as their manager?' > excludes them and >= includes them. Ask which the question means before choosing.
- 'Can you show the manager's manager?' A second JOIN of employees, aliased mm, on m.manager_id = mm.employee_id. Walking further up the chart is its own topic.
- 'Why is the salary test in WHERE and not in ON?' For an inner join the result is identical; WHERE keeps the relationship and the question apart, which is easier to read and to change.


> Where answers lose points on this question
>
> - Writing the salary comparison before the second copy of the table exists
> - Getting the > direction backwards and returning Bob and Dave instead of Carol
> - Leaving the CEO unmentioned until the interviewer brings it up
> - Returning only the employee's name when the question said 'alongside their manager'
> - Reaching for a nested subquery when the join already holds both values


<br>

---

## Why a Subquery Returns One Role

The other route candidates take to this question is a subquery: keep the employee's row in the outer query and look up the manager's salary with a nested SELECT. It is a legitimate answer to the names-only version, and knowing exactly where it stops is what separates a candidate who chose it from one who fell into it.

```sql
-- Correlated subquery: one lookup per employee row
SELECT
  e.name,
  e.salary
FROM employees AS e
WHERE e.salary > (
  SELECT
    m.salary
  FROM employees AS m
  WHERE m.employee_id = e.manager_id
)
```

For each outer row, the inner SELECT runs with that row's manager_id plugged in and returns one value: the manager's salary. Carol's row gets 200000 back, 220000 > 200000 holds, Carol is kept. Alice's row plugs in NULL, the inner query finds no row and returns NULL, `200000 > NULL` is unknown, Alice is dropped. The result matches the self-join exactly. But look at what the output row holds: Carol's name and Carol's salary. The 200000 that decided the row was compared and then thrown away, so the output carries only the employee role.


<br>

### The follow-up that breaks it

'Show me the manager's name beside each employee.' With the self-join that is one more column in the SELECT list, `m.name`, because the manager's whole row is already attached. With the subquery there is no m in the outer query to reference. The manager's row existed only inside the parentheses, for the duration of one comparison, and it is gone. Getting the name back means a second subquery in the SELECT list, with the same correlation repeated.

```sql
-- One subquery per manager column you need
SELECT
  e.name,
  e.salary,
  (
    SELECT
      m.name
    FROM employees AS m
    WHERE m.employee_id = e.manager_id
  ) AS manager_name,
  (
    SELECT
      m.salary
    FROM employees AS m
    WHERE m.employee_id = e.manager_id
  ) AS manager_salary
FROM employees AS e
WHERE e.salary > (
  SELECT
    m.salary
  FROM employees AS m
  WHERE m.employee_id = e.manager_id
)
```

The query now has 3 nested SELECTs that find the same manager row, and each may return only 1 column, because a scalar subquery produces 1 value. Add the manager's hire date and there are 4. Every one of them repeats the correlation `m.employee_id = e.manager_id`, so a typo in 1 of them silently returns the wrong manager's value in 1 column while the others are right. The self-join states that condition once, in the ON clause, and then every column of the manager's row is available by prefixing it with m.

There is a cost story too, and it is worth one sentence. On paper a correlated subquery runs the inner query once per outer row, and while most optimizers rewrite a simple one into a join, 3 of them against the same table may not all be rewritten. The self-join reads the table twice and matches once. On 4 rows nothing is measurable; on a 1,200-row org chart it is still fine; the point to make in the room is that the join expresses the work once and leaves the optimizer less to guess at.

| ✓ Self-join | ✗ Correlated scalar subquery |
| --- | --- |
| • Both rows sit on 1 output row; any column from either is e.col or m.col<br><br>• The relationship is stated once, in ON<br><br>• Adding a manager column is 1 line in the SELECT list<br><br>• Reads as 'employee paired with manager', which is how the question was asked | • Output holds the outer row only; the inner row is consulted and discarded<br><br>• The relationship is restated inside every subquery<br><br>• Adding a manager column is another nested SELECT<br><br>• Reads as 'employee, with a lookup', which hides that 2 roles exist |


<br>

### When the subquery is the right answer

A subquery wins when the question only ever wants 1 role in the output. 'Which employees have at least 1 direct report?' is WHERE EXISTS (SELECT 1 FROM employees r WHERE r.manager_id = e.employee_id), and no column from the report's row is wanted, so there is nothing for a join to carry. The rule to state out loud: if the answer shows columns from both roles, join; if it shows 1 role and the other only decides which rows survive, use a subquery or `EXISTS`, which is often clearer.


<br>

### The sentence that shows you chose

If you reach for the subquery, say why: 'The question wants only the employee's name, so a correlated subquery is enough; if we need the manager's columns too, I would switch to a self-join so both rows are on the same output row.' That tells the interviewer you know the limit before they test it. If you reach for the join, the mirror sentence works: 'I am joining so the manager's columns are available for the follow-ups.' If you say neither, expect a follow-up aimed at that gap.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Say 'self-join' and name the 2 roles before writing FROM<br><br>• Alias by role with e and m instead of t1 and t2<br><br>• Put the pointer on the child alias: e.manager_id = m.employee_id<br><br>• Trace 1 row through the ON clause out loud, then 1 through the WHERE<br><br>• Mention the NULL manager_id and name the join type it implies | • Write a WHERE comparison while employees is still listed only once in FROM<br><br>• Leave any column unprefixed in a self-join<br><br>• Trust the row count to catch a reversed join condition<br><br>• Stack scalar subqueries when the output needs columns from both roles<br><br>• Wait for the interviewer to ask about the CEO |


<br>

---

## Putting It All Together

A compensation team at a 1,200-person software company is running its annual pay equity review. Their people system exports one employees table with employee_id, name, manager_id, salary and level, and the first question from the VP of People is the one from the interview: who is paid more than the person they report to, by how much, and does the list include anyone whose manager left the company last quarter?

- The request puts an employee next to their manager from a single export, so the analyst joins employees to itself as e and m rather than hunting for a managers table that does not exist.
- The ON clause is e.manager_id = m.employee_id, checked by tracing one engineer and her director before anything else is written, because a reversed condition would list every director's reports as their managers.
- The CEO's NULL manager_id and any manager_id pointing at a departed employee both fail the match; the inner join drops them for the pay inversion list, and a LEFT JOIN run beside it surfaces the departed-manager rows the VP asked about.
- WHERE e.salary > m.salary filters the pairs, and e.salary - m.salary AS gap with ORDER BY gap DESC ranks them; each row shows both people's names and salaries for the review meeting.
- A correlated subquery could have found the names alone, but the VP wanted the manager's name and salary on the same row, which is exactly the point where a subquery per manager column stops being worth writing.


<br>

---

## Key Takeaways

- A question that compares 2 rows of one table is a self-join; the word 'their' or 'its' attached to a role is the tell.
- List the table twice under the role aliases e and m. Prefix every column, because every column has a twin.
- The ON clause puts the pointer on the child alias and the parent's employee_id on the parent alias: e.manager_id = m.employee_id, traced on 1 row.
- A NULL pointer matches nothing; an inner join drops that row, a LEFT JOIN keeps it with NULL partner columns, and the question decides which.
- A correlated subquery returns 1 value and 1 role; the moment the output needs columns from both roles, the join is the only clean answer.
