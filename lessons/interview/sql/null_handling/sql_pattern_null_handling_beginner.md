# NULL Handling: Beginner

Twenty minutes into a phone screen at a meal-kit company, the interviewer pastes a table into the shared editor: customer_id, name, phone, about 50,000 rows.
"Support is cleaning up contact records. Give me every customer who has no phone on record."
Most candidates type `WHERE phone = NULL`, run it, and get 0 rows. Nothing errors. The empty grid looks like a tidy answer, and the interviewer says nothing while she waits to see whether you trust it.
The question leaves something out: "no phone" can sit in that column 2 ways, and only one of them is NULL. What she is really testing is whether you know how SQL evaluates a comparison against a missing value, and whether you check a row count before you call the query done.


<br>

### What you will be able to do

Predict whether a WHERE clause keeps a row by evaluating its predicate, including when the result is UNKNOWN

Explain why an arithmetic or concatenation expression with one NULL input returns NULL, and choose a default you can defend

Find and rule out missing values with IS NULL and IS NOT NULL, and use them to check a filter's row count

Spot the <> and NOT IN filters that silently drop rows because of NULL, and rewrite them correctly

Separate NULL from 0 and the empty string, and ask the clarifying question that decides which one counts as missing


<br>

---

## The Three-Valued Logic Landmine

The prompt sounds routine: "find the customers we have no phone number for." The candidate writes `WHERE phone = NULL`, runs it against a 5-row `customers` table in which 2 phones are missing, and gets an empty result. The engine raises no error and no warning. The empty result comes from a rule about comparisons, and knowing that rule is what this question checks.

| customer_id | name | phone |
| --- | --- | --- |
| 1 | Ana | 555-0101 |
| 2 | Ben | NULL |
| 3 | Chen | 555-0303 |
| 4 | Dara | NULL |
| 5 | Eli | '' (empty string) |

*These 5 customers are the running example, and their values stay the same in every section that uses them.*

NULL marks a cell with no value in it, and any column not declared `NOT NULL` can hold one in any row. Production tables collect them from ordinary causes, such as a form field the customer skipped or a LEFT JOIN that found no match.


<br>

### A Comparison Has Three Possible Results

A SQL comparison can return UNKNOWN as well as TRUE and FALSE. A comparison that needs a value the database does not have cannot be settled. Is 5 equal to a number nobody recorded? It might be 5 and it might be anything else, so the engine answers UNKNOWN. The same holds for `<>` and `<`. It holds for `>` and every other comparison operator too, and it holds when both sides are NULL: 2 values nobody knows are not known to match.

| Expression | Result | Why |
| --- | --- | --- |
| 5 = 5 | TRUE | Both values known and equal |
| 5 = 3 | FALSE | Both values known and different |
| 5 = NULL | UNKNOWN | The right side could be anything |
| 5 <> NULL | UNKNOWN | Not-equal needs both values too |
| NULL = NULL | UNKNOWN | Two unknowns may or may not match |
| NULL > 0 | UNKNOWN | Ordering needs a value as well |

You can see the third value outside a filter. In PostgreSQL, `SELECT 5 = NULL;` returns one row holding NULL, because the engine represents UNKNOWN as a boolean NULL. Seeing that cell once makes the rest of the rule concrete.


<br>

### How AND, OR and NOT Handle UNKNOWN

Real filters combine comparisons with AND and OR, and sometimes negate them with NOT, so you also need to know how UNKNOWN moves through each. At the whiteboard, treat UNKNOWN as "could be TRUE, could be FALSE" and try both to see whether the answer changes. If it stays the same either way, that is the result. If it changes, the result is UNKNOWN.

| Expression | Result | Reasoning |
| --- | --- | --- |
| TRUE AND UNKNOWN | UNKNOWN | Depends on the unknown side |
| FALSE AND UNKNOWN | FALSE | FALSE AND anything is FALSE |
| TRUE OR UNKNOWN | TRUE | TRUE OR anything is TRUE |
| FALSE OR UNKNOWN | UNKNOWN | Depends on the unknown side |
| NOT UNKNOWN | UNKNOWN | Flipping a maybe gives a maybe |

