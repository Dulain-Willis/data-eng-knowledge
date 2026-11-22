# Period-over-Period: Advanced

Forty minutes into the loop, the interviewer shares her screen. It shows 5 tiles screenshotted from a year of a grocery delivery company's growth dashboards. Orders on Monday 17 March, down 22% on the same date a year earlier. Checkout conversion, down a full point week over week. A city launched in March, up 1,150% in a week. GMV growing 20% a month on average this spring. October revenue, down 48% against September.
"Every query behind these passed review," she says. "The CFO won't put a single tile in the board deck. Tell me why."
She has not said which tile is wrong, and the arithmetic in all 5 is correct. The pull is to start reading SQL for bugs. She is scoring whether you ask, of each number, what it is compared against and whether that comparison is fair to the business.


<br>

### What you will be able to do

Choose between a 364-day offset and a calendar-year offset for a daily figure, and name where each one breaks

Split a ratio's change into rate and mix effects when the total moves against every segment

Replace percent change on small baselines with absolute change, contribution to growth and a stated noise floor

Compute compound growth across a span instead of averaging the period-by-period rates

Compare a month still in progress with finished months without manufacturing a collapse


<br>

---

## Same Weekday vs Same Date

The daily version of this question sounds harmless: "How did yesterday do against last year?" Writing `order_date - INTERVAL '1' YEAR` answers a calendar question, and for a business with a weekly rhythm the calendar is the wrong reference. A year is 52 weeks and 1 day, so a date falls on the next weekday each year, and 2 weekdays later when a 29 February sits between them.

For a grocery delivery app, that shift is most of the number. Sunday is the peak, and in the 8 weeks before mid-March 2025 Sunday averaged roughly 1.37 times Monday. Monday 17 March 2025 against 17 March 2024, which was a Sunday, reads as a collapse. Against the Monday 52 weeks earlier, the same day reads as growth.

| Comparison | Date | Weekday | Orders | Change |
| --- | --- | --- | --- | --- |
| This year | 2025-03-17 | Monday | 41,200 | n/a |
| Same date, 1 year back | 2024-03-17 | Sunday | 52,900 | -22.1% |
| Same weekday, 364 days back | 2024-03-18 | Monday | 38,600 | +6.7% |

Both of last year's rows are real, and both percentages are computed correctly. The weekday decides the sign. The interviewer is listening for that sentence before any SQL: "Orders here run on a weekly cycle, so I'd compare with the same weekday 52 weeks back, 364 days, after checking the cycle is real."


<br>

### Prove the weekday drives the number

The check is 1 query, and running it shows you measure before you choose. Average the metric by day of week over a whole number of recent weeks, so every weekday is counted the same number of times.

```sql
SELECT
  EXTRACT(DOW FROM order_date) AS day_of_week,
  AVG(orders) AS avg_orders,
  MIN(orders) AS min_orders,
  MAX(orders) AS max_orders
FROM daily_orders
WHERE order_date >= DATE '2025-01-20'
  AND order_date < DATE '2025-03-17'
GROUP BY EXTRACT(DOW FROM order_date)
ORDER BY day_of_week
```

As a working rule, if the busiest weekday averages more than about 1.2 times the quietest, the weekday moves the number by more than most real growth does, and same weekday is the honest reference. If the averages sit within a few percent of each other, the cycle is weak and the calendar date is fine. Some metrics run on the calendar instead: rent and loan payments on the 1st, payroll on the 15th, renewals on contract anniversaries, tax deadlines. For those the same date carries the business meaning, and a 364-day offset would compare 1 April with 2 April.


<br>

### The 364-day self-join

```sql
SELECT
  cur.order_date,
  cur.orders,
  prev.order_date AS compare_date,
  prev.orders AS compare_orders,
  (
    cur.orders - prev.orders
  ) * 100.0 / NULLIF(prev.orders, 0) AS yoy_pct
FROM daily_orders AS cur
LEFT JOIN daily_orders AS prev
  ON prev.order_date = cur.order_date - INTERVAL '364' DAY
WHERE cur.order_date >= DATE '2025-01-01'
```

Return compare_date in the output: a reader of the tile sees which day last year it was measured against, and a reviewer confirms at a glance that 2025-03-17 paired with 2024-03-18. The offset is INTERVAL '364' DAY, never INTERVAL '1' YEAR and never 365 days. Since 52 weeks of 7 days come to exactly 364, the offset lands on the same weekday in every year, leap or not.

