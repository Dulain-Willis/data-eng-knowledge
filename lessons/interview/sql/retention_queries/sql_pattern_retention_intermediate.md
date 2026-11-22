# Retention Queries: Intermediate

Dagny is 40 minutes into a data engineering loop at Spotify when the interviewer shares a schema: a users table with a signup channel, and an events table of plays and playlist adds. "Product wants the share of new listeners from the past 30 days who came back a week after joining, split by acquisition channel. Write it." Dagny sketches a join from each listener's first day to their later activity, then pauses. Does a week after joining mean day 7 exactly, or any day from 7 on? Should the headline figure average 30 daily rates or pool every listener? If a listener arrived through a paid ad and returned through an email, which channel owns them? And have the newest cohorts even reached day 7? Each choice moves the number, and the interviewer wants to hear which one Dagny picks and why.


<br>

### What you will be able to do

Write the cohort self-join so every cohort member stays in the denominator and each returner counts once.

Compute an average of cohort rates and a pooled rate from the same cohorts, and say which question each answers.

Explain how exactly-day-N and day-N-or-later retention differ, and cap the unbounded version so cohorts compare.

Split retention by the segment each user had on their cohort date, and check that segments add up to the cohort.

Align cohorts to calendar weeks and mask the cells that young cohorts have not finished.


<br>

---

## The Cohort Self-Join

A retention query reads the activity table twice. The first pass folds it to 1 row per user holding the date that user was first seen: the cohort. The second pass reads the same activity again, looking for dates after that first one. Joining the first result back to the second, matched on the user and on the number of days between the 2 dates, is the cohort self-join, and every retention figure in this lesson comes out of it. Interviewers phrase it as "D7 retention", "how many of Monday's signups played again 7 days later", or "what share of new listeners stuck around". Each phrasing is this join with a different elapsed-time condition.


<br>

### Where the activity rows come from

Activity usually arrives as several tables. A listening app logs plays in track_plays and playlist edits in playlist_adds, and counting either as a return means stacking them into a single stream of user and date rows with UNION ALL. The animation stacks the second-week events of users 1 and 2.

https://github.com/user-attachments/assets/5df9cf5c-51fe-4612-9794-4873150e7e5b

UNION ALL keeps every row from both inputs, so user 1's play and playlist add on 8 January arrive as 2 identical rows. That duplicate stays in the activity table used through the rest of this section, and it is the row that will make a careless count say user 1 returned twice. Deduplicating early, with SELECT DISTINCT user_id, event_date over the union, shrinks every later step: a listener with 40 plays on one day becomes 1 row instead of 40.


<br>

### The query: cohort side and return side

```sql
WITH cohorts AS (
  SELECT
    user_id,
    MIN(event_date) AS cohort_date
  FROM activity
  GROUP BY user_id
)

SELECT
  c.cohort_date,
  COUNT(DISTINCT c.user_id) AS cohort_size,
  COUNT(DISTINCT a.user_id) AS returned_day_7
FROM cohorts AS c
LEFT JOIN activity AS a
  ON a.user_id = c.user_id
    AND DATE_DIFF('day', c.cohort_date, a.event_date) = 7
GROUP BY c.cohort_date
ORDER BY c.cohort_date
```

The cohorts CTE folds activity to 1 row per user. The outer query joins those rows back to the same activity table with 2 conditions in the ON clause: the same user, and an event exactly 7 days after the cohort date. The LEFT JOIN is what keeps users who never came back: they survive with NULL in every a column, so COUNT(DISTINCT c.user_id) still sees them while COUNT(DISTINCT a.user_id) skips them. The rate is the second count over the first.


<br>

### Watching the join find returners

The animation starts from the 3 rows the cohorts CTE produces for the 1 January cohort: users 1, 2 and 3. Its activity table holds 3 of their later events: user 1's 2 copies of 8 January and user 2's 9 January. Their day-0 events and user 3's day-2 visit are left out, because none of them can sit 7 days after the cohort date, so user 3 reaches the join with no event at all. Each cohort row is compared with each activity row, and the join keeps a pair only when both conditions hold.

