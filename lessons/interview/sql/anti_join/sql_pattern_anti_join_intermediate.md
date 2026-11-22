# Anti-Join: Intermediate

Shared editor, 45-minute SQL screen at an online retailer. Two tables are pasted at the top, `customers` and `orders`, with a 5-row sample of each.
"Marketing wants a win-back email for everyone who created an account and never bought anything. Give me that list."
She stops there. What she leaves out is that guest checkouts write orders with a NULL `customer_id`. The query most candidates type first, a `NOT IN` against the orders table, returns 2 names on her sample and nobody at all on the production table. Her follow-ups are queued behind it: never bought on the same day, never bought within a week, bought every item in a kit.
What she is scoring is whether your query about absence stays right when the data is messier than the sample, and whether you can explain why it does.


<br>

### What you will be able to do

Write a correlated NOT EXISTS and narrate what its probe checks for each outer row

Explain, using three-valued logic, why one NULL makes NOT IN return no rows

Choose an anti-join form and defend the choice aloud, whether it is NOT EXISTS, LEFT JOIN, NOT IN, EXCEPT or a dialect anti join

Extend an anti-join to composite keys and date windows without widening the match

Turn an 'every item' question into a double NOT EXISTS and handle the empty-list case


<br>

---

## Writing the Correlated NOT EXISTS

### The probe, narrated as you type

The first query the interviewer wants is the single-key version, and the expected shape is a correlated `NOT EXISTS`. Credit comes from narrating it while you write: for every customer row, the subquery probes `orders` for a row carrying that customer's id, and the customer survives only when the probe finds nothing. That sentence fixes the grain of the answer, one row per customer, before any SQL exists.

https://github.com/user-attachments/assets/0eb35c7f-e1de-43c9-a12b-360aa00e204f

Follow the outer rows one at a time. Alice (customer 1) has orders 101 and 103, so her probe finds a partner. `EXISTS` is TRUE, which makes `NOT EXISTS` FALSE and filters her out. Bob (2) and Dana (3) go the same way. Neither Evan (4) nor Carol (5) has an order row with their id, so both probes come back empty and both customers stay. 5 customers go in and 2 come out, because only 2 customers have no partner row. Say the count and its reason before the interviewer asks for it.

Compare the row counts with a join. A `LEFT JOIN` from these customers to these orders produces 7 rows before any filter. Alice and Bob contribute 2 each and Dana 1, and Evan and Carol get 1 NULL-padded row apiece. The probe never builds those 7 rows. It reads 5 customers and returns 2, and no amount of order history can multiply a customer.


<br>

### What the correlation does

The line WHERE o.customer_id = c.customer_id is the correlation. It references c, an alias defined only in the outer query, and that reference ties each probe to one customer. Logically the subquery runs once per outer row. Physically, a modern optimizer is free to rewrite it as a single anti-join pass over both tables, so the per-row reading describes what the query means and the optimizer chooses how it runs.

3 properties of the probe come up as follow-ups, and each has a one-line answer:

- SELECT 1, SELECT \* and SELECT NULL behave identically: EXISTS tests for a row and never reads its values.
- One match settles it: Alice's second order changes nothing, and the engine may stop after the first.
- No fan-out: a customer appears once or not at all, so 40 orders cannot inflate the result.


<br>

### The self-comparison bug

Inside a subquery, an unqualified column name resolves to the nearest table in scope that has it. Write the correlation without aliases and both sides of the equality bind to `orders`:

```sql
SELECT
  c.customer_id,
  c.name
FROM customers AS c
WHERE NOT EXISTS (
  SELECT
    1
  FROM orders AS o
  WHERE customer_id = customer_id -- both sides mean o.customer_id
)
-- every probe finds a row, so the result is empty
```

Each order now compares its own key with itself, the probe stops depending on the customer, and every customer finds a partner. The query returns zero rows, and there is no error to point at the cause. Qualifying both sides of every correlation with an alias is the habit interviewers watch for.


<br>

### Which conditions go inside the probe

The follow-up that tests whether you understand the probe is a scoped version: 'customers with no order in 2024'. The year describes the partner row, so it goes inside the subquery:

