# String Manipulation: Intermediate

You are 20 minutes into a SQL round at a B2B software company, sharing a notebook with the interviewer.
"Finance has 14 open invoices for Acme Corp. Join them to the CRM accounts table and the count comes back zero, even though both tables show a row reading Acme Corp. Find out why. Then give me a row per account with its invoice numbers as a comma-separated list."
She doesn't mention that the accounts table was loaded from a spreadsheet export, or that the same company is spelled 4 ways across 60,000 rows. The reflex is to wrap both join keys in TRIM and LOWER and rerun. On this data it still returns zero.
What she is testing is whether you inspect what's actually inside a string before deciding what to strip from it.


<br>

### What you will be able to do

Measure length and code points to find out why 2 strings that print the same fail to match, and only then choose a fix.

Write LIKE patterns that match exactly what the question means, with literal wildcards and NULL rows handled. Then say when the pattern needs a regex instead.

Aggregate rows into a delimited string with a deterministic order and every source row counted exactly once.

Map inconsistent spellings to a canonical value through a rules-built match key and a mapping table, with unmapped values kept visible.

Parse fields whose length and position vary by locating delimiters and keys, and prove every row parsed.


<br>

---

## Invisible Characters TRIM Misses

This part of the question arrives as a symptom: a join that loses rows it should keep, or a `GROUP BY` that returns 2 groups which print identically. "Why does Acme Corp appear twice in the revenue report?" The interviewer is scoring the order of your moves. Measuring the string first finds the cause in a single query. Guessing at cleanup functions burns minutes and usually ends on a fix that works by accident.


<br>

### What TRIM actually removes

In Postgres and Snowflake, as in SQL Server, `TRIM` called without a character list strips only code point 32, the ordinary space, from both ends of the value. BigQuery's `TRIM` removes Unicode whitespace, which covers the non-breaking space but leaves zero-width characters behind. No engine's `TRIM` touches the middle of a value. These are the characters behind most of these bugs, and none of them is visible when the row prints.

| Character | Code point | Where it usually comes from |
| --- | --- | --- |
| Non-breaking space | U+00A0 (160) | Text copied from web pages, Word or Excel |
| Tab | U+0009 (9) | Pasted spreadsheet cells, TSV files |
| Carriage return | U+000D (13) | Windows line endings on the last column of a CSV |
| Zero-width space | U+200B (8203) | Rich-text editors and CMS fields |
| Byte-order mark | U+FEFF (65279) | Start of a UTF-8 CSV saved from Excel |

Two of these have a signature worth naming in the room. A carriage return affects only the last column of a file, because Windows ends lines with `\r\n` and the loader split on `\n`. A byte-order mark affects only the first value in the first column, because it sits at the start of the file. If the broken rows follow either shape, you've named the cause before running anything.


<br>

### Measure before you clean

The diagnostic move is to compare lengths and read code points. 'Acme Corp' is 9 characters; a stored value reporting 10 holds a character you cannot see, and its code point says which one. State the plan before typing: find rows whose length disagrees with what is printed, then read the codes at the ends.

```sql
-- Which account names hold characters outside printable ASCII?
SELECT
  account_name,
  LENGTH(account_name) AS len,
  LENGTH(TRIM(account_name)) AS trimmed_len,
  ASCII(RIGHT(account_name, 1)) AS last_code_point
FROM crm_accounts
WHERE account_name ~ '[^ -~]'
ORDER BY account_name
```

| account_name | len | trimmed_len | last_code_point |
| --- | --- | --- | --- |
| Acme Corp | 10 | 10 | 160 |
| Acme Corp | 10 | 10 | 13 |
| Bürger GmbH | 11 | 11 | 72 |

Both Acme rows are 10 characters and `TRIM` shortens neither. One ends in code point 160, a non-breaking space; the other ends in 13, a carriage return. The third row is a false positive: 'ü' falls outside printable ASCII and belongs in the name. That row is the reason the fix lists the characters to remove instead of deleting everything non-ASCII.


<br>

### The fix names its characters

