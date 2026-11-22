# String Manipulation: Beginner

You are 20 minutes into a SQL screen at an online retailer. The interviewer pastes 3 rows into the shared editor:
`APP2400417`, `ELE2300102`, `HOM2400033`
"That's the `sku` column. Merchandising wants a count of products per department, and we don't store department anywhere. Go."
There is no department column. It sits in the leading 3 characters of each code, and nobody has said so. Nobody has said whether every SKU is 10 characters long, either, or what should happen to the row that isn't. Most candidates start typing `GROUP BY` before they have read a single code out loud.
What she is scoring is whether you can see the structure inside a value, say how you will cut it, and prove the cut on one row before trusting it on all of them.


<br>

### What you will be able to do

Recognize a question whose answer is buried inside a string column, and name the value's shape before writing SQL

Cut fixed-width codes with SUBSTRING, LEFT and RIGHT without off-by-one errors

Extract the nth delimited field with SPLIT_PART or STRPOS, and say what malformed rows return

Build strings and keys that survive NULLs, and clean values with TRIM and LOWER before comparing them

Remove or swap characters with REPLACE and TRANSLATE, in an order that produces the right result


<br>

---

## When the Data Is Trapped in a String

A single text column often carries several facts at once. A retailer's `sku` packs department, season and serial number into 10 characters. An `email` holds a mailbox and a domain, and a `page_url` holds protocol, host and path. The database stores each one as an opaque value, so `GROUP BY sku` groups by the whole code and gives every product a separate group of 1. Before a question about departments or domains can be answered, the fact it asks about has to be cut out into a column of its own.


<br>

### How the question arrives

Interviewers rarely say "string manipulation". The prompt names a business dimension that has no column, and the string holding it is sitting in the sample rows. These phrasings all mean this pattern:

- "Revenue by email provider." The provider lives after the @ in email.
- "Products per department," with a SKU column and no department column.
- "Which hosts send us the most traffic?" with only a page_url column.
- "This join drops customers." The emails differ by case or a trailing space.
- "Match sign-up phones to the call log." Brackets, dots and dashes differ by form.
- "Show each customer as one display name." First and last name become 1 string.


<br>

### The 3 shapes a buried value takes

| Shape | Example values | Tools | Where it is taught |
| --- | --- | --- | --- |
| Fixed-width code | APP2400417, with each part at fixed offsets | SUBSTRING, LEFT, RIGHT | Cutting Fixed-Width Codes Apart |
| Delimited field | ana@gmail.com, https://shop.example.com/cart | SPLIT_PART, STRPOS | Extracting a Field by Position |
| Messy value | ' Ana@Gmail.com', '(555) 123-4567' | TRIM, LOWER, \|\|, REPLACE | The last 2 sections |

Name the shape out loud before you write a function. "Characters 1 to 3 of `sku` look like a department code, so this is a fixed-width cut" tells the interviewer you read the data. It also commits you to a claim the sample can confirm or break. Candidates who skip that sentence often reach for the wrong tool, such as searching for a delimiter in a code that has none.


<br>

### The question worth asking first

Before writing the extraction, ask whether the format holds on every row: "Are all SKUs 10 characters, or should I check?" Either answer helps you. A yes lets you move on. A "you tell me" means a validation step belongs in the answer, and the interviewer has told you it will be graded. Guessing quietly costs more than asking. The interviewer usually keeps a test row that breaks the format, and an answer that mishandles it loses the round on that row.


<br>

### Extract once, then use the column

The answer reads best in 2 steps. A CTE turns the buried value into a named column, and an outer query groups, filters or joins on that column like any other. When the interviewer asks where department comes from, you point at one line.

```sql
WITH parsed AS (
  SELECT
    sku,
    SUBSTRING(sku, 1, 3) AS dept
  FROM products
)

SELECT
  dept,
  COUNT(*) AS products
FROM parsed
GROUP BY dept
ORDER BY dept
```

