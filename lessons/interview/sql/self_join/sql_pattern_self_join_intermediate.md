# Self-Join: Intermediate

You are 20 minutes into the SQL round at a fitness app. The interviewer pastes a schema, `follows(follower_id, followee_id)`, roughly 300 million rows.
'Give me every pair of users who follow each other.'
You start typing `FROM follows AS f1 JOIN follows AS f2`, and she adds a line: 'Before you run it, tell me how many rows come back for 2 people who follow each other.'
That line is the real question. The join hands back that pair from both sides, user 1 beside user 2 and then user 2 beside user 1, and the prompt never says whether that counts once or twice. The same gap sits under every disguise this round wears: users sharing a city, logins an hour apart, workouts whose times collide. She is scoring whether you decide what a single output row means, and what limits the pairs, before the join exists.


<br>

### What you will be able to do

Decide whether a pair question is ordered or unordered, and predict the row count each version returns

Rewrite a self-join to a per-group aggregate as a window function without changing how ties behave

Find links that point both ways in an edge table, including one stored as a log of follow and unfollow events

Pair each event with the same entity's other events inside a time limit, then settle ties and the window's edge

Write the 2-comparison overlap test, decide whether ends are inclusive (which settles touching intervals), and handle open-ended ones


<br>

---

## Ordered vs Unordered Pairs

Every pair question hides a decision the prompt rarely states: is (A, B) the same answer as (B, A)? 'Users in the same city' is unordered, because sharing a city runs both ways. 'User A referred user B' is ordered, because reversing it states a different fact. The answer sets the join condition and the row count, and the row count is the number the interviewer will ask you to predict.

| Extra condition after the city match | Rows for a city of k users | Austin, k = 3 |
| --- | --- | --- |
| none | k \* k | 9 |
| `u1.user_id <> u2.user_id` | k \* (k - 1) | 6 |
| `u1.user_id < u2.user_id` | k \* (k - 1) / 2 | 3 |

With nothing added, every user pairs with themselves and every real pair arrives twice. `<>` drops the self-pairs and keeps both orders, which fits an ordered question. `<` drops the self-pairs and keeps 1 order, the one with the smaller id on the left, which fits an unordered question. Only the strict `<` returns each pair exactly once.

Say the count before running anything: 'Austin has 3 users, so I expect 3 Austin rows, and without the inequality I would get 9.' A predicted count turns the first run into a check, and an interviewer who hears it knows the result will be verified rather than trusted.

In the run below, 4 users live in 2 cities. Carol lives alone in Denver; Alice and Bob live in Austin, and so does Erin. The query returns 3 rows, all for Austin, because a city of 1 user has no partner to pair with. Watch the comparisons that fail. Alice against Alice fails `<`, and of the mirrored pair Alice with Bob and Bob with Alice, only the row with Alice on the left survives.

https://github.com/user-attachments/assets/ea9b4658-ea51-4dd1-870b-060740ef04eb


<br>

### DISTINCT cannot fix a mirrored pair

The reflex after a doubled result is `SELECT DISTINCT`. It changes nothing here, because (Alice, Bob) and (Bob, Alice) are different tuples and both survive. Interviewers ask about it for exactly that reason. A mirrored pair has to be made canonical, either by the inequality in the join or by ordering the 2 values inside each row.

Ordering inside the row is the tool when the stored data has a direction and the question does not. A messages table records sender and recipient, and 'how many messages has each pair of users exchanged' treats Alice-to-Bob and Bob-to-Alice as a single conversation. `LEAST` and `GREATEST` put the smaller id first on every row, so both directions land in the same group.

```sql
SELECT
  LEAST(sender_id, recipient_id) AS user_a,
  GREATEST(sender_id, recipient_id) AS user_b,
  COUNT(*) AS messages
FROM messages
GROUP BY LEAST(sender_id, recipient_id), GREATEST(sender_id, recipient_id)
```


<br>

### The tiebreaker column has to be unique

`<` deduplicates only because no 2 rows hold the same value in the compared column. Swap `user_id` for `name`, and 2 Austin users both called Sam compare as equal: their pair fails `<` and drops out of the result without an error. The sentence to say aloud is that the tiebreaker is the primary key, or a column whose uniqueness constraint you can point to. Handed a table with no unique column, ask whether one exists, and if it doesn't, number the rows with `ROW_NUMBER()` in a CTE first.