Weekly reporting has its own version. ISO week 11 of 2025 against ISO week 11 of 2024 already pairs Monday with Monday, but an ISO year has 53 weeks every 5 or 6 years, and 2026 is one. Week 53 of 2026 has no counterpart in 2025, and someone has to decide before December what it is compared with.


<br>

### Holidays and drift break the 364-day offset

The follow-up is almost always a holiday. Have the failure modes ready, with dates.

> Failure modes of a 364-day offset
>
> - Drift: each year back adds a day, so going 3 years back, 1,092 days, lands on Monday 21 March 2022, 4 days off the calendar date.
> - Fixed-date holidays: Christmas 2025 is a Thursday, and its 364-day partner is Thursday 26 December 2024, an ordinary day.
> - Moving holidays: from Thanksgiving, 28 November 2024, it lands on 30 November 2023, a week after that year's Thanksgiving.
> - Easter moved from 31 March 2024 to 20 April 2025. No fixed offset of any length pairs them.

The answer to give is a calendar dimension the business owns: one row per date with a `comparable_date` column, defaulting to 364 days back and overridden per holiday so Thanksgiving pairs with Thanksgiving and Christmas with Christmas. The join becomes `prev.order_date = cal.comparable_date`, and the holiday rules live in data that marketing can review instead of in a `CASE` buried in a dashboard.


> **TIP**
>
> A trailing 7-day total sidesteps the weekday question. Any 7 consecutive days hold one of each weekday, so the 7 days through yesterday against the 7 days ending 364 days earlier is fair whatever weekday yesterday was. Offer it when the consumer cares about trend more than about one day.


<br>

---

## When Mix Shift Flips the Total

This one arrives as a rollback request. "Checkout conversion fell from 7.0% to 6.0% the week after we shipped the new checkout. Product wants to revert on Friday. What do you look at first?" Most candidates start auditing event tracking. The first thing to establish is whether the traffic reaching checkout changed, because a sitewide conversion rate is each platform's rate weighted by its share of sessions.

Here are those 2 weeks for the grocery app. In the week of 10 March a paid web campaign tripled web sessions. The query computes each platform's rate and its share of that week's sessions.

https://github.com/user-attachments/assets/7bbf2262-8356-448c-bf18-1b4120ebb6b3

Both platforms improved by half a point: the app from 8.0% to 8.5%, the web from 3.0% to 3.5%. The app's share of sessions dropped from 80% to 50%, and the web converts at well under half the app's rate, so the week's total, orders over sessions, fell from 700 of 10,000 (7.0%) to 720 of 12,000 (6.0%). Checkout performed better on both platforms. The campaign brought visitors who buy less often, and orders still rose.


<br>

### Ratios flip, sums do not

Only a ratio or an average can move against all of its segments. A sum is additive: if every platform's orders rose, total orders rose. Conversion, average order value, revenue per user, churn and on-time rate are each a total divided by a total, and each can flip. Saying this tells the interviewer which tiles on a dashboard need a mix check and which never do.

The same shape turns up in other costumes, and none of them mention mix:

- Average order value fell 6% overall but rose in every country.
- Churn went up this quarter, yet it went down on every plan.
- On-time delivery improved in every city and fell nationally.
- Every sales rep's win rate rose and the team's win rate dropped.
- Revenue per user rose in every signup cohort while the company figure slid.


<br>

### Split the change into rate and mix

Naming mix shift earns some credit. Quantifying it is what lets you defend the revert decision in the meeting. The change in a total rate splits exactly into 2 parts. The rate effect is each segment's change in rate weighted by its old share. The mix effect is each segment's change in share weighted by its new rate.

```sql
WITH seg AS (
  SELECT
    week_start,
    platform,
    sessions * 1.0 / SUM(sessions) OVER (
      PARTITION BY week_start
    ) AS share,
    orders * 100.0 / sessions AS cvr
  FROM weekly_traffic
),
paired AS (
  SELECT
    cur.platform,
    prev.share AS share_prev,
    cur.share AS share_cur,
    prev.cvr AS cvr_prev,
    cur.cvr AS cvr_cur
  FROM seg AS cur
  JOIN seg AS prev
    ON prev.platform = cur.platform
      AND prev.week_start = cur.week_start - INTERVAL '7' DAY
  WHERE cur.week_start = DATE '2025-03-10'
)

SELECT
  SUM(
    share_prev * (
      cvr_cur - cvr_prev
    )
  ) AS rate_effect_pp,
  SUM(
    (
      share_cur - share_prev
    ) * cvr_cur
  ) AS mix_effect_pp
FROM paired
```