Repeating the expression inside `GROUP BY` also works, and it is fine for a single use. The CTE earns its place when the same extracted column feeds a `WHERE`, a `GROUP BY` and a join: 1 definition replaces 3 copies that can drift apart when someone edits only one of them. Postgres, Snowflake and BigQuery accept the output alias in `GROUP BY`, but SQL Server does not, so the CTE is the form that runs everywhere.

> A complete answer, in order
>
> - Name the shape: fixed-width, delimited, or a value that needs cleaning
> - Ask whether the format holds on every row
> - Extract into a named column inside a CTE
> - Trace one sample row through each expression
> - Count the rows that break the format and say where they go


<br>

### Trace one row before trusting the query

Pick a sample row and say what each expression returns for it: "for `APP2400417`, positions 1 to 3 are `APP`." That habit catches an off-by-one or a wrong field number before the interviewer does, and it is the shown work being scored. It also gives you something useful to say while you think, which beats a long silence at the keyboard.

> **TIP**
>
> SQL string positions start at 1. Python slices and JavaScript's `substring` start at 0. Saying "positions are 1-based here" as you write the first cut heads off the bug interviewers see most in this round.


<br>

---

## Cutting Fixed-Width Codes Apart

A fixed-width code puts each part at the same character positions on every row. The retailer's `sku` is 10 characters: 3 for department, 2 for season year, 5 for serial number, so `APP2400417` reads as `APP`, `24` and `00417`. Because the positions never move, every part is a cut with a known start and a known length, and nothing has to be searched for.


<br>

### Write the offset map first

| Part | Positions | Expression | Result for APP2400417 |
| --- | --- | --- | --- |
| Department | 1 to 3 | SUBSTRING(sku, 1, 3) | APP |
| Season year | 4 to 5 | SUBSTRING(sku, 4, 2) | 24 |
| Serial | 6 to 10 | SUBSTRING(sku, 6, 5) | 00417 |
| Serial, to the end | 6 onward | SUBSTRING(sku, 6) | 00417 |

Put this map on the whiteboard or in a comment before the query. One piece of arithmetic checks it: a part starting at position s with length n ends at s + n - 1. Season starts at 4 and runs 2, so it ends at 5. Serial starts at 6 and runs 5, so it ends at 10, the full width. If the last part's end does not equal the code's length, a number in the map is wrong. Leaving the length off, as in `SUBSTRING(sku, 6)`, runs to the end of the value in Postgres, Snowflake and BigQuery; SQL Server requires all 3 arguments.


<br>

### The third argument is a length

SUBSTRING(sku, 4, 5) reads to many people as "positions 4 to 5", and it returns 24004: 5 characters starting at position 4. The third argument **counts characters** and never names an end position. Python's sku[3:5] does take an end, which is where the habit comes from. The second trap is starting at 0. Postgres treats SUBSTRING(sku, 0, 3) as positions 0 through 2, and because position 0 holds nothing, it returns AP, 2 characters, with no error.

| Expression | Returns | Why |
| --- | --- | --- |
| SUBSTRING(sku, 1, 3) | APP | Start 1, 3 characters: the department |
| SUBSTRING(sku, 4, 2) | 24 | Start 4, 2 characters: the season |
| SUBSTRING(sku, 4, 5) | 24004 | 5 characters from position 4, misread as "to position 5" |
| SUBSTRING(sku, 0, 3) | AP | Position 0 is empty, so only 2 characters land (Postgres) |


<br>

### LEFT and RIGHT for the ends

A part at either end of the code reads better as `LEFT(sku, 3)` or `RIGHT(sku, 5)`: 1 fewer argument, and the intent is in the function name. Postgres, Snowflake, BigQuery, SQL Server and MySQL all have both. A middle part like the season still needs `SUBSTRING`.


<br>

### The cut feeding a GROUP BY

The department question needs only the first cut. The animation runs it over 5 SKUs. Each row's first 3 characters are computed, rows that share a department fold into one group, and a count comes out per group.

