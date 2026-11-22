# Semi-Structured Data: Intermediate

Thirty minutes into a SQL round at a marketplace company, the interviewer pastes one order into the shared editor:
`{"order_id": 1001, "items": [{"sku": "A-12", "qty": 2, "price": 12.5}, ...], "coupon": "SPRING10"}`
"Every order lands like this, one JSON document per row. I want units and revenue per order, all orders included, and the lines nested back inside each result row. Also, how many used no coupon?"
She says nothing about the other 41,999 documents. Some carry an empty `items` array. One app version sends `price` as the string "19.99". Older clients never send `coupon` at all. A query written against the tidy row on screen returns a confident total that is wrong in 3 places.
What she is scoring is whether you ask what the other rows look like before you flatten anything.


<br>

### What you will be able to do

Flatten a JSON array with UNNEST and predict the result's row count and grain before running it

Re-nest element rows into ordered arrays or structs without inflating parent-level sums

Keep parents whose arrays are empty, missing or null, and report their element counts as 0

Read a key that arrives as a number in some rows and a string in others without silently losing values

Separate a missing key from a JSON null after extraction and explain why the answer changes


<br>

---

## Flattening Arrays with UNNEST

The flatten step rarely announces itself. "Top 10 SKUs by units sold this week." "Average line price across all orders." "How many orders contain a SKU from the clearance list?" None of these says array, yet each needs the `items` array inside every order's JSON turned into rows before an aggregate can reach it. The strong answer writes that flatten as its own named step, then builds the business logic on top of it.


<br>

### What one output row means

`UNNEST` takes an array and returns a table with one row per element. Written in `FROM` after the parent table, it runs once for each parent row and joins its output back to that row, so every element row carries a copy of the parent's columns. The join is lateral: the function on the right reads a column from the row on the left, which is why it needs no join condition. The running example is `orders_raw`, 4 orders that each have a `shipping_fee` column and a `payload` whose `items` array holds `{sku, qty, price}` objects.

```sql
-- Trino: one row per order line
SELECT
  o.order_id,
  o.shipping_fee,
  i.line_no,
  JSON_EXTRACT_SCALAR(i.item, '$.sku') AS sku,
  CAST(JSON_EXTRACT_SCALAR(i.item, '$.qty') AS INTEGER) AS qty
FROM orders_raw AS o
CROSS JOIN UNNEST(CAST(JSON_EXTRACT(o.payload, '$.items') AS ARRAY(JSON))) WITH ORDINALITY AS i(item, line_no)
ORDER BY o.order_id, i.line_no
```

| order_id | shipping_fee | line_no | sku | qty |
| --- | --- | --- | --- | --- |
| 1001 | 5.00 | 1 | A-12 | 2 |
| 1001 | 5.00 | 2 | B-07 | 1 |
| 1001 | 5.00 | 3 | C-33 | 3 |
| 1002 | 7.50 | 1 | A-12 | 1 |
| 1004 | 6.00 | 1 | D-90 | 2 |
| 1004 | 6.00 | 2 | A-12 | 1 |

Four orders went in and 6 rows came out: 3 for 1001, 1 for 1002, none for 1003 and 2 for 1004. The result's row count is the sum of the array lengths, and the grain has moved from one row per order to one row per order line. `shipping_fee` now repeats on every line of its order, which does no harm while it is only displayed and becomes a bug the moment a later step adds it up.

> What the interviewer is listening for
>
> - The grain, said out loud: after the flatten, one row is one line of one order.
> - The row count, predicted before running: the total of the array lengths, never the order count.
> - The parent key carried through, so every element row can be traced and grouped back.
> - Position kept with `WITH ORDINALITY` whenever line order carries meaning.
> - The empty-array question raised early, even if the fix comes later.


<br>

### The same move in every engine

| Engine | Flatten | Position column |
| --- | --- | --- |
| Trino / Presto | `CROSS JOIN UNNEST(arr) AS t(x)` | `WITH ORDINALITY`, from 1 |
| BigQuery | `CROSS JOIN UNNEST(arr) AS x` | `WITH OFFSET`, from 0 |
| Snowflake | `FROM t, LATERAL FLATTEN(input => t.payload:items) f` | `f.index`, from 0 |
| Postgres | `CROSS JOIN LATERAL jsonb_array_elements(payload->'items') AS i(item)` | `WITH ORDINALITY`, from 1 |
| Spark SQL | `LATERAL VIEW explode(items) t AS x` | `posexplode`, from 0 |

