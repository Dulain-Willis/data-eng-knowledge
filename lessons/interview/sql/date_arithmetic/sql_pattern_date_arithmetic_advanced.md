# Date Arithmetic: Advanced

Forty minutes into the onsite at a vacation-rental marketplace, the interviewer pastes a complaint from the finance channel into the shared doc.
"March revenue on the bookings dashboard is $1.2M above the ledger. The 7-day average for our small markets never dips, even on days they had nothing. And the job behind it reads 3 years of data on every refresh. Bookings has a row per booking, timestamps included. Walk me through it."
She leaves out the part that decides everything: whether a booking earns its revenue on the day it was made or across the nights of the stay, and whose midnight ends a day. The tempting move is to start editing the query on screen. What she is scoring is whether you find the 5 date decisions buried in a single complaint, and say what each one costs the people who read the table.


<br>

### What you will be able to do

Densify a sparse daily series with a bounded date spine, keeping days with no events apart from days with no data

Compute business-day due dates and gaps per market from a calendar table with a running business-day sequence

Split stays and subscriptions across month boundaries and allocate their amounts so the slices sum to the cent

Write date filters the engine can prune on, and show the pruning in the query plan

Choose between UTC and local storage and state what each choice obliges every reader of the table to do


<br>

---

## Filling Gaps with a Date Spine

### How the gap arrives

The request almost never uses the words "missing days." It arrives as "plot daily bookings for each host," "why does day-over-day growth spike every Monday," or "the rolling average looks too high for quiet markets." Underneath each one sits a sparse fact table: a day with no bookings writes no row, and every calculation built on it counts rows while the question counts days. The interviewer is checking whether you name that mismatch before touching the window function.

| Calculation | What it does on sparse rows | What the reader sees |
| --- | --- | --- |
| `AVG(bookings)` | Divides by the days that had bookings | An average inflated by every quiet day |
| `ROWS BETWEEN 6 PRECEDING AND CURRENT ROW` | A frame of 7 rows can span 10 calendar days | A 7-day window wider than its name |
| `LAG(bookings)` | Returns the previous row, not the previous day | Growth measured against 2 days ago |
| Line chart | Draws a straight line from 03-09 to 03-11 | A dead day that vanishes from the picture |


<br>

### Put the dates on the left

The fix changes which side of the join owns the dates. A spine (a row for every calendar day, from a calendar table or a generator) sits on the left, the daily facts LEFT JOIN onto it, and COALESCE turns each unmatched day into a zero. The animation runs it over 4 days of a single market, where 2024-03-10 had no bookings.

https://github.com/user-attachments/assets/29a38052-e5d3-4aa8-ac36-70433967e911

On the 3 sparse rows the average is 11.3 bookings a day; across the 4 dense rows it is 8.5, a 33% overstatement from a single empty day. LAG on 03-11 compares 14 with 9 and reports +56%, when the day before had 0. Every one of those errors goes away once 03-10 has a row.


<br>

### Zero versus unknown

The interviewer waits for this distinction. `COALESCE(bookings, 0)` asserts that nothing happened, and that assertion holds only if the source delivered data for that day. If ingestion failed on 03-10, the true value is unknown: filling 0 publishes a crash that never happened, and leaving the day out publishes an inflated average. The complete answer joins a load-status record into the spine and fills zero only where the pipeline confirms the day landed.

```sql
SELECT
  m.market,
  s.cal_date,
  CASE
    WHEN l.load_date IS NULL THEN NULL
    ELSE COALESCE(d.bookings, 0)
  END AS bookings
FROM dim_market AS m
JOIN dim_calendar AS s
  ON s.cal_date >= m.launch_date
    AND s.cal_date < CURRENT_DATE
LEFT JOIN daily_bookings AS d
  ON d.market = m.market
    AND d.booking_date = s.cal_date
LEFT JOIN pipeline_loads AS l
  ON l.load_date = s.cal_date
    AND l.status = 'complete'
```