https://github.com/user-attachments/assets/b46188eb-50ea-4bbc-bcb0-50d018f8ab32

Five rows go in and 3 groups come out: `APP` and `ELE` with 2 products each, `HOM` with 1. The grouping key now holds 3 distinct values where the full `sku` held 5, and that change of key is why the result has 3 rows. Saying so out loud shows you can predict a result's row count before running the query.


<br>

### Text that only looks like a number

The serial `00417` is text, and it should stay text. It is an identifier, and casting it to an integer returns 417 and throws away the zeros that let it match the SKU again. Cast a part when it is a quantity you will compare or compute with. The season is that kind of part: `2000 + CAST(SUBSTRING(sku, 4, 2) AS INT)` gives 2024, which supports `>=` and subtraction.

```sql
SELECT
  sku,
  LEFT(sku, 3) AS dept,
  2000 + CAST(SUBSTRING(sku, 4, 2) AS INT) AS season_year,
  RIGHT(sku, 5) AS serial
FROM products
WHERE LENGTH(sku) = 10
-- 'APP2400417'  ->  dept 'APP', season_year 2024, serial '00417'
```


<br>

### Why not split it?

An interviewer sometimes asks why you did not use a split function. The answer is that `APP2400417` contains no delimiter. There is no character between department and season to split on, so the boundaries exist only as positions. If the same code arrived as `APP-24-00417`, either tool would work, and splitting would survive a change in the serial's width that breaks a fixed cut.


<br>

### "What if some SKUs aren't 10 characters?"

This follow-up tests whether the cut is safe on real data. Suppose one SKU was keyed as `EL2400560`, missing a letter. The same offsets return department `EL2`, season `40` and serial `0560`, and nothing errors: the row lands in a department that does not exist. The answer that scores has 2 parts. First, check the assumption with a count by length. Second, say what happens to rows that fail: exclude them from the report and state how many, so a shifted cut never puts a product in the wrong department.

```sql
SELECT
  LENGTH(sku) AS sku_length,
  COUNT(*) AS products
FROM products
GROUP BY LENGTH(sku)
ORDER BY sku_length
```


<br>

---

## Extracting a Field by Position

A delimited value marks the boundary between its parts with a character. `ana@gmail.com` has 2 fields split by `@`, and `https://shop.example.com/cart/checkout` has 5 split by `/`. Field lengths change from row to row, so character offsets move, but the field number holds: the domain is always field 2 and the host always field 3. Extracting by position means asking for the nth field.


<br>

### SPLIT_PART takes a field number

```sql
SELECT
  email,
  SPLIT_PART(email, '@', 1) AS mailbox,
  SPLIT_PART(email, '@', 2) AS domain
FROM customers
-- 'ana@gmail.com'  ->  mailbox 'ana', domain 'gmail.com'
-- 'raj@acme.io'    ->  mailbox 'raj', domain 'acme.io'
```

The arguments are the string, the delimiter and the field number, counted from 1. Postgres, Snowflake, Redshift, DuckDB and Trino all provide `SPLIT_PART` with this signature. BigQuery does not: `SPLIT(email, '@')[SAFE_OFFSET(1)]` builds an array and indexes it from 0, so the domain is offset 1 there. Name your engine, and on BigQuery say that the offset is 0-based, so the interviewer does not read your 1 as a bug.

Two more details settle most follow-ups. The delimiter is a literal string and never a pattern, so `SPLIT_PART('analytics.orders.daily', '.', 2)` returns `orders`, and a multi-character delimiter such as `'::'` works the same way. Postgres 14 and later, and Snowflake, also accept a negative field number that counts from the right: `SPLIT_PART(page_url, '/', -1)` returns `checkout`, the last path segment however deep the URL goes.


<br>

### Empty fields count

The URL host is where answers go wrong most often. Split `https://shop.example.com/cart/checkout` on `/`, and the 2 slashes after `https:` have nothing between them. That nothing is still a field, because every delimiter closes one, empty or not.