```sql
-- Postgres. Whitespace in disguise becomes a real space;
-- zero-width characters are removed outright.
SELECT
  TRIM(REGEXP_REPLACE(
    REGEXP_REPLACE(
      account_name,
      '[' || CHR(8203) || CHR(65279) || ']',
      '',
      'g'
    ),
    '[\t\r\n' || CHR(160) || ']+',
    ' ',
    'g'
  )) AS account_name_clean
FROM crm_accounts
```

The 2 replacements do different jobs. A non-breaking space or tab between 'Acme' and 'Corp' is a real word break, so it becomes an ordinary space, and the `+` folds a run of them into a single space. A zero-width space marks no break, so turning it into a space would insert a gap the source never showed. `TRIM` runs last, once every disguised space at the edges has become one it recognizes.


<br>

### The same letter, stored 2 ways

Some mismatches involve no stray character at all. 'é' can be stored as 1 code point, U+00E9 (the composed form, NFC), or as 2: 'e' followed by the combining accent U+0301 (the decomposed form, NFD). 'José' prints identically either way, but `LENGTH` returns 4 for one and 5 for the other, so the measuring query catches this case too. `NORMALIZE(name, NFC)` fixes it in Postgres 13+ and BigQuery; engines without it normalize during ingestion. Whether 'José' should also equal 'Jose' is a separate decision about accents, and NFC doesn't make it for you.

> Where this answer loses the room
>
> - Rerunning with `TRIM(LOWER(...))` on both sides of the join: the same 0 rows, and 3 minutes spent proving the guess wrong.
> - Deleting every character outside printable ASCII: 'Bürger GmbH' becomes 'Brger GmbH' and stops matching.
> - Cleaning inside a single join condition: the next query on the table hits the same bug. Clean once, in a staging model every query reads.
> - Replacing a zero-width space with a space, which inserts a word break the source never displayed.

> **TIP**
>
> The follow-up is usually "how do you stop this coming back?" Answer with a data test on the staging model: count rows where `LENGTH(col)` differs from the length of the cleaned value. When that count is above 0, the test fails the load or warns on it. It turns a 2-hour hunt into an alert on the morning the bad file lands.


<br>

---

## LIKE and Wildcard Pattern Matching

LIKE questions rarely say LIKE. They arrive as "count the customers who signed up with a company email", "every SKU in the kit range", or "how many tickets don't mention a refund". The pattern you write is the specification, so the interviewer reads it word for word and checks that it matches what the sentence asked for, with no extra rows and none missing.

% matches any run of 0 or more characters and _ matches exactly 1. The pattern has to account for the whole value, which is why a contains-search needs % at both ends. Case handling is where engines split. `LIKE` is case-sensitive in BigQuery and also in Postgres and Snowflake, which add `ILIKE` for the insensitive version. MySQL and SQL Server instead follow the column's collation, which is case-insensitive by default. Say which engine you are assuming before you write a character; that alone earns credit.

| Pattern | Matches | Does not match |
| --- | --- | --- |
| 'KIT%' | 'KIT', 'KIT_12', 'KITE-200' | 'kit_12' where LIKE is case-sensitive |
| 'A__' | 'A12', 'AX9' | 'A1', 'A123' |
| '%@acme.com' | 'li.wei@acme.com' | 'li.wei@mail.acme.com', 'li.wei@acme.com.au' |
| '%acme.com' | 'li.wei@acme.com', 'li.wei@notacme.com' | 'li.wei@acme.co' |

The last 2 rows are the ones to say out loud. Dropping the `@` accepts any domain ending in those 8 characters, so a competitor's staff land in your count. And 'Li.Wei@ACME.com' fails `'%@acme.com'` wherever `LIKE` is case-sensitive, so the filter becomes `LOWER(email) LIKE '%@acme.com'` or uses `ILIKE`.


<br>

### Wildcards you meant literally

Product codes and file names often carry `_` and `%` as data, and so do promo codes. `'KIT_%'` looks like a prefix search for KIT plus 1 literal character, but LIKE reads that character as a wildcard for any single character, so it also matches 'KITE-200' and 'KIT9'. Escape it to make it literal, and do the same for the percent sign in a code like '50%OFF'.

