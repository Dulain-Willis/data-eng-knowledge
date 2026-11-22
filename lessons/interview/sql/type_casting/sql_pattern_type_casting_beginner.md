# Type Casting: Beginner

Forty minutes into a live SQL round at a subscription app, the interviewer shares a table called `weekly_funnel`: `week`, `signups`, `conversions`.
"Give me the conversion rate for each week. Then we'll move on."
You type `conversions / signups`, run it, and every row comes back 0. She waits. Nothing on the screen says both columns are integers, and nothing will: the query is valid, the engine prints no warning, and a zero looks like a measurement.
Two more tables are queued behind this one: an orders feed whose amounts arrived as text, and an events table that records time as a 13-digit number. Each hides the same problem in a different place. What she is grading is whether you ask how a column is stored before you believe what it returns.


<br>

### What you will be able to do

Spot a column whose stored type contradicts the meaning of its values, from symptoms that never raise an error

Write CAST and :: conversions and place them on the operand that needs converting

Keep the fraction in a ratio and guard its denominator against zero

Predict which side converts when text meets a number in a filter or a join

Identify an epoch value's unit and turn it into a timestamp you have checked


<br>

---

## When Types Mismatch Silently

This part of the round almost never announces itself as a type question. It shows up as a result that looks reasonable: a rate column full of zeros, a top-orders list missing the biggest order, a signup chart with a single bar in January 1970. The interviewer has built a table where a column's declared type disagrees with what its values represent, and the first thing graded is whether you notice that before you start explaining the output.


<br>

### Stored type versus meaning

Every column carries 2 types at once. The stored type is what the DDL declared: `VARCHAR`, `INTEGER`, `BIGINT`. The meaning is what the values represent: a dollar amount, a postal code, a moment in time. When the 2 agree, every operation does what you read it as doing. When they disagree, the engine still runs every operation, because it validates each one against the stored type and has no access to the meaning.

| Column | Stored as | Means | What goes wrong |
| --- | --- | --- | --- |
| amount_text | VARCHAR | dollar amount | sorts and compares character by character |
| customer_zip | INTEGER | postal code | 02134 is stored as 2134 and the leading zero is gone |
| signups, conversions | INTEGER | counts used in a rate | dividing one by the other discards the fraction |
| created_at_epoch | BIGINT | moment in time | a count of units with no unit attached |
| order_date | VARCHAR | calendar date | '3/9/2024' sorts after '3/10/2024' |


<br>

### Why the engine stays quiet

An error fires only when an operation does not exist for the stored type. `SUM(amount_text)` on Postgres fails with 'function sum(character varying) does not exist', and that is the lucky case, because you find out at once. Text supports sorting and `MIN`, and also `MAX`, `=`, `<` and `DISTINCT`, so on a text column they all run without complaint and apply text rules: compare the first character, and look at the second only on a tie. Integer division exists for integers and returns an integer. Each operation is correct for the type it received, and wrong only for a meaning the engine never sees.

Mismatches come from the path the data travelled. CSV and JSON carry no types, so a loader either guesses or defaults every column to text. JSON extraction with `->>` returns text by design. A spreadsheet export turns 02134 into the number 2134 before any pipeline sees it. When the interviewer says the data arrived as a CSV drop or a JSON payload, or came from a partner file, they are pointing at a type.


<br>

### The running example: amounts landed as text

A partner sends daily order files as CSV, and the loader created every column as `VARCHAR` so that no row would be rejected. `raw_orders` holds 5 orders, ids 101 to 105, with amounts of 1250.00, 99.00, 8.50, 75.00 and 310.00. Asked for the 3 largest, the engine sorts the text.

```sql
-- amount_text is VARCHAR, so this sort compares characters
SELECT
  order_id,
  amount_text
FROM raw_orders
ORDER BY amount_text DESC
LIMIT 3
```

Sorted as text

Sorted as DECIMAL(10,2)