The last row answers the follow-up interviewers like to ask right after the first mistake: "what if I write `WHERE NOT (phone = NULL)`?" It changes nothing. `NOT` turns TRUE into FALSE and FALSE into TRUE, and leaves UNKNOWN where it was, so the negated filter also comes back empty. You can arrange `=` and `<>` any way you like, with or without `NOT`, and still not get a test for a missing value.

```sql
-- All three return 0 rows, whatever the table holds
SELECT name FROM customers WHERE phone = NULL;
SELECT name FROM customers WHERE phone <> NULL;
SELECT name FROM customers WHERE NOT (phone = NULL);
```


<br>

### WHERE Keeps a Row Only When It Gets TRUE

The filter is where 3 values collapse back into 2 outcomes. WHERE evaluates its predicate once per row and keeps the row only when the result is TRUE. FALSE drops the row, and so does UNKNOWN. Here is `WHERE phone = NULL` running over the 5 customers:

https://github.com/user-attachments/assets/217e0aad-bfb6-45b1-8984-64b0d51e6747

Ana's `'555-0101' = NULL` is UNKNOWN, and so is Ben's `NULL = NULL`, the very row the query was written to find. Eli's empty string compared with NULL is UNKNOWN as well. Every row reaches UNKNOWN and none reaches TRUE, so the result is empty on any data at all. Say this out loud in the interview: an empty result from `= NULL` tells you nothing about the table, because the query could never have returned a row.