The keyword changes and the operation does not. Calling it "a lateral join that fans each order out by its item count" lands on whichever engine the interviewer runs, and it shows you know what the syntax does rather than which keyword spells it. Watch the position base when translating: offset 0 in BigQuery is ordinality 1 in Trino, and an off-by-one there misaligns every later join on position.


<br>

### Two arrays on one row

The follow-up that separates people who have flattened real payloads: each order also carries a `promos` array, and the answer needs both. Two independent lateral joins multiply, so an order with 3 items and 2 promos becomes 6 rows, every item paired with every promo. That shape is right only when the question is about pairs, and any sum of `qty` over it has silently doubled for that order.

| ✓ Parallel arrays: zip them | ✗ Unrelated arrays: keep them apart |
| --- | --- |
| • Element 1 of skus belongs with element 1 of qtys<br><br>• Trino and Postgres take both in one UNNEST(skus, qtys) and pad the shorter with NULL<br><br>• BigQuery unnests each WITH OFFSET and joins on equal offsets<br><br>• Rows out equal the longer array's length | • items and promos describe different things<br><br>• Flatten each one in its own CTE<br><br>• Aggregate each back to one row per order<br><br>• Join the 2 results on order_id |


<br>

### Counting parents after the flatten

The clearance-list disguise hides a second trap. After the flatten, `COUNT(*)` behind a clearance filter counts lines, so an order holding 2 clearance SKUs is counted twice. Counting orders needs `COUNT(DISTINCT o.order_id)`, or an `EXISTS` over the unnested array, which never changes the grain at all. The `EXISTS` form is the one worth naming: it can stop at the first matching element of each order and returns exactly one verdict per order by construction.

```sql
-- Trino: orders holding at least one clearance SKU, grain unchanged
SELECT
  COUNT(*) AS orders_with_clearance
FROM orders_raw AS o
WHERE EXISTS (
  SELECT
    1
  FROM UNNEST(CAST(JSON_EXTRACT(o.payload, '$.items') AS ARRAY(JSON))) AS i(item)
  WHERE JSON_EXTRACT_SCALAR(i.item, '$.sku') IN (
    SELECT
      sku
    FROM clearance_skus
  )
)
```

> **TIP**
>
> Before writing the flatten, ask for the longest array and the 99th-percentile length. A 50-line cart limit caps the fan-out at 50x. A bulk-ordering client that sends 5,000 lines in one order puts all of them on one worker the moment anything shuffles by `order_id`.


<br>

---

## Re-Nesting After Aggregation

This part of the question comes back as a required output shape. "One row per order, with its lines as an array." "Per customer, the distinct SKUs they bought, as a list." "Correct the prices and hand me the payload back in the same form." Each one flattens, does work at the element grain, then climbs back to the parent grain with the elements gathered up. The climb is a `GROUP BY` on the parent key with an array aggregate. The code below reads the earlier flatten materialised as `order_lines`, one row per order line.

```sql
-- Trino, reading the flattened model order_lines
-- (order_id, line_no, sku, qty, shipping_fee)
WITH per_sku AS (
  -- step 1: one row per order and SKU
  SELECT
    order_id,
    sku,
    SUM(qty) AS qty,
    MIN(line_no) AS first_line
  FROM order_lines
  GROUP BY order_id, sku
) -- step 2: one row per order

SELECT
  order_id,
  SUM(qty) AS units,
  ARRAY_AGG(
    CAST(ROW(sku, qty) AS ROW(sku VARCHAR, qty INTEGER)) ORDER BY first_line, sku
  ) AS lines
FROM per_sku
GROUP BY order_id
```

The first step collapses repeated SKUs within an order, which real carts produce whenever a client posts one line per tap. The second folds those rows into one per order. Narrate them as "first per order and SKU, then per order": that sentence proves you know which grain each aggregate runs at, and it is exactly where a single `GROUP BY order_id` over the raw lines goes wrong, because a client that posted `A-12` as 2 taps in order 1001 would get an array listing it twice.


<br>

### Arrays come back in no fixed order