The text sort ranks '9' above '8' above '7', so 99.00 outranks 1250.00, whose first character is '1'. `MAX(amount_text)` returns '99.00' for the same reason. Neither query is invalid. On a 5-row sample the error is visible at a glance; on a table of 40 million rows it reaches a dashboard and stays there until a finance analyst asks why the biggest order of the quarter was 99 dollars.


<br>

### Symptoms that point at a type

- A rate or average that is exactly 0 on most rows: integer division
- A sort where 99 outranks 1250: numbers stored as text
- Dates in 1970, or thousands of years ahead: an epoch read in the wrong unit
- A join matching far fewer rows than either table holds: the key types differ
- Postal codes or ids with 4 digits where 5 belong: a leading zero lost to an integer column


<br>

### Checking the type first

The habit that scores at this stage is a type check, said out loud, before the first real query. Read the schema the interviewer shows; when there is none, ask for it. On Postgres and most warehouses the catalog answers in a single query:

```sql
SELECT
  column_name,
  data_type
FROM information_schema.columns
WHERE table_name = 'raw_orders'
```

> Phrasings that mean a type is involved
>
> - "The rate comes back 0 for every week. What's wrong?"
> - "These amounts came from a partner CSV. Find the 10 largest orders."
> - "Join the CRM accounts to the events table on customer id."
> - "created_at is a number. Show me signups per day."
> - "Why does this report say the biggest order was 99 dollars?"

The usual mistake is explaining a wrong result instead of questioning it. Candidates who see a column of zeros start debugging the join or the filter, and lose 5 minutes there. When a number is suspiciously round, a sort is out of order or a date is decades off, the first suspect is a column stored as something other than what it means.

> **TIP**
>
> Name the type alongside the column: 'amount_text is a VARCHAR, so I'll cast it to a decimal before I sort or compare it.' That sentence costs 5 seconds and shows the interviewer you check types before reading results, which is most of what this stage grades.


<br>

---

## CAST and Its Double-Colon Form

Once the mismatch has a name, the repair is an explicit conversion, and the interviewer watches for 2 things: that you write it without hesitating, and that it lands on the right part of the expression. SQL offers 2 spellings of the same operation.

```sql
-- ANSI standard: runs on every major engine
SELECT CAST(amount_text AS DECIMAL(10,2)) AS amount
FROM raw_orders;

-- Postgres-family shorthand: Postgres, Redshift, Snowflake, DuckDB
SELECT amount_text::DECIMAL(10,2) AS amount
FROM raw_orders;
```

Both return the same 5 decimals, and both are explicit: you name the target type instead of letting the engine choose one. `CAST(x AS type)` is the SQL standard. SQL Server and BigQuery accept it, as do MySQL and Oracle, and all 4 reject `::` as a syntax error. The double colon is shorter, which is why Postgres and Snowflake codebases are full of it. Match the engine named in the question, and write `CAST` when no engine is named.


<br>

### The targets you will actually write

| Target | Spelled | Typical use |
| --- | --- | --- |
| exact decimal | DECIMAL(10,2), NUMERIC(10,2) | amounts that arrived as text |
| whole number | INTEGER, BIGINT | ids, counts, epoch values held as text |
| floating point | DOUBLE PRECISION, FLOAT | ratios and averages |
| text | VARCHAR, TEXT | concatenation, matching a text key |
| calendar date | DATE | dropping the time from a timestamp |
| date and time | TIMESTAMP | ISO text such as '2024-03-15 14:30:45' |

`DECIMAL(10,2)` allows 10 digits in total with 2 after the point, so its largest value is 99,999,999.99. A value too wide for the target fails the cast instead of wrapping around, which is the behaviour you want from an amount column.

Text in ISO 8601 form, '2024-03-15' or '2024-03-15 14:30:45', casts to `DATE` or `TIMESTAMP` on every major engine. Text in any other layout, such as '03/15/2024', needs a format string, and that is a different function with its own rules.


<br>

### What a cast does to the value

