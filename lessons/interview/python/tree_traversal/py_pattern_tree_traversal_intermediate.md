# Tree Traversal: Intermediate

Ines is 40 minutes into a Google data engineering loop when the interviewer pastes a product taxonomy into the shared doc, each category row pointing at its parent. The opening ask: which category is the nearest shared parent of trail shoes and rain jackets? Her recursive search passes the sample. Then the follow-ups land in quick order. One branch of the real taxonomy runs 6,000 levels deep; does her code survive it? Search wants autocomplete over every category name; what structure answers a prefix in time set by the prefix length alone? Another service needs the whole tree as a string; how does it rebuild the exact shape? Each follow-up is a tree traversal in different clothes, and each one turns on a cost Ines has to name with a number before she writes a line.


<br>

### What you will be able to do

Find the lowest common ancestor in a binary tree or a BST, and from a parent map when there is no tree to search, then say which approaches silently return a wrong answer when a node is missing

Collect and count tree paths with backtracking, and name the memory cost of copying paths instead

Rewrite a recursive DFS with an explicit stack and explain the 1000-frame limit that forces the rewrite

Build a dict-of-dicts trie that answers search and prefix completion, and weigh it against a sorted list searched with bisect

Serialize and deserialize a binary tree in preorder and level order, with exact token counts for each format


<br>

---

## Lowest Common Ancestor (LCA)

The lowest common ancestor (LCA) of nodes `p` and `q` is the deepest node with both of them in its subtree, counting a node as a descendant of itself. Interviewers rarely use the term. They ask for the closest manager 2 employees share, the narrowest folder holding 2 files, or the most specific category covering 2 products. Any prompt that names 2 members of a hierarchy and asks for the nearest thing above both is an LCA question, whatever the wording.


<br>

### Binary tree: let the subtrees report back

The values have no ordering, so the only way to locate `p` and `q` is to search for them. Each recursive call returns 1 of 3 things: a node matching `p` or `q`, an LCA already settled further down, or `None`. A node whose left and right calls both come back non-null sits exactly where the 2 searches split, so it is the answer. A node with 1 non-null side passes that result upward unchanged. Before playing the run below, predict its 3 printed lines; the third deserves the most thought.

https://github.com/user-attachments/assets/bdd5e66d-9aef-4cb9-bfbe-f87e2a14a285

*A call that finds a value returns at once; a node hearing back from both sides is the LCA.*

The first search finds 7 and 4 under node 2, both sides report to 2, and it prints `Node(2)`. The second prints `Node(5)` without ever visiting 4: the call on node 5 matches `p` and returns immediately, and the right subtree of 3 returns `None`. That shortcut is sound when both nodes exist, because anything below 5 has 5 as an ancestor. The third asks for 5 and 99. There is no 99 in the tree, and it still prints `Node(5)`.

> The follow-up that catches people
>
> Ask whether both nodes are guaranteed to be in the tree. If not, the early return hides a missing node. One fix runs 2 membership searches before the LCA search, tripling the passes over the tree. The tighter fix makes every call return a pair: the candidate, plus a count of how many of p and q its subtree holds. The answer is trusted only when that count reaches 2.

```sql
def lca_checked(root, p, q):
    def walk(node):
        if node is None:
            return None, 0
        left, left_count = walk(node.left)
        if left_count == 2:
            return left, 2
        right, right_count = walk(node.right)
        if right_count == 2:
            return right, 2
        count = left_count + right_count + (node.val in (p, q))
        return (node if count == 2 else None), count

    return walk(root)[0]
```

A matched node no longer ends its branch, so the search keeps going below it, and when a value is missing it visits all n nodes. That full pass is the price of the guarantee. On the tree above, `lca_checked(root, 5, 99)` returns `None`. `lca_checked(root, 5, 4)` still returns node 5.


<br>

### BST: let the ordering steer

A binary search tree keeps every value in a node's left subtree below it and every value in its right subtree above it. That rule says where `p` and `q` live without searching for them. When both are smaller than the current node, both are on the left; when both are larger, both are on the right. The first node where they fall on different sides, or where 1 of them equals the node, is the split point and therefore the LCA.

```sql
def bst_lca(root, p, q):
    node = root
    while node is not None:
        if p < node.val and q < node.val:
            node = node.left
        elif p > node.val and q > node.val:
            node = node.right
        else:
            return node
    return None
```

