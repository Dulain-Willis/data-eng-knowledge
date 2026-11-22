# Two Pointers: Intermediate

Priya is in the second technical round at Meta. The interviewer writes 6 integers on the board, 2 of them equal to -1, and asks for every distinct triplet that sums to 0. She sorts, fixes one index, and squeezes the rest with 2 pointers, then the interviewer points at the repeated -1 and asks why her output lists one triplet twice. Twenty minutes later the question changes shape: 9 vertical lines, pick 2 that hold the most water. Then a list of 0s, 1s and 2s to group in a single pass. The final 10 minutes bring 1,000 sorted event files that must become 1 sorted stream. Four questions, and each is the same move: 2 or 3 indexes walking a sequence, with a rule that says which one to advance. This lesson works through each of them until the rule is yours.


<br>

### What you will be able to do

Solve 3Sum in quadratic time by sorting, pinning the lowest value of each triplet and squeezing the rest with 2 pointers

Place the 3 duplicate skips where they belong and predict the output, or the traceback, of a skip written in the wrong place

Argue why moving the shorter wall loses no candidate in Container With Most Water, including the tie case

Partition a list of 3 values in a single pass with low, mid and high pointers and state the 4 region invariants

Merge K sorted lists with a heap of heads, give the N log K bound, and explain why the tuple carries the list index


<br>

---

## 3Sum: Fix One, Scan Two

The question arrives as a list of integers and one demand: return every triplet of 3 different positions whose values add to 0, with no repeated triplet in the result. On [-1, 0, 1, 2, -1, -4] the expected result is [[-1, -1, 2], [-1, 0, 1]], in any order. The interviewer grades 2 things: the time bound you reach, and whether the output is free of repeats. This section settles the first; the next settles the second.


<br>

### Three loops versus a sort and 2 pointers

Three nested loops check every triple of positions, about n cubed over 6 of them. At n = 3,000 that is 4.5 billion sums, and pure Python runs roughly 5 to 20 million such loop iterations per second, so the search takes about 4 to 15 minutes; the interviewer will ask for better before you finish writing it. Sorting the list first changes the shape of the problem. Once values are in order, fix the smallest member of the triplet at index i, and the rest of the question reads: in the sorted slice to the right of i, find 2 values that add to -nums[i]. That is the opposite-end convergence scan, one pointer at i + 1, one at the last index, moving inward, and it finishes in at most n steps. Running it once for each of the n choices of i gives n times n, so the whole algorithm is quadratic: at most 9 million scan steps at n = 3,000, finished in under 2 seconds, with the sort's n log n absorbed. Fixing the smallest member and scanning only to its right also guarantees the 3 positions are distinct, and visits each unordered triplet from exactly one value of i.

| approach | time | extra space | repeats handled by |
| --- | --- | --- | --- |
| 3 nested loops | O(n^3) | O(1) | a set of sorted tuples |
| hash set per fixed i | O(n^2) | O(n) | a set of sorted tuples |
| sort, fix one, scan two | O(n^2) | O(1) beyond the sort | skipping equal neighbours |


<br>

### One fixed value, one scan

Sorted, the sample is [-4, -1, -1, 0, 1, 2]. Fix i = 1, value -1, so the scan needs 2 values from positions 2 through 5 adding to 1. The pointer lo starts at 2 (value -1) and hi at 5 (value 2): -1 + 2 = 1, a hit, so record [-1, -1, 2]. After a hit both pointers move: lo to 3 (value 0), hi to 4 (value 1): 0 + 1 = 1, a second hit, record [-1, 0, 1]. Both move again, lo passes hi, and the scan for i = 1 is done after 2 steps. When the running sum falls short, the left pointer advances to a larger value; when it overshoots, the right pointer retreats to a smaller one. Each step retires one index for good, which is where the linear bound on the scan comes from.

| i | nums[i] | lo | hi | sum | action |
| --- | --- | --- | --- | --- | --- |
| 0 | -4 | 1 | 5 | -3 | sum < 0, lo += 1 |
| 0 | -4 | 2 | 5 | -3 | sum < 0, lo += 1 |
| 0 | -4 | 3 | 5 | -2 | sum < 0, lo += 1 |
| 0 | -4 | 4 | 5 | -1 | sum < 0, lo += 1, scan ends |
| 1 | -1 | 2 | 5 | 0 | record [-1, -1, 2], move both |
| 1 | -1 | 3 | 4 | 0 | record [-1, 0, 1], move both, scan ends |
| 2 | -1 | 3 | 5 | 1 | sum > 0, hi -= 1 |
| 2 | -1 | 3 | 4 | 0 | record [-1, 0, 1] again, scan ends |
| 3 | 0 | 4 | 5 | 3 | sum > 0, hi -= 1, scan ends |