> How This Question Arrives
>
> - "Find the customers we can't reach by phone."
> - "List the orders whose status was never set."
> - "Show every order except the cancelled ones." (status is nullable)
> - "Which customers have never placed an order?" (the order's customer key can be NULL)
> - "Why does this report have fewer rows than the table?"

None of these says NULL. The tell is an optional column: a phone number, a status, a fee posted later, a customer key that a guest checkout leaves empty. When the column in the question can be missing, the interviewer is grading whether your filter accounts for UNKNOWN. A candidate who says "this column is nullable, so I need to think about what `=` does here" before typing has already scored the main point.

> **TIP**
>
> The interviewer is grading correctness first. Run the query, read the row count, and say whether it matches what the data should contain. An empty result from `= NULL` that you catch yourself is a strong answer; the same empty result caught by the interviewer is a weak one.


<br>

---

## Why NULL + 1 Is NULL

The reasoning that makes a comparison UNKNOWN makes an expression NULL. Adding 1 to a number nobody recorded produces another number nobody knows, so `NULL + 1` is NULL. The rule covers every arithmetic operator and the standard string operator `||`: one NULL input makes the whole expression NULL. The usual name is NULL propagation, and the engine reports nothing when it happens.


<br>

### One Missing Fee, One Missing Total

The running example adds an `orders` table, which records an item amount and a shipping fee for each of 6 orders. The fee is nullable because the warehouse system posts it after packing, and 2 orders have no fee yet. Order 103 shipped free, stored as `0.00`.

```sql
SELECT
  order_id,
  amount,
  shipping_fee,
  amount + shipping_fee AS order_total
FROM orders
```

| order_id | amount | shipping_fee | order_total |
| --- | --- | --- | --- |
| 101 | 40.00 | 5.00 | 45.00 |
| 102 | 25.00 | NULL | NULL |
| 103 | 60.00 | 0.00 | 60.00 |
| 104 | 15.00 | 5.00 | 20.00 |
| 105 | 30.00 | NULL | NULL |
| 106 | 20.00 | 5.00 | 25.00 |

Orders 102 and 105 lost their totals. Their amounts of 25.00 and 30.00 are known. The query still reports no total for either, because the missing fee spread through the sum. Order 103 keeps its total of 60.00: a fee of 0 is a known number and adds like one. Tax and margin computed from `order_total` afterwards start from NULL for those 2 rows, and so does any check against a free-shipping threshold.


<br>

### Zero Does Not Rescue the Expression

Candidates who know the rule still trip on expressions where the answer looks forced. Zero times anything is zero, so `NULL * 0` feels like it must be 0. SQL does not reason about which operand would decide the result; it sees a NULL input and returns NULL. Most built-in scalar functions follow the same contract: `UPPER(NULL)` is NULL, and so are `LENGTH(NULL)` and `ROUND(NULL, 2)`.

| Expression | Result |
| --- | --- |
| NULL + 1 | NULL |
| NULL \* 0 | NULL |
| NULL - NULL | NULL |
| 40.00 \* (1 - NULL) | NULL |
| 'Order ' \|\| NULL | NULL |
| UPPER(NULL) | NULL |
| '' \|\| 'Ben' | 'Ben' |

In the last row, the empty string is a real value, so concatenating it leaves the other side unchanged. Only NULL propagates.

Dates follow the rule too. Adding 3 days to a NULL `shipped_at` gives NULL, and subtracting 2 timestamps gives NULL when either one is missing, which is how a delivery-time metric drops every order that has not shipped yet without raising anything.


<br>

### Concatenation Follows the Same Rule

Building a contact label from the customers table shows propagation in text:

```sql
SELECT
  name,
  name || ' (' || phone || ')' AS contact_label
FROM customers
```

| name | contact_label |
| --- | --- |
| Ana | Ana (555-0101) |
| Ben | NULL |
| Chen | Chen (555-0303) |
| Dara | NULL |
| Eli | Eli () |

Ben and Dara lose their names along with their phones: one NULL piece erases the whole label, including the parts that were known. Eli's empty phone yields `Eli ()`, an awkward but non-NULL string. Engines split on the function form. PostgreSQL's `||` operator follows the standard and returns NULL, as it does in Snowflake and BigQuery. The `CONCAT()` function skips NULL arguments in PostgreSQL and SQL Server and returns NULL in MySQL, so name the engine before relying on either.


<br>

### Fixing It Means Choosing a Value

The fix is `COALESCE(shipping_fee, 0)`, which returns the fee when one exists and 0 when it is NULL. Writing it takes seconds. The interviewer is listening for the sentence that justifies the 0, because replacing NULL with a number asserts a fact the table does not hold.

```sql
SELECT
  order_id,
  amount + COALESCE(shipping_fee, 0) AS order_total
FROM orders
-- 102 -> 25.00 and 105 -> 30.00
-- the other 4 orders keep the totals above
```

| ✓ Default to 0 when | ✗ Keep the NULL when |
| --- | --- |
| • The column counts events, and missing means none happened<br><br>• The consumer needs a number in every row, such as a billing export<br><br>• You state the assumption and the interviewer accepts it | • Missing means not known yet, like a fee the warehouse posts later<br><br>• A 0 would be read as a real value, such as free shipping<br><br>• Someone downstream needs to find the gaps and chase them |

> The Phrasings That Point Here
>
> - "Why do some rows in my report show a blank total?"
> - "Build a full-name column, with the middle name between first and last."
> - "Compute each order's price after discount." (the discount is optional)
> - "Add the bonus to base salary for every employee."

> **TIP**
>
> An answer that scores sounds like this: "I'm defaulting the fee to 0 so the total comes back as a number, which assumes an unposted fee is free. If unposted means pending, I'd keep it NULL and list those orders separately." That names the propagation and the fix, and says what the fix costs.


<br>

---

## Finding NULLs With IS NULL

`IS NULL` is its own predicate, separate from `=`. It asks whether a value is missing and answers TRUE or FALSE, never UNKNOWN. That 2-valued answer is what makes it safe inside WHERE: a NULL phone gets TRUE and the row is kept, any other phone gets FALSE and the row is dropped. `IS NOT NULL` is its exact complement, and both work on every type, from strings to numbers to dates.

```sql
-- Customers with no phone on file: Ben, Dara
SELECT customer_id, name
FROM customers
WHERE phone IS NULL;

-- Customers with any phone value: Ana, Chen, Eli
SELECT customer_id, name
FROM customers
WHERE phone IS NOT NULL;
```


<br>

### Each Predicate, Row by Row

Laying the 3 predicates side by side for the 5 customers shows why only one of them answers the question:

| name | phone | phone = NULL | phone IS NULL | phone IS NOT NULL |
| --- | --- | --- | --- | --- |
| Ana | 555-0101 | UNKNOWN | FALSE | TRUE |
| Ben | NULL | UNKNOWN | TRUE | FALSE |
| Chen | 555-0303 | UNKNOWN | FALSE | TRUE |
| Dara | NULL | UNKNOWN | TRUE | FALSE |
| Eli | '' (empty) | UNKNOWN | FALSE | TRUE |

`IS NULL` returns Ben and Dara, 2 rows. `IS NOT NULL` returns the other 3 rows, Eli's among them along with Ana's and Chen's. Those counts add to 5, the full table. The `phone = NULL` column holds no TRUE anywhere, which is the empty result from the opening query, and no FALSE either, which is why negating it stays empty.


<br>

### The Two Predicates Split the Table Exactly

That sum is the property to lean on. `IS NULL` and `IS NOT NULL` put every row on exactly one side for any column, so their counts always add to the table's row count. A pair built from `=` and `<>` loses that guarantee as soon as one NULL appears. The predicate therefore doubles as a measuring tool: profile the column before writing the real query.

```sql
SELECT COUNT(*) AS missing_phone
FROM customers
WHERE phone IS NULL;       -- 2

SELECT COUNT(*) AS has_phone
FROM customers
WHERE phone IS NOT NULL;   -- 3
```

In an interview you rarely get to run the profile, so say it: "Before filtering, I'd check how many phones are NULL, so I know what the result should contain." That line tells the interviewer you treat a nullable column as something to measure, and it sets up the row-count check that exposes filter traps later in the answer.


<br>

### Keeping or Dropping NULLs Deliberately

Most real filters mix a value test with a NULL test. The NULL test has to be written out whenever the missing rows should stay, because the value test never gives a NULL row TRUE.

```sql
-- Orders with a fee charged or not yet posted
SELECT
  order_id
FROM orders
WHERE shipping_fee > 0
  OR shipping_fee IS NULL
-- 101, 102, 104, 105, 106
```

Orders 102 and 105 vanish without `OR shipping_fee IS NULL`, because `NULL > 0` is UNKNOWN. The opposite case needs no extra clause: a filter meant to exclude NULLs already does, since every comparison on a NULL row fails. Writing `IS NOT NULL` anyway helps the next reader see the intent. `WHERE phone IS NOT NULL AND phone LIKE '555-%'` returns the same 2 rows for Ana and Chen that the `LIKE` returns alone, and it states the decision in the code.


<br>

### IS NULL After a LEFT JOIN

The same predicate finds missing matches as well as missing values. Each order also carries a `customer_id`: orders 101 and 105 belong to Ana (1), 102 to Ben (2), 103 to Chen (3) and 104 to Dara (4), and order 106 is a guest checkout whose `customer_id` is NULL. Eli (5) placed none. A LEFT JOIN keeps every row from the left table and fills the right side's columns with NULL where nothing matched, so filtering one of those columns with `IS NULL` returns exactly the unmatched rows.

```sql
SELECT
  c.customer_id,
  c.name
FROM customers AS c
LEFT JOIN orders AS o
  ON o.customer_id = c.customer_id
WHERE o.order_id IS NULL
-- 5, Eli: the one customer with no orders
```

Test a column that can only be NULL because the match failed, such as the right table's key `order_id`. Testing a column that is nullable in its own right, like `shipping_fee`, would also return Ben and Ana. Their orders 102 and 105 matched but have no fee posted.

> When an Engine Seems to Accept = NULL
>
> SQL Server has a session setting, `SET ANSI_NULLS OFF`, under which `= NULL` behaves like `IS NULL`. Microsoft has marked the OFF setting for removal, and code written against it breaks the moment it runs on another engine or session. If an interviewer raises it, the answer is that you write `IS NULL` everywhere and depend on no session mode.

> **TIP**
>
> Read the schema before the question goes deep. A column declared `NOT NULL` cannot hold NULL, so a NULL test on it does nothing. Any column without that declaration can, whatever the 10 sample rows on screen show.


<br>

---

## NULLs Break Equality in WHERE

The `= NULL` mistake from the opening is visible once you know the rule. The version that gets through code review looks correct: a not-equal filter on a column that sometimes holds NULL. Asked for "every order except the cancelled ones", nearly every candidate writes `WHERE status <> 'cancelled'`. The `orders` table has 6 rows and 1 cancelled order, so the expected answer is 5 rows. The query returns 4.

https://github.com/user-attachments/assets/e76ebd61-9a64-4a63-a48e-04ea593356af

For order 105, `'cancelled' <> 'cancelled'` is FALSE, so the row drops as intended. Order 104 has no status, so `NULL <> 'cancelled'` is UNKNOWN and the row drops too, though the question never asked to exclude it. An order with no recorded status was never shown to be cancelled, so the business question keeps it, and the filter silently disagrees with the question.


<br>

### The Row-Count Check That Catches It

A filter and its opposite should cover the whole table between them. Run both and add the counts:

| Filter | Rows returned |
| --- | --- |
| status = 'cancelled' | 1 (order 105) |
| status <> 'cancelled' | 4 (orders 101, 102, 103, 106) |
| Sum of both | 5 |
| Rows in orders | 6 |

If every comparison came back TRUE or FALSE, each row would land on one side or the other. The rows that land on neither are the ones whose comparison came back UNKNOWN, here order 104's NULL status. Saying "1 plus 4 is 5, the table has 6, so a NULL status is falling through" is the diagnosis the interviewer is waiting for, and it works on any filter you are unsure about.


<br>

### The Fix and Its Parentheses

```sql
SELECT
  order_id,
  status
FROM orders
WHERE status <> 'cancelled'
  OR status IS NULL
-- 101, 102, 103, 104, 106: 5 rows
```

The extra clause turns order 104's UNKNOWN OR TRUE into TRUE, so the row stays. A second trap appears as soon as another condition joins the fix. AND binds tighter than OR, so this filter for customer 1's non-cancelled orders is wrong:

```sql
-- Wrong: runs as (customer_id = 1 AND status <> 'cancelled')
--        OR status IS NULL
WHERE customer_id = 1
  AND status <> 'cancelled'
   OR status IS NULL

-- Right: group the status test
WHERE customer_id = 1
  AND (status <> 'cancelled' OR status IS NULL)
```

The unparenthesised version returns customer 1's order 101, plus order 104, which belongs to customer 4 and slips in through the bare `OR`. On 6 rows you would see the stray order; on 6 million rows nobody does. Write the parentheses every time `OR col IS NULL` sits next to an AND.


<br>

### NOT IN and One NULL

The harsher version of this trap asks about absence: "which customers have never placed an order?" The natural answer is `NOT IN` over the order table's customer keys. In the running example, order 106 is a guest checkout, so its `customer_id` is NULL. Eli, customer 5, has no orders, so the expected answer is 1 row.

https://github.com/user-attachments/assets/20d04eb5-3407-4dd3-935f-5e36ecf9045b

The result is empty. `NOT IN` expands into not-equal tests joined by AND, so for Eli it reads `5 <> 1 AND 5 <> 2 AND 5 <> 3 AND 5 <> 4 AND 5 <> 1 AND 5 <> NULL`. The first 5 tests are TRUE, the last is UNKNOWN, and TRUE AND UNKNOWN is UNKNOWN, so Eli drops. Every other customer matches some order and gets FALSE. One NULL anywhere in the list stops `NOT IN` from ever returning a row.

`IN` handles the same NULL: `customer_id IN (1, NULL)` is TRUE for customer 1, because one TRUE match settles an OR chain. Say that asymmetry out loud. IN needs a single TRUE comparison, NOT IN needs every comparison to be TRUE, and a NULL in the list makes one comparison UNKNOWN for every row.

```sql
-- Fix 1: keep NULLs out of the list
SELECT customer_id, name
FROM customers
WHERE customer_id NOT IN (
  SELECT customer_id
  FROM orders
  WHERE customer_id IS NOT NULL
);

-- Fix 2: test for a matching row instead
SELECT c.customer_id, c.name
FROM customers AS c
WHERE NOT EXISTS (
  SELECT 1
  FROM orders AS o
  WHERE o.customer_id = c.customer_id
);
-- Both return one row: 5, Eli
```

| ✓ NOT IN (subquery) | ✗ NOT EXISTS |
| --- | --- |
| • Compares each customer against every value the subquery returns<br><br>• One NULL in that list empties the whole result<br><br>• Needs IS NOT NULL inside the subquery to be safe | • Asks whether any order row matches this customer<br><br>• The guest order's NULL key matches nobody and is ignored<br><br>• Stays correct whether the key column is nullable |

> **TIP**
>
> Reach for `NOT EXISTS` by default when the question is about absence, and say why: it stays correct if the key column ever becomes nullable. The other form interviewers accept is the LEFT JOIN filtered on `o.order_id IS NULL` from the previous section, which returns the same single row for Eli.

> Other questions that hide the same NULL filter
>
> - "Orders not from test accounts" over a nullable account_type column
> - "Users not on the blocklist" when the blocklist import left some emails NULL
> - "Products that never sold" with NOT IN over order lines missing a product key
> - "Sessions without a purchase" where the purchase's session key can be NULL


<br>

---

## NULL Means Unknown, Not Empty

The opening question had a second layer. Eli's phone is the empty string `''`, so every `IS NULL` query so far has left Eli out. That is correct behaviour and possibly the wrong answer, because NULL records a different fact from the empty string, and 0 records a third, and "customers we have no phone number for" does not say which fact it means.

| Stored phone | What the row says | phone IS NULL | phone = '' | LENGTH(phone) |
| --- | --- | --- | --- | --- |
| NULL (Ben) | Nobody recorded a phone | TRUE | UNKNOWN | NULL |
| '' (Eli) | A phone was saved, and it is blank | FALSE | TRUE | 0 |
| '555-0101' (Ana) | The phone is 555-0101 | FALSE | FALSE | 8 |

NULL is the absence of a value: the database holds nothing in that cell, and every comparison against it is UNKNOWN. An empty string is a value, a string of length 0 that equals itself and that you can compare or concatenate like any other string. Ben's row says the company does not know his phone. Eli's row says a phone field was saved and it was blank, perhaps from a form submitted with the box cleared.

| order_id | shipping_fee | What it says |
| --- | --- | --- |
| 101 | 5.00 | Standard fee charged |
| 102 | NULL | Fee not posted yet |
| 103 | 0.00 | Shipped free |

Numbers split the same way. Order 103's 0.00 is a settled fact, and a finance analyst reading it closes the order. Order 102's NULL is an open question, and the same analyst chases the warehouse about it. A dashboard that draws both as 0, or both as a blank cell, hides that difference, which is why the stored value decides what a query should do with the row.


<br>

### Where the Distinction Changes the Answer

On the 5 customers, "how many have no phone?" has 2 defensible answers:

```sql
-- Never recorded: Ben, Dara (2 rows)
SELECT name FROM customers
WHERE phone IS NULL;

-- Never recorded or saved blank: Ben, Dara, Eli (3 rows)
SELECT name FROM customers
WHERE phone IS NULL OR phone = '';
```

Neither count is wrong in the abstract. If support wants every customer they cannot call, Eli belongs in the list, since a blank phone dials nobody. If the data team wants to know how often the signup form saved no phone at all, Eli does not. The interviewer usually has one reading in mind and has left it unstated on purpose.


<br>

### The Clarifying Question to Ask

Ask before writing the filter, and ask with the data in front of you: "I see phones stored as NULL and at least one stored as an empty string. Should a blank phone count as missing?" The question shows you looked at the values instead of assuming, and it hands the choice to the person who owns the requirement. If the answer is yes, the `OR phone = ''` form is the query. If the sample also shows phones made only of spaces, replace that test with `TRIM(phone) = ''` and say why.

> Oracle Stores the Empty String as NULL
>
> In Oracle, inserting `''` into a VARCHAR2 column stores NULL, so `phone = ''` is UNKNOWN on every row and `LENGTH('')` is NULL. PostgreSQL and SQL Server keep the two apart. So do MySQL and Snowflake, and so does BigQuery. A query that counts blank phones correctly on one engine can count 0 on another, so name the engine whenever the question involves empty strings.


<br>

### Defaults Erase the Difference

The `COALESCE(shipping_fee, 0)` fix has a cost. After coalescing, order 102's unposted fee and order 103's free shipping both read 0.00, and no later query can tell them apart. The same loss happens when a load job writes `''` for every missing phone: Ben's row and Eli's row become indistinguishable. Keep NULL in stored data wherever the gap is real, and apply defaults inside the query that needs a number, where the assumption sits next to the result it changes.

> **TIP**
>
> If the interviewer turns it back, "what would you do?", pick a reading and give the reason: "For the call list I'd count blank as missing, because support can't dial an empty string, and I'd report NULL and blank separately to the data team." A choice with a reason scores; a string of questions with no decision does not.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Test for missing values with IS NULL and IS NOT NULL, every time<br><br>• Ask whether each column in the question can hold NULL before filtering on it<br><br>• Add OR col IS NULL to a <> filter when rows with no value should stay<br><br>• Check that a filter and its opposite add up to the table's row count<br><br>• Ask whether blank strings and zeros count as missing for this question | • Write = NULL or <> NULL; both return UNKNOWN for every row<br><br>• Use NOT IN over a column that can hold NULL; use NOT EXISTS instead<br><br>• Mix AND with OR col IS NULL without parentheses<br><br>• Default NULL to 0 or '' without saying what the default assumes<br><br>• Assume an empty string and NULL behave the same on every engine |


<br>

---

## Putting It All Together

A meal-kit company's support lead asks for a call list: every customer with no usable phone, excluding accounts whose status is 'closed', and only customers who have never received a callback. Callbacks live in a table where an old import left some customer_id values NULL. The list goes to a vendor that bills per row, and last week's version came back empty.

- The empty list traces to NOT IN over callbacks: one NULL customer_id empties it, so the exclusion becomes NOT EXISTS.
- "No usable phone" is phone IS NULL OR phone = '', a reading to confirm with the support lead because blank and missing differ.
- "Excluding closed" needs (status <> 'closed' OR status IS NULL) in parentheses, or every customer with no status silently drops off.
- Counting IS NULL and IS NOT NULL at each step lets you explain the final row count before the vendor bills for it.


<br>

---

## Key Takeaways

- A comparison with NULL is UNKNOWN and WHERE keeps only TRUE, so = NULL and <> NULL return 0 rows on any data.
- One NULL input makes an arithmetic or || expression NULL; COALESCE(fee, 0) fixes it only if you can defend the 0.
- IS NULL and IS NOT NULL never return UNKNOWN, so they split a table exactly and work both as filters and as row-count checks.
- A <> filter drops NULL rows and one NULL in a NOT IN list empties the result; add OR col IS NULL or use NOT EXISTS.
- NULL, '' and 0 record different facts, so ask which one counts as missing before writing the filter.