| ✓ Unordered: dedupe with < | ✗ Ordered: keep the direction |
| --- | --- |
| • Users who live in the same city<br><br>• Logins by one user within an hour of each other<br><br>• Workouts whose time ranges overlap<br><br>• Products bought together in one order | • User A referred user B<br><br>• User A follows user B<br><br>• Order O1 was replaced by order O2<br><br>• Both orders wanted: use <> and accept 2 rows per pair |

In an ordered question the direction usually lives in the keys, and no inequality is needed. 'Users referred by someone in their own city' joins on `u2.referred_by = u1.user_id AND u2.city = u1.city`, so u1 plays referrer and u2 plays the referred user. Adding `u1.user_id < u2.user_id` there would silently drop any referral where the referrer holds the larger id, a wrong answer that looks tidy.

Occasionally the self-pair is the finding. An account that referred itself is a fraud signal, and catching it takes no join at all, only `WHERE referred_by = user_id`.


<br>

### Follow-ups on this part

> Questions that test whether the choice was deliberate
>
> - 'How many rows for a city of 1,000 users?' Unordered: 499,500. Ordered: 999,000. With no inequality: 1,000,000.
> - 'Now return triples.' Chain the key as `u1.user_id < u2.user_id AND u2.user_id < u3.user_id` and each set of 3 appears once.
> - 'Why not `<=`?' It keeps every user paired with themselves, the exact rows the inequality was there to remove.
> - 'The product team wants both directions.' Switch to `<>`: self-pairs stay out and each pair returns twice on purpose.

- **166,167,000** — unordered triples in a city of 1,000

> **TIP**
>
> Before typing the join, say: 'Is (A, B) the same answer as (B, A)? I will treat it as unordered and use < on the primary key.' One sentence fixes the expected row count and shows the choice was made on purpose.


<br>

---

## Self-Join vs Window Function

This part arrives as 'list every workout longer than that user's average' or 'return each user's longest run'. The answer most people learned first joins the table to an aggregate of itself: an average per user in a subquery, joined back on `user_id`. That is a self-join with one side collapsed to 1 row per group, and the interviewer's next line is usually 'can you do that without the join?'

```sql
SELECT
  w.workout_id,
  w.user_id,
  w.minutes,
  u.avg_minutes
FROM workouts AS w
JOIN (
  SELECT
    user_id,
    AVG(minutes) AS avg_minutes
  FROM workouts
  GROUP BY user_id
) AS u
  ON u.user_id = w.user_id
WHERE w.minutes > u.avg_minutes
```

```sql
SELECT
  workout_id,
  user_id,
  minutes,
  avg_minutes
FROM (
  SELECT
    workout_id,
    user_id,
    minutes,
    AVG(minutes) OVER (
      PARTITION BY user_id
    ) AS avg_minutes
  FROM workouts
) AS t
WHERE minutes > avg_minutes
```

The window version reads `workouts` once and has no join. The self-join reads it twice, builds the grouped result, then matches it back, and on a distributed engine that join is an extra shuffle or broadcast of the aggregate. The window computes the average inside the partition it already formed on `user_id`. Say that the rewrite removes the second read and the join, because 'it's cleaner' is the answer the interviewer hears most and scores least.

The outer query is part of the answer. `WHERE` runs before window functions are computed, so `WHERE minutes > AVG(minutes) OVER (...)` is an error on every engine. The filter goes in a wrapping query or a CTE. Some warehouses add `QUALIFY` for exactly this, but write the portable form unless the interviewer names the engine.


<br>

### When the rewrite applies

The conversion is safe when the aggregate covers rows that share a key with the current row, the output keeps 1 row per input row, and the answer needs nothing from a particular partner row beyond what the aggregate returns. Any per-group aggregate passes, whether it is an average, a total, a maximum, a count or a rank. A pair result fails, since it needs columns from both rows side by side and can return several partners for one row.


<br>

### Ties change which window function is correct

'Each user's longest workout' hides a trap in the rewrite. Joining back to `MAX(minutes)` returns every workout tied at the maximum. `ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY minutes DESC) = 1` returns exactly 1, and that same `ORDER BY` decides which tied row it keeps, arbitrarily unless a tiebreak column follows `minutes DESC`. `RANK()` over the same window, or `minutes = MAX(minutes) OVER (PARTITION BY user_id)`, keeps the tie behaviour of the original join. Leave `ORDER BY minutes DESC` out of the `RANK()` window and every row ranks 1. User 7 below has 2 workouts of 45 minutes.