| Field number | Value |
| --- | --- |
| 1 | https: |
| 2 | (empty string) |
| 3 | shop.example.com |
| 4 | cart |
| 5 | checkout |

The host is `SPLIT_PART(page_url, '/', 3)`. A candidate who counts only the fields they can see writes 2 and gets an empty string back, which looks like missing data rather than a wrong number. Writing this table out for one sample row, in a comment or out loud, is how the right field number gets chosen and defended.


<br>

### Asking for a field that is not there

Request field 2 of a value with no `@` and there is nothing to return. Postgres and Snowflake give back an empty string, Trino gives NULL, and none of them raises an error. A NULL input returns NULL on every engine. Both cases slip straight into a `GROUP BY`, which the animation shows on 5 customers: 3 well-formed emails, 1 value with no `@`, and 1 NULL.

https://github.com/user-attachments/assets/03cbd389-376a-4945-a470-623d1acf6f7f

`gmail.com` collects 2 customers and `acme.io` collects 1. `no-email-given` is a single field, so its field 2 is an empty string and it forms a group with a blank domain. The NULL email gives a NULL domain and a group of its own. Neither row errors, and in a quick scan both look like plausible output. The answer that scores names both groups, then filters with `WHERE STRPOS(email, '@') > 0` (`STRPOS` returns the position of the `@`, or 0 when there is none, as the next part shows) and reports how many rows the filter removed.


<br>

### Building it by hand with STRPOS

Some interviewers rule out `SPLIT_PART` to see whether you can build it, and SQL Server has no such function. `STRPOS(email, '@')` returns the position of the first `@`, which is 4 for `ana@gmail.com`, and `SUBSTRING` from one past that position to the end returns the domain. The SQL-standard spelling is `POSITION('@' IN email)` and SQL Server's is `CHARINDEX('@', email)`; all 3 return the same number.

```sql
SELECT
  email,
  STRPOS(email, '@') AS at_pos,
  SUBSTRING(email, STRPOS(email, '@') + 1) AS domain
FROM customers
-- 'ana@gmail.com'   ->  at_pos 4, domain 'gmail.com'
-- 'no-email-given'  ->  at_pos 0, domain 'no-email-given'
```

The second row is the trap. `STRPOS` returns 0 when the delimiter is missing, so the start becomes 0 + 1 = 1 and `SUBSTRING` returns the entire value as its "domain". Where `SPLIT_PART` produced an empty string, the hand-built version invents a domain called `no-email-given`. A guard fixes it: `CASE WHEN STRPOS(email, '@') > 0 THEN SUBSTRING(email, STRPOS(email, '@') + 1) END` returns NULL for the malformed row.

| ✓ SPLIT_PART | ✗ STRPOS + SUBSTRING |
| --- | --- |
| • One call, with the field number counted from 1<br><br>• Missing delimiter: empty string in Postgres and Snowflake, NULL in Trino<br><br>• Reaches any field, including field 4 of a 5-field URL<br><br>• Absent in BigQuery (use SPLIT) and in SQL Server | • Two functions and a + 1 offset to step past the delimiter<br><br>• Missing delimiter: returns the whole value unless guarded with CASE<br><br>• Fits "everything after the first @" with no field counting<br><br>• Runs wherever a position function exists: STRPOS, POSITION, CHARINDEX |

> **TIP**
>
> State the field count before the function: "the URL splits into 5 fields on slash, and the host is field 3 because of the empty field after https:". That sentence answers the question the interviewer was about to ask.


<br>

---

## Concatenation and Simple Cleanup

Concatenation and cleanup run in the opposite direction from extraction. Concatenation builds one string from several, and cleanup reshapes a value so that 2 versions differing only by case or edge spaces compare as equal. Both decide whether a join matches and whether a label reads right, and both fail without raising an error.


<br>

### One NULL erases the whole string

