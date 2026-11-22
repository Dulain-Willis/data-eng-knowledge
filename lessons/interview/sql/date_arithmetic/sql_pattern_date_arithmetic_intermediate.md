# Date Arithmetic: Intermediate

Round two at a subscription company. The interviewer drops a schema into the shared doc: `orders(order_id, region, order_ts, amount)` and `regions(region, tz_name)`.
"Finance closes the books by fiscal quarter, and our year starts July 1. I need revenue per region per quarter for FY2025. Go."
She stops typing. Nobody has said whether `order_ts` holds UTC or each store's wall-clock time. That alone decides whether a Los Angeles order rung up at 7 p.m. on June 30 counts in FY2025 or FY2026. Within a minute most candidates have written `DATE_TRUNC('quarter', order_ts)`, which buckets January-start quarters on the UTC clock and is wrong twice.
What she is scoring is whether you settle which calendar and which clock before any date function goes on the page.


<br>

### What you will be able to do

Map any date to its fiscal period or ISO week-year, and ask the questions that pin the calendar down

Convert stored timestamps to a region's local day with AT TIME ZONE, in the right direction and at the right step

Explain what 23-hour and 25-hour days do to hourly charts and daily totals, how they skew durations, and give the fix

Predict what adding a month or a year does to January 31 and February 29, and write schedules that do not drift

Translate date math from Postgres to BigQuery or Snowflake and on to Spark, naming the calls whose results change


<br>

---

## Fiscal Calendars and ISO Weeks

This part of the question rarely announces itself. It arrives as "Q3 bookings", "last week's signups" or "revenue this year", and each phrase names a period whose edges the company chose. Microsoft's year begins in July, the US federal government's in October, and Apple's ends on the last Saturday of September. Before any `DATE_TRUNC`, the interviewer is listening for the question that fixes which calendar the business counts by.


<br>

### 4 calendars behind one word

| Calendar | Year begins | How a date finds its period | On the record |
| --- | --- | --- | --- |
| Calendar year | January 1 | Extract the year and quarter directly | Most companies |
| Month-offset fiscal year | First day of a chosen month | Shift by whole months, then extract | Microsoft (July 1), US federal government (October 1) |
| 52/53-week fiscal year | A weekday near a month end | Look up a published boundary in a calendar table | Apple (last Saturday of September), Target (Saturday nearest January 31) |
| ISO 8601 week-year | Monday of the week holding the first Thursday | ISO week paired with ISO year | Week numbers in Postgres and Spark |


<br>

### Mapping a date to a month-offset year

For a year that begins on the first of a month, shift each date forward by the number of months from the fiscal start to the next January, then read the year and quarter off the shifted date. A July year needs 6 months: July lands on January, so fiscal Q1 lines up with calendar Q1 of the shifted value. Whole-month shifts are safe here because they always land in the right month even when the day gets clipped (August 31 becomes February 28), and only the month and year feed the period.

```sql
-- order_date is the order's local date, derived from order_ts
-- as the next section shows
-- Fiscal year begins July 1 and is named by the year it ends
SELECT
  region,
  EXTRACT(YEAR FROM order_date + INTERVAL '6' MONTH) AS fiscal_year,
  EXTRACT(QUARTER FROM order_date + INTERVAL '6' MONTH) AS fiscal_quarter,
  DATE_TRUNC('quarter', order_date + INTERVAL '6' MONTH) - INTERVAL '6' MONTH AS quarter_start,
  SUM(amount) AS revenue
FROM orders
WHERE order_date >= DATE '2024-07-01' -- FY2025 only
  AND order_date < DATE '2025-07-01'
GROUP BY 1, 2, 3, 4
ORDER BY 1, 2, 3
```

The `quarter_start` column answers the follow-up that usually comes next, "now give me fiscal quarter to date". Truncating the shifted date and shifting it back yields the real first day of the fiscal quarter, 2025-01-01 for anything in fiscal Q3, and that value works in a range filter like any other date. The animation below runs the period mapping on the 4 dates that decide most fiscal reports.

https://github.com/user-attachments/assets/7aba7e0f-a102-4dec-ba93-63543f664412