> **TIP**
>
> The sentence to say: "A missing row means zero if the load for that day completed and NULL if it did not, so the chart shows a gap instead of a dip." It covers the failed-load case and tells the interviewer what the dashboard's reader sees when it happens.

> Where a spine goes wrong
>
> - Facts on the left and the spine on the right: the LEFT JOIN keeps the facts, and the gaps stay gaps.
> - A WHERE filter on a fact column after the join: the filled rows carry NULL in that column and fail the test, so the gaps come back.
> - A spine that runs through today while today's load is still in flight: the last day shows a false zero.


<br>

### Size the spine before building it

A per-entity spine is a cross join, so its size is entities times days. Plotting 40,000 hosts over 2 years from a single global start date builds 29.2 million rows before any fact joins, most of them for hosts who hadn't listed yet. Bounding each entity by its own active range, from launch to churn, keeps the spine proportional to the data, and it is also the correct answer: a host who joined in June has no zero-booking days in January.

Keep facts sparse in storage and densify at read time, in the final model that feeds the chart. A fact table stored at host-by-day grain pays storage and scan cost for rows that carry no information. For the dates themselves, Postgres has `generate_series`, BigQuery `GENERATE_DATE_ARRAY` with `UNNEST`, Spark `sequence` with `explode`, and other engines a recursive CTE. A persisted calendar table beats all of them, because holiday logic needs one anyway.

- **36,525** — rows in a calendar from 2000 to 2099


<br>

### The follow-up: can you skip the spine?

It comes often. A `RANGE` frame measures the window in calendar time instead of rows, so this rolling sum is correct on sparse rows without any fill:

```sql
SELECT
  booking_date,
  SUM(bookings) OVER (
    ORDER BY booking_date
    RANGE BETWEEN INTERVAL '6' DAY PRECEDING AND CURRENT ROW
  ) AS bookings_7d
FROM daily_bookings
```

Then name what it leaves broken. The output still has no row for 03-10, so the chart still skips it, and a 7-day average needs a fixed denominator of 7 rather than `AVG` over whatever rows land in the frame. Support varies too: Postgres accepts interval offsets in `RANGE` from version 11, while BigQuery requires a numeric `ORDER BY` such as `UNIX_DATE(booking_date)`. In the room, say that the frame fixes the window and the spine fixes the output, and a dashboard usually needs both.


<br>

---

## Holiday-Aware Calendar Tables

The question carries a single word that changes the tooling: business. "Host payouts release 2 business days after check-in; find the late ones." "Support replies within 3 business days; report the breach rate by country." `DATE_ADD` has never heard of July 4. Once a rule depends on the status of a day (holiday, weekend, trading day, office closure), that status is data, and data belongs in a table someone maintains.


<br>

### Why weekday arithmetic fails first

The first attempt usually skips Saturdays and Sundays with `EXTRACT(DOW ...)`. It survives until the first holiday, then fails across markets, because weekends are local too: the UAE moved its weekend from Friday and Saturday to Saturday and Sunday in January 2022. Rules hardcoded in `CASE` expressions also get copied, and 2 copies edited at different times are how 2 dashboards end up disagreeing about the same SLA.

| ✓ Weekday arithmetic in the query | ✗ Calendar table |
| --- | --- |
| • Knows weekends, never holidays<br><br>• A single weekend definition for every market<br><br>• Copied into each query that needs it<br><br>• N business days later needs a loop or a guess | • Every weekend and holiday stored as a row, observed dates included<br><br>• A row per market per date, so markets never collide<br><br>• A single owner and a single update, so every query agrees<br><br>• N business days later becomes an equality join |


<br>

### One row per market per date

The grain is a row per market per date, so a holiday in Lisbon and a holiday in Austin never collide. Each row carries whether the day is a business day, the holiday's name, and the column every due-date calculation reads: `business_day_seq`, a running count of business days that holds its value across weekends and holidays.