https://github.com/user-attachments/assets/4ebaeb2a-7a46-4aff-93a0-b71b63d124cd

The 1 January cohort ends with 3 users and 1 returner, a day-7 rate of 33%. User 1 matched twice, once for each copy of 8 January. User 2 did come back, on 9 January, but that is day 8, so the exact-day condition rejects it, and user 3's only later visit was day 2. Each further first-seen date would add 1 row to the grouped result.


<br>

### 4 counts over the same joined rows

| Aggregate | What it counts | 1 Jan cohort |
| --- | --- | --- |
| `COUNT(\*)` | every joined row, matched or NULL-extended | 4 |
| `COUNT(a.user_id)` | joined rows with a matching event | 2 |
| `COUNT(DISTINCT a.user_id)` | users with at least 1 matching event | 1 |
| `COUNT(DISTINCT c.user_id)` | users in the cohort | 3 |

Only the last 2 belong in a retention rate. COUNT(\*) counts users 2 and 3 through their NULL rows, so it never falls below the cohort size: here it claims 4 returners from 3 users. COUNT(a.user_id) drops the NULLs but counts user 1 once per matching event, the fan-out that the duplicate from the union creates. On production data the gap widens: a listener with 12 events on day 7 adds 12 to that count and 1 to the distinct one.


<br>

### The filter that erases the denominator

A common rewrite moves the elapsed-day test out of the ON clause and into WHERE. It reads the same and returns something else.

```sql
SELECT
  c.cohort_date,
  COUNT(DISTINCT c.user_id) AS cohort_size,
  COUNT(DISTINCT a.user_id) AS returned_day_7
FROM cohorts AS c
LEFT JOIN activity AS a
  ON a.user_id = c.user_id
WHERE DATE_DIFF('day', c.cohort_date, a.event_date) = 7
GROUP BY c.cohort_date
ORDER BY c.cohort_date
```

Day test in ON

| cohort_date | cohort_size | returned_day_7 |
| --- | --- | --- |
| 2024-01-01 | 3 | 1 |

Day test in WHERE

| cohort_date | cohort_size | returned_day_7 |
| --- | --- | --- |
| 2024-01-01 | 1 | 1 |

WHERE runs after the join has finished. Users 2 and 3 do reach it, paired with their own events, but none of those events is 7 days out, and the NULL-extended row a LEFT JOIN adds for unmatched users never existed, because they did match on user. Every row that fails the test is discarded, so the cohort shrinks to its 1 returner and reports 100%. The review check that catches it: cohort_size must stay the same for every N, because it depends only on first-seen dates. If a day-7 query and a day-30 query disagree on the size of the 1 January cohort, a filter on the activity side has leaked into WHERE.

> What a complete answer covers
>
> - The cohort from `MIN(event_date)` per user, so each user sits in exactly 1 cohort.
> - A `LEFT JOIN` back to activity with the user and the elapsed days both in `ON`.
> - `COUNT(DISTINCT)` on both sides, so duplicate events and repeat visits count once.
> - A check that `cohort_size` stays the same whatever N the query uses.

> **TIP**
>
> Trim activity to the dates the cohorts can reach before it meets the join: January cohorts at day 7 need events from 1 January to 7 February. Put that range in a subquery on activity, so it filters before the `LEFT JOIN` rather than after it; on a date-partitioned table it also limits the partitions read.


<br>

---

## Blending Cohorts into One Rate

Ask for "day-7 retention for January" and the self-join hands back 31 rows, one per daily cohort, to someone who wanted 1 number. Folding those rows has 2 defensible answers that disagree, and many interview questions are this fold in disguise: "what was retention last quarter", "is retention better this month than last", "give me one D30 figure for the board deck".


<br>

### 2 ways to fold a cohort table

The **average of rates** computes each cohort's rate, then takes AVG over them, so every cohort carries the same weight whatever its size. The **pooled rate** adds the returners across cohorts and divides by the summed cohort sizes, so every user carries the same weight. The animation computes both from 3 daily cohorts the self-join produced for late January.