The loop visits 1 node per level: O(h) time, O(1) extra space, no recursion. On a balanced BST of 1,000,000 keys, h is around 20, against as many as 1,000,000 visits for the general search. The ordering is also its blind spot. Asked for 5 and 99 in a BST rooted at 8, it sees 5 below 8 and 99 above, and returns 8 without checking that 99 exists.


<br>

### Parent map: climb instead of search

Hierarchies in data work rarely arrive as linked objects. An org chart or category table lands as rows of child and parent, which load into a dict from each node to its parent. LCA then needs no search from the root: climb from the first node to the top, recording every ancestor in a set, then climb from the second node until it reaches 1 of them.

```sql
manager = {"ana": "cto", "ben": "cto", "dee": "cfo", "cto": "ceo", "cfo": "ceo"}

def common_manager(a, b):
    ancestors = set()
    while a is not None:
        ancestors.add(a)
        a = manager.get(a)
    while b is not None and b not in ancestors:
        b = manager.get(b)
    return b

print(common_manager("ana", "dee"))
print(common_manager("ana", "cto"))
```

It prints `ceo`, then `cto`. The first call climbs from ana through cto to ceo, recording each name, then climbs from dee through cfo to ceo. In the second, cto is already in the set on the first check. Each climb costs the depth of its starting node, and an unknown name comes back as `None` instead of a wrong answer.

| Input | Method | Time | Extra space | Detects a missing node |
| --- | --- | --- | --- | --- |
| Binary tree, child links | Split search, early return | O(n) | O(h) call stack | No |
| Binary tree, child links | Search returning counts | O(n) | O(h) call stack | Yes |
| BST | Walk down by comparison | O(h) | O(1) | No |
| Child-to-parent dict | Ancestor set, then climb | O(depth of p + depth of q) | O(depth of p) | Yes |

> **TIP**
>
> Before writing LCA, ask 3 questions: is it a BST, do nodes link to their parents, and are both nodes guaranteed present? Each answer selects a different row of the table above, and asking shows you know the rows exist.


<br>

---

## Path Problems and Backtracking

A path question asks for something along a route through the tree: every root-to-leaf route whose values add up to a target, every file under a folder with its full path, every dotted column name inside a nested record. The solution is a DFS that carries the route it is on, and the engineering choice is how it carries that route, which decides both correctness and memory.


<br>

### One shared list, plus an undo step

Backtracking keeps a single `path` list for the whole search. Entering a node appends its value; leaving the node pops it, so when control returns to the parent the list is exactly what the parent had. Each node is pushed once and popped once, and the only copying happens at a match, where the current route is saved.

https://github.com/user-attachments/assets/0e1b96e2-0f28-4da1-b3d6-6443ee5b8f0d

*One path list grows on the way down and shrinks on the way back up.*

The run prints `[[5, 4, 11, 2], [5, 8, 4, 5]]`. Watch `path` on the stage: it grows to 4 values down the left side, shrinks back to `[5]` once the 11 branch is finished, then grows again on the right. The `remaining` argument needs no undo, because each call rebinds its own local name to a new integer, while `path` is 1 object that every call mutates.


<br>

### The bug interviewers wait for

Change `results.append(list(path))` to `results.append(path)` and predict the output. It prints `[[], []]`. Both matches stored a reference to the same list, and by the time `path_sum` returns, every value has been popped off it; `results[0] is results[1]` is `True`. Any shared mutable state saved during a backtracking search has to be copied at the moment it is saved.

| ✓ Backtrack with one shared list | ✗ New list per call, path + [val] |
| --- | --- |
| • Route memory: 1 list of at most h values<br><br>• Per node: 1 append and 1 pop<br><br>• Copies only at matches: O(k·h) for k matches<br><br>• Failure mode: a missing pop or a missing copy | • Route memory: a fresh list of up to h values per live call<br><br>• Per node: copy up to h values<br><br>• Up to 20,000,000 element copies on a balanced 1,000,000-node tree<br><br>• Failure mode: none from aliasing, which is why it reads safer |

Both versions visit each node once. The copying version adds O(n·h) element copies on top, while backtracking copies only the k routes that match, O(k·h). In an interview, write the backtracking version and name the copying one as the readable alternative, with that cost attached.


<br>

### When a path can start anywhere

The follow-up drops the root-to-leaf rule: count downward paths that start and end at any nodes and sum to the target. Launching a fresh search from every node costs O(n·h). The faster answer borrows prefix sums from array problems. Keep a running total from the root; a path ending at the current node hits the target exactly when some earlier running total on the route equals `running - target`. A dict counts how many points on the current route have each running total.