```sql
WHERE sku LIKE 'KIT_%'                    -- also matches 'KITE-200'
WHERE sku LIKE 'KIT\_%' ESCAPE '\'        -- literal underscore
WHERE promo_code LIKE '50!%%' ESCAPE '!'  -- starts with '50%'
```


<br>

### NOT LIKE and rows with no text

`notes LIKE '%refund%'` evaluates to NULL when `notes` is NULL, and `WHERE` keeps only rows that evaluate to true. For the positive filter that is harmless, because a ticket without notes does not mention a refund. For `NOT LIKE` it is a bug: the empty ticket also evaluates to NULL and gets dropped. The count of tickets that don't mention a refund then comes out short by exactly the number of tickets with no notes. Interviewers plant a NULL in the sample for this reason.

```sql
-- Tickets that do not mention a refund, including tickets with no notes
WHERE COALESCE(notes, '') NOT LIKE '%refund%'
```


<br>

### Where LIKE runs out

`LIKE` matches fixed text at fixed edges. Once the question involves alternatives, character classes, a range of lengths or whole words, the pattern needs a regex, and `'%refund%'` is the usual tell: it also matches 'non-refundable', a ticket saying the order can't be refunded.

| ✓ LIKE expresses it | ✗ Needs a regular expression |
| --- | --- |
| • A fixed prefix: 'INV-%'<br><br>• A fixed suffix: '%@acme.com'<br><br>• A fixed substring anywhere: '%refund%'<br><br>• An exact length: 'INV-______' (6 single-character wildcards) | • 'INV-' followed by digits only, and nothing after them<br><br>• Any of several words: refund or chargeback<br><br>• A whole word: 'refund' but not 'refundable'<br><br>• A range of lengths: 3 to 5 digits<br><br>• A character class: one capital letter |

```sql
-- Postgres ~ / ~* and BigQuery REGEXP_CONTAINS match anywhere unless anchored
WHERE invoice_code ~ '^INV-[0-9]{6}$'

-- Whole word, any case (\m and \M are Postgres word boundaries)
WHERE notes ~* '\m(refund|chargeback)\M'

-- Snowflake REGEXP_LIKE anchors at both ends, the way LIKE does
WHERE REGEXP_LIKE(invoice_code, 'INV-[0-9]{6}')
```

Two errors appear when a `LIKE` pattern is rewritten as a regex. The first is anchoring: Postgres `~` and BigQuery's `REGEXP_CONTAINS` match anywhere in the value, so `'INV-[0-9]{6}'` without `^` and `$` accepts 'OLD-INV-1234567', while Snowflake's `REGEXP_LIKE` must match the whole value and rejects it. Same pattern, different answer by engine. The second is the dot, a plain character in `LIKE` and a wildcard in regex: `'acme.com'` as a regex matches 'acmeXcom', so it becomes `'acme\.com'`.


<br>

### The follow-up about speed

"The tickets table has 400 million rows. Is that filter fast?" A fixed prefix such as `'INV-%'` can use a B-tree index (in Postgres, only when the index uses the C collation or the `text_pattern_ops` operator class). A leading `%` can't use one at all and reads every row. The answer that scores is to change what is stored: an `email_domain` column filtered with `=` is indexable and immune to the `notacme.com` problem, and a trigram index (`pg_trgm` in Postgres) serves contains-searches that have to stay. The same reasoning covers `LIKE` in a join condition, such as `ON c.email LIKE '%@' || d.domain`, which compares every pair of rows; joining on the extracted domain turns it into an equality join.


<br>

---

## Aggregating Rows into One String

This one arrives as an export spec: "a row per order with its products listed", "each customer's tags in a single column for the CRM sync", "the pages each session visited, in order". Naming the function earns little. What gets scored is whether the list comes out in a stated order and whether every source row appears in it exactly once.

| Engine | Rows into a single string |
| --- | --- |
| Postgres, BigQuery | STRING_AGG(x, ', ' ORDER BY y) |
| SQL Server 2017+ | STRING_AGG(x, ', ') WITHIN GROUP (ORDER BY y) |
| Snowflake, Oracle, Redshift, Trino | LISTAGG(x, ', ') WITHIN GROUP (ORDER BY y) |
| MySQL | GROUP_CONCAT(x ORDER BY y SEPARATOR ', ') |
| Spark | CONCAT_WS(', ', COLLECT_LIST(x)), order not guaranteed until the array is sorted |