https://github.com/user-attachments/assets/a3e7389c-04c7-4e32-b6ff-777cef15b1f0

*Fix nums[i], squeeze lo and hi; the second -1 rediscovers [-1, 0, 1].*

The printed result holds [-1, 0, 1] twice. Positions 1 and 2 both carry -1, and each one, used as the fixed value, rediscovers the same partners at 0 and 1. The structure of the solution is complete at this point and the time bound is already quadratic; what remains is the repeat handling, which the next section builds rule by rule. The if nums[i] > 0: break line in the code above is worth naming: once nums[i] is positive, every value to its right is at least as large, so no triplet starting there can reach 0 and the outer loop stops. On a list of mostly positive numbers that cut removes most of the work, and it costs 2 lines.

> Why both pointers move after a hit
>
> - Holding lo still and moving hi inward can only produce another 0 sum if the new hi value equals the old one, and that triplet is a repeat.
> - The same holds in mirror for holding hi still, so advancing both loses nothing and saves a step.
> - Equal neighbours still need explicit skipping, which is the job of the next section.

> **TIP**
>
> State the bound as 2 parts: the sort costs n log n, then each of n fixed values pays a scan of at most n steps, so n squared dominates. Add that extra space is constant beyond the sort and the output list; interviewers listen for whether you count the output.


<br>

---

## Skipping Duplicates Correctly

Repeats enter a 3Sum result from exactly 3 places: the fixed value at i can equal the fixed value one step earlier, the value at lo can equal its right neighbour, and the value at hi can equal its left neighbour. A correct solution closes all 3 doors, and each closure has a direction and a timing that the common wrong versions get backwards. Getting the direction wrong drops answers; getting the timing wrong drops answers or crashes.


<br>

### Rule 1: skip the fixed value by looking back

At the top of the outer loop: if i > 0 and nums[i] == nums[i - 1]: continue. The comparison looks at the previous element, never the next one. The first copy of a value must run its scan, because its later copies are candidates for lo: in [-1, -1, 2] the triplet needs both copies of -1, and a forward-looking skip (nums[i] == nums[i + 1]) discards i = 0 before the scan starts and returns an empty list. Looking back, the second copy is skipped only after the first has already found everything the pair of them can form.


<br>

### Rules 2 and 3: skip lo and hi only after a hit

When the sum reaches 0, record the triplet, then run while lo < hi and nums[lo] == nums[lo + 1]: lo += 1 and the mirror while lo < hi and nums[hi] == nums[hi - 1]: hi -= 1, and finally move each pointer one more step onto the fresh value. Two details carry the correctness. The skipping happens after the hit, never before the sum is checked: [0, 0, 0] needs lo and hi to both hold 0, and skipping equal values ahead of the comparison walks past the only answer. And the lo < hi guard stays inside the skip loop: without it, on [0, 0, 0, 0] the loop compares nums[3] with nums[4] and the program ends in IndexError: list index out of range.

https://github.com/user-attachments/assets/54fd5ff9-391b-46d7-bf06-670f2103b745

*All 3 skips in action: lo steps over the second 0, hi over the second 2, i over the second 0.*

The input is already sorted, so the program skips the sort. Watch i = 0. The hit at lo = 1, hi = 4 records [-2, 0, 2]; then lo steps over the second 0 to index 2 and hi steps over the second 2 to index 3, and the final move of both ends the scan with lo at 3 and hi at 2. At i = 1 the fixed 0 matches nothing, and at i = 2 the look-back rule fires because index 1 also holds 0. One triplet, printed once.

| wrong version | input | what it prints | correct output |
| --- | --- | --- | --- |
| outer skip compares with nums[i + 1] | [-1, -1, 2] | [] | [[-1, -1, 2]] |
| lo and hi skipped before the sum check | [0, 0, 0] | [] | [[0, 0, 0]] |
| skip loop without the lo < hi guard | [0, 0, 0, 0] | IndexError traceback | [[0, 0, 0]] |
| no skipping at all | [-2, 4, 0, -2, 2] | [[-2, -2, 4], [-2, 0, 2], [-2, 0, 2]] | [[-2, -2, 4], [-2, 0, 2]] |