```sql
from collections import defaultdict

def count_paths(root, target):
    prefix = defaultdict(int)
    prefix[0] = 1

    def dfs(node, running):
        if node is None:
            return 0
        running += node.val
        count = prefix.get(running - target, 0)
        prefix[running] += 1
        count += dfs(node.left, running) + dfs(node.right, running)
        prefix[running] -= 1
        return count

    return dfs(root, 0)
```

The dict is shared state, the same as `path`, so it gets the same undo: increment on the way in, decrement on the way out. Skip the decrement and running totals from the left subtree stay in the dict while the right subtree is searched, so the count includes 'paths' that jump between branches. The seed `prefix[0] = 1` stands for the empty route above the root and lets a path that starts at the root count. Reading with `prefix.get` keeps lookups from inserting keys, so the dict holds at most n + 1 keys, and the whole search is O(n) time.

> **TIP**
>
> Read the verb in the prompt. 'List every route' means backtracking with a copy at each match. 'Count the routes' usually means running totals and a counting dict, and the routes themselves are never built.


<br>

---

## Iterative DFS with Explicit Stack

Each recursive DFS so far stores its pending work on Python's call stack, and CPython caps that stack: `sys.getrecursionlimit()` returns 1000 by default. A balanced tree never comes close, since 1,000,000 nodes fit in about 20 levels. Real hierarchies can. Inserting already sorted keys into a BST builds a chain with 1 level per key, and a deeply nested JSON document can run thousands of levels deep.

```sql
import sys

class Node:
    def __init__(self, val, left=None, right=None):
        self.val, self.left, self.right = val, left, right

def depth(node):
    if node is None:
        return 0
    return 1 + max(depth(node.left), depth(node.right))

root = None
for i in range(5000):
    root = Node(i, root)

print(sys.getrecursionlimit())
print(depth(root))
```

The first line prints `1000`. The second never prints: the traceback ends in a `RecursionError` whose message starts with `maximum recursion depth exceeded`. Raising the cap with `sys.setrecursionlimit` can let a deeper tree through, but the Python documentation warns that a limit set too high can crash the interpreter instead of raising an error you can catch. The durable fix moves pending work into a list on the heap, which holds 5,000 entries as ordinary data.


<br>

### Preorder: pop, visit, push the children

A list used only through `append` and `pop` is a stack, last in, first out. Push the root, then loop: pop a node and visit it before pushing its children. The last item pushed comes off first, so push the right child before the left and the left subtree finishes before the right one starts. Extra state rides along as tuples. This depth calculation pushes `(node, level)` pairs and prints `5000` on the chain above.

```sql
def max_depth(root):
    best, stack = 0, [(root, 1)]
    while stack:
        node, level = stack.pop()
        if node is None:
            continue
        best = max(best, level)
        stack.append((node.right, level + 1))
        stack.append((node.left, level + 1))
    return best

print(max_depth(root))
```


<br>

### Inorder: run down the left edge, then step right

Inorder can't visit a node when it first reaches it, because the whole left subtree comes first. The loop runs down the left edge pushing every node, pops the deepest one, visits it, then moves to its right child and repeats. On a BST the visits come out sorted.

https://github.com/user-attachments/assets/efe323c1-3500-478a-8007-f6bba2bbfc53

*The stack holds the left edge still waiting to be visited.*

It prints `[1, 2, 3, 4, 5, 6, 7]`. The stack peaks at 3 nodes, the height of this tree, and every node goes on and comes off once: O(n) time and O(h) space, the bounds of the recursive version without its 1000-frame ceiling.


<br>

### One template for all 3 orders

Postorder is the awkward one, because a node is visited after both children. The general fix pushes each node twice: once as work to expand, and once with a flag meaning visit now. Popping an unexpanded node pushes its marker and its children in the reverse of the order they should be visited.

```sql
def postorder(root):
    out, stack = [], [(root, False)]
    while stack:
        node, expanded = stack.pop()
        if node is None:
            continue
        if expanded:
            out.append(node.val)
        else:
            stack.append((node, True))
            stack.append((node.right, False))
            stack.append((node.left, False))
    return out
```

| Order | Push sequence when expanding | Visit sequence |
| --- | --- | --- |
| Preorder | right, left, (node, True) | node, left, right |
| Inorder | right, (node, True), left | left, node, right |
| Postorder | (node, True), right, left | left, right, node |