`GROUP BY` promises nothing about the sequence in which rows reach the aggregate, so a bare `ARRAY_AGG(sku)` can return `[C-33, A-12, B-07]` today and a different arrangement after the cluster is resized. When position matters, the `ORDER BY` goes inside the aggregate call, and the ordinality captured during the flatten is the only reliable record of the source order. Interviewers who have chased a flaky pipeline test ask it directly: "will that array be identical on every run?" It is identical only when the sort key is deterministic, which is why the query above adds `sku` as a tie-breaker.


<br>

### The parent column that gets summed

Every element row carries its parent's columns, so an aggregate over a parent-level column at the element grain counts that value once per element. Here are the `order_lines` rows for orders 1002 and 1004, with `shipping_fee` copied onto each line, folded by `order_id`.

https://github.com/user-attachments/assets/21604a03-cb27-4d8f-90e2-45e6da4c9d7f

Order 1004 paid 6.00 for shipping and the summed column reports 12.00, because it has 2 lines. Order 1002 comes out right only because it has a single line. `units` comes out right because `qty` lives at the element grain; shipping comes out wrong because it lives at the order grain. The fixes, in order of preference: take parent-level columns from the parent table and join the element aggregate to it; use `MAX` or `ANY_VALUE` when the value is constant within each group; and treat any `SUM` or `AVG` over a column coarser than the row as a bug on sight. This is the fan-out a duplicate join key causes, and naming it that way ties the flatten to a failure every interviewer already scores.

- **34.50** — shipping summed over all 6 line rows
- **18.50** — charged to the 3 orders with items


<br>

### Structs, objects and NULLs by engine

| Engine | Re-nest as | If the value itself is NULL |
| --- | --- | --- |
| Trino | `array_agg(CAST(ROW(...) AS ROW(...)) ORDER BY ...)` | kept in the array |
| BigQuery | `ARRAY_AGG(STRUCT(sku, qty) ORDER BY ...)` | error if one reaches the result; `IGNORE NULLS` drops them |
| Snowflake | `ARRAY_AGG(OBJECT_CONSTRUCT('sku', sku)) WITHIN GROUP (ORDER BY ...)` | skipped |
| Postgres | `jsonb_agg(jsonb_build_object('sku', sku) ORDER BY ...)` | kept as JSON null |

That last column applies only when the aggregated value itself is NULL, as with a bare `ARRAY_AGG(sku)`. A struct or object built from an outer flatten's placeholder row is a non-null record of nulls on every engine: a `ROW` of nulls in Trino, a `STRUCT` of nulls in BigQuery, `{"sku": null}` in Postgres and `{}` in Snowflake. No rule in the table removes it, and `IGNORE NULLS` passes it straight through. Exclude the placeholder before the aggregate: `FILTER (WHERE sku IS NOT NULL)` on Trino and Postgres, `IF(sku IS NULL, NULL, STRUCT(sku, qty))` with `IGNORE NULLS` on BigQuery, `IFF(sku IS NULL, NULL, OBJECT_CONSTRUCT(...))` on Snowflake, then apply the empty-array fallback from the next section.


<br>

### Transform in place when the grain stays put

When the work is per element and the answer is still one row per order (prices to cents, cancelled lines removed, lines sorted by price), flattening and regrouping sends every element through a shuffle only to land where it started. A correlated array subquery rebuilds the array inside each row and never changes the grain. BigQuery writes it as `ARRAY(SELECT ... FROM UNNEST(o.items))`, Trino offers the `transform` and `filter` lambdas, and Snowflake has `TRANSFORM` and `FILTER` higher-order functions. Offering this when the interviewer asks for "the payload back" shows you weighed the cost of the regroup rather than reaching for `GROUP BY` out of habit.

```sql
-- BigQuery, items stored as ARRAY<STRUCT<sku STRING, qty INT64, price NUMERIC>>
SELECT
  o.order_id,
  ARRAY(
    SELECT AS STRUCT i.sku, i.qty, CAST(i.price * 100 AS INT64) AS price_cents
    FROM UNNEST(o.items) AS i WITH OFFSET AS pos
    ORDER BY pos
  ) AS items
FROM orders AS o;
```

No `GROUP BY`, no ordering risk, and order 1003 comes back holding an empty array, because the subquery runs inside its row instead of joining against it.


<br>

---

## Keeping Parents with Empty Arrays