| Expression | Result | What happened |
| --- | --- | --- |
| CAST('1250.00' AS DECIMAL(10,2)) | 1250.00 | text parsed into an exact decimal |
| CAST(1250.00 AS VARCHAR) | '1250.00' | number written out as characters |
| CAST(8.50 AS INTEGER) | 8 or 9 | fraction removed; engines differ on rounding |
| CAST(TIMESTAMP '2024-03-15 14:30:45' AS DATE) | 2024-03-15 | time of day dropped |
| CAST(NULL AS INTEGER) | NULL | NULL stays NULL in every type |
| CAST('N/A' AS DECIMAL(10,2)) | error | the whole statement stops |

The last row is the one to know cold. A strict cast stops the entire statement at the first value it cannot parse, so a single 'N/A' among 40 million rows fails the query. When the column is supposed to be clean, that failure is a feature: the error is your data-quality alert. When the column is known to be dirty, functions that return NULL instead of failing are the separate tool, and naming them is enough unless the interviewer asks for more.


<br>

### Where the cast binds

`::` binds tighter than every arithmetic operator, so it converts only the single operand immediately to its left. `CAST` converts exactly what sits inside its parentheses. Those 2 rules decide what changes type, and the interviewer reads your parentheses to see whether you know them.

```sql
-- :: attaches to amount_text alone: convert first, then multiply
SELECT amount_text::DECIMAL(10,2) * 1.08 AS with_tax
FROM raw_orders;

-- the cast arrives too late: Postgres rejects text * numeric
SELECT (amount_text * 1.08)::DECIMAL(10,2) AS with_tax
FROM raw_orders;
```

The second query fails on Postgres with 'operator does not exist: character varying \* numeric', because the multiplication runs before the cast. Convert a value at the point where it enters arithmetic or a comparison, never afterwards. The tidiest way to guarantee that is to cast once, at the top of the query:

```sql
WITH orders AS (
  SELECT
    order_id,
    CAST(amount_text AS DECIMAL(10, 2)) AS amount
  FROM raw_orders
)

SELECT
  order_id,
  amount
FROM orders
ORDER BY amount DESC
LIMIT 3
```

This returns the real top 3, with order 101 first, then 105 and 102. Saying 'I cast once in the source CTE so nothing downstream ever touches the text column' gives the interviewer a design reason along with the syntax, and it means a later filter or join cannot quietly bring the text rules back.


<br>

### Typed literals

Literals carry types too. `'2024-03-15'` is a string. `DATE '2024-03-15'` and `TIMESTAMP '2024-03-15 14:30:45'` are typed literals from the SQL standard, and `'2024-03-15'::DATE` is the shorthand. Writing a literal with its type removes a decision from the engine, which matters most in comparisons, where the engine otherwise picks which side converts.

> **TIP**
>
> With no engine named, write `CAST`. It runs everywhere, nobody marks down the long form, and a `::` written into a SQL Server or BigQuery exercise reads as a syntax error before it reads as a cast.


<br>

---

## Integer Division Drops the Decimal

This is the type bug interviewers plant most often, because it hides in the most ordinary request: 2 count columns and a question about a rate. `weekly_funnel` holds 3 weeks.

```sql
SELECT
  week,
  signups,
  conversions,
  conversions / signups AS rate
FROM weekly_funnel
```

| week | signups | conversions | rate |
| --- | --- | --- | --- |
| 2024-02-26 | 1000 | 250 | 0 |
| 2024-03-04 | 830 | 7 | 0 |
| 2024-03-11 | 1200 | 330 | 0 |

On Postgres and SQL Server, and on Redshift and SQLite too, an integer divided by an integer returns an integer, and the fraction is thrown away. Dividing 250 by 1000 gives 0.25, whose integer part is 0. The truncation runs toward zero, so `-7 / 2` returns -3 on Postgres, where Python's `-7 // 2` returns -4. MySQL and BigQuery return a fraction from the same expression, as do Snowflake and DuckDB. That is how the bug appears when a query moves from a warehouse to a Postgres replica with no edits at all.


<br>