<br>

### Four inputs that catch every skip bug

- [0, 0, 0, 0] expects [[0, 0, 0]]: tests the guard and the after-hit timing
- [-2, 0, 0, 2, 2] expects [[-2, 0, 2]]: tests lo and hi skipping
- [-2, 4, 0, -2, 2] expects [[-2, -2, 4], [-2, 0, 2]]: tests the look-back outer skip
- [1, 2, 3] expects []: tests the positive early exit

```sql
def three_sum(nums):
    nums = sorted(nums)
    n = len(nums)
    result = []
    for i in range(n - 2):
        if nums[i] > 0:
            break
        if i > 0 and nums[i] == nums[i - 1]:
            continue
        lo, hi = i + 1, n - 1
        while lo < hi:
            s = nums[i] + nums[lo] + nums[hi]
            if s < 0:
                lo += 1
            elif s > 0:
                hi -= 1
            else:
                result.append([nums[i], nums[lo], nums[hi]])
                while lo < hi and nums[lo] == nums[lo + 1]:
                    lo += 1
                while lo < hi and nums[hi] == nums[hi - 1]:
                    hi -= 1
                lo += 1
                hi -= 1
    return result
```

| ✓ Do | ✗ Don't |
| --- | --- |
| • Compare the fixed value with its predecessor, nums[i - 1]<br><br>• Skip equal lo and hi values only after recording a hit<br><br>• Keep lo < hi inside every skip loop<br><br>• Run [0, 0, 0, 0] before you say you are done | • Skip the fixed value by peeking at nums[i + 1]<br><br>• Collect triplets in a set of tuples to paper over a skipping bug<br><br>• Advance past equal values before the sum is checked<br><br>• Sort the caller's list in place if its original order matters |

*Both choices cost O(n) extra memory: sorted(nums) allocates a copy, and nums.sort() runs Timsort, whose merge buffer can reach n/2 elements. The real difference is that nums.sort() reorders the caller's list. Say which you chose and why; the scan itself stays constant space beyond the sort.*


<br>

---

## Container With Most Water

Nine vertical lines stand on the x axis with heights [1, 8, 6, 2, 5, 4, 8, 3, 7]. Pick 2 of them as the walls of a container; the water it holds is the shorter wall times the distance between them, min(h[l], h[r]) \* (r - l). The answer for this input is 49, walls at indexes 1 and 8 with heights 8 and 7. Every pair of walls is a candidate, so brute force measures n times n minus 1 over 2 containers, and the two-pointer version finds the same maximum in n minus 1 steps.


<br>

### The move: always advance the shorter wall

Start with l at 0 and r at the last index, the widest container possible. Compute its area, keep the best so far, then move the pointer at the shorter wall inward. The reason this loses nothing is an argument about every container you skip. Suppose h[l] is the shorter wall. Any container that keeps l and uses a right wall closer than r has a smaller width, and its height is still capped by h[l], the shorter of its 2 walls, so its area is at most the one you already measured. Every container with left wall l is therefore accounted for, and l can be retired. The mirror argument retires r when h[r] is shorter. Each step retires one index, so after n minus 1 steps every pair has been either measured or proven no better than something measured.

| step | l | r | h[l] | h[r] | area | best | move |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 | 8 | 1 | 7 | 8 | 8 | l, since 1 < 7 |
| 2 | 1 | 8 | 8 | 7 | 49 | 49 | r, since 7 < 8 |
| 3 | 1 | 7 | 8 | 3 | 18 | 49 | r |
| 4 | 1 | 6 | 8 | 8 | 40 | 49 | r, a tie |
| 5 | 1 | 5 | 8 | 4 | 16 | 49 | r |
| 6 | 1 | 4 | 8 | 5 | 15 | 49 | r |
| 7 | 1 | 3 | 8 | 2 | 4 | 49 | r |
| 8 | 1 | 2 | 8 | 6 | 6 | 49 | r, pointers meet |

https://github.com/user-attachments/assets/77e31ebd-04ab-4b26-8f13-071cead3e8da

*Each line prints l, r and the area measured before the shorter wall retires.*