| workout_id | minutes | Join to MAX | ROW_NUMBER() = 1 | RANK() = 1 |
| --- | --- | --- | --- | --- |
| 11 | 45 | kept | kept (or 12) | kept |
| 12 | 45 | kept | dropped (or 11) | kept |
| 13 | 30 | dropped | dropped | dropped |

A silent change from 2 rows to 1 is the follow-up interviewers use to check whether the rewrite was understood or memorized. Say which the question wants, 'every longest workout' or 'one per user, newest wins', and put the tiebreak in the `ORDER BY` if it is the second.


<br>

### Adjacent rows: LAG against the self-join

The other common rewrite is 'compare each workout with the user's previous one'. As a self-join, 'previous' means 'the latest earlier row', which needs a `NOT EXISTS` or a correlated `MAX` on top of the join, so each row is matched to all its predecessors before all but one are thrown away. `LAG(minutes) OVER (PARTITION BY user_id ORDER BY started_at)` does it in one sorted pass. Keep the self-join when the partner is chosen by a condition instead of a position: every earlier workout within 7 days, or every earlier workout that ran longer.

```sql
SELECT
  cur.workout_id,
  cur.minutes,
  prev.minutes AS prev_minutes
FROM workouts AS cur
LEFT JOIN workouts AS prev
  ON prev.user_id = cur.user_id
    AND prev.started_at < cur.started_at
WHERE NOT EXISTS (
  SELECT
    1
  FROM workouts AS mid
  WHERE mid.user_id = cur.user_id
    AND mid.started_at < cur.started_at
    AND mid.started_at > prev.started_at
)
```

| ✓ Rewrite as a window function | ✗ Keep the self-join |
| --- | --- |
| • The partner is the group's aggregate: average, max, total, count<br><br>• The partner is a fixed offset: previous, next, 3 rows back<br><br>• The output keeps 1 row per input row<br><br>• Saves the second read and the join | • The output is pairs with columns from both rows<br><br>• The partner is chosen by a predicate, not a position<br><br>• One row may match several partners<br><br>• The match crosses columns, like follower to followee |


<br>

### The rewrite in 3 sentences

Delivered aloud: 'The subquery computes 1 value per user and joins it back to every row for that user. A window function with `PARTITION BY user_id` attaches that value to each row with no join, so the table is read once. I wrap it in an outer query because a window column cannot be filtered in `WHERE`.' Each sentence covers 1 thing this follow-up is scored on, and the third is the execution-order catch.

> **TIP**
>
> 'Is the window always faster?' Usually, and say what it removes instead of promising a speedup. Then name the exception: if a per-user summary table is already materialized, joining to it reads a small table instead of aggregating a large one, and the self-join can win.


<br>

---

## Mutual Follows in an Edge Table

The edge-table version arrives as 'find mutual follows', 'find accounts that sent each other money', or 'find users who each blocked the other'. One table stores directed links, so a link that points both ways is 2 rows, (1, 2) and (2, 1). The self-join pairs each edge with its reverse, and what the interviewer watches is whether the condition swaps the columns.

The `follows` table below holds 6 edges. Users 1 and 2 follow each other, and so do 3 and 4; the edges from 1 to 3 and from 2 to 3 have no reverse. The condition `f1.follower_id = f2.followee_id AND f1.followee_id = f2.follower_id` crosses the columns. The last line keeps the copy of each mutual pair whose smaller id leads, and without it the result has 4 rows, each mutual pair once from each of its edges.

https://github.com/user-attachments/assets/392cd550-1a3d-4de1-a6a4-a6e8d8818d56

The result is 2 rows: (1, 2) and (3, 4). Note where the `<` reads: both its sides come from `f1`, because the pair's identity lives on 1 edge, and the reverse edge only confirms it exists. A self-follow row such as (5, 5) matches itself as its own reverse, and the same `<` removes it along with the mirrored copies.


<br>

### This join cannot explode

Both ends of the edge sit in the equality, so if `(follower_id, followee_id)` is unique, each edge matches at most 1 reverse edge. The output can never exceed the edge count, even for an account with 80 million followers. Say that when scale comes up. The risk in graph self-joins belongs to queries that join on only one end of the edge, like 'pairs of users who follow the same account', where an account with d followers produces d \* (d - 1) / 2 candidate pairs.

- **3.2 quadrillion** — co-follower pairs under one 80M account