| platform | rate effect (pp) | mix effect (pp) |
| --- | --- | --- |
| app | +0.40 | -2.55 |
| web | +0.10 | +1.05 |
| total | +0.50 | -1.50 |

The 2 effects sum to the observed -1.0 points: the page got half a point better and the traffic mix cost a point and a half. The sentence for the product meeting is "At last week's traffic mix, conversion would have been 7.5%." That is the mix-adjusted rate, this week's platform rates weighted by last week's shares: 0.8 times 8.5 plus 0.2 times 3.5.

| ✓ Total rate: 6.0% | ✗ Mix-adjusted rate: 7.5% |
| --- | --- |
| • What the business actually got from its traffic<br><br>• Matches finance: orders divided by sessions<br><br>• Moves with marketing spend and channel mix<br><br>• Answers: are we converting more of our visitors? | • Holds segment shares at a reference period<br><br>• Isolates whether the product itself improved<br><br>• Ages as the reference period drifts; refresh it<br><br>• Answers: did the checkout redesign work? |

The next question is which one belongs on the exec dashboard. Both, labelled. Showing only the mix-adjusted rate looks like spin; showing only the total gets a good release reverted.

If the shares barely moved, one query has ruled mix out and the conversation goes back to checkout itself: a 1-point drop with stable mix is a real regression, and reverting is the right call.


<br>

### Choosing the segments

The decomposition is only as good as the segmentation. Cut by dimensions where 2 things hold: the shares moved between the periods, and the segments convert at markedly different rates. Platform, new versus returning customer, traffic source and country are the usual candidates, and a paid campaign can move all 4. Cutting by every dimension at once yields cells too small to hold a stable rate.

> **TIP**
>
> If a segment exists in only one period, such as a platform launched this week, the inner join drops it and the 2 effects stop summing to the total change. Use a `FULL OUTER JOIN` and `COALESCE` the missing share and rate to 0 so every segment is counted.


<br>

---

## Growth Rates on Tiny Baselines

The request: "Rank our 40 cities by week-over-week order growth so regional managers know where to look." The first draft sorts by percent change, and the top row is Boise, launched 2 weeks ago, up from 40 orders to 500. That is +1,150%, computed correctly, and it sits above Chicago, which added 3,000 orders. Percent change has no units, so it hides the size of the baseline, and a ranking built on it points at whichever segment had least to start from.


<br>

### Small counts swing on their own

- **±16%** — chance swing, 40 orders a week
- **±0.4%** — chance swing, 61,000 orders a week

Counts wobble from week to week with no change in demand, by roughly the square root of the count, which is what the tiles above show for a single week. A week-over-week change carries the wobble of both weeks, around 1.4 times as much: roughly ±22% at 40 orders. Relative to the count, that wobble shrinks as volume grows, which is why a 30% move in a 40-order city is routine and a 3% move in Chicago is news. A ranking or alert that ignores this fires on the smallest segments every week and teaches the managers to stop reading it.

Put a number on the floor. For a 10% change to clear twice the single-week noise, 2 divided by the square root of the baseline has to come in under 0.10, which takes a baseline of about 400 events. Counting both weeks' noise, the strict version of that test needs about 800, so 400 is a deliberately loose floor that withholds the worst offenders without blanking mid-size cities. For a rate, the floor applies to the count on top: 3% conversion on 500 sessions is 15 orders, and 15 orders swings by about a quarter on its own.


<br>

### Absolute change, contribution and a floor

```sql
WITH weekly AS (
  SELECT
    city,
    week_start,
    orders AS orders_cur,
    LAG(orders, 1) OVER (
      PARTITION BY city
      ORDER BY week_start
    ) AS orders_prev
  FROM weekly_city_orders
)

SELECT
  city,
  orders_prev,
  orders_cur,
  orders_cur - orders_prev AS orders_added,
  CASE
    WHEN orders_prev >= 400 THEN (
      orders_cur - orders_prev
    ) * 100.0 / orders_prev
  END AS wow_pct,
  (
    orders_cur - orders_prev
  ) * 100.0 / NULLIF(
    SUM(orders_cur - orders_prev) OVER (
    ),
    0
  ) AS share_of_growth_pct
FROM weekly
WHERE week_start = DATE '2025-03-10'
ORDER BY orders_added DESC
```