https://github.com/user-attachments/assets/f7f484e9-5a45-4233-b440-fa06392da24b

The 24 January cohort holds 100 of the 2,000 users, yet in the average its 10% gets the same vote as each 40% cohort, which pulls the figure down to 0.3. The pooled rate counts 770 returners over 2,000 users and lands at 0.385. Both are correct arithmetic over different weights, and the question being asked decides which weight is right.

- **8.5 pts** — gap between the two blended rates
- **1,900** — users in the two 40% cohorts


<br>

### Which figure answers which question

| ✓ Average of cohort rates | ✗ Pooled across users |
| --- | --- |
| • Answers: how does a typical daily cohort retain?<br><br>• Every cohort weighs the same, so a 100-user day moves it as much as a 1,000-user day<br><br>• Steady when acquisition volume swings, which suits tracking product changes<br><br>• Noisy when many cohorts are small, since each small rate swings widely | • Answers: what share of the users we acquired came back?<br><br>• Every user weighs the same, so large cohorts dominate<br><br>• Equals the size-weighted average of the cohort rates<br><br>• Moves when the mix of cohorts shifts, even if no cohort's rate changes |

The user-level self-join already pools. Each user sits in exactly 1 cohort, so dropping cohort_date from the GROUP BY and dividing the 2 distinct counts gives the pooled figure in one pass, with no per-cohort table in between. The average of rates has no such shortcut, because it needs each cohort's rate before it can average them.

```sql
SELECT
  CAST(COUNT(DISTINCT a.user_id) AS DOUBLE) / COUNT(DISTINCT c.user_id) AS pooled_day_7
FROM cohorts AS c
LEFT JOIN activity AS a
  ON a.user_id = c.user_id
    AND DATE_DIFF('day', c.cohort_date, a.event_date) = 7
WHERE c.cohort_date BETWEEN DATE '2024-01-22'
AND DATE '2024-01-24'
```


<br>

### When the mix moves, the pooled rate moves

The pooled rate inherits every change in where users come from. Take 2 channels over 2 months: each retains 2 points better in February than in January, while paid signups grow 5 times over.

| Channel | Jan users | Jan day-7 | Feb users | Feb day-7 |
| --- | --- | --- | --- | --- |
| organic | 1,500 | 50% | 1,500 | 52% |
| paid | 500 | 20% | 2,500 | 22% |
| pooled | 2,000 | 42.5% | 4,000 | 33.25% |

Both channels improved, and the pooled figure fell 9.25 points, because 2,500 of February's 4,000 users came through the channel that retains worse. That reversal is Simpson's paradox, and it is the argument to put in front of an interviewer: the pooled rate answers "what share of the users we acquired came back" correctly, and misleads as a signal of whether the product got better. Holding January's mix of 75% organic and 25% paid, February's channel rates give 44.5%, 2 points up. A complete answer offers the pooled figure for the first question, and per-channel rates or a fixed-mix average for the second.

> Questions to settle before blending
>
> - Is the reader asking about the users acquired, or about how a typical cohort behaves?
> - Did cohort sizes swing in the window, from a campaign, an outage or a holiday?
> - Are any cohorts too young to have reached day N? They belong in neither sum.
> - Will this figure be compared across periods with a different channel mix?

*A median of cohort rates is a third option, used when a few outlier cohorts, such as a day the signup flow broke, would distort both the mean and the pool.*

> **TIP**
>
> Returners and cohort sizes are integers, and integer division of 770 by 2,000 returns 0. Cast one side to DOUBLE before dividing, as both queries in this section do, or every rate in the report reads as 0.


<br>

---

## Bounded vs Unbounded Retention

"Came back on day 7" has 2 readings, and the self-join switches between them with 1 comparison operator. **Bounded** retention counts a user active on day 7 itself, = 7. **Unbounded** retention, also called rolling retention, counts a user active on day 7 or any day after it, >= 7. Conditional counts compute both from a single join on user alone. The animation starts after that join, from the 4 later events of the 1 January cohort that the self-join section matched, each with its elapsed days in days.