<br>

### Links that point only one way

'Who follows user 3 without being followed back?' is the same join turned inside out. `LEFT JOIN` to the reverse edge and keep the rows where nothing matched. Testing a key column of `f2` for NULL is safe, because a matched row never has a NULL key; testing a nullable column would mix 'no match' with 'matched a NULL'. On the sample it returns users 1 and 2, and user 4 is followed back.

```sql
SELECT
  f1.follower_id AS fan
FROM follows AS f1
LEFT JOIN follows AS f2
  ON f2.follower_id = f1.followee_id
    AND f2.followee_id = f1.follower_id
WHERE f1.followee_id = 3
  AND f2.follower_id IS NULL
```


<br>

### Ask what kind of table it is

Duplicate edges change the answer: a re-follow that inserted a second (1, 2) row doubles every mutual pair it touches, so dedupe before the join or confirm the key exists. An event log changes it too. When each row is a follow or unfollow action, you need current state first: the latest action per edge, kept only when that action is a follow. 'Is this current state or a log?' is the question that keeps people who unfollowed last year out of the answer.

```sql
WITH current_follows AS (
  SELECT
    follower_id,
    followee_id
  FROM (
    SELECT
      follower_id,
      followee_id,
      action,
      ROW_NUMBER() OVER (
        PARTITION BY follower_id, followee_id
        ORDER BY action_at DESC
      ) AS rn
    FROM follow_events
  ) AS t
  WHERE rn = 1
    AND action = 'follow'
)

SELECT
  f1.follower_id AS user_a,
  f1.followee_id AS user_b
FROM current_follows AS f1
JOIN current_follows AS f2
  ON f1.follower_id = f2.followee_id
    AND f1.followee_id = f2.follower_id
    AND f1.follower_id < f1.followee_id
```


<br>

### The variants that come next

> Follow-ups on the edge table
>
> - 'Count mutuals per user.' Remove the `<` so every user appears on the left of each of their mutual pairs, then `GROUP BY f1.follower_id`.
> - 'Users with at least one mutual.' `EXISTS` on the reverse edge returns each user once, with no pairs to collapse.
> - 'Mutual follows inside one city.' Join `users` once for each end of the edge and require the 2 cities to match; the `<` stays on the edge.

The no-join answer deserves a sentence, because it is shorter and interviewers probe what it assumes: group by `LEAST(follower_id, followee_id)` and `GREATEST(follower_id, followee_id)`, then keep `HAVING COUNT(*) = 2`. It is correct only when edges are unique, since a duplicated one-way edge also counts 2 and passes as mutual.

Some schemas sidestep the question by storing each friendship once, as (smaller_id, larger_id). Mutuality is then built into every row, and the cost moves elsewhere: listing user 3's friends reads both columns, `WHERE smaller_id = 3 OR larger_id = 3`. Saying which storage you would pick, and what each one makes cheap, is a strong close to this part.


<br>

---

## Pairing Events in a Time Window

Time-window pairs come in several disguises: 'flag logins from 2 countries within an hour', 'find the same card charged the same amount twice inside 2 minutes', 'find carts deleted and rebuilt within 10 minutes'. Underneath, each matches an entity's rows to that entity's other rows whose timestamps fall inside a limit. Security teams call the first one impossible travel, and using the name tells the interviewer you have seen the real alert.

```sql
SELECT
  l1.user_id,
  l1.login_id AS first_login,
  l2.login_id AS second_login,
  l1.country AS first_country,
  l2.country AS second_country
FROM logins AS l1
JOIN logins AS l2
  ON l2.user_id = l1.user_id
    AND l2.login_time > l1.login_time
    AND l2.login_time <= l1.login_time + INTERVAL '60' MINUTE
    AND l2.country <> l1.country
```

The equality on `user_id` keeps every pair inside one account. `l2.login_time > l1.login_time` is the direction: it drops a login paired with itself and returns each pair once, earlier login on the left, the time-ordered version of `<` on an id. The upper bound turns 'every later login' into 'every later login within the hour'. The country test is the business rule, the line that changes most from one disguise to the next.

logins for user 7

Result

Only 1 pair survives. Logins 101 and 103 differ in country but sit 75 minutes apart. Logins 103 and 104 fail the other test because they share a country. Tracing a sample like this aloud, row by row, is the check the interviewer would otherwise ask for.