Predict what the next program prints. It walks a nested event record with the same stack and builds dotted column names, which is how a JSON payload becomes flat table columns.

```sql
def flatten(doc):
    flat, stack = {}, [("", doc)]
    while stack:
        prefix, value = stack.pop()
        if isinstance(value, dict):
            for key, child in value.items():
                stack.append((f"{prefix}.{key}" if prefix else key, child))
        else:
            flat[prefix] = value
    return flat

event = {"user": {"id": 7, "geo": {"city": "Lyon", "zip": "69001"}}, "ts": 1700000000}
print(flatten(event))
```

It prints `{'ts': 1700000000, 'user.geo.zip': '69001', 'user.geo.city': 'Lyon', 'user.id': 7}`. Every key is there, in reverse of document order, because the stack hands back the child pushed last. Pushing `reversed(list(value.items()))` restores document order. LIFO decides the order of visits and nothing else, so either version is correct; pick by whether column order matters downstream.

> **TIP**
>
> When depth hasn't come up, write the recursive version first and say where it breaks: past about 1000 levels in CPython. Then offer the stack version. 'Can you do it without recursion?' is the cue for everything in this section.


<br>

---

## Trie (Prefix Tree)

A trie, or prefix tree, stores strings 1 character per level, so every word that shares a prefix shares the nodes spelling it. In Python the leanest version is a dict of dicts, where each node maps a character to its child node. A word ends at a node holding the marker key `"$"`. That marker is what separates the stored word `car` from the first 3 letters of `card`.

https://github.com/user-attachments/assets/44cbded4-b51f-4807-8e9f-78dc73415ce2

*Words sharing a prefix share its dicts; the $ key marks where a word ends.*

The run prints `['car', 'card', 'care']`, then `['car', 'card', 'care', 'cat']`, then `[]`. Walking a prefix costs 1 dict lookup per character, so locating the end of `ca` takes 2 lookups whether the trie holds 5 words or 5,000,000. Completion is the backtracking search from the path section. Characters are pushed onto and popped off a `path` list, and `sorted(node)` places `"$"` ahead of every lowercase letter so a word comes out before its extensions.


<br>

### Why the end marker stays

Delete the line `node["$"] = True` and the trie no longer knows where words end: a walk for `ca` succeeds through 2 dicts, so a search built on walking alone would report `ca` as a stored word. With the marker, exact search is a walk plus 1 membership test.

```sql
def contains(trie, word):
    node = trie
    for ch in word:
        node = node.get(ch)
        if node is None:
            return False
    return "$" in node

print(contains(trie, "car"), contains(trie, "ca"), contains(trie, "cars"))
```

Run against the trie built above, it prints `True False False`. Deletion follows from the same structure: remove the marker, then delete child dicts on the way back up while they are empty, so a removed word leaves no orphan nodes for later prefix searches to wander into.


<br>

### What a dict-of-dicts trie costs

A trie is fast per lookup and expensive in memory. On 64-bit CPython 3.9, `sys.getsizeof({})` reports 64 bytes and a dict holding 1 key reports 232, and every node below the root holds at least 1 key. A vocabulary of 100,000 words averaging 8 letters, sharing prefixes down to 500,000 nodes, therefore spends about 116 MB on dict objects alone, before the character keys are counted. A sorted list of the same 100,000 words pays 8 bytes per list slot plus each string, which `sys.getsizeof` puts at 49 bytes plus 1 per ASCII character, 57 for an 8-letter word. That comes to about 6.5 MB, and `bisect` answers the same prefix question from it.

```sql
from bisect import bisect_left

def with_prefix(sorted_words, prefix):
    i = bisect_left(sorted_words, prefix)
    out = []
    while i < len(sorted_words) and sorted_words[i].startswith(prefix):
        out.append(sorted_words[i])
        i += 1
    return out

print(with_prefix(["car", "card", "care", "cat", "dog"], "car"))
```

It prints `['car', 'card', 'care']`, the same answer the trie gave. Locating the first match costs O(log N) string comparisons, and the matches sit next to each other after it. Inserting a word means shifting the list, O(N), which is where the trie pulls ahead.

| Need | Dict-of-dicts trie | Sorted list + bisect |
| --- | --- | --- |
| Find where a prefix starts | O(L) dict lookups for an L-character prefix | O(log N) string comparisons |
| List the k matches | DFS under the prefix node | Scan forward k entries |
| Insert a word | O(L) | O(N), the list shifts |
| Memory | A dict per node, 232 bytes or more | 1 string per word |
| Best fit | Words arriving continuously; longest-prefix match | Fixed vocabulary under a memory budget |