https://github.com/user-attachments/assets/a70b3a6d-726c-44f1-aad3-caf71ca121e7

The 1 January cohort retains 1 of 3 users on exactly day 7 and 2 of 3 on day 7 or later. User 2's visit on 9 January, day 8, is the whole difference: the bounded count rejects it and the unbounded count keeps it. User 3's visit on day 2 counts in neither, because both readings start at day 7.


<br>

### How the 2 curves behave

Properties that hold for any cohort

- **Unbounded is never below bounded** *for every N*\
  Every user active on day N is also active on day N or later, so the unbounded count contains the bounded one.
- **Unbounded never rises as N grows** *a survival curve*\
  Moving from day N to day N+1 removes the users whose last visit was day N and adds no one, so the curve holds flat when no user's last visit fell on day N.
- **Bounded can rise from one N to the next** *weekly rhythm*\
  A listener who plays every Saturday shows up on days 7 and 14 and is absent on days 8 through 13, so day 14 can beat day 10.
- **Bounded is final once day N is over** *no revisions*\
  After the cohort's day N has passed, no later visit by the user can change its exactly-day-N count.


<br>

### The unbounded figure keeps changing

Unbounded retention counts returns up to whatever date the query runs. On 2024-03-15 the 1 January cohort has 74 days of history, so its day-7-or-later figure counts visits from day 7 through day 74. A 1 March cohort has 14 days of history and is checked over days 7 to 14 only. Setting those 2 figures side by side compares windows of very different lengths, and the older cohort scores higher for reasons unrelated to the product. The same arithmetic revises old reports: a user whose first return comes on day 60 raises the 1 January cohort's unbounded day-7 figure 2 months after it was first published.

- **68 days** — return days counted, 1 Jan cohort
- **8 days** — return days counted, 1 Mar cohort


<br>

### Capping the window so cohorts compare

The repair gives every cohort the same window: count returns from day 7 through day 30, and include only cohorts whose day 30 has fully passed.

```sql
SELECT
  c.cohort_date,
  COUNT(DISTINCT c.user_id) AS cohort_size,
  COUNT(DISTINCT a.user_id) AS returned_day_7_to_30
FROM cohorts AS c
LEFT JOIN activity AS a
  ON a.user_id = c.user_id
    AND DATE_DIFF('day', c.cohort_date, a.event_date) BETWEEN 7
    AND 30
WHERE c.cohort_date < CURRENT_DATE - INTERVAL '30' DAY
GROUP BY c.cohort_date
ORDER BY c.cohort_date
```

This WHERE is safe where the one in the self-join section was harmful, because it tests only the cohort side: it removes whole cohorts, never the NULL rows of users who did not return. With today at 2024-03-15, current_date - INTERVAL '30' DAY is 14 February, so the latest cohort kept is 13 February, whose day 30 is 14 March, the last complete day. The strict < matters: the 14 February cohort's day 30 is today, and today is only half over. A capped unbounded figure is final once it appears, the same property bounded retention has.


<br>

### Which reading fits which product

| Product rhythm | Example | Reading that fits |
| --- | --- | --- |
| Daily habit | music streaming, messaging | bounded day N, or a narrow window such as days 6 to 8 |
| Weekly habit | grocery delivery, a weekly podcast | bounded week N, days 7 to 13 |
| Occasional need | travel booking, tax filing | unbounded, capped at a window the buying cycle allows |

Bounded retention asks whether the habit holds on a given day, so it suits products people are meant to use daily. Unbounded retention asks whether a user came back at all from some point on, which suits products used a few times a year, where a strict day 7 would score almost every healthy customer as lost. In an interview, name the reading before writing the comparison operator: "I'll read 'came back on day 7' as active on day 7 exactly, because listening is a daily habit. If you mean ever returned, I'd switch to day 7 through 30 so the cohorts compare."