```sql
SELECT
  c.customer_id,
  c.name
FROM customers AS c
WHERE NOT EXISTS (
  SELECT
    1
  FROM orders AS o
  WHERE o.customer_id = c.customer_id
    AND o.order_date >= DATE '2024-01-01'
    AND o.order_date < DATE '2025-01-01'
)
```

A condition about the partner lives inside the probe, and a condition about the outer row lives outside it. Reverse either one and the query answers a different question. Move the date range to the outer `WHERE` and it cannot reference `o` at all. Move a customer condition such as `c.status = 'active'` inside the probe and every inactive customer's probe comes back empty, so inactive customers who ordered all year show up as customers who never ordered.

> **TIP**
>
> Before typing, say the requirement as a probe: 'For each customer, look for an order in 2024, and keep the customer when none is found.' That one sentence fixes the grain and names both the partner and its scope, which is most of what the opening minutes are graded on.


<br>

---

## The NOT IN NULL Trap

### Same data, one guest order

The interviewer's next line is usually 'Could you write it with `NOT IN` instead?' and, once you have, 'What if `orders.customer_id` contains a NULL?' In a retail schema that NULL comes from guest checkout: the order exists, the account does not. Add one guest order, 106, to the 5 orders from the probe example and run the `NOT IN` form against the same 5 customers.

https://github.com/user-attachments/assets/abdc1c42-4f4b-4696-881b-1e43dc561aee

The result is empty. Evan and Carol, who have never ordered, are gone along with everyone else, and the engine raised nothing.


<br>

### How one NULL fails every row

x NOT IN (list) means x differs from every element, so it is evaluated as a chain of <> comparisons joined by `AND`. The subquery returns 6 values, one per order, and the last of them is NULL: 1, 2, 1, 3, 2, NULL. Here is Evan's chain:

| Comparison | Result |
| --- | --- |
| `4 <> 1` | TRUE |
| `4 <> 2` | TRUE |
| `4 <> 1` | TRUE |
| `4 <> 3` | TRUE |
| `4 <> 2` | TRUE |
| `4 <> NULL` | UNKNOWN |
| All 6 joined by AND | UNKNOWN |

`WHERE` keeps a row only when its condition is TRUE, and UNKNOWN fails that test, so Evan is filtered out. Alice goes for the ordinary reason: her chain contains the FALSE comparison `1 <> 1`, and FALSE AND anything is FALSE. Once the list holds a NULL, no customer can reach TRUE: either one comparison is FALSE or the NULL supplies an UNKNOWN that the rest cannot outvote.


<br>

### Why IN survives the same NULL

`IN` is the same list joined by `OR`, and TRUE OR UNKNOWN is TRUE, so a real match still wins. Only the non-matching rows turn UNKNOWN, and those were excluded anyway. `NOT IN` flips the connective to `AND`, where one UNKNOWN blocks TRUE for every row. That asymmetry is why a report built on `IN` runs correctly for years while its negation breaks the day the first NULL arrives. Naming it explains why the bug hides, which is the depth the follow-up is fishing for.


<br>

### NOT EXISTS ignores the NULL order

`NOT EXISTS` evaluates its condition against one order at a time and asks only whether any order made it TRUE. Order 106 makes `o.customer_id = c.customer_id` UNKNOWN for every customer, UNKNOWN is not TRUE, so 106 never counts as anyone's partner. Evan's probe still finds no matching row and he stays. The NULL is ignored row by row instead of contaminating a list.

| ✓ NOT IN | ✗ NOT EXISTS |
| --- | --- |
| • One NULL in the subquery empties the whole result<br><br>• An outer NULL key is dropped whenever the subquery returns any rows<br><br>• Correct only when the subquery column is provably non-NULL<br><br>• Fails silently, returning an empty or shrunken result without an error | • An inner NULL never matches, so it changes nothing<br><br>• An outer NULL key finds no partner, so the row is kept<br><br>• Correct on any data without an extra guard<br><br>• Same result before and after the first NULL lands |


<br>

### Where the NULL comes from

- Guest checkouts: the order is real, the account is not, so customer_id is NULL by design.
- A CTE built upstream with LEFT JOIN, which emits a NULL key for every unmatched row.
- Late-arriving dimensions, where a fact row lands before its key is resolved and is backfilled later.
- A test or migration row inserted without a key, which nobody downstream was told about.