Step 4 shows the tie: both walls are 8 and the code moves r because the else branch owns equality. Moving l would have been equally safe. When the walls are equal, every container keeping l and shrinking from the right is capped at height 8 with less width, and the same holds for every container keeping r, so the argument retires both ends at once and either move loses nothing. The code moves r, and l stays at index 1 until the pointers meet; every container measured after that keeps l, which the tie already proved can hold no more than 40, and the areas 16, 15, 4 and 6 confirm it.


<br>

### Why the taller wall is the wrong one to move

A frequent instinct is to move the taller wall, hoping a taller partner will appear for the short one. Trace it on the sample: at step 1 the taller wall is the 7 at index 8, so r moves and the wall of height 1 at index 0 stays in play for every remaining step. Each container measured keeps that wall, so no area exceeds 8, and the 49 at indexes 1 and 8 is never computed. The shorter wall is the one that limits the area, and the only way to beat the current area is to replace it.

Set this next to 3Sum's inner scan and the shared skeleton shows. In both, 2 pointers start at the ends and each step discards one index after proving it has no better partner remaining. What differs is the evidence: the sorted sum says which pointer to move in 3Sum, the shorter height says it here. An interviewer who hands you a new opposite-end problem is asking you to find that piece of evidence, and the proof that it retires an index is the part worth saying out loud.

At n = 100,000 the 2 approaches differ by a factor of about 50,000: at the loop speed from the 3Sum estimate, brute force runs for about 4 to 17 minutes in pure Python, and the squeeze finishes in milliseconds.

- **5.0B** — pairs checked by brute force
- **99,999** — steps taken by the squeeze

| ✓ 3Sum inner scan | ✗ Container squeeze |
| --- | --- |
| • Target: a fixed sum<br><br>• Evidence to move: too small moves lo, too large moves hi<br><br>• Result: every hit recorded<br><br>• Per fixed value: at most n steps | • Target: a maximum<br><br>• Evidence to move: the shorter wall cannot do better<br><br>• Result: one best value kept<br><br>• Whole problem: n minus 1 steps |

> **TIP**
>
> Say the proof in 2 sentences: the shorter wall caps the height of every container it belongs to, and moving the other pointer only shrinks the width, so the shorter wall has no better partner left. Those 2 sentences separate a memorized answer from an understood one.


<br>

---

## Partitioning: Dutch National Flag

The input is a list holding only 0, 1 and 2, and the ask is to arrange it as all 0s, then all 1s, then all 2s, in place, in a single pass. Dijkstra posed it as the Dutch national flag problem in A Discipline of Programming: 3 colours to be grouped by one sweep. The constraint that matters is the single pass. Counting each value and rewriting the list takes 2 passes, and it only works when the elements are the values themselves rather than records carrying a value.


<br>

### Three pointers mark four regions

| region | index range | holds |
| --- | --- | --- |
| settled zeros | 0 to low - 1 | only 0 |
| settled ones | low to mid - 1 | only 1 |
| unexamined | mid to high | anything |
| settled twos | high + 1 to n - 1 | only 2 |

The 3 pointers start with low and mid at 0 and high at the last index, which makes the 3 settled regions empty and the unexamined region the whole list. The loop looks at nums[mid] and does one of 3 things. A 0 is swapped with nums[low], and both low and mid advance. A 1 is already where it belongs, so only mid advances. A 2 is swapped with nums[high], and only high moves, downward. The loop runs while mid is at most high, and when it stops the unexamined region has shrunk to nothing, which means the other 3 regions tile the whole list.


<br>

### Why mid stands still after a swap with high

The value that arrives at mid from the high end has never been looked at: it could be a 0 that still has to travel left. Advancing mid past it would park an unexamined value inside the ones region and break the invariant. After a swap with low the situation differs: the value that arrives from low is a 1, because the region from low to mid minus 1 holds only 1s, or low equals mid and the swap exchanged an element with itself. Either way mid can advance. That asymmetry is the whole difficulty of the problem, and interviewers probe it with an input whose last element is a 0.

| step | nums[mid] | low | mid | high | action | list after |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 2 | 0 | 0 | 5 | swap mid and high, high = 4 | [0, 0, 2, 1, 1, 2] |
| 2 | 0 | 0 | 0 | 4 | swap mid and low, low = 1, mid = 1 | [0, 0, 2, 1, 1, 2] |
| 3 | 0 | 1 | 1 | 4 | swap mid and low, low = 2, mid = 2 | [0, 0, 2, 1, 1, 2] |
| 4 | 2 | 2 | 2 | 4 | swap mid and high, high = 3 | [0, 0, 1, 1, 2, 2] |
| 5 | 1 | 2 | 2 | 3 | mid = 3 | [0, 0, 1, 1, 2, 2] |
| 6 | 1 | 2 | 3 | 3 | mid = 4, loop ends | [0, 0, 1, 1, 2, 2] |