<br>

### Order lives inside the aggregate

An `ORDER BY` at the end of the query sorts the output rows and does nothing to the items inside each string. Without an ordering clause inside the aggregate, items follow whatever order the scan or hash table produced, so the same query can return 'outdoor, running' today and 'running, outdoor' after a parallel plan change. Any test or diff that compares those strings starts failing with no change in the data.

```sql
-- A row per session, pages in the order they were viewed
SELECT
  session_id,
  STRING_AGG(page_path, ' > ' ORDER BY viewed_at, event_id) AS path
FROM page_views
GROUP BY session_id
```

The second sort key is the detail interviewers notice. Two page views in a session can share a `viewed_at` value, and between tied rows the order is back in the engine's hands. `event_id` breaks the tie, so the string is identical on every run.


<br>

### Every row in, nothing doubled

Completeness fails in 3 quiet ways, and a small run shows 2 of them. The query lists tags per product; product 1 has a tag row whose value is NULL, and product 2 has no tag rows at all.

https://github.com/user-attachments/assets/3b035690-9cb0-4d24-8ed9-49f780c99655

Trail Shoe has 2 tag rows and a 1-item string, because `STRING_AGG` skips the NULL as every aggregate does, with no warning. `tag_rows` counts the join key rather than the tag, which is why the 2 numbers disagree. Gift Card survives the `LEFT JOIN` as a single row carrying a NULL tag, and an aggregate over no non-null values returns NULL rather than an empty string. Say which you want: `COALESCE(STRING_AGG(...), '')` for an export that rejects NULLs, or `STRING_AGG(COALESCE(t.tag, '(blank)'), ...)` when a blank tag is information someone needs to see.

#### The third way: a join that multiplies

```sql
-- Rain Jacket: 2 tags x 3 variants = 6 joined rows
SELECT
  p.product_id,
  STRING_AGG(t.tag, ', ' ORDER BY t.tag) AS tags,
  COUNT(v.sku) AS variants
FROM products AS p
JOIN product_tags AS t
  ON t.product_id = p.product_id
JOIN product_variants AS v
  ON v.product_id = p.product_id
GROUP BY p.product_id
-- tags:     'outdoor, outdoor, outdoor, waterproof, waterproof, waterproof'
-- variants: 6, not 3
```

Adding `DISTINCT` inside the aggregate cleans the string and hides the bug: the variant count stays at 6, and on a session path `DISTINCT` deletes a real second visit to `/cart`. Postgres also rejects `STRING_AGG(DISTINCT tag, ', ' ORDER BY created_at)`, because with `DISTINCT` the sort key must be the aggregated value. The fix the interviewer is listening for is to aggregate each child table to the product grain in its own CTE, then join the CTEs, so every join is one-to-one.

```sql
WITH tag_lists AS (
  SELECT
    product_id,
    STRING_AGG(tag, ', ' ORDER BY tag) AS tags
  FROM product_tags
  GROUP BY product_id
),
variant_counts AS (
  SELECT
    product_id,
    COUNT(*) AS variants
  FROM product_variants
  GROUP BY product_id
)

SELECT
  p.product_id,
  t.tags,
  COALESCE(v.variants, 0) AS variants
FROM products AS p
LEFT JOIN tag_lists AS t
  ON t.product_id = p.product_id
LEFT JOIN variant_counts AS v
  ON v.product_id = p.product_id
```

"How long can that string get?" tests whether you have shipped one. Multiply items per group by average item length: a customer with 5,000 tags averaging 12 characters puts about 60 KB in a single cell, far past the limits below.

> Limits that cut the string short
>
> - MySQL `GROUP_CONCAT` truncates at `group_concat_max_len`, 1,024 bytes by default, and reports it only as a warning.
> - Oracle `LISTAGG` raises ORA-01489 past the 4,000-byte VARCHAR2 limit unless the call says `ON OVERFLOW TRUNCATE` (12.2 and later).
> - A value containing the delimiter, such as 'Smith, Jr.', becomes 2 entries for whoever splits the string later.

