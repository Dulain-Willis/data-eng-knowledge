# Prefix Sum: Intermediate

Ines is 40 minutes into a data engineering loop at Stripe when the interviewer pastes a list of signed integers: one merchant's net balance change per minute, refunds negative, captures positive. How many contiguous stretches of minutes net to exactly 3,000 cents? She reaches for a sliding window, then stops: refunds make the running total fall as well as rise, so shrinking the window from the left no longer moves the sum in one direction. Then come the follow-ups. Fee adjustments must be applied to whole ranges of minutes at once, and the dashboard needs a 7-day rolling refund total per merchant. Every part is one idea: compare a running total with an earlier running total, and store the earlier ones in the structure the question needs. This lesson builds that idea until each disguise reads as the same question.


<br>

### What you will be able to do

Count and measure subarrays with a target sum in O(n) by pairing a running total with a dict, and decide what the dict stores: counts, or the first or latest index of each prefix

Answer range XOR queries in O(1) and count subarrays by XOR value, including the bitmask form for parity questions

Apply range updates in O(1) each with a difference array sized so the last slot never raises IndexError, with inclusive or exclusive ends chosen on purpose

Recode balance questions on strings into zero-sum questions, including the tuple key for 3 or more symbols

Predict how cumulative sums and rolling sums, including SQL window frames, behave when timestamps tie or days go missing, and what happens on a table with no partitioning


<br>

---

## Prefix Sums with a Hash Map

Interviewers phrase this pattern many ways: count the subarrays that sum to k, find the longest run of days whose net change is zero, count the windows of a ledger that balance. Three features mark it. The range is contiguous, the target is an exact sum, and the values can be negative. That last feature rules out the sliding window. With nonnegative values, growing a window can only raise its sum and shrinking it can only lower it, so 2 pointers can chase a target. One negative value breaks that ordering, and the pointers no longer know which way to move.


<br>

### Turning a range question into a lookup

Let P[i] be the sum of the first i values, with P[0] = 0. The sum of nums[i..j] is P[j + 1] - P[i]. A subarray ending at index j sums to k exactly when some earlier prefix equals P[j + 1] - k. The question 'which start points work?' becomes 'how many earlier prefixes had this value?', and a dict answers that in O(1) average time. The result is one left-to-right pass with a lookup and an insert per element: O(n) time and up to n + 1 keys in memory, against O(n^2) for summing every pair of endpoints.

- **5,000,050,000** — subarrays to check at n = 100,000
- **100,000** — dict lookups in the one-pass scan

| index | x | prefix | needs | times seen | count | new subarrays |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 2 | 2 | -1 | 0 | 0 | none |
| 1 | -1 | 1 | -2 | 0 | 0 | none |
| 2 | 3 | 4 | 1 | 1 | 1 | [3] |
| 3 | -2 | 2 | -1 | 0 | 1 | none |
| 4 | 1 | 3 | 0 | 1 | 2 | [2, -1, 3, -2, 1] |
| 5 | 2 | 5 | 2 | 2 | 4 | [-1, 3, -2, 1, 2] and [1, 2] |

Index 5 is the row to study. Prefix 2 had already occurred after index 0 and again after index 3, so 2 different start points close a subarray summing to 3 there and the count jumps by 2. That is why the map stores how many times each prefix occurred. A set would record that 2 had appeared, lose the second start point, and return 3 instead of 4.

https://github.com/user-attachments/assets/6173153d-00f5-463f-bd8c-c383dde28e8b

*Each step looks up prefix - k, then records the current prefix*

Predict the final printed dict before you play it. Prefix 2 occurs twice, so its value is 2, and every other prefix occurs once, including the seed 0. The seed is the empty prefix before index 0. Delete it and the subarray [2, -1, 3, -2, 1], which starts at index 0, is never counted, so the function returns 3.


<br>

### Two lines whose order changes the answer