| city | orders_prev | orders_added | wow_pct | share_of_growth_pct |
| --- | --- | --- | --- | --- |
| Chicago | 61,000 | 3,000 | 4.9 | 60.0 |
| Austin | 9,800 | 800 | 8.2 | 16.0 |
| Boise | 40 | 460 | NULL | 9.2 |
| Tulsa | 300 | -90 | NULL | -1.8 |

*Shown: 4 of the 40 cities. National orders rose by 5,000 this week.*

Sorted by orders added, Chicago leads with 60% of the week's national growth and Boise sits third at 9.2%, the size of its actual impact. Boise's percent is NULL because 40 orders is under the floor, and Tulsa's 30% drop on 300 orders is held back for the same reason. Austin's 8.2% clears the floor and is the most useful percent on the page: a mid-size market growing faster than the leader.

NULL is the right value in the table and the wrong thing to show a manager. Render it as a label with its reason, such as "new: 40 to 500" or "low volume", so the gap reads as a decision. If product insists on a percent for Boise, put the baseline beside it: "+1,150% from 40 orders" is honest, and a bare "+1,150%" is not.

The same floor stops false alarms on the way down. A dark store that goes from 3 orders to 0 reports -100%, the steepest decline on any weekly list, and it means 3 orders. Gate decline alerts on the absolute drop as well, and the overnight page for a -100% stops.

> Other honest replacements
>
> - A longer window: pooling 4 weeks lifts a 40-order city's baseline to 160 and halves its relative noise.
> - Smoothed growth: (cur + k) / (prev + k) - 1. With k = 400, Boise reads +105% and Chicago still reads +4.9%.
> - Dual-threshold alerts: fire only when percent and absolute change both clear a bar, such as 20% and 500 orders.
> - Share of national orders: moves only when a city's change is large enough to matter to the total.

Expect the push: "Isn't suppressing a number hiding information?" Nothing is hidden. The counts and the absolute change stay on the row, and the percent is withheld only where it would mostly be measuring chance. State the floor in the tile's footnote so the rule is visible to everyone reading it.

What the interviewer scores here is the move from "sort by growth" to "growth measured how, on what base". Proposing the floor, the absolute column and the contribution column before being asked usually closes this part of the round.

> **TIP**
>
> Contribution breaks on a small denominator too. When the national change is near 0, say +50 orders across all 40 cities, each city's share of growth runs into thousands of percent, positive and negative. Fall back to absolute change when the national delta is small next to the national total.


<br>

---

## Averaging Growth Across Periods

The phrasing is friendly: "What was our average monthly GMV growth from January to April?" or "If we keep growing at our average rate, where are we in December?" The wrong answer is `AVG(mom_growth)`. Growth compounds, so rates multiply across periods, and an arithmetic mean of numbers that multiply answers a question nobody asked.

The series: a promotion in February doubled GMV, March fell back to January's level, and April recovered by a tenth. LAG turns 4 months into 3 growth rates, and the first month has none.

https://github.com/user-attachments/assets/df4f2753-94bd-48c8-a390-ef9b5828b40b

The 3 rates are +100%, -50% and +10%, which average to +20% a month. Compounded from January's 120,000 for 3 months, +20% predicts 207,360 for April; April was 132,000. Doubling and then halving returns GMV to where it began, yet those 2 rates add 50 points to the average. The more the rates swing, the further their arithmetic mean sits above the real growth.


<br>

### The rate that reproduces the data

Growth across a span depends only on its endpoints. April over January is 1.10, so GMV grew 10% in 3 months. The compound monthly rate is the one that, applied 3 times, gets there: 1.10 to the power 1/3, minus 1, or 3.23%. Check it by compounding: 120,000 times 1.0323 cubed is 132,000.

```sql
WITH rates AS (
  SELECT
    month_start,
    gmv * 1.0 / LAG(gmv, 1) OVER (
      ORDER BY month_start
    ) AS growth_factor
  FROM monthly_gmv
  WHERE month_start BETWEEN DATE '2025-01-01'
  AND DATE '2025-04-01'
)

SELECT
  AVG(growth_factor - 1) AS arithmetic_avg,
  EXP(AVG(LN(growth_factor))) - 1 AS compound_monthly,
  EXP(SUM(LN(growth_factor))) - 1 AS growth_over_span,
  COUNT(growth_factor) AS intervals
FROM rates
```

| arithmetic_avg | compound_monthly | growth_over_span | intervals |
| --- | --- | --- | --- |
| 0.2000 | 0.0323 | 0.1000 | 3 |