https://github.com/user-attachments/assets/1e09d4e1-f250-4fe9-b573-442bffaf640d

*After each step the list is printed with low, mid and high; note mid holds still after a swap with high.*

> The loop condition is mid <= high
>
> - With mid < high the element at high is never examined.
> - On [1, 0] that leaves the list unchanged: mid advances to 1, the condition fails, and the 0 at index 1 stays where it is.
> - With <=, the final iteration examines nums[high] and places it.

The reason this outranks counting in a data engineering interview is what the elements are. A change feed delivers rows tagged insert, update or delete, and a downstream step wants them grouped by tag before applying them in one batch per kind. Counting the tags tells you how many of each exist, and nothing about which row goes where; the flag partition moves the rows themselves, with at most n swaps in total, one per iteration, and no second list allocated. The same 3-pointer step is the partition inside 3-way quicksort, where the groups are less than, equal to and greater than the pivot, and it is the reason that sort runs in linear time on inputs with few distinct keys.

The follow-up is usually 4 or more values. With plain values, counting wins: k counters and a rewrite. With records, repeat the partition: split the list into one value versus the rest, then partition the rest, which costs one pass per value and stays in place.

- Name the 4 regions and their index ranges before you write the loop
- State which pointer each branch moves and why mid stays after the high swap
- Trace [1, 0] and [2, 0] out loud: 2 elements cover the edge cases
- Give the cost: n iterations, at most n swaps, constant extra space


<br>

---

## K-Way Merge: Scaling Two Pointers

Merging 2 sorted lists is the move from the beginner tier: one pointer per list, emit the smaller head, advance that pointer, total steps equal to the combined length. Interviewers scale it by handing you K sorted lists, often phrased as K sorted log files or K sorted partition outputs, and asking for a single sorted stream. The direct extension keeps K pointers and, at every emission, scans all K heads for the smallest. With N total elements that is N times K comparisons, and K is the dimension that grows in practice.


<br>

### A heap of K heads

The scan over K heads answers one question, which head is smallest, and a min-heap answers it in log K time instead of K. Seed the heap with the first element of every list, each stored as a tuple of (value, list index, position). Each loop iteration pops the smallest tuple, appends its value to the output, and pushes the next element from the same list if one remains. The heap never holds more than K entries, because each pop removes one and each push adds at most one, so memory stays proportional to K while the output grows to N.

| step | popped | pushed | heap after (sorted) | output so far |
| --- | --- | --- | --- | --- |
| seed |  | (1,0,0) (2,1,0) (3,2,0) | (1,0,0) (2,1,0) (3,2,0) | [] |
| 1 | (1,0,0) | (4,0,1) | (2,1,0) (3,2,0) (4,0,1) | [1] |
| 2 | (2,1,0) | (5,1,1) | (3,2,0) (4,0,1) (5,1,1) | [1, 2] |
| 3 | (3,2,0) | (6,2,1) | (4,0,1) (5,1,1) (6,2,1) | [1, 2, 3] |
| 4 | (4,0,1) | (7,0,2) | (5,1,1) (6,2,1) (7,0,2) | [1, 2, 3, 4] |
| 5 | (5,1,1) | none, list 1 exhausted | (6,2,1) (7,0,2) | [1, 2, 3, 4, 5] |
| 6 | (6,2,1) | (8,2,2) | (7,0,2) (8,2,2) | [1, 2, 3, 4, 5, 6] |
| 7 | (7,0,2) | none | (8,2,2) | [1, 2, 3, 4, 5, 6, 7] |
| 8 | (8,2,2) | none | empty, loop ends | [1, 2, 3, 4, 5, 6, 7, 8] |

https://github.com/user-attachments/assets/25c7fb0c-8abf-49b1-b0d2-5c1bfc925681

*The heap never holds more than 3 tuples while the merged list grows to 8.*


<br>

### Why the list index sits in the tuple