### Promoting one operand

A division takes its result type from its operands. When either one is a decimal or a float, the engine promotes the other and keeps the fraction. Any of these does it:

```sql
-- multiply by a decimal literal first
SELECT conversions * 1.0 / signups AS rate FROM weekly_funnel;

-- cast the numerator
SELECT CAST(conversions AS DECIMAL(12,4)) / signups AS rate FROM weekly_funnel;

-- Postgres-family shorthand on the numerator
SELECT conversions::DECIMAL / signups AS rate FROM weekly_funnel;
```

Each returns 0.25, about 0.0084 and 0.275 for the 3 weeks. The `* 1.0` form is what most candidates type, and it works because `*` and `/` share a precedence level and evaluate left to right: `conversions * 1.0` runs first and produces a decimal. The `CAST` form states the intent in words, which reads better in code someone else will maintain.


<br>

### Fixes that still return zero

A conversion that runs after the division comes too late. All 3 of these still lose the fraction:

```sql
-- the division runs first; 0 * 1.0 is still 0
SELECT conversions / signups * 1.0 AS rate FROM weekly_funnel;

-- the cast converts a quotient that is already 0
SELECT CAST(conversions / signups AS DECIMAL(12,4)) AS rate FROM weekly_funnel;

-- a percentage hides the truncation until it bites
SELECT 100 * conversions / signups AS pct FROM weekly_funnel;
```

The third is the dangerous one, because it looks fixed. The first week returns 25, correct only because 25,000 divides evenly by 1000. The third week returns 27 where the true figure is 27.5, and the second returns 0 where the true figure is roughly 0.84. A low-converting cohort is exactly what an analyst is hunting for, and this query reports it as zero. Writing `100.0 * conversions / signups` returns 25, about 0.84 and 27.5.


<br>

### Guarding the denominator

The follow-up arrives almost every time: 'what if a week has no signups?' Postgres and SQL Server raise an error on division by zero, and Snowflake and BigQuery do the same, so a single empty week stops the whole report. `NULLIF(signups, 0)` returns NULL when signups is 0, and arithmetic with a NULL operand returns NULL, so that week's rate becomes NULL instead of an error.

```sql
SELECT
  week,
  conversions * 1.0 / NULLIF(signups, 0) AS rate
FROM weekly_funnel
```

Use that line for any rate question: a decimal in the numerator, NULLIF around the denominator. When the interviewer asks why NULL and not 0, the answer is that a week with no signups has no conversion rate. A 0 would claim a rate that was measured and found to be zero, and it would drag down any average taken across weeks.

> The same bug in other costumes
>
> - Average units per order as `SUM(quantity) / COUNT(*)`: both sides are integers, so 7 units over 3 orders reports 2
> - Share of late shipments as `SUM(CASE WHEN late THEN 1 ELSE 0 END) / COUNT(*)`: reports 0 until every order is late
> - Minutes between events as `seconds_between / 60`: 119 seconds reports as 1 minute
> - Milliseconds to seconds as `epoch_ms / 1000`: the sub-second part disappears


<br>

### When truncation is what you want

Integer division is the right tool when you want buckets. `minute_of_day / 15 * 15` maps minutes 0 to 14 onto 0 and 15 to 29 onto 15, a 15-minute bucket with no function call, and `age / 10 * 10` groups ages by decade. Saying 'here the truncation is intentional' shows the interviewer you control the behaviour instead of tripping over it. Negative values truncate toward zero rather than down, so -5 lands in bucket 0 next to 5, and for signed data `FLOOR` over a decimal division is the safer tool.

> **TIP**
>
> Say the rule while you type it: 'both counts are integers, so I multiply by 1.0 before dividing and wrap the denominator in NULLIF.' Interviewers hear that as someone who has shipped this bug once and will not ship it again.


<br>

---

## Comparing a String to a Number

This part arrives as a filter or a join that returns the wrong number of rows. 'Find orders over 100 dollars' against `amount_text`, or 'join the CRM accounts to events on customer id' where a table stores the id as an integer and the other stores it as text. Underneath both is a single question: which side does the engine convert, and does it convert at all?