This one usually arrives as a reconciliation. "Yesterday `orders_raw` had 42,000 orders and the order-lines model has 41,880. Where did 120 go?" Sometimes it hides inside a requirement instead: "line count per order, every order included." Both describe one mechanic. `CROSS JOIN UNNEST` is an inner join between a row and its own elements, and an array with zero elements leaves nothing to join, so the parent disappears. Order 1003, a gift-card purchase whose payload holds `"items": []`, sits in the input and is absent from every flattened result so far.

Three payload shapes cause the drop: an empty array, a missing `items` key, and `"items": null`. The first 2 yield zero element rows on every major engine. The third depends on the engine: Trino casts the JSON null to SQL NULL and quietly returns nothing, while Postgres stops the query with `cannot extract elements from a scalar`, which at least fails loudly. On Trino the gap of 120 can hold all 3 shapes, and the interviewer may ask how you would tell them apart before fixing anything.


<br>

### The outer flatten

```sql
-- Trino: every order survives, empty or not
SELECT
  o.order_id,
  COUNT(i.item) AS line_count -- counts elements, so 1003 gets 0
FROM orders_raw AS o
LEFT JOIN UNNEST(CAST(JSON_EXTRACT(o.payload, '$.items') AS ARRAY(JSON))) AS i(item)
  ON TRUE
GROUP BY o.order_id
ORDER BY o.order_id
```

| order_id | line_count |
| --- | --- |
| 1001 | 3 |
| 1002 | 1 |
| 1003 | 0 |
| 1004 | 2 |

`LEFT JOIN ... ON TRUE` keeps every order and fills the element columns with NULL when there is nothing to pair. The condition is `TRUE` because the lateral reference has already decided which elements belong to which row; the outer join's only job is to keep the parent that found none. The result is back to 4 rows for 4 orders, with 1003 reporting a line count of 0.

Every aggregate over 1003's element columns now sees only NULL. `COUNT(i.item)` returns 0, but a `SUM` over an element field such as `qty` returns NULL, because a sum over no values has no value. Wrap it in `COALESCE(SUM(qty), 0)` when the consumer expects a number, and say why in the room: NULL units in a revenue extract reads as missing data, while 0 reads as an order with nothing in it, which is exactly what 1003 is.

| Engine | Outer flatten |
| --- | --- |
| Trino / Presto | `LEFT JOIN UNNEST(arr) AS t(x) ON TRUE` |
| BigQuery | `LEFT JOIN UNNEST(arr) AS x` |
| Snowflake | `LATERAL FLATTEN(input => payload:items, OUTER => TRUE)` |
| Postgres | `LEFT JOIN LATERAL jsonb_array_elements(payload->'items') AS i(item) ON TRUE` |
| Spark SQL | `LATERAL VIEW OUTER explode(items)`, or `explode_outer` |


<br>

### Three ways to lose the row again

Switching to the outer flatten is half the answer. The NULL placeholder row it creates for 1003 is fragile, and 3 ordinary later steps distort or delete it. The follow-ups live here.

| Later step | What happens to 1003 | Fix |
| --- | --- | --- |
| `COUNT(\*)` | Reports 1 line, because the NULL placeholder is a row | Count an element column: `COUNT(i.item)` |
| `WHERE qty > 0` | NULL > 0 is unknown, the row is filtered, 1003 vanishes | Move the test into the aggregate: `COUNT(CASE WHEN qty > 0 THEN 1 END)` |
| `ARRAY_AGG(sku)` | Trino and Postgres build `[NULL]`, a 1-element array for an order with none | `ARRAY_AGG(sku) FILTER (WHERE sku IS NOT NULL)`, then `COALESCE` the NULL result to an empty array |

The `WHERE` row is the trap interviewers set on purpose. They accept the `LEFT JOIN`, nod, and then ask for "line counts per order, ignoring zero-quantity lines." A predicate on an element column in `WHERE` runs after the join, the placeholder row fails it, and the outer flatten has become an inner one again, with no error and 120 orders missing. Moving the condition into a conditional aggregate keeps the parent and still excludes the lines.


<br>

### When to skip the flatten

If the only output is a number per order, the safest way to keep 1003 is to never produce element rows at all. A scalar subquery over the array runs inside each parent row, returns exactly one value per order, and has no join that could drop anything. The `COALESCE` stays, because an aggregate over zero rows still returns NULL.