Order 1 on 2024-06-30 shifts to 2024-12-30 and closes FY2024 Q4; order 2, a day later, shifts to 2025-01-01 and opens FY2025 Q1. Order 3 on 2025-01-02 sits in calendar Q1 and fiscal Q3, which is the row a `DATE_TRUNC('quarter', ...)` answer files under the wrong quarter. Order 4 on 2025-06-30 is the last day of FY2025.

> **TIP**
>
> Ask how the year is named before writing the shift. Microsoft and the US government name a fiscal year by the calendar year it ends in, so July 2024 to June 2025 is FY2025, which adding 6 months produces. A company that names by the start year needs the date shifted back 6 months instead, and the 2 labels differ by 1 on every row.


<br>

### Week-based years need a lookup table

A 52/53-week year has boundaries that move. Apple's year ends on the last Saturday of September, so most years run 52 weeks and every fifth or sixth year runs 53, as fiscal 2023 did. No month shift reproduces that, and a 4-5-4 retail calendar adds week-based months on top. The answer is a calendar table keyed by date that carries `fiscal_year` plus `fiscal_quarter` and `fiscal_week`. Build it from the dates finance publishes and join it on the order's date. Say the split out loud: arithmetic for a month-aligned year, a lookup for anything week-based, because there the boundary is a published date rather than a rule.


<br>

### ISO weeks and the year they belong to

ISO 8601 weeks run Monday to Sunday, and week 1 is the week holding the year's first Thursday. That rule lets the week-year slide away from the calendar year by up to 3 days at either end, and it gives some years 53 weeks, 2026 among them.

| Date | Weekday | Calendar year | ISO year | ISO week |
| --- | --- | --- | --- | --- |
| 2024-12-29 | Sunday | 2024 | 2024 | 52 |
| 2024-12-30 | Monday | 2024 | 2025 | 1 |
| 2024-12-31 | Tuesday | 2024 | 2025 | 1 |
| 2026-12-31 | Thursday | 2026 | 2026 | 53 |
| 2027-01-03 | Sunday | 2027 | 2026 | 53 |
| 2027-01-04 | Monday | 2027 | 2027 | 1 |

The usual bug comes from pairing the calendar year with the ISO week. `EXTRACT(YEAR ...)` next to an ISO week number turns December 30 and 31, 2024 into the key (2024, 1), the same key as January 1 to 7, 2024, so a weekly report adds 2 days of late-December revenue into a week from 12 months earlier. Pair the ISO week with the ISO year, or group by the Monday that starts each week and skip both numbers: a week-start date is unique per week, so it never collides as a join key or a chart label. Which weekday a given engine treats as the start is the part to confirm against the engine in front of you.

> Pin the calendar before the SQL
>
> - Does the fiscal year begin on the 1st of a month, or follow a 52/53-week pattern?
> - Is FY2025 the year that ends in 2025 or the one that begins in it?
> - Do weeks start on Monday (ISO) or Sunday, and who reads the week numbers?
> - Does a week straddling New Year count in the old year or the new one, or is it split at midnight?


<br>

---

## Converting With AT TIME ZONE

The time zone part arrives as "daily revenue for the Tokyo office", "orders by hour of the day" or "why doesn't our month-end match finance's?" Each needs the same fact: a single instant has one UTC value and a different local date and hour in every zone, so the day a row belongs to depends on whose clock reads it.

| Order | Stored instant (UTC) | Los Angeles wall clock | Tokyo wall clock |
| --- | --- | --- | --- |
| A | 2024-03-01 03:30 | 2024-02-29 19:30 (UTC-8) | 2024-03-01 12:30 (UTC+9) |
| B | 2024-02-29 22:00 | 2024-02-29 14:00 (UTC-8) | 2024-03-01 07:00 (UTC+9) |

Order A is March revenue in UTC and February revenue in Los Angeles. Order B is February revenue in UTC and March revenue in Tokyo. A month-end report that buckets on the stored value puts each in the wrong month for one region, and the same shift at June 30 moves orders across a fiscal year: an order stored at 2025-07-01 02:00 UTC was rung up at 19:00 on June 30 in Los Angeles, inside FY2025 rather than FY2026.


<br>

### Which way the conversion goes