The standard concatenation operator is `||`, as in `first_name || ' ' || last_name`. When any piece is NULL the whole result is NULL, so a contact with no first name loses their last name as well. SQL Server writes `+` instead of `||`, with the same NULL behaviour under its default settings. The animation builds display names for 4 contacts: 2 with stray spaces and 1 with no first name.

https://github.com/user-attachments/assets/5254991d-e550-475a-a184-214093603195

Contact 3 has `last_name` set to `Okafor`, and `full_name` still comes back NULL: `NULL || ' '` is NULL, and every piece after it inherits that. The `safe_name` column wraps the optional part, the first name with its trailing space, in `COALESCE(..., '')`. A missing first name then contributes nothing and `Okafor` survives. The `TRIM` calls turn `' Maria'` and `'Chen '` into clean names before they are joined, which keeps double spaces out of the output.


<br>

### CONCAT and CONCAT_WS change by engine

| Expression | Postgres, SQL Server, DuckDB | MySQL | Snowflake, BigQuery |
| --- | --- | --- | --- |
| CONCAT('Ana', NULL) | 'Ana' | NULL | NULL |
| CONCAT_WS('-', 'US', NULL, 'SF') | 'US-SF' | 'US-SF' | Snowflake: NULL. BigQuery: no such function |

That table is the answer to "what does `CONCAT` do with a NULL?": it depends on the engine, and saying so beats a confident answer that is wrong for the company's warehouse. `COALESCE` on every piece that can be NULL behaves the same on all of them, which makes it the move to name when the engine is unknown.


<br>

### Keys built by concatenation need a separator

Concatenation also builds keys, such as a customer id and an order sequence number combined into one order key. Without a separator, different inputs collide: customer 1 with order 23 and customer 12 with order 3 both become `123`, and a join on that key pairs orders that have nothing in common. A separator that cannot occur inside either part keeps them apart, giving `1-23` and `12-3`.

```sql
SELECT
  customer_id,
  order_seq,
  CAST(customer_id AS VARCHAR) || '-' || CAST(order_seq AS VARCHAR) AS order_key
FROM orders
-- customer 1,  order 23  ->  '1-23'
-- customer 12, order 3   ->  '12-3'
```

The reverse of a fixed-width cut is a padded build. `LPAD(CAST(417 AS VARCHAR), 5, '0')` returns `00417`, so `'APP' || '24' || LPAD(CAST(417 AS VARCHAR), 5, '0')` rebuilds `APP2400417` from stored parts. Interviewers ask for this to see whether a candidate knows the serial's zeros belong to the identifier.


<br>

### TRIM and LOWER before comparing

`=` compares strings character by character, so `'Ana@Gmail.com '` with a trailing space and `'ana@gmail.com'` are different values to a filter and to a join. Postgres, Snowflake and BigQuery also compare case-sensitively by default, while the default collations in MySQL and SQL Server ignore case. SQL Server's `=` also ignores trailing spaces, as do MySQL's older PAD SPACE collations, but leading spaces count everywhere, and the cleaned value is what you group and display, so clean it anyway. `TRIM(x)` removes leading and trailing spaces and `LOWER(x)` folds case, so `LOWER(TRIM(email))` turns both into `ana@gmail.com`. Codes such as currency are conventionally upper case, so `UPPER(TRIM(currency))` brings `' eur'` and `'EUR'` together.

```sql
SELECT
  o.order_id,
  c.customer_id
FROM orders AS o
JOIN customers AS c
  ON LOWER(TRIM(o.contact_email)) = LOWER(TRIM(c.email))
```

Both sides of the join get the same expression. Cleaning only one side is the half-fix interviewers see most, and it still misses every row where the uncleaned side carries the stray space. When the cleaned value feeds more than one join, compute it once in a CTE as `email_clean` and keep the raw column beside it, so anyone auditing a mismatch can see what was actually entered.

`LTRIM` and `RTRIM` clean one end only, and `TRIM(BOTH '.' FROM code)` removes a named character instead of spaces, turning `'..A17..'` into `'A17'`. `TRIM` stops at the first character it is not removing, so `'Ana Lopez'` keeps both inner spaces. Changing characters in the middle of a value is a job for `REPLACE`.