| market | cal_date | is_business_day | business_day_seq | holiday_name |
| --- | --- | --- | --- | --- |
| US | 2024-07-03 | true | 1350 |  |
| US | 2024-07-04 | false | 1350 | Independence Day |
| US | 2024-07-05 | true | 1351 |  |
| US | 2024-07-06 | false | 1351 |  |
| US | 2024-07-07 | false | 1351 |  |
| US | 2024-07-08 | true | 1352 |  |

Observed dates belong in the rows too, and they are where calendars split. July 4, 2026 falls on a Saturday, so federal offices close on Friday, July 3, and so do companies that follow the federal schedule. The Federal Reserve stays open that Friday, so banks process payouts over Fedwire and ACH as on any other business day. The staff calendar marks July 3 as a non-business day while the bank calendar keeps it a business day, which is why payouts and support SLAs cannot read the same rows.


<br>

### Business-day math becomes a join

```sql
-- Built once, when the calendar loads
SELECT market, cal_date, is_business_day, holiday_name,
       SUM(CASE WHEN is_business_day THEN 1 ELSE 0 END)
         OVER (PARTITION BY market ORDER BY cal_date
               ROWS UNBOUNDED PRECEDING) AS business_day_seq
FROM calendar_base;

-- Payout due 2 business days after check-in, per market
SELECT b.booking_id, b.check_in, due.cal_date AS payout_due
FROM bookings b
JOIN dim_business_calendar ci
  ON ci.market = b.market
 AND ci.cal_date = b.check_in
JOIN dim_business_calendar due
  ON due.market = b.market
 AND due.business_day_seq = ci.business_day_seq + 2
 AND due.is_business_day;
```

Walk the interviewer through a row. A check-in on July 3 sits at sequence 1350, so the payout lands on the business day numbered 1352, which is July 8. A Saturday check-in on July 6 inherits 1351 from Friday and lands at 1353, on July 9, the same day as a Friday check-in. That inheritance is a convention, and stating it before you are asked ("a weekend start counts from the last business day") is what a strong answer does. Business days between 2 dates is a subtraction of sequences, so an SLA breach becomes `closed.business_day_seq - opened.business_day_seq > 3`.

The trap answer walks forward a day at a time with a recursive CTE, checking each day against a holiday list. It returns correct dates and does at least N iterations per row, so 10 million bookings at a 2-day offset run 20 million probes, and a 30-day SLA window runs 300 million. The sequence column replaces the loop with a single equality join, and the interviewer hears the difference between computing business days and looking them up.

Expect the cross-border probe: a US guest books a Lisbon property owned by a host whose bank is in Portugal. The payout follows the host's banking market; the guest's support SLA follows the support team's calendar. Which market goes into the join key is a decision, and the interviewer wants to hear it made out loud.


<br>

### Somebody owns this table

Holidays are set by governments and companies on their own schedules, so the calendar is reference data. It needs an owner and a load process, and someone has to set a policy for history. When a holiday is added after the fact, are last year's breach rates recomputed or frozen? Recomputing makes old reports disagree with what was published; freezing means versioning the calendar with effective dates. Either is defensible. Leaving it undecided is how finance and support end up quoting different breach rates for the same quarter.


> **TIP**
>
> Most companies run 2 calendars: the bank calendar that governs when money moves and the company calendar that governs when staff work. Payouts follow the first, support SLAs the second. Asking which one the rule means is a question interviewers remember.


<br>

---

## Splitting Date Ranges by Month

This question arrives without the word range. "Revenue is recognized per night stayed; give me monthly revenue." "Subscriptions start on any day of the month; what is MRR by month?" "Leave requests have a first and last day; how many fall in each payroll month?" Every row has a start and an end, and the answer buckets by month. Grouping by `DATE_TRUNC('month', check_in)` books the whole stay to the month it began, which is how a revenue dashboard drifts above the ledger without a single wrong row.


<br>

### Exploding versus joining

