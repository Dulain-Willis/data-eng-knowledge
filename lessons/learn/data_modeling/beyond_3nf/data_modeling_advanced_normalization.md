Intermediate·Data Modeling · 19 min · 12 challenges

# Beyond 3NF

At Airbnb, a host profile table pairs every language a host speaks with every listing the host manages. A host with 3 languages and 4 listings fills 12 rows, and the table passes every 3NF check. A host adds Italian, and the language-sync job inserts 1 row where the full update needs 4. One dashboard now shows that host's Italian on 1 listing, another on all 4.


<br>

---

## Boyce-Codd Normal Form

Every normal form is a rule about functional dependencies. Column A determines column B, written `A -> B`, when 2 rows that agree on A always agree on B. A candidate key is a set of columns that determines every other column, and a table can have more than 1 candidate key. 3NF requires that every column outside the keys depends on a whole candidate key and on nothing else. The rule says nothing about columns that sit inside a key, and that silence is the gap Boyce-Codd Normal Form closes.


<br>

### A table that passes 3NF and still breaks

A tutoring marketplace records which tutor a student works with in each subject in `sessions(student_id, subject, tutor_id)`. Two business rules hold: a student has 1 tutor per subject, and a tutor teaches exactly 1 subject.

| student_id | subject | tutor_id |
| --- | --- | --- |
| S1 | Algebra | T7 |
| S1 | Physics | T2 |
| S2 | Algebra | T7 |
| S3 | Algebra | T9 |
| S4 | Physics | T2 |

The rules give 2 dependencies. `{student_id, subject} -> tutor_id`, because a student has 1 tutor per subject. `tutor_id -> subject`, because a tutor teaches 1 subject. That second dependency makes `{student_id, tutor_id}` a second key of the table: knowing the tutor tells you the subject. `subject` belongs to the key `{student_id, subject}`, so it counts as a key column, and 3NF exempts any dependency whose right side is a key column. That exemption lets `tutor_id -> subject` slip through, and the table passes.

Now watch it fail. Tutor T7 moves from Algebra to Geometry: every row carrying T7 must change, 2 rows in this sample and thousands in production, and a job that misses 1 leaves T7 teaching 2 subjects at once. Student S3 drops Algebra: the only row recording that T9 teaches Algebra disappears with the student. A new tutor T11 who teaches Chemistry can't be stored at all until a student signs up, because `student_id` is part of every key.

> The BCNF test
>
> - Write down every dependency the business rules imply.
> - Check whether the left side of each one is a candidate key of the table.
> - A dependency whose left side isn't a candidate key breaks BCNF, even when its right side is a key column.

`tutor_id` isn't a candidate key of `sessions`, because it doesn't determine `student_id`. So `tutor_id -> subject` breaks BCNF. The fix moves that dependency into a table where its left side is the key.


<br>

### The decomposition

![Schema diagram 1](_images/data_modeling_advanced_normalization_diagram_1.png)

`tutor_subjects` has 1 determinant, `tutor_id`, and it's the key. `student_tutors` has a 2-column key and no other columns, so nothing can depend on part of it. T7 moving to Geometry is now 1 row. S3 leaving deletes 1 row in `student_tutors` while T9 keeps teaching Algebra. T11 gets a row before any student arrives. The original 3-column view comes back with a join.

```sql
SELECT
  st.student_id,
  ts.subject,
  st.tutor_id
FROM student_tutors AS st
JOIN tutor_subjects AS ts
  ON st.tutor_id = ts.tutor_id
```

The price is that the rule `{student_id, subject} -> tutor_id` now spans 2 tables. A row pairing S1 with T7 and a second row pairing S1 with T9 would give S1 2 Algebra tutors, and neither table can reject the second row on its own. The check becomes a join that counts tutors per student per subject.

```sql
SELECT
  st.student_id,
  ts.subject,
  COUNT(*) AS tutors
FROM student_tutors AS st
JOIN tutor_subjects AS ts
  ON st.tutor_id = ts.tutor_id
GROUP BY st.student_id, ts.subject
HAVING COUNT(*) > 1
```