The payments disguise adds equalities: same `card_id`, same `amount`, within 2 minutes. Every extra equality joins the key the engine hashes on, which narrows each bucket before any time comparison runs. Sorting the conditions into equalities and ranges is half of reading this question well.


<br>

### Ties and the edge of the window

`>` silently drops 2 logins with identical timestamps, and machine-generated events tie constantly at second precision. When ties must pair, extend the direction with the key, so the smaller id leads when the times match. The upper bound needs the same scrutiny: `<=` keeps a gap of exactly 60 minutes and `<` does not. The spec almost never says which, so ask, then make the choice visible in the code.

```sql
 AND (
      l2.login_time > l1.login_time
   OR (l2.login_time = l1.login_time AND l2.login_id > l1.login_id)
 )
```


<br>

### The cost sits in one hot user

The engine hashes or sorts on `user_id`, then tests the time conditions within each user's rows. A typical user with 6 logins a day costs almost nothing. A credential-stuffing bot with 50,000 attempts in a day is one hot key, and an engine without a range-aware join plan compares its attempts pairwise before the window discards nearly all of them.

- **1.25 billion** — pair checks for one 50,000-event user

When pushed on scale, filter before the join whatever the question allows, such as successful logins or the last 7 days, so the hot key shrinks before pairing. And if only the nearest event matters, compare with `LAG`, which costs one sorted pass no matter how many logins the user has.

If the question is a count, 'how many logins did this user make in the hour before each login', a window frame answers without pairing: `COUNT(*) OVER (PARTITION BY user_id ORDER BY login_time RANGE BETWEEN INTERVAL '60' MINUTE PRECEDING AND CURRENT ROW)`, on engines that accept interval offsets in a `RANGE` frame, PostgreSQL among them.


<br>

### Pairs or flags

Read what the output row is. 'Return the pairs' needs the join. 'Flag each login that had a foreign login within an hour of it' wants 1 row per login, and the join returns 1 per match, so a login with 3 matches appears 3 times. `EXISTS` returns each login once. It also looks both ways in time, so the directional `>` disappears and the window becomes 60 minutes either side. On the sample it flags 102 and 103.

```sql
SELECT
  l1.login_id,
  l1.user_id,
  l1.login_time
FROM logins AS l1
WHERE EXISTS (
  SELECT
    1
  FROM logins AS l2
  WHERE l2.user_id = l1.user_id
    AND l2.country <> l1.country
    AND l2.login_time >= l1.login_time - INTERVAL '60' MINUTE
    AND l2.login_time <= l1.login_time + INTERVAL '60' MINUTE
)
```

> **TIP**
>
> Narrate the ON clause as you type it: 'same user, later login, within 60 minutes, different country'. Each phrase is one line of code, so the interviewer can check your reading of the requirement against the query as it appears.


<br>

---

## Finding Overlapping Intervals

Interval questions arrive as 'find double-booked rooms', 'find overlapping shifts for the same nurse', 'find subscription periods billed twice', or, at a fitness app, 'find workouts recorded twice, once by the watch and once by the phone'. Each row has a start and an end, and the task is every pair of rows for the same entity whose ranges share any time.


<br>

### 2 comparisons cover every case

Candidates who sketch a timeline start listing shapes: B starts inside A, B ends inside A, B sits inside A, A sits inside B. Writing those as 4 OR branches invites bugs, because one branch is always the one forgotten. Reason from the opposite instead. Intervals A and B miss each other only when one ends before the other starts, and negating that gives 2 comparisons that cover all 4 shapes.

```sql
NOT (a.end_time <= b.start_time OR b.end_time <= a.start_time)

a.end_time > b.start_time AND b.end_time > a.start_time

a.start_time < b.end_time AND b.start_time < a.end_time
```

The run below holds user 7's 4 workouts from one day, so it leaves out the `a.user_id = b.user_id` line the full query has, and it returns 1 pair. Workouts 1 and 2 are the double log: the phone started 2 minutes after the watch and stopped 1 minute before it, so workout 2 sits wholly inside workout 1, the shape the branch-by-branch version tends to miss. Workouts 3 and 4 touch at 18:30 and are left out, because strict `<` reads an end and a start at the same minute as back to back.

https://github.com/user-attachments/assets/de570aea-d52b-407b-aff0-72201860316a


<br>

### Boundary decisions the spec leaves open