<br>

### Text against text: nothing converts

With the threshold quoted, as in `amount_text > '100'`, both sides are text. Nothing converts, and the engine compares the strings a character at a time from the left, stopping at the first difference. The animation runs that comparison beside a cast-and-compare version over the 5 orders in `raw_orders`.

https://github.com/user-attachments/assets/04bb99de-69ee-43c2-96e9-6d12a2914f02

Watch the as_text column fill in. '8.50' passes because '8' comes after '1'; '99.00', '75.00' and '310.00' pass on their first character the same way; '1250.00' ties on '1' and passes on its second character, '2' against '0'. Every order counts as more than 100. The as_number column casts first and compares against the number 100, keeping only orders 101 and 105, which is what the business asked for.


<br>

### Text against a number: the string side converts

Remove the quotes and the 2 sides now hold different types. Engines that convert implicitly, such as SQL Server and Snowflake, rank types by precedence, and character types rank lowest, so when a string meets a number the string is converted. Postgres works differently: a quoted literal has no type until context gives it one, so `WHERE order_id = '101'` reads '101' as the integer 101, but a `VARCHAR` column compared with an integer is rejected with an error. When the string is a literal, a single value converts once and the result is usually harmless. When the string is the column, the conversion runs on every row, so the column's worst value decides the outcome. An `IN (2134, 10001)` list follows the same rule, since it is a chain of `=` comparisons.

Take `ship_zip`, a `VARCHAR` column holding '02134', '10001' and 'K1A 0B1', a Canadian postal code, filtered with `WHERE ship_zip = 2134`:

| Engine | What it does with ship_zip | When it reaches 'K1A 0B1' |
| --- | --- | --- |
| SQL Server | converts every value to INT; '02134' matches 2134 | fails: conversion failed for 'K1A 0B1' |
| Snowflake | converts every value to NUMBER | fails: numeric value not recognized |
| MySQL | compares both sides as floating-point numbers | becomes 0 with a warning, no error |
| Postgres | refuses: operator does not exist: character varying = integer | fails before reading a row |

The table has 2 silent outcomes. The leading-zero collapse makes '02134' and '2134' equal the same number, so 2 different strings become a single key. MySQL's conversion turns every non-numeric string into 0, so `WHERE ship_zip = 0` returns every Canadian address. The failures are the better outcome: a failed query is a bug report you get today, while a wrong count nobody notices is a meeting 3 weeks from now.


<br>

### Choosing the type from the meaning

The fix is to pick the comparison type on purpose and cast toward it, and meaning decides the pick. A zip code is an identifier: nobody adds 2 zip codes together, and the leading zero is part of the value, so compare as text with `WHERE ship_zip = '02134'`. An amount is a quantity, so compare as a number with `WHERE CAST(amount_text AS DECIMAL(10,2)) > 100`. SKUs are identifiers even when every character is a digit, and so are phone and account numbers.

| ✓ Compare as text | ✗ Compare as a number |
| --- | --- |
| • Identifiers: zip codes and SKUs, plus phone and account numbers<br><br>• Leading zeros and letters survive the comparison<br><br>• Quote the literal: '02134'<br><br>• > and ORDER BY follow character rules, so avoid range filters | • Quantities: amounts, counts, durations<br><br>• Cast the text column explicitly: CAST(x AS DECIMAL(10,2))<br><br>• A non-numeric value fails the cast loudly<br><br>• > and ORDER BY follow numeric rules |


<br>

### The join version

A join condition is a comparison evaluated for every candidate pair, so an `INTEGER` key in `accounts` meeting a `VARCHAR` key in `events` follows the same precedence rule across the whole table. Write the conversion yourself so the engine never picks it:

```sql
-- accounts.customer_id is INTEGER, events.customer_id is VARCHAR
SELECT
  a.customer_id,
  COUNT(*) AS event_count
FROM accounts AS a
JOIN events AS e
  ON CAST(a.customer_id AS VARCHAR) = e.customer_id
GROUP BY a.customer_id
```