Tuples compare position by position, so 2 heads with the same value compare on the list index next, and the heap never reaches the third field, because a list contributes one head at a time. The index also tells the loop which list to pull the successor from. Leave it out and store (value, record) for rows instead of integers, and the first tie in value forces a comparison of the records themselves.

```sql
import heapq

runs = [
    [{"ts": 1, "user": "a"}, {"ts": 3, "user": "b"}],
    [{"ts": 1, "user": "c"}, {"ts": 4, "user": "d"}],
]
heap = []
for run in runs:
    heapq.heappush(heap, (run[0]["ts"], run[0]))
print(heapq.heappop(heap))
```

The second heappush raises TypeError: '<' not supported between instances of 'dict' and 'dict', and the program never reaches the print. The fix is the tuple shape from the animation, (ts, run index, position), which resolves every tie on integers and keeps the dict out of the comparison. A welcome side effect: ties resolve toward the lower run index, so the merge is deterministic, and when runs are numbered by arrival, equal timestamps keep their run order.

Picture N = 10 million events spread across K = 1,000 sorted files, so log base 2 of K is about 10. The gap between the naive scan and the heap is 2 orders of magnitude, and it is the number to say in the room, because it decides whether the merge runs in a minute or for hours.

- **10B** — head comparisons, naive merge
- **100M** — heap operations, heap merge


<br>

### Where this runs in production

The merge phase of an external sort is this loop: the sort writes runs that each fit in memory, then merges them with one read buffer per run and a heap of run heads, so working memory is a buffer per run rather than the whole input. Log-structured storage engines compact sorted on-disk segments the same way, and a sort-merge join whose inputs arrive as many sorted partitions merges them before the join pointers start walking. In each case the decision is the one the interview asks about: K pointers scanned linearly, or K heads in a heap, chosen by how large K gets.

| K | naive comparisons per emit | heap work per emit | pick |
| --- | --- | --- | --- |
| 2 | 1 | about 1 | two pointers |
| 8 | 7 | 3 | either |
| 1,000 | 999 | 10 | heap |

> Edge cases to name
>
> - An empty input list: skip it while seeding, or the seed indexes past its end.
> - An exhausted list: pop without a push, the heap shrinks, and the loop ends when it empties.
> - Equal values across lists: the list index breaks the tie, never the payload.
> - K = 1: the loop copies the single list, which is the right answer.

> **TIP**
>
> For K = 2 the heap is overhead: a push and a pop cost more than 1 comparison. Below about 8 lists a linear scan of the heads matches the heap in wall time; above that the heap wins by a growing margin. Name the crossover, then write the heap version, because the interviewer wants the one that scales.


<br>

---

## Putting It All Together

A payments platform receives change events from 40 database shards, each shard's feed already ordered by commit time. A nightly job must produce a single commit-ordered stream, group each batch by operation type before applying it to the warehouse, and run a reversal check that flags any 3 transactions on one account whose amounts net to 0 within a day.

- The 40 shard feeds are a K-way merge: a heap of 40 (commit_ts, shard index, position) tuples emits the stream in order with memory proportional to the shard count, and the shard index keeps equal timestamps deterministic without ever comparing event payloads.
- Grouping a batch into inserts, updates and deletes before applying is the Dutch flag partition on records: low, mid and high move rows in place in a single pass, where counting the tags would say nothing about which row belongs where.
- The reversal check is 3Sum on each account's sorted amounts, and the duplicate skips matter because repeated identical refunds would otherwise report the same net-zero triple many times.
- The habit learned from the container squeeze, retiring an index only after proving it has no better partner, is the same reasoning that lets every merge pointer move forward once and never look back.


<br>

---

## Key Takeaways

- 3Sum is a sort followed by n opposite-end scans: fix the smallest member, squeeze the rest, and the bound is n squared with constant extra space.
- Duplicates are skipped in 3 places: the fixed value against its predecessor, and lo and hi against their neighbours only after a hit, each loop guarded by lo < hi.
- The squeeze in Container With Most Water retires the shorter wall because it caps the height of every container it belongs to; the taller wall has no such guarantee.
- The Dutch flag partition keeps 4 regions with 3 pointers, and mid stays put after a swap with high because the arriving value is unexamined.
- K sorted inputs merge in N log K with a heap of (value, list index, position) tuples, and the list index both breaks ties and locates the successor.
- Every opposite-end problem turns on one piece of evidence that proves an index can be retired; naming that evidence is the answer the interviewer is listening for.