> Settle these before the query is final
>
> - Touching ends: strict `<` treats 18:30 to 18:30 as back to back. Use `<=` only if sharing an instant counts as a clash.
> - Self-match: `a.workout_id < b.workout_id` stops a row overlapping itself and returns each overlapping pair once.
> - Entity scope: the `user_id` equality keeps the query from testing every interval in the table against every other.

The open interval costs the most in practice. A workout still in progress, a subscription with no end date, a shift not yet clocked out: all store NULL, and `b.start_time < NULL` is unknown, which an inner join treats as false. The live session of a user double-logging right now never appears, and the query reports nothing wrong. Close the interval at the present moment and say which value you chose.

```sql
 AND a.start_time < COALESCE(b.end_time, CURRENT_TIMESTAMP)
 AND b.start_time < COALESCE(a.end_time, CURRENT_TIMESTAMP)
```

Date-grained intervals raise one more question: is the end inclusive? A subscription stored as 2024-03-01 to 2024-03-31 usually covers the 31st, so a second period starting on 2024-03-31 overlaps it, and strict `<` misses it. With inclusive end dates the test becomes `a.start_date <= b.end_date AND b.start_date <= a.end_date`. Half-open ranges, where the end is the first moment not covered, keep the strict form and are the convention worth proposing.


<br>

### BETWEEN finds only half the overlaps

A version that turns up often is `b.start_time BETWEEN a.start_time AND a.end_time`. It finds B starting inside A and misses A starting inside B. Paired with `a.workout_id < b.workout_id`, which fixes which row plays A, it drops every overlap where the lower-id interval starts second. Renumber the sample so the phone's workout from 07:02 has id 1 and the watch's workout from 07:00 has id 2, and the double log vanishes. The 2-comparison test does not care which row is called A.

One follow-up marks where this pattern ends: 'now merge each user's overlapping workouts into a single row'. Merging a chain of overlaps is a gaps-and-islands problem built on window functions, because a pairwise join sees only 2 intervals at a time and a chain can run to any length. Name the switch instead of stacking more self-joins.

> **TIP**
>
> Derive the overlap test aloud from its negation: 'they miss when one ends before the other starts, so they overlap when each starts before the other ends.' Interviewers trust a condition they watched you derive far more than one recited.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Ask whether (A, B) and (B, A) are the same answer before writing the join<br><br>• Dedupe unordered pairs with < on the primary key<br><br>• Keep the entity equality in the ON clause, next to the direction and window-bound comparisons<br><br>• Predict the output row count aloud, then check it against the result<br><br>• Test overlap with a.start_time < b.end_time AND b.start_time < a.end_time | • Reach for DISTINCT to remove mirrored pairs; it sees (A, B) and (B, A) as different rows<br><br>• Break the tie on a non-unique column such as name<br><br>• Join a table to its own per-group aggregate when a window function returns the same rows<br><br>• Compare a NULL end time without COALESCE; the open interval vanishes<br><br>• Return 1 row per match when the question asks for 1 row per event |


<br>

---

## Putting It All Together

A fitness app ranks each user weekly against their friends, defined as mutual follows, by total minutes trained. Support tickets say some users sit far too high, and a first look shows the same morning runs counted twice, once from a watch and once from a phone, plus a few accounts that look shared between people in different countries.

- Friends come from the follows self-join with crossed columns, and the < stays off here, because each user needs every friend on their own side of the row.
- Double-logged workouts are overlapping intervals for one user; the overlap pairs, each listed once by workout_id , decide which row to drop before minutes are summed.
- Workouts still in progress have a NULL end, so the overlap test wraps it in COALESCE or the live duplicate escapes.
- The 'trained more than their own weekly average' badge attaches AVG ( minutes ) OVER ( PARTITION BY user_id ) to each workout instead of joining a grouped copy back.
- Shared accounts show up as logins from 2 countries inside an hour, the time-window self-join with a direction and a bound.


<br>

---

## Key Takeaways

- Decide ordered or unordered first: < on a unique key returns each unordered pair once, <> keeps both directions, and DISTINCT fixes neither.
- A self-join to a per-group aggregate becomes a window function when the output keeps 1 row per input row, and then the table is read once and never joined.
- Mutual links cross the columns in the join, and a log of follow and unfollow events needs current state before the self-join.
- Time-window pairs put the entity equality in the ON clause beside the direction and bound comparisons; ask about ties and the window's edge.
- Overlap is a . start < b . end AND b . start < a . end ; settle touching ends and NULL ends before calling the query done.