`EXP(AVG(LN(x)))` is the geometric mean of the growth factors, and on a series without gaps it equals the endpoint formula. Its advantage is that it works under `GROUP BY`, so it returns a compound rate per city or per product in one pass where picking first and last rows takes more plumbing. It fails on a zero or negative month, because the logarithm is undefined there; report the span from the first nonzero month and say so.

The December projection shows the cost in money. From April's 132,000, 8 more months at 3.23% reach roughly 170,000. At the 20% average they reach about 568,000, more than 4 times April, and a plan built on that number hires for a business that does not exist.

Summing the rates goes wrong in the other direction. "January grew 10%, February 12%, March 8%. What did the quarter grow?" Adding gives 30%. Multiplying the factors, 1.10 times 1.12 times 1.08, gives 1.3306: the quarter grew 33.1%. Interviewers offer round numbers on purpose, because the sum looks right.


<br>

### Follow-ups on the span

> Follow-ups that test whether you have done this
>
> - Off by one: January to April is 4 months but 3 intervals. Using 1/4 as the exponent reports 2.41% instead of 3.23%.
> - Annualizing: 3.23% a month compounds to 46.4% a year, which is 1.10 to the 4th. Multiplying by 12 gives 38.7% and understates it.
> - Endpoints: start in promo-month February and the same data shows -45% over 2 months. Say which endpoints you chose and why.
> - Noisy series: regress `LN(gmv)` on month number (`REGR_SLOPE` in Postgres and Snowflake); EXP of the slope, minus 1, is the trend rate.

| ✓ Arithmetic mean of rates | ✗ Compound rate |
| --- | --- |
| • Describes how much a typical single month moved<br><br>• Overstates span growth whenever the rates vary<br><br>• Here: +20% a month, predicting 207,360<br><br>• Wrong for projections, targets and annualizing | • Reproduces the end value from the start value<br><br>• Depends only on endpoints, so they must be representative<br><br>• Here: +3.23% a month, matching 132,000<br><br>• Right for projections, targets and board reporting |

The sentence that closes this part of the interview: "Rates compound, so I use the geometric mean, 3.2% a month here; the 20% average would put April at 207,000 instead of 132,000."


<br>

---

## A Month Still in Progress

The dashboard refreshes at 6am on 16 October 2025. The month-over-month tile reads -48%: October has 1,560,000 of revenue so far and September closed at 3,000,000. Both figures are right and the business is growing. October has 15 complete days on the books against September's 30, and a naive tile reports a collapse early in every month and, late in every month, a recovery that is only the calendar filling in.


<br>

### Name the partial period first

The interviewer usually builds this in through phrasing: "Build a revenue tile that refreshes daily and shows month over month." The word daily is the hint that the newest month will almost never be finished. Say so before writing anything, then lay out the options and ask the consumer which question they want answered, because each option answers a different one.

The opening line that lands: "October is 15 days old, so before choosing a comparison I'd ask whether finance wants this month's pace or a forecast of the whole month."

| Approach | Compares | Reads on 16 Oct | Breaks when |
| --- | --- | --- | --- |
| Naive | Oct 1-15 vs all of September | -48% | Always, until the month closes |
| Finished months only | September vs August | No October figure | Stale for up to 31 days |
| Month to date | Oct 1-15 vs Sep 1-15 | +6.1% | Days 29 to 31, weekday mix, billing timing |
| Daily run rate | 104,000 vs 100,000 a day | +4.0% | Revenue bunched at month start or end |
| Projection | Forecast month vs September | Labelled estimate | Short history or an unusual month |


<br>

### Month to date against the same days

Month to date is the common default, because it compares equal day counts. On 16 October it pairs October's 1,560,000 with 1 to 15 September, which took 1,470,000, for +6.1%. Anchor it on the last complete day and not on `CURRENT_DATE`: at 6am today holds a few hundred orders, and including it drags the current window down.

```sql
WITH w AS (
  SELECT
    DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1' DAY) AS cur_start,
    CURRENT_DATE - INTERVAL '1' DAY AS as_of
),
bounds AS (
  SELECT
    cur_start,
    as_of,
    cur_start - INTERVAL '1' MONTH AS prev_start,
    as_of - INTERVAL '1' MONTH AS prev_as_of
  FROM w
)

SELECT
  b.as_of,
  SUM(
    CASE
      WHEN d.order_date BETWEEN b.cur_start
      AND b.as_of THEN d.revenue
    END
  ) AS mtd_revenue,
  SUM(
    CASE
      WHEN d.order_date BETWEEN b.prev_start
      AND b.prev_as_of THEN d.revenue
    END
  ) AS prior_mtd_revenue
FROM daily_revenue AS d
CROSS JOIN bounds AS b
WHERE d.order_date >= b.prev_start
GROUP BY b.as_of
```