BCNF always removes the redundancy. It sometimes gives up the ability to enforce a dependency inside 1 table, and the engineer decides which costs more. For a tutor who changes subject once a year while thousands of session rows carry that subject, the join check wins.

> **TIP**
>
> A table with 2 overlapping candidate keys is the signature of a BCNF problem. Find the dependency that created the second key and ask whether its left side identifies a row on its own.

**A retail chain stores shifts(employee_id, store_id, manager_id). Each manager runs exactly 1 store, and each employee has exactly 1 manager at a given store. Which change brings the table into BCNF?**

- **A.** Leave the table alone. Both store_id and manager_id are key columns, so no dependency between them can violate a normal form.
- **B.** Split into managers(manager_id, store_id) and shifts(employee_id, manager_id), and derive the store through a join when a query needs it.
- **C.** Split into employees(employee_id, store_id) and stores(store_id, manager_id), with 1 row per store in the second table.
- **D.** Add a shift_id column as a new single-column key so that every other column depends on that key alone.

<details>
<summary>Solution</summary>

**B.** Split into managers(manager_id, store_id) and shifts(employee_id, manager_id), and derive the store through a join when a query needs it.

The dependency manager_id -> store_id now lives in a table where manager_id is the key, and a manager moving stores is 1 row.

**Why the others are wrong**

- **A.** Key columns are exactly what BCNF examines. manager_id -> store_id has a left side that isn't a candidate key, so the store repeats on every shift the manager covers.
- **C.** A store can have several managers, so store_id -> manager_id doesn't hold, and the split loses which manager each employee reports to.
- **D.** A new key changes nothing about manager_id -> store_id. The store still repeats on every row the manager appears in.

</details>


<br>

---

## Fourth Normal Form (4NF)

BCNF governs facts with 1 value: a tutor has 1 subject. Many facts carry a list of values, like the several languages a host speaks and the several listings a host manages. A table that stores both lists side by side has no functional dependency at all, passes BCNF, and still multiplies rows.

| host_id | language | listing_id |
| --- | --- | --- |
| 41 | English | L100 |
| 41 | English | L205 |
| 41 | English | L310 |
| 41 | Spanish | L100 |
| 41 | Spanish | L205 |
| 41 | Spanish | L310 |
| 58 | French | L411 |

Host 41 speaks 2 languages and manages 3 listings, so the table needs 6 rows, 1 per combination. Nothing determines anything: the same host appears with 2 languages and the same language with 3 listings, so the key is all 3 columns and BCNF has no complaint. Now host 41 learns Italian. The complete update inserts 3 rows, 1 per listing. A job that inserts only `(41, Italian, L100)` leaves the table claiming Italian goes with 1 listing and not the other 2, a claim nobody ever made, because a language belongs to the host and applies to every listing.


<br>

### Multi-valued dependency

The relationship is a multi-valued dependency, written `host_id ->> language`: for a given host, the set of languages across the rows is the same whatever listing those rows carry. The symmetric dependency `host_id ->> listing_id` holds for the same reason. 4NF requires that the left side of every such dependency is a candidate key. `host_id` alone is not a key of `host_profile`, so the table fails. The repair puts each list in its own table keyed by the host.

![Schema diagram 2](_images/data_modeling_advanced_normalization_diagram_2.png)

host_languages

| host_id | language |
| --- | --- |
| 41 | English |
| 41 | Spanish |
| 58 | French |

host_listings

| host_id | listing_id |
| --- | --- |
| 41 | L100 |
| 41 | L205 |
| 41 | L310 |
| 58 | L411 |

Adding Italian is now 1 row in `host_languages`, and no listing is involved. The saving grows with the lists: a host with 5 languages and 10 listings costs 50 rows in the combined table and 15 across the pair.


<br>

### The test that tells split from keep

Not every 3-column table with repeated values is a cross product. `listing_translations(listing_id, language, translated_title)` stores the languages a particular listing has been translated into. Adding a Japanese translation to L100 says nothing about L205. The language is a fact about that listing, so the columns stay together, and the table is already in 4NF. One question separates the 2 cases: when you add a value to column B for a given A, must you also add it for every value of column C that A has? If yes, B and C are independent lists and the table splits. If no, B and C form a single fact and the table stays.

Real data can answer the question for you. Count the distinct values of each list per host and compare the product with the rows stored.