The loop looks up, then inserts. Swap the 2 lines and the current prefix is already in the map when you ask for prefix - k. For any nonzero k nothing changes, since a prefix minus a nonzero k never equals itself. For k = 0 the swap counts every position against itself as an empty subarray: on nums = [0] with k = 0, lookup-first returns 1 and insert-first returns 2. A k = 0 test case is the cheapest way for an interviewer to check whether you thought about this.

```sql
nums = [2, -1, 3, -2, 1, 2]
k = 3
seen = {0: 1}
prefix = 0
count = 0
for x in nums:
    prefix += x
    count += seen[prefix - k]
    seen[prefix] = seen.get(prefix, 0) + 1
print(count)
```

This version never reaches the print. On the first element the prefix is 2, the lookup asks for key -1, which was never inserted, and the program stops with KeyError: -1. A defaultdict(int) avoids the crash with a side effect: reading a missing key inserts it with value 0, so every failed lookup adds an entry and the map grows past the n + 1 prefixes it needs. seen.get(prefix - k, 0) reads without writing.


<br>

### What the map stores depends on the question

| question | map value | seed | update rule |
| --- | --- | --- | --- |
| How many subarrays sum to k? | count of each prefix | {0: 1} | increment every time |
| Longest subarray summing to k? | first index of each prefix | {0: -1} | insert only if absent |
| Shortest subarray summing to k? | latest index of each prefix | {0: -1} | overwrite every time |
| Does any subarray sum to k? | membership of each prefix | {0} | add to a set |

For the longest variant, a match ending at index j has length j minus the stored index, so you want the earliest start: store the first index and never overwrite it. On the same list with k = 3, prefix 2 first appeared at index 0, so the match ending at index 5 covers indices 1 to 5, length 5. Overwriting with index 3 would measure that match as length 2, which is the rule for the shortest variant and the wrong one here. The seed index -1 lets a match against the empty prefix measure from the start: at index 4, the needed prefix 0 is stored at -1, length 5 again.

> **TIP**
>
> When the problem statement allows negative values, read it as a pointer toward prefix sums with a hash map: negatives are the detail that disqualifies the sliding window, and saying so early shows the interviewer you know why.


<br>

---

## Prefix XOR: The Bitwise Sibling

Prefix sums work because subtraction undoes addition. XOR undoes itself (a ^ a == 0 and a ^ 0 == a), and because the operation is also associative and commutative, a running XOR has the same shape as a running sum. Define X[0] = 0 and X[i + 1] = X[i] ^ arr[i]. The XOR of arr[l..r] is X[r + 1] ^ X[l], because every element before l appears in both prefixes and cancels.

| i | arr[i] | arr[i] in binary | X[i + 1] | X[i + 1] in binary |
| --- | --- | --- | --- | --- |
| 0 | 3 | 011 | 3 | 011 |
| 1 | 5 | 101 | 6 | 110 |
| 2 | 6 | 110 | 0 | 000 |
| 3 | 1 | 001 | 1 | 001 |
| 4 | 7 | 111 | 6 | 110 |

Query the XOR of indices 1 to 3: X[4] ^ X[1] is 1 ^ 3, which is 2. Direct check: 5 ^ 6 is 3, and 3 ^ 1 is 2. Every query costs one XOR whatever its length, after an O(n) build. The table also shows cancellation at work: X[3] is 0 because 3 ^ 5 ^ 6 is 0, and X[5] equals X[2] because indices 2 to 4 XOR to 0.


<br>

### Counting subarrays by XOR value

Counting mirrors the sum version with one operator swapped. A subarray ending at j has XOR k when an earlier prefix satisfies X[i] ^ X[j + 1] == k, which rearranges to X[i] == X[j + 1] ^ k. The lookup key changes from prefix - k to prefix ^ k. The seed and the frequency map carry over unchanged, and so does the lookup-then-insert order.

https://github.com/user-attachments/assets/dd1800c4-1db6-40b5-bb14-13b73a0058cf