> **TIP**
>
> When a match count looks wrong, compare `COUNT(DISTINCT email)` with `COUNT(DISTINCT LOWER(TRIM(email)))`. The gap is the number of values that differ only by case or edge spaces, and quoting it turns a hunch into a diagnosis.


<br>

---

## Replacing Characters Inside a Value

`REPLACE(value, search, replacement)` swaps every occurrence of `search` for `replacement`, anywhere in the value. An empty replacement deletes: `REPLACE('555-123-4567', '-', '')` returns `5551234567`, both dashes gone in one call. Every major SQL engine replaces all occurrences, which surprises people coming from JavaScript, where `replace` with a plain string changes only the first match. In Postgres, Snowflake, BigQuery and MySQL the search is case-sensitive, so `REPLACE(code, 'x', '')` leaves an `X` in place. SQL Server matches using the column's collation, which ignores case by default, so there the `X` is removed too.

`REPLACE` on a NULL phone returns NULL. A missing number stays missing instead of becoming an empty string, which matters later: 2 empty strings are equal and would match each other in a join, while 2 NULLs never do.


<br>

### Nesting REPLACE for a set of characters

Phone numbers from 3 sign-up forms arrive as `(555) 123-4567`, `555.123.4567` and `555 123 4567`. Each `REPLACE` removes one character, so clearing brackets, dashes, dots and spaces takes 5 calls nested inside each other. The innermost call runs first and hands its output to the next one out.

```sql
SELECT
  phone,
  REPLACE(
    REPLACE(
      REPLACE(REPLACE(REPLACE(phone, '(', ''), ')', ''), '-', ''),
      '.',
      ''
    ),
    ' ',
    ''
  ) AS phone_digits
FROM signups
```

| Step | Removes | Value after the step |
| --- | --- | --- |
| Start |  | (555) 123-4567 |
| 1 | ( | 555) 123-4567 |
| 2 | ) | 555 123-4567 |
| 3 | - | 555 1234567 |
| 4 | . | 555 1234567 (no change) |
| 5 | space | 5551234567 |

Tracing one row step by step is what the interviewer wants to watch. The trace also shows a step that changes nothing for this row, the dot, which is correct: `REPLACE` leaves a value alone when it does not contain the search character, so one expression handles all 3 formats.

As entered

After the 5 REPLACE calls


<br>

### TRANSLATE: many characters in one call

`TRANSLATE(value, from_chars, to_chars)` maps each character of the second argument to the character at the same position in the third. In Postgres, Snowflake and DuckDB, a character with no partner in the third argument is deleted, so `TRANSLATE(phone, '()-. ', '')` strips all 5 characters in one call. SQL Server's `TRANSLATE` requires both lists to be the same length and raises an error otherwise, so there the nested `REPLACE` is the portable form.


<br>

### Swapping 2 characters needs one pass

A European amount such as `1.234,56` uses the dot for thousands and the comma for decimals. Converting it to `1,234.56` with 2 `REPLACE` calls fails. The first turns dots into commas, giving `1,234,56`, and the second turns every comma into a dot, including the one the first call produced, giving `1.234.56`. Each call sees the output of the call before it. `TRANSLATE` maps both characters in a single pass, so `TRANSLATE('1.234,56', '.,', ',.')` returns `1,234.56`.

| Expression on amount = '1.234,56' | Result |
| --- | --- |
| REPLACE(REPLACE(amount, '.', ','), ',', '.') | 1.234.56 |
| TRANSLATE(amount, '.,', ',.') | 1,234.56 |
| CAST(REPLACE(REPLACE(amount, '.', ''), ',', '.') AS DECIMAL(12, 2)) | 1234.56 |
| CAST(REPLACE(REPLACE(amount, ',', '.'), '.', '') AS DECIMAL(12, 2)) | 123456.00 |