> **TIP**
>
> When the follow-up is "a downstream job will split this back apart", keep the list as an array (`ARRAY_AGG` with the same ordering) or as JSON until the last step. A delimited string is a format for people and flat-file exports, and every parser that reads one assumes the delimiter never appears in the data.


<br>

---

## Normalizing Inconsistent Spellings

The disguise here is a chart. "Signups by country shows 14 bars for the United States." "Vendor spend lists Acme Corp and Acme Corp. as 2 vendors, and ACME Corporation as a third." The answer that scores has 2 stages: rules that clean every value the same way into a match key, then a mapping from that key to a single canonical value, plus a plan for the values the mapping has never seen.


<br>

### Stage 1: a match key built from rules

```sql
-- Same rule for every row, no knowledge of what the values mean
LOWER(
  TRIM(
    REGEXP_REPLACE(
      REGEXP_REPLACE(country_raw, '[.,]', '', 'g'),  -- drop dots and commas
      '\s+', ' ', 'g')                               -- collapse whitespace runs
  )
) AS match_key
```

'U.S.A.' becomes 'usa' and ' United States' becomes 'united states'. The invisible-character cleanup runs before any of this, so a non-breaking space is already an ordinary one by the time `\s+` sees it. Every rule applies to every value in the column, and that's the risk to name: deleting dots is safe for country names and wrong for version numbers, where '3.5' and '35' are different releases, and deleting all punctuation would merge 'C' with 'C++'.


<br>

### Stage 2: a canonical value per key

| ✓ CASE WHEN in the query | ✗ A mapping table joined once |
| --- | --- |
| • Fits up to roughly 10 variants<br><br>• The first matching branch wins, so branch order is logic<br><br>• A new spelling means a code change and a deploy<br><br>• Copied into every query that needs it, and the copies drift | • Holds hundreds of variants, a row each<br><br>• Edited by the team that knows the domain, without a deploy<br><br>• Joined in a staging model that everything downstream reads<br><br>• Needs a unique key, or the join multiplies rows |

#### Pattern branches swallow their neighbours

```sql
CASE
  WHEN match_key IN ('us', 'usa', 'united states') THEN 'US'
  WHEN match_key LIKE 'united%'                    THEN 'GB'  -- meant for 'united kingdom'
  WHEN match_key IN ('germany', 'deutschland')     THEN 'DE'
  ELSE 'UNMAPPED'
END AS country_code
-- 'united arab emirates' is now GB, and nothing warns you
```

`LIKE 'united%'` was written for the UK and also catches the UAE, and because `CASE` returns the first branch that matches, reordering the branches changes the output. Exact-match lists are safer than patterns in a mapping, and past a handful of variants the list belongs in a table.

The canonical value should be a code. ISO 3166-1 alpha-2 codes ('US', 'DE') never change spelling, while display names do ('Czech Republic' became 'Czechia' in 2016), and a label stored as the canonical value turns that rename into a fresh round of normalization. The label lives in a country dimension keyed by the code.

Here is stage 2 on 3 signups, with the key simplified to `REPLACE(LOWER(TRIM(...)), '.', '')` so the run stays readable.

https://github.com/user-attachments/assets/cd78bd83-4c17-406a-9e92-d8eecc010922

'u.s.a.' and ' United States' land on US once the key loses its dots and the leading space. 'America' has no row in the map, so the `LEFT JOIN` keeps signup 3 with a NULL code and `COALESCE` labels it UNMAPPED. With an inner join that signup disappears, and a chart built on it undercounts with nothing on screen to show a row went missing.

The first version of the map comes from the data. List every distinct key with its row count and sort most frequent first. Map from the top. On a country column a few dozen keys usually cover nearly all rows, with a long tail of one-off spellings behind them; the tail shows up as UNMAPPED, and its share tells you when it has grown enough to be worth mapping.

```sql
-- Seed the map: every distinct key, most frequent first
SELECT
  match_key,
  COUNT(*) AS signups
FROM staged_signups
GROUP BY match_key
ORDER BY signups DESC
```


<br>

### The follow-ups, and what to say