*Subarrays with XOR 6, found by looking up prefix ^ k*

Four subarrays have XOR 6: [3, 5], [6], [1, 7] and the whole list. The final step adds 2 at once, because prefix 6 looks for an earlier 0, and 0 occurred twice: once as the seed, once after index 2. Prefix XOR has no sliding-window shortcut even when every value is positive: adding an element can raise or lower a running XOR, so no pointer move is ever safe.


<br>

### The disguise: parity as a bitmask

A common disguise asks for the longest substring in which every vowel appears an even number of times. Give each vowel a bit: a = 1, e = 2, i = 4, o = 8, u = 16. XOR the vowel's bit into a running mask at each character, and a bit is 1 exactly when its vowel has appeared an odd number of times so far. A substring has all even counts when the masks at its 2 ends are equal. Store where each mask first occurred, seeded with mask 0 at index -1, and measure each repeat against that earliest position. Here is s = 'aebbea', with the e bit on the left.

| index | char | mask | first index of mask | length |
| --- | --- | --- | --- | --- |
| start | none | 00 | -1 (seed) | none |
| 0 | a | 01 | 0 | new mask |
| 1 | e | 11 | 1 | new mask |
| 2 | b | 11 | 1 | 1 (b) |
| 3 | b | 11 | 1 | 2 (bb) |
| 4 | e | 01 | 0 | 4 (ebbe) |
| 5 | a | 00 | -1 | 6 (aebbea) |

The answer is 6: the whole string holds 2 a's and 2 e's. The map never holds more than 32 keys, one per possible mask, so memory stays constant however long the string grows. The move applies whenever a question asks about the parity of several counts at once: give each event type a bit and compare masks.


<br>

### Where prefix XOR shows up in pipelines

Data reconciliation uses the same identity. Hash each row to a 64-bit integer. With the source and its replica both sorted by primary key, store the running XOR beside each key. The fingerprint of any key range is the XOR of 2 stored prefixes, so comparing the tables becomes a binary search: compare the 2 halves' fingerprints, descend into the half that differs, and locate a single divergent row among 1,000,000 in about 20 rounds. The price is a blind spot. XOR cancels pairs, so a row written 3 times into the replica XORs to the same value as one copy, and the range holding that defect reads as matching. A sum of hashes modulo 2^64 sees the extra copies, and pays with the subtraction bookkeeping that XOR let you skip.

Python builds the whole X array in one call: list(accumulate(arr, operator.xor, initial=0)) on [3, 5, 6, 1, 7] returns [0, 3, 6, 0, 1, 6], the prefix column above with its seed in front.

| ✓ Prefix sum | ✗ Prefix XOR |
| --- | --- |
| • Inverse is subtraction: range = P[r + 1] - P[l]<br><br>• Lookup key for target k: prefix - k<br><br>• Totals grow with the input and can overflow fixed-width columns<br><br>• Duplicate rows add up and stay visible | • Inverse is XOR itself: range = X[r + 1] ^ X[l]<br><br>• Lookup key for target k: prefix ^ k<br><br>• Results never exceed the bit width of the inputs<br><br>• Duplicate pairs cancel and disappear |


<br>

---

## Difference Arrays for O(1) Updates

Now reverse the workload: many range writes, one read at the end. Add 10 to slots 0 through 2, add 5 to slots 1 through 4, add 20 to slot 3, then report the array. Applying each update slot by slot costs the length of its range, so m updates over n slots cost O(m \* n) in the worst case. At 10,000 updates that each span 1,000,000 slots, that is 10 billion writes.

- **20,000** — diff writes for those 10,000 updates
- **1,020,000** — operations with a difference array

A difference array records the change between neighbouring slots: diff[i] holds a[i] - a[i - 1]. Adding v to slots l through r takes 2 writes, diff[l] += v and diff[r + 1] -= v. The running sum of diff picks up v at l and carries it forward until it drops off right after r. With 2 writes per update and one prefix-sum pass to rebuild the array, the total is O(m + n).