```sql
-- Postgres: one value per order, no join, no dropped parents
SELECT
  o.order_id,
  (
    SELECT
      COALESCE(
        SUM(
          CAST(
            (
              e ->> 'qty'
            )
            AS INT
          )
        ),
        0
      )
    FROM JSONB_ARRAY_ELEMENTS(o.payload -> 'items') AS e
  ) AS units
FROM orders_raw AS o
```

> **TIP**
>
> Reconcile before presenting any flattened model: compare `COUNT(DISTINCT order_id)` on the output with `COUNT(*)` on the parent, and offer to keep that comparison as a test on the model. It is the line that sounds like a pipeline you have run, and it catches the next 120 the day a client starts sending empty carts.


<br>

---

## A Key Whose Type Varies by Row

This one shows up as a number that is slightly too small. "Revenue rebuilt from the `items` array is 3% under the finance ledger." "This join from events to users loses about a fifth of rows." The JSON parses fine; the same key is typed differently by different writers. Order 1004 came from an older Android build that serialises `price` as `"19.99"`, while the iOS app sends `12.5`. To a JSON parser those are a string and a number, and a function that expects one misreads, rejects or quietly skips the other.

Which function breaks depends on what it expects. Casting the JSON value directly, `(item->'price')::numeric` in Postgres, works on the number and fails the whole query on the string with `cannot cast jsonb string to type numeric`. Comparisons on the raw JSON value fail silently: Postgres sorts `jsonb` by type before value, with every Number above every String, so `item->'price' > '15'::jsonb` is false for `"19.99"`. Equality has the same flaw, because the number `123` and the string `"123"` are different JSON values, so a join on `payload->'user_id'` never matches across the 2 writers.


<br>

### Profile the types before casting

```sql
-- Postgres: what types does price actually arrive as?
SELECT
  JSONB_TYPEOF(e -> 'price') AS price_type,
  COUNT(*) AS line_rows
FROM orders_raw AS o
CROSS JOIN JSONB_ARRAY_ELEMENTS(o.payload -> 'items') AS e
GROUP BY 1
ORDER BY 2 DESC
```

| price_type | line_rows |
| --- | --- |
| number | 5 |
| string | 1 |

This is the query to open with when a type question lands, before any cast is written. Every engine has the probe: `jsonb_typeof` in Postgres, `JSON_TYPE` in BigQuery, `TYPEOF` on a `VARIANT` in Snowflake. The output says which branches the conversion needs, and on a real feed the long tail is where the surprises sit: an object where a scalar was expected, a boolean, an empty string. Six rows here; across 42,000 orders a day the third type might be 14 rows, and those 14 are what the follow-up will ask about.


<br>

### Normalise through text, cast defensively

Text extraction is the common ground across types. `->>` in Postgres, `JSON_VALUE` in BigQuery, `JSON_EXTRACT_SCALAR` in Trino and `::STRING` in Snowflake all return `12.5` for the number and `19.99` for the string, both as unquoted text. Cast that text to a decimal once, with the safe variant so a bad value becomes NULL instead of failing the run, and count those NULLs so the loss is visible.

```sql
-- Trino: one numeric price whatever the writer sent, plus a loss counter
WITH lines AS (
  SELECT
    o.order_id,
    CAST(JSON_EXTRACT_SCALAR(i.item, '$.qty') AS INTEGER) AS qty,
    JSON_EXTRACT_SCALAR(i.item, '$.price') AS price_text
  FROM orders_raw AS o
  CROSS JOIN UNNEST(CAST(JSON_EXTRACT(o.payload, '$.items') AS ARRAY(JSON))) AS i(item)
)

SELECT
  SUM(qty * TRY_CAST(price_text AS DECIMAL(10, 2))) AS revenue,
  COUNT(price_text) AS prices_present,
  COUNT(price_text) - COUNT(TRY_CAST(price_text AS DECIMAL(10, 2))) AS prices_unparsed
FROM lines
```

| revenue | prices_present | prices_unparsed |
| --- | --- | --- |
| 141.98 | 6 | 0 |

The last column answers the follow-up before it is asked. `TRY_CAST` turns `"N/A"`, `"12,50"` and `""` into NULL, and `SUM` skips NULLs, so a defensive cast without a counter swaps a crash for an undercount nobody notices. Report the unparsed count beside the total, or fail the job when it crosses a threshold such as 0.1% of lines. BigQuery spells the safe cast `SAFE_CAST`; Snowflake uses `TRY_TO_DECIMAL` on the text.