<br>

### Longest-prefix match: routing paths to tables

A trie is worth that memory when the question walks character by character and wants the deepest match along the way. Routing landed files is a clean case: each registered prefix maps to a destination table, and an incoming object path belongs to the longest registered prefix it starts with.

```sql
def insert(trie, word):
    node = trie
    for ch in word:
        node = node.setdefault(ch, {})
    node["$"] = True

def longest_prefix(trie, path):
    node, best = trie, None
    for i, ch in enumerate(path):
        node = node.get(ch)
        if node is None:
            break
        if "$" in node:
            best = path[:i + 1]
    return best

routes = {}
for prefix in ["raw/", "raw/events/", "raw/events/clicks/"]:
    insert(routes, prefix)

print(longest_prefix(routes, "raw/events/views/2024-06-01.json"))
print(longest_prefix(routes, "staging/orders.csv"))
```

It prints `raw/events/` and then `None`. The walk stops at the first character with no child, so its cost is bounded by the shorter of the path and the deepest route, however many routes are registered. A character-level trie spends 18 nodes on `raw/events/clicks/`; keying the trie by path segment, splitting on `/`, cuts that to 3 nodes, the variant to propose when memory comes up.

> **TIP**
>
> Autocomplete, spell-check suggestions, path routing and 'find every dictionary word on this letter grid' all reduce to a prefix walk. When a prompt keeps asking whether anything starts with a given string, reach for a trie and state its memory cost in the same breath.


<br>

---

## Serializing and Deserializing Trees

Serializing a tree turns linked node objects into a flat string that can be stored in a column, sent to another service, or written to a cache, and deserializing rebuilds the identical shape from it. The interview version asks for both functions and judges 1 property: `deserialize(serialize(t))` must reproduce `t` exactly, for every tree.

Values alone cannot do it. A root 1 with left child 2 and a root 1 with right child 2 both have preorder `1,2`, so the receiver cannot tell them apart. Writing a marker for every missing child removes the ambiguity, since the reader then knows exactly where each subtree stops. Predict the string the run below prints before playing it.

https://github.com/user-attachments/assets/0a2a1ce0-6d14-422f-a44c-b1f41ce935e9

*Every empty child slot becomes a # token, so the reader knows where each subtree stops.*

It prints `1,2,#,#,3,4,#,#,5,#,#` and then `True`. The 5 nodes produced 11 tokens. That count holds for every binary tree: n nodes have exactly n + 1 empty child slots, so the string is always 2n + 1 tokens. The reader works because `deserialize` consumes tokens from one shared iterator in the same preorder the writer produced them: each call takes the next token, and a `#` ends that branch.


<br>

### Why one shared iterator matters

Each recursive call must pick up where the previous call stopped, so the read position has to live outside any single frame. Calling `next()` on 1 iterator does that with no index bookkeeping. Passing a list and slicing it per call would copy the remainder at every step, O(n²) for the whole tree. An integer index passed as an argument fails, because each frame rebinds its own copy and a child call can't advance the caller's. An index does work when it lives in an enclosing scope through `nonlocal`, as `build_bst` below does, or when every call returns the new position. The iterator is the version that needs neither.


<br>

### Level order: the format practice sites print

Many coding-practice sites display trees breadth-first, writing children level by level and trimming the nulls at the end. The example tree becomes `1,2,3,#,#,4,5`: 7 tokens where the full form has 11, because the 4 trailing `#` markers under the leaves 4 and 5 tell the reader nothing it cannot infer. Building it uses a queue, so it needs no recursion at all.

```sql
from collections import deque

def serialize_levels(root):
    out, queue = [], deque([root])
    while queue:
        node = queue.popleft()
        if node is None:
            out.append("#")
            continue
        out.append(str(node.val))
        queue.append(node.left)
        queue.append(node.right)
    while out and out[-1] == "#":
        out.pop()
    return ",".join(out)

def deserialize_levels(text):
    if not text:
        return None
    tokens = iter(text.split(","))
    root = Node(int(next(tokens)))
    queue = deque([root])
    while queue:
        node = queue.popleft()
        for side in ("left", "right"):
            tok = next(tokens, "#")
            if tok != "#":
                child = Node(int(tok))
                setattr(node, side, child)
                queue.append(child)
    return root
```