> **TIP**
>
> One minus unbounded day-N retention is the share of the cohort whose last visit came before day N. Many teams call that churned by day N, so the same query yields a churn figure.


<br>

---

## Splitting Cohorts by Channel

"Which acquisition channel brings listeners who stay?" "Break D7 retention out by platform." "Compare free and premium users." Each is the self-join with a segment column added to GROUP BY. Adding it takes one line. Deciding which value of the segment each user carries is the part the question tests, because most segments change over a user's life.


<br>

### A segment that changes after the cohort date

Channel, plan, country and device all move. Attribution tables often keep only the latest touch, and plan tables only the current plan. Read as of today, the segment reflects what the user did after joining, and returning is the very behaviour that rewrites it: a listener who came back through a reminder email now has email as their latest channel. The animation reads both values from a sessions table for a cohort of 6 users who all joined on 5 February.

https://github.com/user-attachments/assets/9f7e08c9-a623-4ead-8892-45effa843257

min_by(channel, session_date) returns the channel on each user's earliest session and max_by the one on the latest. Users 21 and 24 arrived through paid social on 5 February and came back through email on 12 February, day 7. User 26 came back on day 7 through organic search, the channel that first brought them. Splitting day-7 retention by each column gives 2 different reports.

Split by signup_channel

| channel | users | returned | day-7 rate |
| --- | --- | --- | --- |
| email | 1 | 0 | 0% |
| organic | 1 | 1 | 100% |
| paid_social | 4 | 2 | 50% |

Split by latest_channel

| channel | users | returned | day-7 rate |
| --- | --- | --- | --- |
| email | 3 | 2 | 67% |
| organic | 1 | 1 | 100% |
| paid_social | 2 | 0 | 0% |

The latest-channel report says paid social retains no one and email retains 67%. Both claims come from relabelling. Every paid user who returned through an email moved into email, so the users left in paid social are, by construction, the ones who never came back. The segment absorbed the outcome it was meant to explain. Freezing the segment at the cohort date keeps the label independent of anything that happened afterwards, and only then does a retention gap between segments say something about the segments.


<br>

### Reading a segment as of the cohort date

When the segment lives in a history table, with a row per value and the dates it held, the frozen value comes from a point-in-time join: match on the user, and require the cohort date to fall inside the row's validity range.

![Schema diagram 1](_images/sql_pattern_retention_intermediate_diagram_1.png)

```sql
SELECT
  COALESCE(h.channel, 'unknown') AS signup_channel,
  COUNT(DISTINCT c.user_id) AS cohort_size,
  COUNT(DISTINCT a.user_id) AS returned_day_7
FROM cohorts AS c
LEFT JOIN channel_history AS h
  ON h.user_id = c.user_id
    AND c.cohort_date >= h.valid_from
    AND c.cohort_date < h.valid_to
LEFT JOIN activity AS a
  ON a.user_id = c.user_id
    AND DATE_DIFF('day', c.cohort_date, a.event_date) = 7
GROUP BY COALESCE(h.channel, 'unknown')
ORDER BY 1
```

Drop the 2 date conditions and users 21 and 24 each match 2 history rows, paid social and email. The cohort of 6 becomes 8 user-channel rows, both users count in both segments, and the segment sizes sum to 8. That gives a check worth running on every split: the sizes across segments must add up to the cohort size, because each user belongs to exactly 1 segment for a given cohort date. The LEFT JOIN and the 'unknown' label serve the same check from the other side, so a user with no history row still lands in a segment.


<br>

### Ties, thin segments and missing values

- Ties on day 0: a user with an ad click and an email click on the first day needs a rule, such as earliest timestamp, so min_by picks the same channel on every run.
- Thin segments: organic's 100% rests on 1 user. Report the user count beside every rate and suppress segments below a floor, such as 100 users.
- Missing values: users with no segment row fall out of an inner join. Keep them as unknown so segments still add up to the cohort.
- Crossed segments: 3 channels by 4 platforms is 12 cells per cohort, and each cell gets a twelfth of the users on average.