| ✓ Explode to nights, then group | ✗ Overlap join to a month table |
| --- | --- |
| • A row per night via generate_series, or sequence plus UNNEST<br><br>• Any bucket afterwards: month, fiscal period, ISO week<br><br>• Cost is ranges times length: 30M stays at 4 nights is 120M rows<br><br>• Breaks on long ranges: 2M annual plans become 730M rows | • A row per range per month it touches<br><br>• Clipping arithmetic with GREATEST and LEAST<br><br>• Output stays close to input: most stays touch 1 or 2 months<br><br>• Needs a small table of months, which the calendar supplies |

```sql
-- Explode (Trino): a row per night, then any bucket
SELECT
  DATE_TRUNC('month', n.night) AS month_start,
  COUNT(*) AS nights
FROM stays AS s
CROSS JOIN UNNEST(SEQUENCE(s.check_in, s.check_out - INTERVAL '1' DAY)) AS n(night)
GROUP BY 1
```

Both work, and the interviewer grades whether you name the cost. Explode when ranges are short and the next step needs daily grain anyway. Use the overlap join when ranges run long, or when the output only needs months.


<br>

### The overlap join, row by row

A range overlaps a month when it starts before the month ends and ends after the month starts. With both sides half-open (check-out is the morning the guest leaves, so that night is not stayed), the test is 2 strict comparisons, and the nights in each month are the clipped end minus the clipped start.

https://github.com/user-attachments/assets/6e01841d-690b-48c2-8e5b-3dae3c865beb

Stay 102 runs from March 29 to the morning of April 3 and passes both comparisons against both months, so it becomes 2 rows: 3 nights in March and 2 in April. Its $600 becomes $360 and $240, where grouping by check-in month put all $600 in March. The slices add back to its 5 nights, and that check is worth saying aloud: the slices of a range must sum to the range's length. A stay from March 4 to March 9 fails April's first comparison, since April 1 is not before March 9, and stays a single row. A stay from February 27 to April 2 passes the same 2 comparisons in 3 months. February gets 3 nights of it, because 2024 has a February 29.


<br>

### The convention to say aloud

Hotel nights are half-open by nature. Subscriptions often are not: a plan "ending 2024-03-31" usually includes the 31st. Feed an inclusive end into the same arithmetic and every range loses its last day, a 1-day error per subscription that adds up to a visible MRR gap. Do the conversion to half-open once with `end_date + INTERVAL '1' DAY` where the data enters, then tell the interviewer you did.


<br>

### Allocating the money to the cent

Revenue per slice is amount times nights over total nights, and rounding each slice on its own leaks cents: $100.00 across 3 single-night slices rounds to 33.33 in each slice and loses a cent. Taking differences of rounded cumulative amounts makes the slices sum to the original exactly.

```sql
WITH slices AS (
  SELECT
    s.stay_id,
    CAST(s.amount AS DECIMAL(18, 2)) AS amount,
    m.month_start,
    DATE_DIFF(
      'day',
      GREATEST(s.check_in, m.month_start),
      LEAST(s.check_out, m.next_month)
    ) AS nights,
    DATE_DIFF('day', s.check_in, s.check_out) AS total_nights
  FROM stays AS s
  JOIN months AS m
    ON m.month_start < s.check_out
      AND m.next_month > s.check_in
),
running AS (
  SELECT
    *,
    SUM(nights) OVER (
      PARTITION BY stay_id
      ORDER BY month_start
    ) AS cum_nights
  FROM slices
)

SELECT
  stay_id,
  month_start,
  nights,
  ROUND(amount * cum_nights / total_nights, 2) - ROUND(
    amount * (
      cum_nights - nights
    ) / total_nights,
    2
  ) AS revenue
FROM running
```

For the $100.00 case, the running totals after each night round to 33.33, then 66.67, then 100.00, so the slices are 33.33, 33.34 and 33.33. Finance reconciles to the cent, and an allocation that drifts a cent per booking turns into a reconciliation ticket every month.

The usual follow-up swaps the bucket: "now by fiscal period," or "now by ISO week." Nothing in the join is specific to months. Any table of half-open periods with a start and a next start works, which is the argument for drawing the periods from the calendar table instead of generating months inline in each query.