<br>

### The outer-side follow-up

A sharper interviewer turns it around: what if `customers.customer_id` is NULL for a half-migrated account? `NOT IN` drops that row whenever the subquery returns anything, and `NOT EXISTS` keeps it, because no order can equal NULL. Neither result is automatically right. State which one the business wants (an account with no id belongs in a data-quality report, not a marketing list) and filter it explicitly with `c.customer_id IS NOT NULL` if it should go.


<br>

### The guard, if NOT IN has to stay

```sql
WHERE c.customer_id NOT IN (
  SELECT o.customer_id
  FROM orders o
  WHERE o.customer_id IS NOT NULL   -- without this line, 0 rows
)
```

This version is correct. Its weakness is that correctness now depends on every future author keeping the guard, including whoever later swaps the subquery for a CTE built from a `LEFT JOIN`, which produces NULLs on purpose. Literal lists carry the same risk: `status NOT IN ('cancelled', NULL)` returns nothing, and the NULL usually arrives through a bound parameter or an upstream value, not because someone typed it into the list.

> **TIP**
>
> The one-breath answer: 'NOT IN is a chain of inequalities joined by AND. One NULL makes a link UNKNOWN, so no row can come out TRUE and the result is empty. NOT EXISTS tests orders one at a time, so a NULL order never matches anyone and changes nothing.'


<br>

---

## Choosing a Form You Can Defend

Once you have explained the NULL behaviour, the next question is 'So which one would you ship?' The form matters less than the reason attached to it. 'Whichever is fastest' and 'I always use LEFT JOIN' both cost points, because neither says what happens when the data changes. The answer that scores names the NULL behaviour, what the form returns, and the engine it will run on.


<br>

### The 5 forms side by side

| Form | NULL in the excluded column | What comes back | Where it fits |
| --- | --- | --- | --- |
| `NOT EXISTS` | Ignored, result correct | Any outer columns, once each | The default on every engine |
| `LEFT JOIN ... IS NULL` | Ignored, if the join key is tested | Any outer columns, once each | The join already exists for another reason |
| `NOT IN` | Empties the result unless guarded | Any outer columns | Literal lists and NOT NULL columns |
| `EXCEPT` | 2 NULLs compare as equal | Only the compared columns, deduplicated | Key-to-key diffs |
| `LEFT ANTI JOIN`, `ANTI JOIN` | Ignored | Left-side columns only | Spark SQL and DuckDB |

Read it column by column. The NULL column says whether a form is safe without extra care. The return column says how much work is left: `EXCEPT` hands back bare keys, so recovering a customer's name means joining again. The last column is about the dialect and the codebase you are walking into.


<br>

### LEFT JOIN ... IS NULL Has 2 Traps

This form is readable and portable, and the interviewer will probe 2 ways it goes wrong. First, the `IS NULL` test needs a column that cannot be NULL on a matched row: the join key or the right table's primary key. Test a nullable column such as `o.coupon_code` and every customer whose orders carried no coupon looks like a customer with no orders.

```sql
-- Wrong: the status filter runs after the join
SELECT c.customer_id
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.customer_id
WHERE o.status = 'paid'
  AND o.customer_id IS NULL;        -- always empty

-- Right: conditions on the excluded table go in ON
SELECT c.customer_id
FROM customers c
LEFT JOIN orders o
  ON  o.customer_id = c.customer_id
  AND o.status = 'paid'
WHERE o.order_id IS NULL;
```

Second, a filter on the excluded table placed in `WHERE` runs after the join. An unmatched row has NULL in `o.status`, so `o.status = 'paid'` can never be TRUE on the same row as `o.customer_id IS NULL`, and the query returns nothing. Moved into `ON`, the filter shapes which orders count as a match, the same job the probe's inner `WHERE` does in the `NOT EXISTS` form.

This form is the right call when the query already joins `orders` for another reason, such as a report that shows customers with and without paid orders side by side, or when the team's style guide standardises on it. Matching house style is a defensible reason, and saying so goes over better than inventing a performance argument.


<br>

### EXCEPT for key diffs