```sql
SELECT
  host_id,
  COUNT(DISTINCT language) AS languages,
  COUNT(DISTINCT listing_id) AS listings,
  COUNT(*) AS stored_rows
FROM host_profile
GROUP BY host_id
```

When `stored_rows` equals `languages` times `listings` for every host, the table is storing 2 independent lists as a product and belongs in 2 tables. When it falls short for some hosts, either a job skipped rows or the 2 columns share a real relationship, and the data owners can tell you which.

**A university stores course_offerings(course_id, textbook_isbn, instructor_id). The textbooks for a course are fixed by the department, and the instructors for a course are assigned by the scheduling office. Neither list depends on the other. A course with 3 textbooks and 4 instructors holds 12 rows. What does 4NF call for?**

- **A.** Keep the table as it is, because course_id determines nothing on its own and so there is no dependency to repair.
- **B.** Split into course_textbooks(course_id, textbook_isbn) and textbook_instructors(textbook_isbn, instructor_id), with 2 smaller tables.
- **C.** Add a section_id column so that each row records 1 section taught with 1 textbook by 1 instructor.
- **D.** Split into course_textbooks(course_id, textbook_isbn) and course_instructors(course_id, instructor_id), 7 rows in place of 12.

<details>
<summary>Solution</summary>

**D.** Split into course_textbooks(course_id, textbook_isbn) and course_instructors(course_id, instructor_id), 7 rows in place of 12.

Each independent list gets its own table keyed by the course. Adding a textbook is 1 row and never touches the instructors.

**Why the others are wrong**

- **A.** There are 2 multi-valued dependencies from course_id, one per list, and a left side that isn't a key is exactly what 4NF repairs.
- **B.** This ties instructors to textbooks, a relationship nobody stated, and the second table still holds all 12 combinations.
- **C.** This invents a fact. The department's textbook list belongs to the course, and a section would have to repeat it.

</details>


<br>

---

## Fifth Normal Form (5NF)

4NF splits 2 independent lists. 5NF handles 3 lists tied together by a rule, and the rule decides whether a 3-column table is a fact in its own right or a product that a join could rebuild.

A creator marketing platform tracks sponsorships: a creator promotes a brand on a platform. `sponsorships(creator_id, brand, platform)` has a 3-column key and no functional or multi-valued dependency, so it passes BCNF and 4NF. Whether it passes 5NF depends on 1 sentence from the business. Suppose the sentence is: a creator promotes a brand on every platform where that creator is active and that brand advertises. Under that rule, every row of `sponsorships` follows from 3 smaller facts: which brands a creator works with, which platforms a creator is active on, and which platforms a brand advertises on.

| creator_id | brand | platform |
| --- | --- | --- |
| C1 | Acme | Video |
| C1 | Acme | Audio |
| C1 | Zest | Video |
| C1 | Zest | Audio |
| C2 | Acme | Video |

C1 works with Acme and Zest, is active on Video and Audio, and both brands advertise on both platforms, so C1 gets 4 rows. C2 works with Acme alone and is active on Video alone, so C2 gets 1. When C1 joins a third platform where both brands advertise, the rule demands 2 new rows. A creator with 5 brands on 4 platforms costs 20 rows, all of which follow from 9 facts about this creator (5 brands, 4 platforms) plus the brand-platform facts that every creator shares. The join dependency `*({creator_id, brand}, {creator_id, platform}, {brand, platform})` states that the table equals the join of its 3 projections. 5NF requires that every join dependency follows from the keys; here it follows from a business rule instead, so the table fails 5NF and splits 3 ways.

![Schema diagram 3](_images/data_modeling_advanced_normalization_diagram_3.png)

```sql
SELECT
  cb.creator_id,
  cb.brand,
  cp.platform
FROM creator_brands AS cb
JOIN creator_platforms AS cp
  ON cb.creator_id = cp.creator_id
JOIN brand_platforms AS bp
  ON bp.brand = cb.brand
    AND bp.platform = cp.platform
```


<br>

### The spurious row