> What breaks next
>
> - Fan-out: any SUM(amount) after this join counts a 3-month stay 3 times. Sum the allocated revenue, never the original amount.
> - Open ranges: a stay or plan with no end needs COALESCE to the reporting period's end. Make that choice on purpose and state it.
> - Large range tables on both sides: an inequality join between them has no hash key. Keep one side a small period table that broadcasts.
> - Policy: if finance recognizes revenue at booking, splitting by night is wrong. Ask for the recognition rule first.


<br>

---

## Partition Pruning on Date Columns

The pruning question rarely says partition. It shows up as "this dashboard costs $40 a refresh," "this job gets slower every month," or a pull request whose filter returns the right rows. The tell is a query whose cost grows with the table's history while its answer needs a week of it. The interviewer wants you to explain the mechanism before you propose the rewrite, then show the evidence.

- **$6.25** — per TiB scanned, BigQuery on-demand


<br>

### What the engine decides before reading

Pruning is decided at planning time, before a byte of data is read. The planner compares the `WHERE` clause with what it already knows about each partition. That's either the value in a directory name such as `dt=2024-03-14` or the minimum and maximum a file's metadata records for the column. A partition whose values cannot satisfy the predicate is skipped. The form every planner can compare is the bare partition column against a constant.

Wrap the column in a function and the outcome becomes engine-specific. Spark evaluates deterministic expressions against directory partition values, so `YEAR(dt) = 2024` still prunes there. On Postgres declarative partitioning and BigQuery a transformed column can cost the pruning, and so it can under min/max pruning over Snowflake micro-partitions or Parquet and Iceberg file statistics, because the planner would need to know the function preserves order. The answer that holds on every engine keeps the column bare and moves the arithmetic to the constant side.

| Filter on a table partitioned by booking_date | Prunes portably? | Why |
| --- | --- | --- |
| `booking_date >= DATE '2024-03-01' AND booking_date < DATE '2024-04-01'` | Yes | Bare column against constants |
| `DATE_TRUNC('month', booking_date) = DATE '2024-03-01'` | No | A function wraps the column |
| `CAST(booking_date AS VARCHAR) LIKE '2024-03%'` | No | Cast plus pattern match |
| `booking_date >= CURRENT_DATE - INTERVAL '7' DAY` | Yes, in most engines | Folded to a constant at planning |
| `booking_date >= (SELECT MAX(loaded_date) FROM loads)` | Engine-dependent | Value unknown until the subquery runs |
| `created_at_utc >= TIMESTAMP '2024-03-01 00:00:00'` | No | Filters a column the table is not partitioned by |

The last row is the one people miss: a table partitioned by `booking_date` gets nothing from a filter on `created_at_utc`, unless the table format derives its partitions from that column, as Iceberg hidden partitioning does with `days(created_at_utc)`.


<br>

### The Rewrite

```sql
-- Reads every partition on most engines: the column is transformed
SELECT market, SUM(amount) AS revenue
FROM bookings
WHERE DATE_TRUNC('month', booking_date) = DATE '2024-03-01'
GROUP BY market;

-- Reads 31 daily partitions: the arithmetic moved to the constants
SELECT market, SUM(amount) AS revenue
FROM bookings
WHERE booking_date >= DATE '2024-03-01'
  AND booking_date <  DATE '2024-04-01'
GROUP BY market;
```

Both return identical rows. That is why this bug survives code review: the result is right, and only the bill shows the difference.


<br>

### The incremental model that scans everything

The most expensive case is in incremental pipelines. A dbt model filtered with `WHERE booking_date >= (SELECT MAX(booking_date) FROM target)` looks incremental, but its bound is a subquery, and an engine that can't resolve it before planning reads the entire source on every run. Resolve the bound first and pass it in as a literal. The orchestrator's data interval works, and so does a script variable or any value rendered into the SQL. Spark 3.0 added dynamic partition pruning for the related join case, where the wanted dates come from a filtered dimension table, but a portable pipeline does not depend on it.


<br>

### Prove it from the plan