SELECT customer_id FROM customers EXCEPT SELECT customer_id FROM orders is NULL-safe in the opposite direction from NOT EXISTS: set operations treat 2 NULLs as equal, so a NULL id on both sides cancels out. It returns only the columns it compares and removes duplicates. Dialects disagree on the spelling: Oracle long used MINUS, and BigQuery requires EXCEPT DISTINCT. It fits when the task is a diff between 2 key sets with the same shape.

> When NOT IN is defensible
>
> - The list is literal constants with no NULL, such as `status NOT IN ('cancelled', 'refunded')`.
> - The subquery column is declared `NOT NULL`, and a comment says so, since a constraint describes only today's schema.
> - The subquery carries an explicit `IS NOT NULL` guard that will survive the next refactor.


<br>

### Dialect notes

- Spark SQL and Databricks: LEFT ANTI JOIN puts the intent in the join and returns only left-side columns.
- DuckDB: ANTI JOIN and SEMI JOIN are join types of their own, with the same NULL-safe meaning.
- Older MySQL ran NOT EXISTS once per outer row, so many MySQL shops standardised on LEFT JOIN ... IS NULL.
- Any engine: if speed is challenged, the answer is EXPLAIN on the real tables, not folklore about forms.


<br>

### The defence, out loud

| Interviewer asks | Answer that earns credit |
| --- | --- |
| 'Which form would you ship?' | 'NOT EXISTS. It stays correct whether or not the orders key has NULLs, and it reads like the requirement.' |
| 'Isn't NOT IN faster?' | 'With the NULL question settled, optimizers tend to plan these alike. I'd confirm with EXPLAIN before trading correctness for a guess.' |
| 'Our team uses LEFT JOIN everywhere.' | 'Then I'll match it, test the join key for NULL, and put any filter on orders in the ON clause.' |
| 'We run on Spark.' | 'LEFT ANTI JOIN says the same thing and ignores NULL keys, so I'd use it or NOT EXISTS.' |
| 'Why not EXCEPT?' | 'It returns only the key and deduplicates, so I'd need a second join to get the name back.' |

> **TIP**
>
> Order the reasons the way you rank them: correctness first, readability second, speed only when asked. The order itself tells the interviewer what you protect when a dashboard is on the line.


<br>

---

## Multi-Column Anti-Joins

The escalation arrives as a product question: 'Which users viewed the pricing page but never reached checkout on the same day?' A match now needs the user and the date to agree, and every form from the single-key version changes shape. In the `page_visits` table below, one row is one visit by a user to a page on a date; page A is pricing and page B is checkout.


<br>

### Every matching column goes in the probe

https://github.com/user-attachments/assets/4bc7439e-7e1d-45c3-ab8a-066ebc61e744

User 1 visited A and B on 2024-03-04, so the probe finds a partner and the A row is dropped. User 2 visited A on 2024-03-04 and B on 2024-03-07. The probe needs the page to agree as well as `user_id` and `visit_date`. It finds nothing, so user 2's A row survives. One row comes back.

Delete the `visit_date` line and the probe asks whether user 2 ever visited B, which they did, so user 2 vanishes and the result is empty. A column missing from the probe makes the match wider and the anti-join stricter, and the output is a plausible smaller number with no error attached. If the grain allows repeats (a user viewing pricing 3 times in one day), add `DISTINCT` to the outer select, because `NOT EXISTS` keeps every qualifying outer row.

The `LEFT JOIN` form follows the same rule. `ON` holds `b.user_id = a.user_id` along with `b.visit_date = a.visit_date` and `b.page = 'B'`, and the `IS NULL` test goes on `b.user_id`, which every matched row fills in because it is one of the join columns.


<br>

### Tuple NOT IN shrinks the result instead of emptying it

```sql
SELECT
  a.user_id,
  a.visit_date
FROM page_visits AS a
WHERE a.page = 'A'
  AND (a.user_id, a.visit_date) NOT IN (
    SELECT
      b.user_id,
      b.visit_date
    FROM page_visits AS b
    WHERE b.page = 'B'
  )
```