In Postgres and Redshift, `AT TIME ZONE` runs in opposite directions depending on its input. Applied to a TIMESTAMP WITH TIME ZONE, an instant, it returns a TIMESTAMP with no zone that holds the wall clock in the named zone. Applied to a plain TIMESTAMP, it reads the value as wall-clock time in the named zone and returns the instant. The keyword stays the same and the input type picks the direction.

```sql
-- order_ts is TIMESTAMP WITH TIME ZONE: one AT gives the local wall clock
SELECT o.order_id,
       o.order_ts AT TIME ZONE r.tz_name AS local_ts
FROM orders o
JOIN regions r ON r.region = o.region;

-- order_ts is a plain TIMESTAMP holding UTC values:
-- pin it to UTC first (giving an instant), then convert to local
SELECT o.order_id,
       (o.order_ts AT TIME ZONE 'UTC') AT TIME ZONE r.tz_name AS local_ts
FROM orders o
JOIN regions r ON r.region = o.region;
```

The bug shows up in the second case written with a single `AT TIME ZONE`. The plain value 2024-03-01 03:30 is read as 03:30 in Los Angeles, which is the instant 11:30 UTC, so the conversion moves order A 8 hours later instead of 8 hours earlier. The result sits 16 hours from the right answer, and an error of exactly twice a zone's offset is the signature of a conversion run backwards. Ask the question that prevents it before writing anything: is `order_ts` an instant or a wall-clock reading, and in which zone?


<br>

### Convert first, then bucket

Order of operations decides the answer. Truncating to the day in UTC and converting the label afterwards relabels a UTC day: the bucket still runs midnight to midnight UTC, which in Los Angeles is 16:00 to 16:00 before the clocks change on March 10 and 17:00 to 17:00 after. A BI tool's time zone setting does the same, changing the labels it draws and never the groups the warehouse computed. The local day exists only after conversion, so convert first and only then cast or truncate before grouping.

```sql
WITH local_orders AS (
  SELECT
    r.region,
    CAST(o.order_ts AT TIME ZONE r.tz_name AS DATE) AS local_day,
    o.amount
  FROM orders AS o
  JOIN regions AS r
    ON r.region = o.region
  WHERE o.order_ts >= TIMESTAMP WITH TIME ZONE '2024-02-29 00:00+00'
    AND o.order_ts < TIMESTAMP WITH TIME ZONE '2024-04-02 00:00+00'
)

SELECT
  region,
  local_day,
  SUM(amount) AS revenue
FROM local_orders
WHERE local_day >= DATE '2024-03-01'
  AND local_day < DATE '2024-04-01'
GROUP BY region, local_day
```

The padded range on the stored column keeps the scan bounded, since no zone sits more than 14 hours from UTC, and the exact filter runs on the converted date. Writing the conversion once, in the CTE, means the `GROUP BY` and the filter agree about which day a row is on, and so does any window function downstream.


<br>

### Zone names, not offsets

| ✓ Fixed offset ('-08:00') | ✗ IANA zone name ('America/Los_Angeles') |
| --- | --- |
| • Right for Los Angeles only until 2024-03-10, when its clock moves to UTC-7<br><br>• Off by 1 hour for around 8 months of every year, with no error raised<br><br>• In Postgres AT TIME ZONE, 'UTC+8' follows POSIX signs and means 8 hours behind UTC | • Carries every DST transition and historical rule change<br><br>• Converts each row with the offset in force at that instant<br><br>• Lives in a tz_name column on the regions table, one value per region |

One more question decides the join: whose clock? A store's sales belong to the store's zone and a customer's activity streak to the customer's zone. A company-wide daily total needs one zone for everyone, usually headquarters or UTC. Each is a different source for `tz_name`, and stating which you picked is half the answer.

> **TIP**
>
> Name the column's type and the conversion point in one sentence: "order_ts is an instant, so I convert once to the region's zone in the source CTE and bucket on the local date." That sentence answers the 2 follow-ups most candidates fumble.


<br>

---

## DST and the Missing Hour

Daylight saving arrives disguised as an anomaly: "Sunday revenue jumped in November and nothing launched", or "the hourly chart has a hole at 2 a.m. every March". Both come from the same fact. In a zone that observes daylight saving, 2 local days a year are not 24 hours long, and any math that assumes a fixed-length day or a unique hour label breaks on those days.