"How would you know?" is the follow-up, and "the query got faster" is the answer that loses the point. Every engine shows pruning directly. Spark's physical plan lists `PartitionFilters` on the scan node, and an empty list means a full read. A BigQuery dry run reports bytes processed before anything runs. Snowflake's query profile shows partitions scanned against partitions total. Postgres `EXPLAIN` lists only the partitions that survived.

> **TIP**
>
> In the room, the order is: name the mechanism (the planner compares predicates with partition values), give the rewrite (bare column, constants on the other side), then say where you would confirm it in the plan. Without that third step, the rewrite is a claim you have not checked.


<br>

### Guardrails beyond one query

Fixing a query helps a dashboard. The organizational answer is a guardrail: BigQuery's `require_partition_filter` table option rejects any query without a filter on the partition column, which turns an accidental full scan into an error message. Pair it with an alert on bytes scanned per query, since a filter that satisfies the rule can still ask for years of partitions. Then choose the partition column by what readers filter on: a table partitioned by ingestion date serves the pipeline, while analysts filtering on booking date get no pruning at all.

Granularity is the other half of the design. Daily partitions over 3 years make 1,095; hourly makes 26,280, and at modest volume most of those hold files far below the 128MB to 1GB that columnar readers scan efficiently. Partition by day and sort or cluster by the timestamp inside each partition: the day prunes, and file statistics on the timestamp narrow further within it.


<br>

---

## Storing UTC vs Local Time

This question often arrives as a design prompt with no time zones in it: "design the bookings table," while the interviewer watches what type you give `created_at`. Or it arrives as a symptom: "a booking made at 11:30pm in Honolulu shows up on tomorrow's report," or "daily numbers shifted when someone changed the warehouse session zone." The storage choice is made once, and every reader of the table inherits it.


<br>

### What each choice commits readers to

| ✓ Store the UTC instant | ✗ Store local wall-clock time |
| --- | --- |
| • Ordering and durations across regions are exact<br><br>• Every local-day question needs a conversion<br><br>• Every reader must know which zone defines the day<br><br>• Daylight saving is handled by the conversion, never by the data | • A local day is a plain DATE cast for a single market<br><br>• Events in different zones cannot be ordered against each other<br><br>• 01:30 happens twice on the night clocks fall back<br><br>• Converting to any other zone needs a zone nobody stored |

Put it the way the interviewer wants to hear it: UTC storage moves work onto the reader, and local storage makes some questions impossible to answer at all. Work can be paid for; lost information can't be recovered, which is why the UTC instant is the default.


<br>

### Instant, zone and local date

The complete answer stores the instant, in a type that means an absolute point in time, and the IANA zone of whatever defines the business day, here the property's `America/Los_Angeles`, since the guest's zone and headquarters' zone answer different questions. Where readers filter by local day constantly, it also stores a `local_date` column written at load time, so nobody repeats the conversion and the partition key can match it. The type names differ by engine, and naming the right one is part of the answer:

| Engine | Absolute instant | Wall-clock, no zone |
| --- | --- | --- |
| Postgres | `TIMESTAMPTZ` (stored as UTC) | `TIMESTAMP` |
| BigQuery | `TIMESTAMP` | `DATETIME` |
| Snowflake | `TIMESTAMP_TZ` or `TIMESTAMP_LTZ` | `TIMESTAMP_NTZ` |
| Spark | `TIMESTAMP` (shown in the session zone) | `TIMESTAMP_NTZ` (3.4 and later) |


<br>

### A local day expressed in UTC

Reading a local day out of UTC storage converts the day's boundaries, never each row. The Los Angeles day of 2024-03-14 runs from 07:00 UTC that morning to 07:00 UTC the next, because clocks sprang forward on March 10 and the offset is now 7 hours. Bounds on the bare timestamp keep the filter in the form the planner can prune on.

https://github.com/user-attachments/assets/289d6b3f-3605-4b9d-944f-bb6c6ac1402c