The split works only while the rule holds. Suppose deals are negotiated 1 at a time: C1 promotes Acme on Video only and Zest on Audio only, even though C1 is active on both platforms and both brands advertise on both. The pair tables record C1 with Acme, C1 with Zest, C1 on Video, C1 on Audio, and each brand on each platform. Joining them produces 4 sponsorships where 2 exist.

| creator_id | brand | platform | status |
| --- | --- | --- | --- |
| C1 | Acme | Video | real deal |
| C1 | Acme | Audio | spurious |
| C1 | Zest | Video | spurious |
| C1 | Zest | Audio | real deal |

The 2 extra rows are spurious tuples: facts the join invents because the pieces no longer determine the whole. When each deal is its own agreement, the triple is the fact, the table is already in 5NF, and splitting it destroys information.

> The 5NF decision
>
> - Write the rule in business words: does every combination the 3 pairs allow exist as a real fact?
> - If yes, the triple table is derived data. Store the 3 pair tables and join when a query needs the triple.
> - If no, the triple is a fact of its own. Keep it in 1 table, which already satisfies 5NF.

Most 3-column tables in a warehouse are genuine facts: an order line, a deal, a session. They're already in 5NF and nobody needs to touch them. 5NF matters when a table turns out to be a product of pairs and a pipeline writes 5 rows when a creator with 5 brands joins 1 new platform, an event that changed 1 fact. The query below tests the rule against real data by comparing the rows the pairs predict with the rows stored.

```sql
SELECT
  (
    SELECT
      COUNT(*)
    FROM sponsorships
  ) AS stored_rows,
  COUNT(*) AS predicted_rows
FROM creator_brands AS cb
JOIN creator_platforms AS cp
  ON cb.creator_id = cp.creator_id
JOIN brand_platforms AS bp
  ON bp.brand = cb.brand
    AND bp.platform = cp.platform
```

Equal counts over months of data make the rule credible and the split safe. A stored count below the predicted one means some combinations are deliberately absent, and the triple stays where it is.

**A logistics company stores routes(courier_id, zone_id, vehicle_type). The dispatch rule: a courier may serve a zone with a vehicle type whenever the courier is certified for that vehicle, the courier is assigned to that zone, and the zone permits that vehicle. Which design follows from the rule?**

- **A.** Store courier_vehicles, courier_zones and zone_vehicles, and build routes with a 3-way join whenever a query needs it.
- **B.** Store courier_vehicles and courier_zones only, since a vehicle the courier is certified for is allowed wherever the courier goes.
- **C.** Keep routes as the only table, because a 3-column key can never be decomposed without losing rows on the way back.
- **D.** Store routes and the 3 pair tables together, and run a nightly comparison job that reconciles them when they drift.

<details>
<summary>Solution</summary>

**A.** Store courier_vehicles, courier_zones and zone_vehicles, and build routes with a 3-way join whenever a query needs it.

The rule is a join dependency over 3 pairs, so the triple is derived data and the pairs are the facts.

**Why the others are wrong**

- **B.** This drops the zone permissions. The join would place a courier in a zone on a vehicle that zone forbids.
- **C.** Decomposition loses rows only when the join dependency fails. The dispatch rule guarantees it holds.
- **D.** This stores the same fact twice. The pairs plus the rule already define routes, so the triple is pure redundancy.

</details>


<br>

---

## Strategic Denormalization

Normal forms optimise for writes that touch 1 row and for a table that can never contradict itself. Analytical tables face a different load. A dashboard reads 2 billion order rows and writes nothing. A pipeline rewrites a whole partition once an hour. Under that load a join across 2 billion rows costs minutes of compute per query, while a column copied into the fact table costs a few bytes per row plus 1 refresh step. Denormalization is the decision to pay the second price in place of the first, and strategic means the decision is written down with its conditions.


<br>

### The query that forces the question

A delivery marketplace keeps `orders`, `customers`, `cities` and `regions` in 3NF. Revenue by region, the number on every executive dashboard, needs 3 joins.

```sql
SELECT
  r.region_name,
  SUM(o.order_total) AS revenue
FROM orders AS o
JOIN customers AS c
  ON o.customer_id = c.customer_id
JOIN cities AS ci
  ON c.city_id = ci.city_id
JOIN regions AS r
  ON ci.region_id = r.region_id
WHERE o.order_date >= DATE '2026-10-01'
GROUP BY r.region_name
```