https://github.com/user-attachments/assets/8827aa7a-6965-4d82-883c-db70da76ef03

*Three range updates as 6 boundary writes, then one rebuild*

The first 3 printed lists show each update landing as 2 entries. The third, [10, 5, 0, 10, -20, -5], holds all 3 updates in 6 slots, and the running sum turns it into [10, 15, 15, 25, 5]. Slot 3 holds 10 because the first update's -10 and the third update's +20 share it, and adding that 10 to the running 15 gives 25. Index 5 is never read by the rebuild: it exists to absorb the -5 of an update that runs to the last slot.


<br>

### Why the array has n + 1 slots

```sql
n = 5
updates = [(0, 2, 10), (1, 4, 5), (3, 3, 20)]
diff = [0] * n
for left, right, v in updates:
    diff[left] += v
    diff[right + 1] -= v
print(diff)
```

Predict what this prints before reading on. The first update writes indices 0 and 3. The second has right = 4, so it writes diff[5] on a list of 5 elements, and Python stops with IndexError: list index out of range before the print runs. A crash is the good outcome here: it points at the line. Sizing diff at n + 1 costs one slot and removes the edge case. The alternative guard if right + 1 < n also works but adds one more condition to get wrong under interview pressure.


<br>

### Inclusive or exclusive end

In pipelines this pattern answers concurrency questions: given sessions with start and end minutes, what's the peak number active at once? Each session is a range update of +1, and the peak is the maximum of the rebuilt array. Before writing code, ask one question: is a session that ends at minute 4 still active during minute 4? Here are the same 3 sessions, (1, 4), (2, 5) and (4, 6), under both answers.

End exclusive: active on [start, end)

| minute | active |
| --- | --- |
| 0 | 0 |
| 1 | 1 |
| 2 | 2 |
| 3 | 2 |
| 4 | 2 |
| 5 | 1 |
| 6 | 0 |

End inclusive: active on [start, end]

| minute | active |
| --- | --- |
| 0 | 0 |
| 1 | 1 |
| 2 | 2 |
| 3 | 2 |
| 4 | 3 |
| 5 | 2 |
| 6 | 1 |

Peak 2 or peak 3 from identical input. Half-open intervals write diff[end] -= 1; closed intervals write diff[end + 1] -= 1. Half-open is the safer default for event timestamps: a session ending at 10:04:00 and another starting at 10:04:00 are a handoff, and a capacity alert built on closed intervals fires on every clean handoff.

When coordinates are timestamps, the dense array becomes the cost. A day in seconds is 86,400 slots, which is fine; a day in milliseconds is 86,400,000 slots for perhaps 2,000 sessions. Keep (timestamp, delta) pairs instead and run the prefix sum over them once they are sorted: O(m log m) time and O(m) memory, independent of resolution. Sorting the tuples puts (t, -1) ahead of (t, 1), so ends at a shared timestamp apply before starts, which is the half-open rule for free.

> When a difference array is the wrong tool
>
> - Reads interleave with updates: every read needs an O(n) rebuild, so q reads cost O(q \* n).
> - Coordinates are sparse and fine-grained: sort the events instead of allocating a slot per unit of time.
> - Updates assign a value instead of adding one: assignment doesn't commute, so 2 boundary writes cannot record it.
> - A few updates hit short ranges: a direct loop over each range costs the total range length and needs no rebuild.


<br>

---

## Balanced Substring Problems

Balance questions arrive in many costumes: the longest stretch with as many 0s as 1s, the number of log segments with as many logins as logouts, the longest run of matches where wins equal losses. None of them mentions a sum, but one recode turns each into a sum: map one symbol to +1 and the other to -1, and equal counts becomes a sum of 0. After the recode, each one is the target-sum question with k = 0, solved by the same one-pass scan over running totals.

https://github.com/user-attachments/assets/46428a74-7967-4c07-a685-350f24468789