> Questions that come after the mapping
>
> - Values you have never seen? Track the UNMAPPED share on every load, alert above a threshold such as 1% of rows, and add the new spellings to the map.
> - Fuzzy matching instead? Use edit distance to propose candidate rows for the map, a person approves them, and the join stays exact.
> - Two map rows with the same key? The join doubles those signups. Enforce uniqueness on `match_key` with a test.
> - Keep the raw value? Always. With `country_raw` next to the canonical code, fixing the map is a rerun instead of a reload.

> **TIP**
>
> Edit distance is `LEVENSHTEIN` in Postgres (fuzzystrmatch extension), `EDITDISTANCE` in Snowflake and `EDIT_DISTANCE` in BigQuery. 'Smith' and 'Smyth' score 1. A cutoff of 2 catches typos in short names and also pairs Austria with Australia, which is why its output goes to a review queue instead of into the join.


<br>

---

## Handling Variable-Length Fields

Here the question hands you a column whose pieces move. "Pull the domain out of these emails." "The order id is the last segment of the URL path." "Parse these log lines; the keys don't always come in the same order." Fixed character offsets break because every row has a different length. A strong answer locates each piece by its delimiter or its key, decides what happens when the delimiter is missing, and proves every row parsed.


<br>

### Find the delimiter, then cut

```sql
SELECT
  email,
  SUBSTRING(email FROM STRPOS(email, '@') + 1) AS domain_raw,
  SUBSTRING(email FROM NULLIF(STRPOS(email, '@'), 0) + 1) AS domain
FROM crm_contacts
```

| email | STRPOS | domain_raw | domain |
| --- | --- | --- | --- |
| li.wei@acme.com | 7 | acme.com | acme.com |
| ops@northwind.io | 4 | northwind.io | northwind.io |
| n/a | 0 | n/a | NULL |

`STRPOS` returns 0 when the delimiter is absent, and `0 + 1` is a valid start position, so 'n/a' passes through as its own domain without any error. `NULLIF` turns the 0 into NULL, NULL propagates through the arithmetic and the `SUBSTRING`, and the bad row becomes a NULL you can count. The same guard belongs on the left side: `LEFT(email, STRPOS(email, '@') - 1)` on a row with no `@` asks for -1 characters, which Postgres reads as "all but the last".


<br>

### Last segments and counting delimiters

```sql
-- '/shop/orders/2024/A-77310': the order id is the last segment
SPLIT_PART(path, '/', -1)          -- Postgres 14+, Snowflake
REGEXP_EXTRACT(path, r'[^/]+$')    -- BigQuery
REGEXP_SUBSTR(path, '[^/]+$')      -- Oracle, Redshift, Snowflake

-- Shape of each value: how many '/' it contains
LENGTH(path) - LENGTH(REPLACE(path, '/', '')) AS slash_count
```

Strip a trailing delimiter first with `RTRIM(path, '/')`. On '/shop/orders/2024/A-77310/' the 3 forms above fail differently: `SPLIT_PART` returns an empty string, which passes every NULL check and lands in the output as a blank order id, while the `[^/]+$` regex forms find no match and return NULL. After `RTRIM`, all 3 return 'A-77310'.

The delimiter count is the profiling step to run before writing the parser. `GROUP BY slash_count` over the column shows how many shapes exist: if 98% of paths have 4 slashes and the rest have 5 because some URLs carry a locale prefix such as `/en-gb/`, the last segment is still safe, but taking the year by its position is wrong for those rows. Interviewers ask "how do you know every row looks like the sample?" and this query is the answer.


<br>

### Keys that change places

Log lines such as `2024-03-15T14:30:45|event=login|user_id=123|amount=99.50` look positional until a release adds a key in the middle or a client omits one. Extract by key name instead of by position. Where the engine has a map type, split the pairs into a map and look keys up; elsewhere, use a regex anchored to the delimiter.

```sql
-- Trino: pairs into a map, then lookup by name
SELECT ELEMENT_AT(kv, 'user_id')                             AS user_id,
       TRY_CAST(ELEMENT_AT(kv, 'amount') AS DECIMAL(12, 2))  AS amount
FROM (
  SELECT SPLIT_TO_MAP(SUBSTR(line, STRPOS(line, '|') + 1), '|', '=') AS kv
  FROM raw_logs
) AS t;

-- Postgres: the key must follow the start of the line or a '|'
SUBSTRING(line FROM '(?:^|\|)user_id=([^|]*)')
```