> What a complete answer covers
>
> - The segment value as of the cohort date, from first touch or a point-in-time join.
> - The reason: a current-value segment absorbs the return it is meant to explain.
> - A check that segment sizes sum to the cohort size.
> - User counts beside rates, and a floor for thin segments.

> **TIP**
>
> The rule covers any attribute a return can change: plan, device, country, app version. A question about how users behave after switching plans needs the plan at the start of each period instead, and the answer should say it measures something different from cohort retention.


<br>

---

## Aligning Cohorts to a Calendar

A matrix of daily cohorts runs to 365 rows a year, and for a product with a few hundred signups a day each row is noisy. Weekly or monthly cohorts pool those days, and the interview versions name the period: "build the weekly retention matrix", "week-1 retention for Q1's cohorts", "monthly cohorts for the last year". Grouping by calendar period forces 2 decisions the daily query never faced: how to count elapsed periods, and what to do with periods that have not finished.


<br>

### 2 ways to count week 1

**Elapsed alignment** counts whole weeks since each user's own first day: date_diff('week', first_seen, event_date) returns 0 for days 0 to 6 and 1 for days 7 to 13. **Calendar alignment** truncates both dates to the Monday that starts their week with date_trunc('week', ...) and counts the weeks between those Mondays. The animation applies both to 4 users who all fall in the cohort week of 15 January.

https://github.com/user-attachments/assets/e12f7583-fc36-44a9-9852-9da918ac10bb

User 31 joined on Sunday 21 January and came back the next day: elapsed week 0, calendar week 1. User 33 joined on Wednesday 17 January and returned 12 days later: elapsed week 1, calendar week 2. Under calendar alignment, week 0 lasts from the join day to Sunday, 7 days for a Monday joiner and 1 day for a Sunday joiner, so late-week joiners reach week 1 sooner and a cohort's week-1 rate shifts with the weekdays its signups fell on.

| ✓ Elapsed weeks from first day | ✗ Calendar weeks |
| --- | --- |
| • Every user gets a full 7-day week 0<br><br>• Week N means the same exposure for everyone<br><br>• A cell mixes calendar weeks, so a holiday spreads across 2 columns<br><br>• Fits product questions about habit formation | • Week 0 runs from the join day to Sunday, 1 to 7 days<br><br>• Each cell is one calendar week, so it lines up with releases and campaigns<br><br>• Week-1 rates shift with the weekday mix of signups<br><br>• Fits reporting that sits beside other weekly business metrics |


<br>

### Young cohorts and the unfinished diagonal

Whichever alignment the matrix uses, its newest cells are incomplete. Today is Friday 2024-03-15, so the calendar week of 11 March has run from Monday to Friday afternoon. Every cohort has 1 cell in that week, and together those cells form the diagonal along the right edge of the matrix.

| Cohort week | Users | Week 0 | Week 1 | Week 2 | Week 3 |
| --- | --- | --- | --- | --- | --- |
| 2024-02-19 | 1,200 | 100% | 41% | 35% | 19% (partial) |
| 2024-02-26 | 1,100 | 100% | 40% | 21% (partial) |  |
| 2024-03-04 | 1,300 | 100% | 23% (partial) |  |  |
| 2024-03-11 | 610 (partial) | 100% (partial) |  |  |  |

Read without the labels, week 2 falls from 35% to 21% between neighbouring cohorts and week 1 from 40% to 23%, which looks like a release that broke retention in early March. The fall is a weekend that has not happened yet and a Friday still in progress. The newest cohort is incomplete on both sides of its fraction: its 610 users are Monday-to-Friday signups, and its denominator keeps growing until Sunday.


<br>

### Masking cells that have not closed