Casting the integer side to text never fails, because every integer has a text form, while 'guest' and empty strings have no integer form. The price is that '00042' in events stops matching 42 in accounts. Before committing, count the event ids that find no account under each choice and say both numbers. The follow-up is nearly always 'how do you know you didn't lose rows?', and that count is the answer.

> **TIP**
>
> When a join returns fewer rows than expected, check the key types before the join type. An inner join that matches far too little is often an integer column meeting text padded with zeros or spaces.


<br>

---

## Epoch Numbers to Timestamps

The last disguise is a number that stands for a moment. Event streams often send time as an epoch value, a count of units elapsed since 1970-01-01 00:00:00 UTC, and mobile SDKs and REST APIs do the same. The question arrives as 'show signups per day; `created_at_epoch` is a BIGINT', and the catch is that the column holds a count with no unit attached.


<br>

### One moment in 4 units

Take an order placed at 2024-03-15 14:30:45 UTC. Depending on the producer, that same moment lands in the column as any of these:

| Unit | Value | Commonly sent by |
| --- | --- | --- |
| seconds | 1710513045 | Unix tools, many REST APIs, Postgres EXTRACT(EPOCH FROM ...) |
| milliseconds | 1710513045000 | JavaScript Date.now(), Java, Kafka record timestamps |
| microseconds | 1710513045000000 | BigQuery UNIX_MICROS, many Parquet files |
| nanoseconds | 1710513045000000000 | Go UnixNano, some Arrow and Parquet files |

- **10 digits** — an epoch in seconds today
- **13 digits** — an epoch in milliseconds today
- **16 digits** — an epoch in microseconds today

Count the digits before writing any conversion. Every epoch between September 2001 and November 2286 has a fixed width in each unit, so for any date your data will plausibly hold, the length of the number names its unit. `LENGTH(CAST(created_at_epoch AS VARCHAR))` over a sample settles it, and so does asking the interviewer, which scores as well.


<br>

### Converting to a timestamp

Postgres and DuckDB provide `TO_TIMESTAMP(n)`, which reads `n` as seconds. Any other unit gets divided down to seconds first, and that division walks straight back into integer truncation:

```sql
-- seconds: convert directly
SELECT TO_TIMESTAMP(created_at_epoch) AS created_at FROM events;

-- milliseconds: divide by a decimal so the fraction survives
SELECT TO_TIMESTAMP(created_at_epoch / 1000.0) AS created_at FROM events;

-- wrong for milliseconds: integer division drops the sub-second part
SELECT TO_TIMESTAMP(created_at_epoch / 1000) AS created_at FROM events;

-- a form that needs no epoch function
SELECT TIMESTAMP '1970-01-01 00:00:00'
       + created_at_epoch * INTERVAL '1 second' AS created_at
FROM events;
```

Other engines put the unit in the function's name or arguments. BigQuery names one function per unit, `TIMESTAMP_SECONDS` alongside `TIMESTAMP_MILLIS` and `TIMESTAMP_MICROS`. Snowflake's `TO_TIMESTAMP(n, 3)` takes the scale as a second argument, where 3 means milliseconds and 6 means microseconds. On every engine the unit is an input you supply. Nothing in a BIGINT column tells the function what it holds.


<br>

### Misreading the unit

Read milliseconds as seconds and 1710513045000 becomes a timestamp more than 54,000 years in the future. Postgres returns it without complaint; engines with a narrower timestamp range raise an out-of-range error, which is the kinder outcome. Read seconds as milliseconds and 1710513045 becomes 1970-01-20 19:08:33.045, a date that looks entirely plausible in a column nobody is reading closely.

Aggregates make the misread harder to see. A month of millisecond values read as seconds spreads across around 82 years far in the future, and a per-day count returns tens of thousands of days holding a handful of events each. A month of second values read as milliseconds fits inside 43 minutes of 1970-01-20, so the per-day count returns 1 row holding every event. A chart with a single bar, or dates the interviewer never mentioned, points at the unit.