*Columns: index, char, prefix, longest so far, count so far*

Two values grow as the scan runs. The longest balanced substring reaches 6 at index 5, where the prefix returns to 0 and the seed at -1 measures from the start: '001011' has 3 zeros and 3 ones. The count reaches 8 because equal prefixes pair up. Prefix -1 occurs 4 times, which makes 6 pairs, and 0 and -2 occur twice each, 1 pair apiece. Every pair of equal prefixes is one balanced substring, so the count equals the sum of c \* (c - 1) / 2 over the prefix frequencies, accumulated one step at a time.


<br>

### A count map and a first-index map

The program keeps 2 maps because the 2 questions need different facts about the same prefix value: how often it occurred, and where it first occurred. Asked one question, keep one map. Asked both, an interviewer will watch whether you notice that the first-index map can't answer the count, since it records nothing about repeats.


<br>

### Three symbols: the prefix becomes a tuple

Balance across 3 symbols doesn't fit in one number. Track the 3 counts and key the map on 2 differences, (count_a - count_b, count_b - count_c). A substring is balanced exactly when both differences match at its 2 ends. Tuples are hashable, so the dict code stays the same and only the key changes. Here is s = "abcbca":

| index | char | (a - b, b - c) | seen before? |
| --- | --- | --- | --- |
| start | none | (0, 0) | seed |
| 0 | a | (1, 0) | no |
| 1 | b | (0, 1) | no |
| 2 | c | (0, 0) | yes: 'abc' |
| 3 | b | (-1, 1) | no |
| 4 | c | (-1, 0) | no |
| 5 | a | (0, 0) | yes, twice: 'bca' and 'abcbca' |

Key (0, 0) occurs 3 times, so 3 substrings balance, and the longest is the whole string. With m symbol types the key holds m - 1 differences. Building and hashing it costs O(m) per character, so the scan costs O(n \* m).


<br>

### Strictly more of one symbol

A harder variant asks for the longest stretch of days in which tiring days strictly outnumber the rest. Recode hours above 8 as +1 and everything else as -1, so hours [9, 9, 6, 0, 6, 6, 9] become +1, +1, -1, -1, -1, -1, +1 with prefixes 1, 2, 1, 0, -1, -2, -1. A positive prefix means the whole stretch from index 0 qualifies. A prefix p of 0 or less needs an earlier prefix of at most p - 1, and since the prefix moves by exactly 1 per step, it reached p - 1 before it reached any lower value. So the lookup is first[p - 1], one key, and the answer here is 3, the opening [9, 9, 6].

> **TIP**
>
> Say the recode out loud before you code: 'zeros become -1, ones become +1, so balanced means 2 equal prefixes.' It shows the interviewer the pattern you recognized, and it settles the seed: {0: -1} for a length, {0: 1} for a count.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Ask whether the question wants a count or a length, or only yes/no, before choosing what the map stores<br><br>• Seed the map with the empty prefix before the loop starts<br><br>• Key the map on a tuple of count differences when 3 or more symbols must balance<br><br>• Test a string balanced from index 0, the case only the seed catches | • Overwrite a stored first index when the question asks for the longest substring<br><br>• Count balanced substrings with a set, which forgets how often a prefix repeated<br><br>• Recode as 1 and 0, where balance means a sum of half the length, a target that moves<br><br>• Insert the current prefix before the lookup, which counts every empty substring |


<br>

---

## Prefix Sums in Spark and pandas

Every cumulative metric in a pipeline is a prefix sum under another name: revenue to date, a running account balance, a 7-day rolling order count. Dataframe libraries expose it as a cumulative sum and a rolling sum, and SQL exposes it as a window function. The first computes P, and the second computes P[i + 1] - P[i - w + 1] for a window of w rows. Knowing that lets you predict their output on the cases that break dashboards, such as tied timestamps and missing days, and on tables nobody partitioned.