- **23 hours** — in Los Angeles on 2024-03-10
- **25 hours** — in Los Angeles on 2024-11-03
- **4.2%** — 1 hour in 24 gained or lost on a DST day


<br>

### The hour that happens twice

| Instant (UTC) | Los Angeles wall clock | Offset |
| --- | --- | --- |
| 2024-11-03 08:00 | 01:00 | UTC-7 (PDT) |
| 2024-11-03 08:30 | 01:30 | UTC-7 (PDT) |
| 2024-11-03 09:00 | 01:00 | UTC-8 (PST) |
| 2024-11-03 09:30 | 01:30 | UTC-8 (PST) |
| 2024-11-03 10:00 | 02:00 | UTC-8 (PST) |

Group that day by local hour and the 01:00 bucket holds 2 real hours of orders, so it reads as a spike. Group the March day the same way and the 02:00 bucket never appears, because 02:00 to 02:59 did not happen on any clock in the zone. The daily total moves too: the long day carries an extra hour of sales into a day-over-day comparison, which is the November jump with nothing launched.

A table that stores naive local time loses information on these days. The wall-clock value 2024-11-03 01:30 names 2 instants an hour apart, and 2024-03-10 02:30 names none. Each engine resolves them by its own rule, picking one of the 2 instants or pushing the missing time forward, so no query can recover what the writer threw away.


<br>

### Calendar days versus elapsed hours

Interval math splits into 2 kinds that agree on every other day of the year. In Postgres, adding `INTERVAL '1 day'` to a `TIMESTAMP WITH TIME ZONE` keeps the wall-clock time in the session's zone, while `INTERVAL '24 hours'` adds 24 elapsed hours. Across the spring change they land an hour apart.

```sql
SET TIME ZONE 'America/Los_Angeles';

SELECT TIMESTAMPTZ '2024-03-09 12:00' + INTERVAL '1 day'    AS plus_1_day,
       TIMESTAMPTZ '2024-03-09 12:00' + INTERVAL '24 hours' AS plus_24_hours;

-- plus_1_day:    2024-03-10 12:00:00-07  (23 hours elapsed)
-- plus_24_hours: 2024-03-10 13:00:00-07  (24 hours elapsed)
```

Durations go wrong the same way when computed from naive local values. A support ticket opened at 00:30 and closed at 05:30 local time on 2024-03-10 shows 5 hours, but 4 hours passed; the same ticket on 2024-11-03 shows 5 hours when 6 passed. Any SLA threshold near those values gets the wrong verdict twice a year. Subtract instants instead, whether `TIMESTAMP WITH TIME ZONE` values or UTC, and the elapsed time comes out right every day.

```sql
-- Real length of each local day in one zone (Postgres)
SELECT
  CAST(d AS DATE) AS local_day,
  EXTRACT(EPOCH FROM (
    d + INTERVAL '1 day'
  ) AT TIME ZONE 'America/Los_Angeles' - d AT TIME ZONE 'America/Los_Angeles') / 3600 AS hours_in_day
FROM GENERATE_SERIES(TIMESTAMP '2024-11-01', TIMESTAMP '2024-11-05', INTERVAL '1 day') AS g(d)
-- 2024-11-03 returns 25; the other days return 24
```

Joining `hours_in_day` onto a daily revenue table turns the November question into a sentence: divide by it, compare revenue per hour, and the jump disappears. The interviewer is listening for that move, because it keeps the local day finance asked for and removes the clock from the comparison.


<br>

### Answers that hold up

- Measure every duration by subtracting instants (TIMESTAMPTZ or UTC), never naive local wall-clock values
- Build hourly buckets on UTC, where every hour is 60 minutes, then label each with its local time and offset
- Keep daily totals on the local day, carry hours_in_day, and compare per-hour rates on the 2 DST days
- Use calendar intervals for "same time tomorrow" and elapsed ones for "24 hours later", and say which you mean

Bucketing on UTC gives November 3 its 25 rows, with 2 rows labelled 01:00 and told apart by offset, and gives March 10 its 23. Every bar covers the same length of time, which is the property an hourly chart needs to be read at all.