The default in `next(tokens, "#")` makes the trimming safe: once the string runs out, every remaining child slot reads as empty. Both functions reuse the `Node` class from the run above, and the round trip through `1,2,3,#,#,4,5` rebuilds the same 5-node tree.


<br>

### Choosing a format

| Format | Tokens for n nodes | Recursion needed | Notes |
| --- | --- | --- | --- |
| Preorder with # markers | 2n + 1 | Yes, as written | Shortest code; the depth limit applies |
| Level order, trailing # trimmed | At most 2n + 1 | No | Queue-based; matches how practice sites print trees |
| BST preorder, no markers | n | Yes, as written | Ordering rebuilds the shape; BSTs only |
| Nested JSON lists | n values plus brackets | Inside the encoder | Readable; very deep trees raise RecursionError |

The BST row deserves its own sentence in an interview. Because every key in a BST bounds where its descendants can go, the preorder values alone rebuild the tree: read the next value, and it belongs in the current slot only if it falls between the bounds inherited from the ancestors. Preorder `[8, 3, 1, 6, 10, 14]` rebuilds 8 at the root with children 3 and 10. Below 3 sit 1 and 6, and 14 hangs to the right of 10.

```sql
def build_bst(preorder):
    pos = 0

    def build(low, high):
        nonlocal pos
        if pos == len(preorder) or not low < preorder[pos] < high:
            return None
        node = Node(preorder[pos])
        pos += 1
        node.left = build(low, node.val)
        node.right = build(node.val, high)
        return node

    return build(float("-inf"), float("inf"))

root = build_bst([8, 3, 1, 6, 10, 14])
print(root.val, root.left.val, root.right.val, root.right.right.val)
```

It prints `8 3 10 14`: n values and not a single marker. A value containing the separator, such as a category name with a comma, breaks a comma-joined format. Escape the separator, or encode each value with `json.dumps` and keep structure tokens apart from the values. Once other services read the string, put a version tag at its front, because changing the null marker or the traversal order later makes every reader misread trees written in the old format.

> **TIP**
>
> Open with the round-trip property, write preorder with markers, then offer level order and the BST shortcut with their token counts. The follow-ups are graded on whether you can say what each format costs.


<br>

---

## Putting It All Together

A retailer's product catalog is a category tree of 40,000 nodes, reloaded nightly from a table of category_id and parent_id rows. Site search needs autocomplete over category names, the merchandising team wants the most specific category shared by any 2 products, and the recommendation service receives the whole tree as a string after each load. One branch, created by a faulty import, is a chain 3,000 categories deep.

- The parent_id rows load straight into a child-to-parent dict, so the most specific shared category is the ancestor-set LCA. It needs no recursion, and unknown ids return None.
- The 3,000-deep chain breaks every recursive function at CPython's default limit of 1000 frames, so the nightly job's traversals run on explicit stacks and queues.
- Autocomplete is a trie over category names, completed with the same push-and-pop backtracking that collects root-to-leaf paths.
- Breadcrumbs such as Outdoor > Footwear > Trail are root-to-node paths. Backtracking builds them, or the iterative stack carries them as tuples.
- Shipping the tree uses a queue-based level-order format that survives the deep chain. Categories have any number of children, so each node writes its id and child count where a binary tree writes # markers: the reader dequeues a node, and its count says how many of the next entries are its children, the job # does for an empty slot. A version tag the recommendation service checks sits at the front.


<br>

---

## Key Takeaways

- LCA on a plain binary tree is a split search that returns the node where both sides report back, and it assumes both nodes exist unless every call also returns a count.
- A BST turns LCA into a downward walk with O(h) time and O(1) space, and a child-to-parent dict turns it into an ancestor set plus a climb.
- Backtracking shares 1 path list and undoes every change on the way out; save a copy of the list at each match, never the list itself.
- Counting paths that start anywhere uses running totals and a counting dict, undone on exit like the path list, for O(n) time.
- CPython stops recursion near 1000 frames by default; an explicit list stack, carrying tuples for extra state, removes that ceiling with the same O(n) and O(h) bounds.
- A dict-of-dicts trie finds a prefix in O(L) and pays at least 232 bytes per node on 64-bit CPython 3.9; a sorted list with bisect is the memory-light alternative.
- A binary tree serialized with null markers is 2n + 1 tokens; level order trims the trailing markers, and a BST needs no markers at all.