<br>

### When the column mixes units

The follow-up that tests whether you have handled real event data: 'an SDK upgrade switched the column from seconds to milliseconds halfway through March.' Branch on magnitude. Any value of 100,000,000,000 or more is milliseconds, because read as seconds it would land past the year 5000, while read as milliseconds it covers everything from 1973 onward.

```sql
SELECT
  TO_TIMESTAMP(
    CASE
      WHEN created_at_epoch >= 100000000000 THEN created_at_epoch / 1000.0 -- milliseconds
      ELSE created_at_epoch -- seconds
    END
  ) AS created_at
FROM events
```


<br>

### Checking the conversion out loud

Convert the range before aggregating anything: `SELECT TO_TIMESTAMP(MIN(created_at_epoch) / 1000.0), TO_TIMESTAMP(MAX(created_at_epoch) / 1000.0) FROM events;` Say what you expect before running it ('the table covers March 2024, so both ends should fall in March 2024') and the check reads as a habit rather than a recovery.

`TO_TIMESTAMP` returns a timestamp with time zone, and epoch values are UTC by definition. A per-day grouping then uses the session's time zone unless you convert, so a 'signups per day' answer needs a stated day boundary: UTC, or the business's local midnight.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Check every column's stored type before you trust a sort or ratio on it, or a date read from it<br><br>• Cast once in the first CTE so every later step reads a typed column<br><br>• Put the decimal on an operand before dividing, and wrap the divisor in NULLIF<br><br>• Compare identifiers as text and quantities as numbers, casting toward that type<br><br>• Count an epoch's digits to find its unit, then convert its MIN and MAX and read them | • Don't cast a ratio after the division: the fraction is already gone<br><br>• Don't compare a text column to an unquoted number and let the engine pick the side<br><br>• Don't divide milliseconds by 1000 without a decimal point<br><br>• Don't explain a suspicious result before questioning the type behind it |


<br>

---

## Putting It All Together

A meal-kit subscription company moves its reporting from BigQuery to a Postgres replica. The next Monday, the growth team asks 4 questions: why trial-to-paid shows 0% for every cohort, why the partner-orders tab lists a 99.00 order as the largest of the week, why the referral join, which Postgres first rejected with 'operator does not exist', lost a third of its rows once someone added a cast, and why the new app's signup chart is a single bar dated 1970-01-20.

- All 4 symptoms come from columns whose stored type disagrees with their meaning. Only the referral join raised an error, and the quick fix for that error is what caused the row loss.
- BigQuery returned a fraction for INT / INT and Postgres truncates it, so the rate needs paid_trials \* 1.0 / NULLIF(trials, 0) to be right on both engines.
- The partner amounts are VARCHAR and sort as characters; a single CAST to DECIMAL(10,2) in the source CTE puts the real largest order back on top.
- Referral ids are INTEGER in accounts and zero-padded VARCHAR in the partner file. The added cast turned the integer side into text, so '00042' stopped matching 42; counting unmatched ids under each cast direction shows exactly which ones the text comparison drops.
- The new app SDK sends epoch seconds while the query still divides by 1000.0 for milliseconds, squeezing a week of signups into about 10 minutes of 1970-01-20.


<br>

---

## Key Takeaways

- A column stored as one type and meaning another runs every query without error; the symptom is a result that looks plausible and is wrong.
- CAST(x AS type) works everywhere and x::type on Postgres-family engines; put it on the operand that needs it, ideally once in the first CTE.
- Integer over integer truncates on several engines: conversions \* 1.0 / NULLIF(signups, 0) keeps the fraction and survives a week with no signups.
- When text meets a number, the text side converts. Pick the comparison type from what the column means: compare identifiers as text and quantities as numbers.
- An epoch's digit count names its unit; divide by a decimal to reach seconds, then check the converted MIN and MAX against the dates you expect.