The `WHERE` on `prev_start` lets the engine prune to 2 months of partitions instead of scanning the whole table. Returning `as_of` puts "through 15 Oct" on the tile, so no one reads a partial month as a closed one.


<br>

### Month-end clamping and other edges

Month arithmetic clamps at month end. With `as_of` on 29 or 30 March 2025, `as_of - INTERVAL '1' MONTH` returns 28 February for both, so the prior window stops at 28 days while the current one keeps growing: on 30 March, 30 days of March meet 28 of February and the tile overstates growth by roughly 7%. On the days where the earlier month has run out, switch to daily run rate. The other edge is 1 October: `as_of` is 30 September, so the current window is all of September and the prior window is 1 to 30 August, a day short. Whenever `as_of` is the last day of its month, compare full months.

Weekday mix carries over from the start of the lesson. The first 15 days of October hold 3 Wednesdays and the first 15 of September hold 3 Mondays, close enough for a delivery app whose peak is Sunday. Where an extra Saturday is a fifteenth of the window, as for a restaurant group, compare the 15 days through `as_of` with the 15 days ending 28 days earlier, which hold the same weekdays.

Daily run rate divides by days elapsed: 1,560,000 over 15 days is 104,000 a day against September's 100,000, or +4.0%. It handles months of different lengths without clamping, which makes it a good default for revenue spread evenly through the month. It misleads when revenue bunches: a subscription business that bills most customers on the 1st has its biggest day inside the window by the 2nd, and its run rate projects a record month every month.

A projection estimates the finished month, typically from the share of a month's revenue earned by this day in past months. It is the figure finance wants for planning, and it belongs on the tile only with the word estimate beside it.

> Partial is wider than this month
>
> - Today is partial until midnight in the reporting timezone, and later if ingestion runs behind.
> - Late data: if events land up to 2 days late, anchor on the load watermark rather than the clock.
> - Last month moves too: refunds and chargebacks restate September for weeks, and finance treats it as final only after close.
> - Model it once: an `is_complete` flag on the period table lets every downstream query filter the same way.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Compare weekday-driven daily metrics with 364 days back, holidays overridden in a calendar table<br><br>• Split a ratio's change into rate and mix effects before blaming the product<br><br>• Show absolute change beside percent and withhold percent below a stated noise floor<br><br>• Report span growth as the compound rate from its endpoints, with the interval count stated<br><br>• Anchor partial periods on the last complete day and print the as-of date on the tile | • Compare a Monday with last year's Sunday because the calendar date matched<br><br>• Rank segments by percent change when their baselines differ by orders of magnitude<br><br>• Average period-by-period growth rates to describe or project growth over a span<br><br>• Compare a month in progress with a closed month as if both were finished |


<br>

---

## Putting It All Together

It is the morning of Monday 17 November 2025, and the grocery delivery company's weekly business review opens on one slide: yesterday's orders against last year, sitewide conversion for the week, the fastest-growing cities, growth since January, and November month to date. The head of growth asks you to sign off on every number before the slide goes to the board.

- Yesterday was Sunday 16 November, and its partner is Sunday 17 November 2024, 364 days back; the calendar table confirms no holiday override applies to either date.
- Conversion fell for the week, so the slide carries the total and the mix-adjusted rate, with rate and mix effects by platform beneath them.
- The city ranking sorts by orders added, shows each city's share of national growth, and prints percent only for cities above 400 orders a week.
- Growth since January is the compound monthly rate from the January and October endpoints over 9 intervals, so the board sees the rate that reproduces October.
- November has 16 complete days, compared with 1 to 16 October and labelled through 16 Nov, with the daily run rate beside it as a cross-check.


<br>

---

## Key Takeaways

- For weekday-driven daily metrics, compare with 364 days back and keep holiday pairings in a calendar table the business owns.
- A ratio can fall while every segment rises: split the change into rate and mix effects before blaming the product.
- Percent change hides its baseline: show absolute change and contribution, and withhold percent below a stated noise floor.
- Rates compound: report growth across a span as the geometric rate from its endpoints, counting intervals rather than periods.
- Compare a partial period on equal terms, anchored on the last complete day, with the as-of date printed on the tile.