Row-value NOT IN is a syntax error in SQL Server but works in PostgreSQL, MySQL and Oracle. On the 4 rows shown it returns user 2's pricing visit, the same single row as NOT EXISTS. Now add one checkout row for user 2 with a NULL visit_date, so the subquery also returns (2, NULL). (a, b) <> (x, y) means a <> x OR b <> y, so that NULL row only hurts outer rows whose user_id already agrees. User 2's (2, 2024-03-04) compares as FALSE OR UNKNOWN. That evaluates to UNKNOWN, so the row disappears. Every other user's rows compare TRUE on the first column, so the NULL row cannot touch them. The result shrinks instead of emptying, which is far harder to notice than zero rows: one user quietly missing from a report of thousands.

Concatenating the keys into one string, `user_id || '|' || visit_date`, to dodge the tuple syntax is the version interviewers mark down. It depends on how dates format as text, it blocks any index on the separate columns, and in standard SQL a NULL in either part makes the whole string NULL, so the single-key NOT IN failure comes straight back.


<br>

### When the keys themselves are NULL

NOT EXISTS treats a NULL in any matching column as no match, so a pricing visit with a NULL visit_date always survives. If the business wants 2 unknown dates to count as the same day, which is rare, the probe needs b.visit_date IS NOT DISTINCT FROM a.visit_date in place of =. The usual answer is to ask whether rows with no date belong in the report at all and filter them in the outer query.


<br>

### A range instead of an equality

The next turn is 'never reached checkout within 7 days of the pricing view'. Equality on the date becomes a window, and the set of forms that can express it shrinks:

| Match condition | NOT EXISTS | LEFT JOIN ... IS NULL | NOT IN | EXCEPT |
| --- | --- | --- | --- | --- |
| One column equal | Yes | Yes | With a NULL guard | Keys only |
| Several columns equal | Yes | Yes | Tuple syntax, not SQL Server | Keys only |
| A range or window | Yes | Yes | No | No |

https://github.com/user-attachments/assets/ed6dfb8a-a7fc-4d39-a7a2-5b5d3035863d

User 1 viewed pricing on 2024-03-01 and checked out on 2024-03-03, inside the window, so that row goes. User 2 checked out on 2024-03-12, 11 days after the view and outside `a.visit_date + INTERVAL '7 days'`, so user 2 is kept. `BETWEEN` makes the window inclusive at both ends, which means a checkout on the view day itself also counts as a match.

> **TIP**
>
> 'Within 7 days' hides 2 decisions: whether the view day counts and whether day 7 counts. Ask both before writing the window. It takes 10 seconds and shows the interviewer you treat the boundary as part of the specification.


<br>

---

## Customers Who Bought Everything

The last escalation sounds positive: 'Which customers bought every item in the camping launch kit?' Underneath it is an anti-join. A customer bought everything exactly when no kit item exists that they failed to buy, so the query is 2 `NOT EXISTS` probes, one nested inside the other. The textbook name is relational division, and saying it once tells the interviewer you have seen the shape before.


<br>

### Read it as a double negative

https://github.com/user-attachments/assets/bf9382a4-6f2e-41e5-9ee4-75aa686d43ee

Narrate it from the inside out. For one customer and one kit item, the innermost probe asks whether that customer bought that item. The middle query collects the kit items where that probe found nothing: the items this customer is missing. The outer `NOT EXISTS` keeps the customer when the missing list is empty. Alice bought the tent and the lamp, so nothing is missing and she is kept. Bob bought a tent and a mug, so the lamp is missing and he is dropped; the mug never enters the check, because the middle query only walks kit items. A second tent for Alice would change nothing, since any one matching purchase satisfies the innermost probe. One row comes back.


<br>

### The counting version

```sql
SELECT
  p.customer_id
FROM purchases AS p
JOIN launch_kit AS k
  ON k.product = p.product
GROUP BY p.customer_id
HAVING COUNT(DISTINCT p.product) = (
  SELECT
    COUNT(*)
  FROM launch_kit
)
```

Many interviewers accept this form, and some prefer it because it reads like the business question. It has 2 places to break, and naming both is where the credit is. Drop the join to `launch_kit` and Bob's tent and mug count as 2 distinct products, matching the kit's 2 items, so he passes without ever buying the lamp. Drop `DISTINCT` and the count tracks purchase rows: a second tent would push Alice to 3 and fail her, while a customer who bought 2 tents and nothing else would count 2 and pass.