Grouped by UTC date, March 14 would hold bookings 1 through 3 for $70. The Los Angeles day holds bookings 2 through 4 for $90: the same count, different bookings, $20 apart. Those bounds also move twice a year, from 08:00 UTC before March 10 to 07:00 after, so they belong in the calendar table as `day_start_utc` and `day_end_utc` per zone and date, computed once, rather than as an offset hardcoded in each query.


<br>

### Storage zone and partition date

The zone choice decides which partitions a local query touches. Partition by UTC date and a single Los Angeles day spans 2 partitions, so the query needs the timestamp bounds plus both partition dates when the partition column is separate from the timestamp. Partition by local date and a per-market day prunes to 1, but a global "last hour" query has to read every local date that hour touches. Offsets run from UTC-12 to UTC+14, so a single instant can sit on 3 calendar dates at once. Partition on whichever date most readers filter on, and write down which one you picked.


<br>

### Future times break the rule

The UTC default has a single exception, and naming it is a strong signal. A check-in scheduled for 15:00 local time next summer is a promise about a local clock reading. Convert it to UTC today and the conversion freezes today's daylight-saving rules; if a government changes them before the date, the stored instant points an hour off. Mexico abolished daylight saving time across most of the country in October 2022, so summer 2023 appointments converted under the old rules landed at the wrong hour. Store future events as local wall-clock time plus zone, and convert when the moment arrives.

> **TIP**
>
> Say it in one sentence: "I store the instant in UTC with the property's zone beside it, so any reader can rebuild the local day, and I write local_date at load time because most of our filters use it." That gives the default and its reason, and concedes the column most readers will want.



| ✓ Do | ✗ Don't |
| --- | --- |
| • Densify at read time with a spine bounded to each entity's active dates<br><br>• Fill zero only for days the source confirms it loaded; leave the rest NULL<br><br>• Keep each market's business days and holidays in a single owned calendar table<br><br>• Convert ranges to half-open once, split by overlap join, and allocate by cumulative rounding<br><br>• Store instants in UTC with the zone that defines the day; store future appointments as local time | • Wrap the partition column in a function and trust the result rows to reveal the cost<br><br>• Group a range by its start month when the question counts nights or days<br><br>• Hardcode a UTC offset that daylight saving changes twice a year<br><br>• Bound an incremental load with a subquery the planner can't resolve before reading |


<br>

---

## Putting It All Together

The finance complaint from the opening, worked end to end: the vacation-rental marketplace's March revenue dashboard runs $1.2M above the ledger, its quiet markets show a 7-day average that never dips, and every refresh reads 3 years of bookings. Each symptom traces back to one of the date decisions this lesson covers, and fixing them in the right order is the answer the interviewer was waiting for.

- Revenue was grouped by check-in month; splitting each stay by night with the overlap join and cumulative rounding moves the April nights of late-March stays out of March and matches the ledger to the cent.
- The quiet markets need a spine bounded at each market's launch, with NULL for the days ingestion failed, so the dashboard shows gaps instead of dips and the average stops overstating.
- Day boundaries were drawn in UTC; recomputing them per property zone from day_start_utc and day_end_utc moves late-evening Pacific bookings onto the day they happened locally.
- The refresh filtered on DATE_TRUNC('month', booking_date); rewriting it as a bare range cuts the scan from 1,095 daily partitions to 31, and the plan's partition filters confirm it.
- Host payout timing on the same dashboard reads from the per-market bank calendar, so Memorial Day on May 25, 2026 pushes payouts to the next business day without a code change, while July 3, 2026 moves support due dates and leaves payouts alone.


<br>

---

## Key Takeaways

- A sparse table counts rows; a spine makes it count days. Fill zero only where the source confirms the day loaded, and NULL everywhere else.
- Business-day rules are data: a per-market calendar with a running business-day sequence turns N business days later into a single join.
- Split ranges with a half-open overlap join, check the slices sum to the range, and allocate money by differences of cumulative rounding.
- Pruning needs the bare partition column against constants known at planning. Prove it from the plan, never from the result.
- Store instants in UTC with the zone that defines the day, local wall-clock for future appointments, and say which zone each report means.