The anchor is the trap. An unanchored `'user_id=([^|]*)'` also matches inside `old_user_id=88`, and when that key comes first it returns 88 for every such row. `SPLIT_TO_MAP` has its own failure: a line that repeats a key raises an error and stops the query, so profile for duplicate keys first. `ELEMENT_AT` returns NULL for a missing key, and `TRY_CAST` returns NULL for 'N/A' instead of failing the whole run, which is the behaviour you want while parsing and the reason to count those NULLs afterwards.


<br>

### Prove the parse

```sql
SELECT
  COUNT(*) AS total_rows,
  COUNT(domain) AS parsed,
  COUNT(
    CASE
      WHEN domain IS NULL THEN 1
    END
  ) AS no_at_sign,
  COUNT(
    CASE
      WHEN domain NOT LIKE '%.%' THEN 1
    END
  ) AS no_dot_in_domain
FROM parsed_contacts
```

Ending with this query is what separates a parser from a guess. `total_rows` equals `parsed` plus `no_at_sign`, so every row is accounted for and the answer to "how many rows did you lose?" is a number. `no_dot_in_domain` is a different kind of column: it counts rows that parsed but hold a suspect value, such as 'localhost' from 'admin@localhost', and those rows already sit inside `parsed`, so adding it to the sum overcounts. Keep the reconciliation columns mutually exclusive and label quality checks as checks. Some fields fail this test by design: splitting 'Mary Ann van der Berg' at the first and last space yields 'Mary' and 'Berg', and no rule fixes it. Say so, and ask for first and last name as separate source fields.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Measure LENGTH and code points before choosing what to strip<br><br>• Put ORDER BY, with a tiebreaker, inside every string aggregate<br><br>• Aggregate each child table to the parent's grain before joining<br><br>• LEFT JOIN to the mapping table and count UNMAPPED on every load<br><br>• Wrap STRPOS in NULLIF and reconcile parsed rows against the total | • Strip every non-ASCII character to clean a name column<br><br>• Write NOT LIKE on a nullable column without COALESCE<br><br>• Move a LIKE pattern to regex without escaping dots and adding anchors<br><br>• Patch a fanned-out list with DISTINCT inside the aggregate<br><br>• Extract key=value fields by position or with an unanchored key |


<br>

---

## Putting It All Together

A B2B software company's finance team reconciles open invoices against CRM accounts every month. The CRM is loaded from a spreadsheet export: account names carry non-breaking spaces and carriage returns, billing countries are typed by hand, and contact emails need grouping by domain. Finance wants a row per account with its canonical country, its company email domain, and its open invoice numbers as an ordered, comma-separated list.

- Clean the account name first, or the invoice join still finds nothing. Turn NBSP and CR into spaces and drop zero-width characters, then apply NFC normalization and TRIM last.
- Map billing country through a cleaned match key and a mapping table, LEFT JOINed, so unknown spellings surface as UNMAPPED instead of vanishing.
- Derive the email domain with STRPOS guarded by NULLIF, and filter company addresses with equality on that domain instead of a '%acme.com' pattern.
- Aggregate invoices to the account grain in their own CTE with STRING_AGG ordered by invoice date and number, then join, so contacts cannot multiply the list.
- Finish with a reconciliation query that counts accounts in and accounts out, plus the unmapped countries and unparsed emails.


<br>

---

## Key Takeaways

- Strings that print alike can differ by NBSP, CR, zero-width characters or NFC/NFD forms. Measure LENGTH and code points before choosing a fix.
- LIKE patterns cover the whole value, so escape literal _ and % and guard NOT LIKE against NULL. When you move to regex, anchor the pattern and escape the dots.
- A delimited list is complete only with ORDER BY and a tiebreaker inside the aggregate, NULLs handled on purpose, and children aggregated before joining.
- Canonical values come from a rules-built match key plus a mapping table, LEFT JOINed, with the UNMAPPED share tracked on every load.
- Parse moving fields by delimiter or key name, turn a missing delimiter into NULL with NULLIF, and reconcile parsed rows against the total.