| ✓ Double NOT EXISTS | ✗ GROUP BY with HAVING |
| --- | --- |
| • Starts from customers, so it returns customer columns without a second join<br><br>• Duplicate purchases cannot change the answer<br><br>• Returns every customer when the kit is empty<br><br>• Extends to per-group required lists with one more correlation | • Only sees customers with at least 1 kit purchase<br><br>• Needs COUNT(DISTINCT) and the join to the kit<br><br>• Returns nobody when the kit is empty<br><br>• Easier to bend into 'bought at least half the kit' |


<br>

### The empty-kit follow-up

The follow-up is 'What if the kit has no items?' The double `NOT EXISTS` returns every customer, Bob included, because nobody is missing anything from an empty list. The count version compares against 0 but has no groups to compare, so it returns nobody. Neither is wrong in the abstract. Say which one the business means, and make it explicit, for instance with `AND EXISTS (SELECT 1 FROM launch_kit)` in the outer query, instead of inheriting whichever behaviour the form happens to have.


<br>

### Required lists that vary by row

```sql
-- Each region requires its own kit
WHERE NOT EXISTS (
  SELECT 1
  FROM regional_kit k
  WHERE k.region = c.region
    AND NOT EXISTS (
      SELECT 1
      FROM purchases p
      WHERE p.customer_id = c.customer_id
        AND p.product = k.product
    )
)
```

The middle probe gains one correlation, `k.region = c.region`, so each customer is checked only against their own region's items. The count version needs the same filter in its join and a correlated count in `HAVING`, which is the point where it starts reading worse than the nested probes.

A last variant asks for customers whose purchases are exactly the kit, nothing more. That is the division above plus one more anti-join on the purchase side: no purchase exists for this customer whose product has no row in the kit. Alice bought only the tent and the lamp, so she passes both checks. Bob fails both.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Default to NOT EXISTS and state why: it stays correct when the excluded column holds NULLs<br><br>• Qualify both sides of every correlation with a table alias<br><br>• Put each condition about the partner row inside the probe or the ON clause<br><br>• Match on every column that defines a partner, then check the row count by hand<br><br>• Ask what an empty required list should return before writing a division query | • Don't ship NOT IN against a nullable column without an IS NOT NULL guard<br><br>• Don't test a nullable right-side column for NULL in a LEFT JOIN anti-join<br><br>• Don't concatenate keys into one string to fake a multi-column match<br><br>• Don't count purchases without DISTINCT and a join to the required items<br><br>• Don't pick a form on folklore about speed when EXPLAIN can answer it |


<br>

---

## Putting It All Together

A B2B software company's customer-success team wants a list every Monday: accounts that finished all 4 required onboarding steps, opened no support ticket in the 14 days after finishing, and are not on the do-not-contact list. That list is built from a CRM export in which contacts that failed to match an account arrive with a NULL account_id.

- The 4-step requirement is relational division: a double NOT EXISTS against the onboarding steps table, with a guard for the case where the step list is empty.
- The 14-day ticket check is a multi-column anti-join on account_id plus a date window, which only NOT EXISTS or a LEFT JOIN can express.
- The do-not-contact exclusion is the NOT IN trap waiting to fire: one NULL account_id from the CRM export would empty the whole Monday list.
- Writing all 3 checks as NOT EXISTS, and saying why in one sentence each, is the defence: NULL-safe, readable, and one row per account.


<br>

---

## Key Takeaways

- An anti-join keeps a row when a probe for its partner finds nothing, and every condition about the partner belongs inside that probe.
- One NULL in a NOT IN subquery empties the result, because an AND chain with an UNKNOWN never reaches TRUE. NOT EXISTS ignores the NULL row.
- Defend the form by correctness first: NOT EXISTS is NULL-safe and readable, LEFT JOIN needs its key tested, EXCEPT returns only keys.
- A multi-column match puts every agreeing column in the probe. Leaving one out widens the match and silently shrinks the answer.
- 'Bought everything' is a double NOT EXISTS: keep the customer when no required item is missing, and decide what an empty list means.