<br>

### When text is the wrong common ground

Routing through text works for prices. Four other cases need the type probe and an explicit branch, and naming them is what turns a correct answer into a thorough one.

> Where routing through text goes wrong
>
> - Large integer IDs: a 64-bit ID written as a JSON number can be rounded by any parser that reads it as a double. Prefer the string copy.
> - Booleans: `true` and `"true"` both become the text true, but `"yes"`, `"1"` and `"Y"` need a mapping in a CASE.
> - Timestamps: epoch seconds as a number and an ISO 8601 string need different parse functions.
> - Nested values: an object where a scalar belongs comes back NULL from `JSON_EXTRACT_SCALAR` and `JSON_VALUE`, and as serialized JSON text from Postgres `->>`. The type profile catches both.

```sql
-- Postgres: branch on the type when the formats differ
CASE jsonb_typeof(e->'ts')
  WHEN 'number' THEN to_timestamp((e->>'ts')::bigint)
  WHEN 'string' THEN (e->>'ts')::timestamptz
END AS event_ts
```



- **2^53** — where doubles stop holding every integer

The full answer the interviewer is grading has 4 parts: the profile query, the conversion through text or a type branch, the counter for what failed to convert, and one sentence noting that a typed column written once upstream saves every consumer from repeating this logic.


<br>

---

## Missing Keys and NULL Extraction

"How many orders used no coupon?" The quick query, `WHERE JSON_EXTRACT_SCALAR(payload, '$.coupon') IS NULL`, returns 3 of the 4 orders, and it is answering a different question. Order 1002 sent `"coupon": null`: checkout ran the coupon step and the customer applied nothing. Orders 1003 and 1004 never sent the key, because the app builds that wrote them predate the coupon feature. Scalar extraction turns both into the same SQL NULL, so "no coupon" and "we have no idea" land in one bucket.

| ✓ Key missing | ✗ Key sent as null |
| --- | --- |
| • The writer never produced the field<br><br>• Usual cause: an older client or a skipped optional section<br><br>• For "used no coupon?" the answer is unknown | • The writer produced the field with no value<br><br>• Usual cause: the user cleared it, or the step ran and found nothing<br><br>• For "used no coupon?" the answer is yes |

| payload fragment | payload->'coupon' | payload->>'coupon' | payload ? 'coupon' |
| --- | --- | --- | --- |
| `{"coupon": "SPRING10"}` | `"SPRING10"` (jsonb) | `SPRING10` | true |
| `{"coupon": null}` | `null` (jsonb) | NULL | true |
| `{}` | NULL | NULL | false |

The JSON-returning operator keeps the distinction and the text operator destroys it. Postgres's `->` gives back a `jsonb` null for the explicit null and SQL NULL for the absent key, while `->>` maps both to SQL NULL. BigQuery's `JSON_VALUE`, Trino's `JSON_EXTRACT_SCALAR` and Snowflake's `::STRING` cast all behave like `->>`. Once the value is text, the information is gone, so the check runs on the JSON value or on the key itself, never on the extracted string.


<br>

### Classify into 3 states first

```sql
-- Postgres: present, explicit null, or never sent
SELECT
  CASE
    WHEN NOT (
      payload ? 'coupon'
    ) THEN 'not_sent'
    WHEN JSONB_TYPEOF(payload -> 'coupon') = 'null' THEN 'sent_null'
    ELSE 'applied'
  END AS coupon_state,
  COUNT(*) AS orders
FROM orders_raw
GROUP BY 1
ORDER BY 1
```

| coupon_state | orders |
| --- | --- |
| applied | 1 |
| not_sent | 2 |
| sent_null | 1 |

The answer to "how many used no coupon" is 1 confirmed, with 2 unknown, and saying that split out loud is the moment the interviewer is waiting for. Reporting 3 makes a confident claim about orders the data says nothing about, and it is the version that ends up on a dashboard comparing coupon uptake across app releases, where older releases look like customers who turned coupons down.

The same split applies to array elements. If a client posts `"items": [{"sku": "A-12", "qty": 1}, null]`, the flatten returns 2 element rows and the second holds a JSON null. In Postgres `COUNT(e)` counts it, since a `jsonb` null is a value, while `COUNT(e->>'sku')` does not, so line counts disagree depending on which column is counted. Decide whether a null element is a line, then filter with `jsonb_typeof(e) <> 'null'` where it is not.