> **TIP**
>
> Expect the follow-up "What does your hourly chart show on November 3?" Answer with the number: 25 hours, 2 rows for 01:00 if bucketed on UTC, or a single 01:00 bar holding 2 hours of traffic if bucketed on local wall-clock hours.


<br>

---

## Adding a Month to January 31

This one arrives as "when is the next billing date?", "compare to the same day last year" or "retention 1 month after signup". A month has no fixed length, so `+ 1 month` is a rule the engine applies to the calendar fields rather than a quantity of time. Nearly every engine applies the same rule for a single step: add to the month and keep the day, clipping it to the month's last day when it overflows.

https://github.com/user-attachments/assets/1480e68a-0ecc-404c-b943-c07db142be20

Subscription 1 starts on 2024-01-31 and its next month is 2024-02-29, the clip. Adding a second month to that result gives 2024-03-29, while adding 2 months to the start gives 2024-03-31: the days lost in February never come back when steps are chained. Subscription 3 shows a leap day moving to 2024-03-29 and staying on the 29th, and subscription 4 shows a 31st clipping to 2024-04-30 and then drifting to 2024-05-30.

The clip also makes month math irreversible. Taking 2024-01-31 forward 1 month and back 1 month returns 2024-01-29, so a filter written as `renewal_date - INTERVAL '1 month' = start_date` misses every start that was clipped. And "1 month" and "30 days" part ways at once: 2024-01-31 plus 30 days is 2024-03-01, plus 1 month is 2024-02-29, and a trial sold as a month but coded as 30 days ends on a different date for most starts in a month that is not 30 days long. The exceptions are starts where the clip happens to land on the same day, such as 2024-01-30, which reaches 2024-02-29 either way.


<br>

### Anchor every schedule to its start

A schedule computed as anchor plus n months never drifts, because each date is a single clip away from the start rather than an accumulation of clips. That reproduces the behaviour Stripe documents for monthly subscriptions anchored on the 31st: February 29 in a leap year, then March 31, April 30. The rule the interviewer probes is the anchor that is a month end without being a 31st, such as April 30. Same-day-number gives May 30, last-day-stays-last-day gives May 31, and only the business can say which one it bills.

```sql
-- 12 monthly due dates per subscription, each from the anchor
SELECT
  s.sub_id,
  n.k AS cycle,
  CASE
    WHEN s.start_date = CAST(
      DATE_TRUNC('month', s.start_date) + INTERVAL '1 month' - INTERVAL '1 day'
      AS DATE
    ) THEN CAST(
      DATE_TRUNC('month', s.start_date) + (
        n.k + 1
      ) * INTERVAL '1 month' - INTERVAL '1 day'
      AS DATE
    ) -- month-end anchor: stay on the last day of every month
    ELSE CAST(s.start_date + n.k * INTERVAL '1 month' AS DATE)
  END AS due_date
FROM subscriptions AS s
CROSS JOIN GENERATE_SERIES(1, 12) AS n(k)
```


<br>

### February 29 and year math

Adding a year is the same rule on the year field, so 2024-02-29 plus 1 year is 2025-02-28 in Postgres and BigQuery, and in Snowflake too. Where this costs money is the same-day-last-year join.

| This-year row | day - INTERVAL '1 year' | Last-year row it joins |
| --- | --- | --- |
| 2024-02-28 | 2023-02-28 | 2023-02-28 |
| 2024-02-29 | 2023-02-28 | 2023-02-28 (again) |
| 2024-03-01 | 2023-03-01 | 2023-03-01 |

Joined on `ly.day = ty.day - INTERVAL '1 year'`, the 2023-02-28 row matches 2 rows this year, so last year's February counts that day twice and the growth figure comes out low. Written the other way, `ly.day + INTERVAL '1 year' = ty.day`, February 29 matches nothing. The business has to say whether February 29 compares to February 28 or to nothing. Retail usually sidesteps it by comparing to 364 days back, which keeps a Saturday against a Saturday at the price of the calendar dates drifting apart year after year.

Anniversaries follow the same clip. Someone born on 2004-02-29 turns 21 on 2025-02-28 under the engine's rule, while legal rules differ on whether that birthday falls on February 28 or March 1. Any age or tenure check near the boundary is a policy question to ask. Completed years come from comparing month and day against the anniversary, never from subtracting 2 year numbers.