At 2 billion orders and 40 million customers, the first join alone ships the customer table to every worker and probes it 2 billion times. With `region_name` copied onto each order row, the query reads 1 table, groups, and finishes in a fraction of the time. The copy makes each region name appear on every order in it, which is the redundancy 3NF removed. Whether that's a problem depends on 5 questions.

| Question | Copy the column | Keep the join |
| --- | --- | --- |
| How often does the value change? | Yearly, with notice | Daily or without warning |
| How many reads per write? | Thousands | Comparable |
| Who writes the copy? | One pipeline that can rerun | Several apps, by hand |
| How stale may a read be? | Hours | Seconds |
| Can the copy be rebuilt from the source? | Yes, by a query | No, the source is gone |

Region names change about never, the dashboard runs thousands of times a day, the warehouse pipeline owns `orders`, and a region rename that lands in the next hourly refresh hurts nobody. Every answer lands in the copy column. Contrast a `customer_balance` copied onto orders: it changes with every payment, a payment service writes it, and a stale value sends the wrong collections email. Every answer lands in the join column.


<br>

### The rule that keeps the copy safe

A copy is never a source of truth. regions remains the only place a region name is written, and orders carries a derived value that a job can regenerate from regions at any time. When the copy disagrees with the source, the fix is to rerun the job. The failure to design against is an application writing straight into the wide table: now orders says North and regions says Northeast, each has a writer, and the update anomaly from the start of this lesson is back with 2 owners and no referee.

| ✓ Normalize when | ✗ Denormalize when |
| --- | --- |
| • Many services write the table<br><br>• A wrong value costs money immediately<br><br>• Values change often<br><br>• Reads already run fast enough | • One pipeline writes, thousands of queries read<br><br>• A value 1 hour stale is acceptable<br><br>• Values change rarely<br><br>• The join dominates query time |

| ✓ Do | ✗ Don't |
| --- | --- |
| • Name the source table a copied column derives from, in the column documentation<br><br>• Rebuild the copy from the source on a schedule<br><br>• Measure the join cost before copying<br><br>• Keep the normalized tables as the only write path | • Let applications update a copied column<br><br>• Copy a value that changes with every transaction<br><br>• Copy because the join looks long rather than slow<br><br>• Lose the query that regenerates the copy |

**An analytics team wants to copy product_category from products onto a 5 billion row page_views table so category dashboards stop joining. Categories are reassigned in a quarterly catalog review, a nightly pipeline owns page_views, and the dashboards tolerate 1 day of lag. Which assessment is right?**

- **A.** Copy it, and have the catalog service update page_views directly whenever a category changes so the copy never goes stale.
- **B.** Keep the join, because a normal form forbids storing the same category value 5 billion times in 1 table.
- **C.** Copy it, refreshed by the nightly pipeline from products, and document products as the source of the column.
- **D.** Copy it onto the current quarter's rows only, so the catalog review never has to rewrite historical page views.

<details>
<summary>Solution</summary>

**C.** Copy it, refreshed by the nightly pipeline from products, and document products as the source of the column.

Rare changes, 1 pipeline writer, thousands of reads and a tolerated lag of 1 day put every answer in the copy column.

**Why the others are wrong**

- **A.** That gives the copy a second writer, and the service would rewrite billions of rows on every reassignment.
- **B.** Normal forms are a design for write-heavy tables with many writers. The question here is query cost against staleness.
- **D.** A partial copy forks the query logic: older rows still need the join, and every dashboard carries both paths.

</details>


<br>

---

## Denormalization Patterns

Section 3 decided when to denormalize. Each shape below comes with the query that builds it and the event that breaks it.


<br>

### Pattern 1: Copy a column across the join

One attribute from a parent table is copied onto each child row. The region example is this pattern: `region_name` lands on `orders`. The build is a query the pipeline runs on every refresh.

```sql
CREATE TABLE orders_with_region AS
SELECT
    o.order_id,
    o.customer_id,
    o.order_date,
    o.order_total,
    r.region_name
FROM orders o
JOIN customers c
    ON o.customer_id = c.customer_id
JOIN cities ci
    ON c.city_id = ci.city_id
JOIN regions r
    ON ci.region_id = r.region_id
```