When the amount feeds arithmetic, the third row is the one to write: delete the thousands dot first, then turn the decimal comma into a dot, and the result casts to `DECIMAL`. The order of the 2 calls is the whole answer. Reversed, as in the last row, the comma becomes a dot first, the delete-dots call then removes it along with the thousands separator, and a refund of 1,234.56 is recorded as 123,456, 100 times too large.


<br>

### Check the result, then fix the leftover case

After stripping, a US number should be 10 digits, and `LENGTH(phone_digits)` is the check: a `GROUP BY` on it shows how many rows land at 10. The usual leftover is a country code. With `+` added to the list of removed characters, `+1 (555) 123-4567` becomes `15551234567`, 11 digits, and a `CASE` drops the leading 1 from exactly those rows.

```sql
SELECT
  phone_digits,
  CASE
    WHEN LENGTH(phone_digits) = 11
      AND LEFT(phone_digits, 1) = '1' THEN SUBSTRING(phone_digits, 2)
    ELSE phone_digits
  END AS phone_10
FROM cleaned_signups
-- '15551234567'  ->  '5551234567'
-- '5551234567'   ->  '5551234567'
```

Rows that still are not 10 digits are worth naming rather than forcing. "I'd count those and leave them out of the match" tells the interviewer you will not join a 7-digit fragment to the wrong customer. When the junk characters are not known in advance, a pattern-based replace that keeps only digits is the general tool. For the handful of characters you can see in the sample, nested `REPLACE` is readable, correct, and accepted.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Name the shape first (fixed-width, delimited or messy) and trace a sample row through every expression<br><br>• Write the offset map or the field count before choosing SUBSTRING or SPLIT_PART arguments<br><br>• Count rows that break the format with LENGTH or STRPOS, and say where they go<br><br>• Clean both sides of a comparison with the same LOWER(TRIM()) expression, defined once in a CTE<br><br>• Put a separator in every concatenated key and COALESCE every piece that can be NULL | • Don't read SUBSTRING's third argument as an end position, or start a cut at 0<br><br>• Don't count only the fields you can see: the empty field after https: is field 2<br><br>• Don't trust STRPOS + 1 unguarded: a missing delimiter returns the whole value<br><br>• Don't assume CONCAT skips NULL: Snowflake, BigQuery and MySQL return NULL<br><br>• Don't swap 2 characters with chained REPLACE calls: the second call undoes the first |


<br>

---

## Putting It All Together

A subscription box company's growth team brings 3 complaints about the weekly sign-ups dashboard. gmail.com and Gmail.com appear as separate email providers, about 4% of sign-ups sit under a blank provider, and matching sign-ups to support calls by phone finds roughly half the overlap the support team expects. One analyst gets an afternoon to fix the query that feeds all 3.

- The blank provider is the SPLIT_PART empty-string group: values with no @ are a single field, so field 2 is empty, and a STRPOS guard plus a reported count replaces it.
- gmail.com against Gmail.com is a case difference; LOWER(TRIM(email)) computed once in a CTE collapses them before the GROUP BY and before any join.
- The phone match fails because each side keeps different punctuation; nested REPLACE plus the 11-digit CASE brings both sides to the same 10 digits.
- The dashboard label joins provider and week into one string; a separator and COALESCE keep a NULL week from blanking the whole label.
- Each fix is traced on one sample row first, which is how the analyst shows the team the change is right before rerunning the history.


<br>

---

## Key Takeaways

- A string column can hold several facts; cut the one the question needs into a named column, then group, filter or join on it.
- Fixed-width parts are SUBSTRING(s, start, length) cuts counted from 1: the end is start + length - 1, and LENGTH confirms every row fits.
- SPLIT_PART returns the nth delimited field; empty fields count, and a missing delimiter yields an empty string or NULL, never an error.
- Join strings with a separator and COALESCE nullable pieces, and give both sides of a comparison the same LOWER(TRIM()).
- REPLACE changes every occurrence; nest it for a known set of characters, order the calls deliberately, and use TRANSLATE to swap.