<br>

### The probe in other engines

| Engine | Key present | Explicit JSON null |
| --- | --- | --- |
| Postgres | `payload ? 'coupon'` | `jsonb_typeof(payload->'coupon') = 'null'` |
| Snowflake | `payload:coupon IS NOT NULL` | `IS_NULL_VALUE(payload:coupon)` |
| BigQuery | `JSON_QUERY(payload, '$.coupon') IS NOT NULL` | `JSON_TYPE(JSON_QUERY(payload, '$.coupon')) = 'null'` |

Snowflake turns the trap around. A `VARIANT` holding JSON null is a value, so `payload:coupon IS NULL` is false for order 1002, and a filter written to catch every no-coupon order catches only the missing keys. The BigQuery row assumes `payload` uses the native JSON type. Loading can also erase the difference before any query runs: `STRIP_NULL_VALUES = TRUE` on a Snowflake JSON file format removes every key whose value is null, turning `sent_null` orders into `not_sent` orders permanently.

> **TIP**
>
> Postgres's `?` operator collides with the JDBC parameter placeholder, so a BI tool or Java service may reject the query. Write `??` in JDBC query strings, or call `jsonb_exists(payload, 'coupon')`, the function behind the operator.


<br>

### Where the difference changes the outcome

Partial-update feeds are the follow-up that tests production experience. Under JSON Merge Patch (RFC 7396), `{"coupon": null}` means remove the coupon and an absent `coupon` means leave it as it was. A change-data consumer that extracts with `->>` and writes the result into a target column applies a NULL in both cases, wiping fields the source never touched. The same split decides feature flags (switched off versus never configured) and survey answers (declined versus never shown).

`COALESCE(payload->>'coupon', 'none')` is the line that looks tidy in a dashboard and merges 2 meanings under one label. Classify into the 3 states first, then pick a default inside each state, and keep `not_sent` visible as its own value so the unknowns stay counted rather than relabelled.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Classify present, JSON null and missing before any COALESCE or IS NULL<br><br>• Test for the key on the JSON value: ?, JSON_QUERY or the VARIANT itself<br><br>• Report not_sent as its own bucket so unknowns stay counted<br><br>• Check the loader for STRIP_NULL_VALUES before trusting a null count | • Don't extract to text and then ask whether the key existed<br><br>• Don't COALESCE a missing key and a JSON null into one default label<br><br>• Don't write ->> output into a target column from a merge-patch feed<br><br>• Don't assume IS NULL catches a JSON null held in a Snowflake VARIANT |


<br>

---

## Putting It All Together

A marketplace's finance team reconciles daily order revenue, rebuilt from the raw JSON order feed in the warehouse, against the payments ledger. The rebuilt figure runs 3% low, the revenue model holds fewer orders than the source table, and a coupon-uptake chart split by app release shows older releases with implausibly low uptake. The data team owes finance a corrected model: one row per order with its lines nested inside, revenue that matches the ledger, and a coupon field that says only what the data actually knows.

- The flatten turns each order into one row per line, so revenue is computed at line grain while shipping, read from the parent table, is added once per order.
- Orders with empty, missing or null items drop from a cross join flatten; the outer flatten restores them and a reconciliation test keeps them restored.
- Re-nesting per order with an ordered ARRAY_AGG returns lines in source order, and the NULL placeholder from empty orders is filtered so they carry an empty array.
- Prices sent as strings by older Android builds are profiled, cast through text with TRY_CAST , and the unparsed count is reported beside revenue.
- The coupon chart splits into applied, sent null and not sent, so older releases show as unknown instead of as customers who declined coupons.


<br>

---

## Key Takeaways

- After an UNNEST , one row is one element: predict the row count as the sum of array lengths and never SUM a parent column at that grain.
- Re-nest in stated steps: aggregate per parent and element, then ARRAY_AGG per parent with an ORDER BY inside the aggregate.
- An empty, missing or null array drops its parent from a cross join flatten; LEFT JOIN UNNEST . . . ON TRUE keeps it, then count an element column.
- When a key arrives as both number and string, profile the types, cast through text with TRY_CAST , and count what failed to convert.
- Text extraction erases the gap between a missing key and a JSON null; classify into 3 states on the JSON value before any COALESCE .