It breaks when the parent value changes and the job doesn't rerun. Pick columns that change rarely: names of regions, product categories, plan tiers.


<br>

### Pattern 2: The pre-joined wide table

When several dashboards each need a different handful of columns from the same 4 tables, copying them 1 at a time produces 4 pipelines. The wide table joins once and carries every attribute analysts ask for, 1 row per order.

| order_id | order_date | order_total | customer_name | city_name | region_name | plan_tier |
| --- | --- | --- | --- | --- | --- | --- |
| 9001 | 2026-10-02 | 42.10 | Ana Ruiz | Lisbon | South | Plus |
| 9002 | 2026-10-02 | 18.75 | Tom Ahn | Porto | North | Basic |
| 9003 | 2026-10-03 | 63.00 | Ana Ruiz | Lisbon | South | Plus |

A query touches 1 table. The cost is width: 40 columns, most of them repeated text, across 2 billion rows. Columnar storage reads only the columns a query names, so unused width costs disk rather than query time, which is why wide tables are affordable in a warehouse and painful in a transactional database. The wide table also freezes the join at build time: the value on a row is the value at the last refresh, a feature for reporting and a bug when someone expects the current value.


<br>

### Pattern 3: The stored derived value

A number a query would compute from many rows is computed once and stored on the parent. `order_total` on `orders` is the sum of its lines. `order_count` on `customers` counts that customer's orders. Every read of the number skips the aggregation, and the pipeline overwrites the stored column from a query like this one.

```sql
SELECT
  customer_id,
  COUNT(*) AS order_count,
  MAX(order_date) AS last_order_date
FROM orders
GROUP BY customer_id
```

It breaks the moment a new order lands and the stored count lags by 1. The refresh cadence of the pipeline is the staleness of the number, and the documentation must say so, or a support agent reads 11 orders on the customer page while the order list shows 12.

| Pattern | What is copied | What breaks it | Who repairs it |
| --- | --- | --- | --- |
| Column copy | 1 parent attribute | The parent value changes | Scheduled rebuild from the parent |
| Wide table | Every joined attribute | Any source table changes | Full rebuild of the partition |
| Stored derived value | An aggregate of child rows | A new or changed child row | Recompute from the children |

> **TIP**
>
> Every pattern here is a cache. Keep the regenerating query next to the table definition, because a copy you can't rebuild becomes a liability the day it drifts.


<br>

---

## Putting It All Together

Airbnb's analytics team models host data. Hosts speak several languages and manage several listings. Each listing shows a review count on the search page. A nightly dashboard reports bookings by market region, and the region name lives in a table 3 joins away from the bookings table.

- Host languages and host listings are independent lists, so 4NF puts them in 2 tables and a new language is 1 row.
- A table ( host_id , listing_id , co_host_id ) for shared listings, where a listing has several hosts, each host has 1 co-host per listing and each co-host serves exactly 1 listing, passes 3NF while co_host_id -> listing_id has a left side that is not a key: the BCNF shape of the tutor table.
- The review count on each listing is a stored derived value: computed from reviews on a schedule, with the lag documented for anyone reading it.
- The region name copied onto bookings for the dashboard is a column copy: rarely changed, pipeline-owned, rebuilt from the regions table on every refresh.
- Every one of those copies points back at a normalized table that remains the only place the value is written.


<br>

---

## Key Takeaways

- BCNF fails when a dependency's left side is not a candidate key, even when its right side is a key column; move that dependency into a table where its left side is the key.
- 4NF separates 2 independent lists about the same key into 2 tables, so adding a value is 1 row rather than a product of rows.
- 5NF splits a 3-way table into pairs only when a business rule guarantees the join rebuilds it without spurious rows; most triples are facts and stay whole.
- Denormalize for values that change rarely, are read thousands of times per write, and are owned by 1 pipeline, and keep the normalized tables as the only write path.
- Every copied column, wide table and stored aggregate is a cache with a source, a rebuild query and a documented staleness.

Exercises for this lesson: [_exercises/data_modeling_advanced_normalization.md](_exercises/data_modeling_advanced_normalization.md)