> Questions that pin the month rule
>
> - Is each due date computed from the start date, or from the previous due date?
> - Does a month-end anchor stay on the last day, or keep its day number?
> - Does February 29 compare to last year's February 28 or to the weekday 364 days back, or does it get no comparison at all?
> - Does "1 month" mean a calendar month or a fixed 30 days?


<br>

---

## Dialect Differences in Date Math

Dialect comes up in 2 ways: "we're on Snowflake, write it there", or "this report was ported from SQL Server and the numbers moved". Spelling differences cost a minute of syntax. The expensive ones are calls that read the same and compute something else, and those are what the second phrasing is fishing for.


<br>

### The same operation in 4 dialects

| Operation | Postgres | BigQuery | Snowflake | Spark SQL |
| --- | --- | --- | --- | --- |
| Add 1 month | `d + INTERVAL '1 month'` | `DATE_ADD(d, INTERVAL 1 MONTH)` | `DATEADD(month, 1, d)` | `add_months(d, 1)` |
| Days between | `end_date - start_date` | `DATE_DIFF(end_date, start_date, DAY)` | `DATEDIFF(day, start_date, end_date)` | `datediff(end_date, start_date)` |
| UTC instant to Los Angeles wall clock | `ts AT TIME ZONE 'America/Los_Angeles'` | `DATETIME(ts, 'America/Los_Angeles')` | `CONVERT_TIMEZONE('UTC', 'America/Los_Angeles', ts)` | `from_utc_timestamp(ts, 'America/Los_Angeles')` |
| Last day of month | `CAST(DATE_TRUNC('month', d) + INTERVAL '1 month' - INTERVAL '1 day' AS DATE)` | `LAST_DAY(d)` | `LAST_DAY(d)` | `last_day(d)` |
| ISO week and ISO year | `EXTRACT(WEEK FROM d)`, `EXTRACT(ISOYEAR FROM d)` | `EXTRACT(ISOWEEK FROM d)`, `EXTRACT(ISOYEAR FROM d)` | `WEEKISO(d)`, `YEAROFWEEKISO(d)` | `weekofyear(d)`, `extract(YEAROFWEEK FROM d)` |

The day-difference row and the conversion row deserve a second look. The day difference takes its arguments in different orders: BigQuery and Spark put the end first, Snowflake puts the unit first and the start before the end, and Postgres subtracts. A port that keeps the argument positions flips the sign of every duration, and "days to resolve" turns negative. The conversion row changes return types: all 4 engines hand back a value meant to be read as local wall-clock time, so comparing it later against an instant shifts every row by the offset without an error.


<br>

### Where the Meaning Changes

| Expression | Engine | Result |
| --- | --- | --- |
| `DATEDIFF(year, '2023-12-31', '2024-01-01')` | Snowflake, SQL Server | 1 |
| `TIMESTAMPDIFF(YEAR, '2023-12-31', '2024-01-01')` | MySQL | 0 |
| `DATEADD(month, 1, '2024-02-29')` | Snowflake | 2024-03-29 |
| `ADD_MONTHS('2024-02-29', 1)` | Snowflake | 2024-03-31 |
| `add_months(DATE '2019-02-28', 1)` | Spark 3.x | 2019-03-28 (Spark 2.4 returned 2019-03-31) |
| `DATE_TRUNC(DATE '2024-03-13', WEEK)` | BigQuery | 2024-03-10, a Sunday |
| `DATE_TRUNC('week', DATE '2024-03-13')` | Postgres | 2024-03-11, a Monday |

`DATEDIFF` in Snowflake and SQL Server counts unit boundaries crossed, so a single day across New Year is 1 year, and BigQuery's `DATE_DIFF` counts boundaries the same way at the month and year level. MySQL's `TIMESTAMPDIFF` and Postgres's `AGE` count completed units. A tenure report moved from MySQL to Snowflake adds a year to every employee whose anniversary is still ahead this year, and nothing errors.