In plain Python, itertools.accumulate is the cumulative sum. list(accumulate([3, 1, 4])) is [3, 4, 8], one output per input, which is what a dataframe's cumulative sum returns. Passing initial=0 gives [0, 3, 4, 8], the P array with its leading zero, which is the form range queries index into. A grouped cumulative sum restarts the total for each group, which is the job `PARTITION BY` does in a window function.

```sql
SELECT
  merchant_id,
  order_date,
  revenue,
  SUM(revenue) OVER (
    PARTITION BY merchant_id
    ORDER BY order_date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS revenue_to_date,
  SUM(revenue) OVER (
    PARTITION BY merchant_id
    ORDER BY order_date
    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
  ) AS revenue_7_rows
FROM daily_revenue
```

The first frame is a prefix sum per merchant. The second is a rolling sum, and it obeys the same identity: as the frame slides one row, the total gains the row entering and loses the row 7 places back, so an engine can maintain it in O(1) per row. Both frames spell out ROWS on purpose. The 2 tools disagree before the window fills. On a merchant's first 6 rows, the SQL frame returns a partial sum over however many rows exist. A dataframe rolling sum over 7 rows returns a missing value (NaN) for each of those 6 rows by default. Setting its minimum-periods option to 1 makes it return the same partial sums, which a backfill comparing the 2 outputs needs. A time-based window of 7 days measures dates instead of rows, which also handles the missing days below without densifying.


<br>

### The default frame and tied rows

Drop the frame clause but keep ORDER BY, and the default frame is RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW. RANGE includes every peer row with the same ordering value as the current row, so tied rows all receive the total through the last of them.

ROWS frame

| order_date | amount | running |
| --- | --- | --- |
| 2024-03-01 | 100 | 100 |
| 2024-03-02 | 40 | 140 |
| 2024-03-02 | 60 | 200 |
| 2024-03-03 | 50 | 250 |

Default RANGE frame

| order_date | amount | running |
| --- | --- | --- |
| 2024-03-01 | 100 | 100 |
| 2024-03-02 | 40 | 200 |
| 2024-03-02 | 60 | 200 |
| 2024-03-03 | 50 | 250 |

The RANGE column reports 200 on a row that, read alone, looks like the second sale of a 140 day. The ROWS column has a quieter problem: 2 rows share 2024-03-02, the engine may order them either way, and the 140 can become 160 on the next run. Adding a unique tiebreaker such as order_id to ORDER BY makes the running total deterministic, which is what a backfill comparing old and new output needs.


<br>

### Seven rows versus 7 days

A ROWS frame counts rows, whatever dates they carry. Suppose a merchant sold on March 2 and 3 and on every day from March 5 to March 9, with nothing on March 4. The 7-row frame ending on March 9 reaches back to March 2, an 8-day window. Densify to fix it: join to a calendar holding every date, fill missing revenue with 0, and each row means one day again, so 7 rows cover 7 days. The cost is rows to store and scan: a merchant with sales on 3 days of the year still gets 365.

```sql
WITH calendar AS (
  SELECT
    calendar_date
  FROM UNNEST(SEQUENCE(DATE '2024-03-01', DATE '2024-03-31', INTERVAL '1' DAY)) AS t(calendar_date)
)

SELECT
  c.calendar_date,
  COALESCE(r.revenue, 0) AS revenue,
  SUM(COALESCE(r.revenue, 0)) OVER (
    ORDER BY c.calendar_date
    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
  ) AS revenue_7_days
FROM calendar AS c
LEFT JOIN daily_revenue AS r
  ON r.order_date = c.calendar_date
    AND r.merchant_id = 42
```


<br>

### How a distributed engine runs a running total

With PARTITION BY merchant_id, the engine shuffles each merchant's rows to one worker, which sorts and scans them once, so the work spreads across workers by merchant. Remove PARTITION BY and ask for one running total over the whole table, and every row funnels into a single sorted scan on one task. Parallelising it takes 2 passes, and the second pass is itself a prefix sum.