```sql
WITH cohorts AS (
  SELECT
    user_id,
    DATE_TRUNC('week', MIN(event_date)) AS cohort_week
  FROM activity
  GROUP BY user_id
),
weekly AS (
  SELECT DISTINCT
    c.user_id,
    c.cohort_week,
    DATE_DIFF(
      'week',
      c.cohort_week,
      DATE_TRUNC('week', a.event_date)
    ) AS week_index
  FROM cohorts AS c
  JOIN activity AS a
    ON a.user_id = c.user_id
)

SELECT
  cohort_week,
  week_index,
  COUNT(*) AS active_users
FROM weekly
WHERE DATE_ADD('week', week_index + 1, cohort_week) <= DATE_TRUNC('week', CURRENT_DATE)
GROUP BY cohort_week, week_index
ORDER BY cohort_week, week_index
```

SELECT DISTINCT in weekly reduces activity to 1 row per user per week index, so COUNT(\*) counts users. The WHERE keeps a cell only when the week after it starts on or before the start of the current week, which as of 2024-03-15 is 11 March. All 4 partial cells in the matrix above drop out, including the whole 11 March cohort, whose week 0 is the current week. A daily matrix under elapsed alignment uses the same rule per day: day N of a cohort is complete when date_add('day', N + 1, cohort_date) <= current_date.


<br>

### Averaging a column of the matrix

A summary such as "week-2 retention across these cohorts" has to choose its rows before it divides. Pooling week 2 over the 19 February cohort alone gives 420 of 1,200, 35%. Letting the 26 February cohort's partial cell in adds 231 returners and 1,100 users and gives 651 of 2,300, 28.3%, a drop made entirely of an unfinished week. Treating the blank cells of younger cohorts as 0% is worse still, because it adds their users to the denominator with no chance to return. The blending rule applies with one more condition: numerator and denominator come from the same cohorts, and every one of those cohorts has closed the period being summarised.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Truncate the cohort and the event to the same period before counting periods between them<br><br>• Mask every cell whose period ends after the start of the current period<br><br>• Print cohort size on each row so a small or partial cohort is visible<br><br>• Summarise a column only over cohorts that have closed that period | • Read the right-edge diagonal as a trend; it is the current, unfinished period<br><br>• Fill a young cohort's future cells with 0%<br><br>• Mix calendar and elapsed alignment between the matrix and its summary<br><br>• Compare month-1 rates across months without noting that the months differ in length |

> **TIP**
>
> Monthly cohorts carry the same issue at a larger size. Under calendar alignment, month 1 for a 31 January signup starts the next day, and February 2024 had 29 days against March's 31, so month-1 windows differ between cohorts even under a single alignment.


<br>

---

## Putting It All Together

A music streaming app's growth team launches a paid social campaign in February and asks for a weekly report: day-7 retention by acquisition channel for each weekly cohort, plus 1 headline figure comparing February with January.

- The cohort self-join produces each listener's day-7 return, with the day test in ON so the campaign's non-returners stay in every cohort's size.
- The headline is pooled across users, so the flood of paid signups lowers it even if every channel holds steady; per-channel rates and a fixed-mix figure beside it show whether the product changed.
- Day 7 is read as exactly day 7 because listening is a daily habit, so each cohort's figure is final once its day 7 has passed.
- Channel comes from each listener's first session, so campaign users who return through an email stay credited to paid social.
- Weekly cohorts are calendar-aligned to match the rest of the weekly report, and the current week's cohort and cells stay masked until they close.


<br>

---

## Key Takeaways

- Retention is the cohorts CTE joined back to activity on user and elapsed days, with both conditions in a LEFT JOIN's ON clause and distinct counts on each side.
- An activity-side test placed in WHERE removes non-returners from the denominator; cohort size must not change with N.
- Averaging cohort rates weighs cohorts equally; pooling weighs users equally and moves with the acquisition mix, as Simpson's paradox shows.
- Exactly-day-N retention is final once day N passes and suits daily habits; day-N-or-later grows with time and needs a capped window and old-enough cohorts to compare.
- Segment each user by the value they had on their cohort date, and check that segment sizes add up to the cohort.
- Align periods by truncating both dates or by elapsed time, say which, and mask every cell whose period has not closed.