Snowflake ships 2 month functions with different month-end rules: `ADD_MONTHS` keeps a last-of-month date on the last day, `DATEADD` keeps the day number. Spark changed `add_months` in 3.0 to stop preserving month ends, so the same query returns different dates on 2.4 and 3.x clusters. Week truncation splits on the first weekday: Postgres starts weeks on Monday, BigQuery's `WEEK` starts on Sunday unless written `WEEK(MONDAY)` or `ISOWEEK`, and Snowflake follows the session's `WEEK_START` parameter.

The type name itself moves. A BigQuery `TIMESTAMP` is an instant; a Postgres `TIMESTAMP` is a wall-clock value, as is Snowflake's default `TIMESTAMP_NTZ`; Spark's default `TIMESTAMP` is an instant shown in the session zone. Functions that read the clock depend on the session too. Snowflake's `TIMEZONE` parameter defaults to America/Los_Angeles, so `CURRENT_DATE` there rolls over at Los Angeles midnight unless someone changed it, while BigQuery's `CURRENT_DATE()` uses UTC unless given a zone.

Return types shift under smaller calls as well. In Postgres, a `DATE` plus an integer is a `DATE`, while a `DATE` plus an `INTERVAL` is a `TIMESTAMP`, which is why the month-add queries in this lesson cast back to `DATE` before grouping or joining on the result.


<br>

### Handling dialect in the room

Name a dialect in the first minute and write in it. Then name the places where your answer depends on it, usually 2 of the rows above: "I'm writing Postgres; in Snowflake I'd use `ADD_MONTHS` here because the anchor is a month end, and I'd check `WEEK_START` before trusting the week buckets." Interviewers rarely grade exact spelling. They are listening for whether you know which calls change meaning when the engine changes, because those are the calls that break silently in a migration.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Ask whether the fiscal year is month-aligned or 52/53-week, and how its years are named<br><br>• Convert instants to the region's IANA zone once, and group on the local day only after that<br><br>• Measure durations on instants and bucket hours on UTC across DST days<br><br>• Compute every recurring date from its anchor with an explicit month-end rule<br><br>• Name the dialect, and check DATEDIFF semantics and week start before porting | • Pair EXTRACT(YEAR ...) with an ISO week number<br><br>• Truncate in UTC and relabel the bucket as a local day<br><br>• Store a fixed offset like '-08:00' for a zone that observes DST<br><br>• Chain +1 month steps to build a billing schedule<br><br>• Assume DATEDIFF(year, ...) counts completed years |


<br>

---

## Putting It All Together

A streaming service headquartered in Los Angeles runs its warehouse on Snowflake and closes its books on a fiscal year beginning July 1. Finance asks for FY2025 Q1 subscription revenue by country, booked on each country's local date, together with the renewals falling due in FY2025 Q2 (October to December 2024) and an hourly view of charge volume across that quarter.

- The quarter comes from the July 1 calendar: each local date is shifted 6 months before extracting year and quarter, and weekly cuts group on ISO year and ISO week.
- Each UTC instant is converted to the country's IANA zone before the fiscal mapping, so a June 30, 2024 evening sale in Los Angeles, already July 1 in UTC, stays in FY2024 instead of leaking into FY2025 Q1.
- FY2025 Q2 crosses the EU change on 2024-10-27 and the US change on 2024-11-03, so the hourly charge-volume view is bucketed on UTC and labelled with local time and offset.
- Renewal dates are anchor plus n months with an explicit month-end rule, so a subscription begun on August 31 bills on November 30 and December 31 without drifting.
- On Snowflake, ADD_MONTHS carries the month-end rule where DATEADD would not, and the session TIMEZONE, defaulting to America/Los_Angeles, is set explicitly before CURRENT_DATE decides which quarter is current.


<br>

---

## Key Takeaways

- Every date belongs to a period the business chose: confirm the fiscal start, how its years are named, and whether weeks are ISO before any SQL.
- Convert an instant to the region's IANA zone once and bucket on the truncated local day; on a plain TIMESTAMP, AT TIME ZONE runs the other way.
- DST days run 23 and 25 hours: measure durations on instants, bucket hours on UTC, and compare per-hour rates on those days.
- Adding a month clips the day: compute schedules from the anchor, state the month-end rule, and check February 29 in year-over-year joins.
- DATEDIFF and ADD_MONTHS change meaning across engines, and so do the week start and even the TIMESTAMP type. Name your dialect and the calls that depend on it.