https://github.com/user-attachments/assets/98b3a06d-4b92-46ae-b986-6cd39d676e87

*Pass 1 per chunk, a prefix sum over chunk totals, then pass 2*

Pass 1 runs on every chunk at once and yields local running sums plus one total per chunk, [8, 6, 17]. The coordinator takes a running sum of those totals shifted by one position, which gives the offsets [0, 8, 14]. Pass 2 adds each chunk's offset to its local sums, again in parallel. The output matches a single scan of all 8 values, [3, 4, 8, 9, 14, 23, 25, 31], and the only sequential work touched one number per chunk: with 200 partitions, 200 additions whatever the row count.

```sql
WITH events AS (
  SELECT
    start_ts AS ts,
    1 AS delta
  FROM sessions

  UNION ALL

  SELECT
    end_ts AS ts,
    - 1 AS delta
  FROM sessions
)

SELECT
  MAX(active) AS peak_sessions
FROM (
  SELECT
    SUM(delta) OVER (
      ORDER BY ts, delta
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS active
  FROM events
) AS running
```

This is the difference array written in SQL: each session contributes a +1 row and a -1 row, and the running SUM rebuilds the active count. Ordering by ts, then delta, puts -1 rows ahead of +1 rows at a shared timestamp, the half-open rule as a sort key. With no PARTITION BY, it is also the single-task scan described above, which is fine for one day of sessions. Adding PARTITION BY region would restart the count in each region. MAX(active) would then return the busiest single region's peak, which is correct only when the question asks for a peak per region. To keep one global peak at scale, first sum delta per timestamp so the window scans one row per distinct ts, or run the 2-pass chunk-offset scan.


<br>

---

## Putting It All Together

A payments company's risk team asks for a nightly job that produces 3 figures per merchant: how many contiguous stretches of the merchant's hourly ledger net to exactly zero, a sign of charge-and-refund cycling; the peak number of payout holds open at once; and a 7-day rolling refund total for the merchant dashboard. Before any figure is published, a reconciliation step must confirm that the ledger replica matches its source.

- Zero-net stretches are the target-sum count with k = 0: a frequency map seeded {0: 1}, lookup before insert, because k = 0 is the case where inserting first double counts.
- Overlapping payout holds are a difference array of +1 at each hold's start and -1 at its release, half-open so a release and a new hold in the same hour do not overlap.
- The rolling refund total aggregates refunds to one row per merchant per day, densifies against a calendar with 0 for missing days, then sums a 7-row ROWS frame partitioned by merchant and ordered by date, so 7 rows always cover 7 days. A running total over individual refunds would instead order by timestamp and break ties on order_id, so a rerun or a backfill produces the same totals.
- All 3 figures run partitioned by merchant, so each merchant's scan stays on one worker; a single global total would need the 2-pass chunk offsets.
- The reconciliation can store running XORs of row hashes and binary-search a mismatch, while accepting the blind spot for rows that appear an even number of extra times.


<br>

---

## Key Takeaways

- A running total plus a dict turns 'which start points work?' into one O(1) lookup per element, and the question decides what the dict stores: a count per prefix, or the first or latest index where it appeared.
- Seed the map with the empty prefix and look up before inserting: the seed catches ranges starting at index 0, and the order matters on k = 0 test cases.
- XOR is its own inverse, so prefix XOR answers range XOR in O(1), counts subarrays with the lookup key prefix ^ k, and extends to parity questions through a bitmask.
- A difference array makes each range update 2 writes and defers the cost to one O(n) rebuild; size it n + 1 and settle inclusive or exclusive ends before coding.
- Balance questions become zero-sum questions after a +1/-1 recode, or a tuple of count differences when 3 or more symbols must balance.
- Window frames are prefix sums: name ROWS explicitly, add a tiebreaker, densify dates for day windows, and partition so the scan spreads across workers.
