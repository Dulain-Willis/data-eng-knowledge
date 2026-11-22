# OOP for Data Engineers: Beginner

Dalia is 40 minutes into a data engineering interview at Spotify, whose engineers open-sourced a Python framework in which every batch job is written as a class. The interviewer pastes a short `TableLoader` and describes an incident: a worker process built a loader for `orders` and another for `refunds`, and the refunds table ended up holding order rows. What happened? Dalia scans the constructor, spots `rows=[]` in the signature, and explains that the default list was created once, when the function was defined, so both loaders appended to it. The follow-ups come quickly. Make `batch_size` reject 0 without touching the 30 callers. Make the log line say which table failed. Close the connection even when row 317 raises. Each follow-up tests a different part of how Python classes work, and each has a precise, checkable answer.


<br>

### What you will be able to do

Name the 5 OOP fundamentals behind pipeline-code interview questions and spot each one in a broken class.

Write a class with instance, class and static methods, plus a __repr__ and __str__ that make log lines readable.

Predict what a class with a mutable default argument prints, and fix it with a None default.

Add validation to an existing attribute with @property so callers keep the same syntax.

Implement __enter__ and __exit__ so a connection closes when the body raises, and explain what returning True does.


<br>

---

## The OOP Basics Interviewers Test

Interview questions on object-oriented Python for data roles are usually built from pipeline code. The interviewer hands you a class from a loader, a config holder or a connection wrapper, and asks what it prints or why it misbehaves. Nearly all of these questions come down to 5 ideas, and each one matches a bug that reaches production when it is misunderstood. Learning to name the idea from the symptom is most of the work, because the fix for each is short once you know which one you are looking at.


<br>

### The 5 ideas and the bug each prevents

| Fundamental | Where it lives in pipeline code | The bug when it is misunderstood |
| --- | --- | --- |
| Method types: instance, class, static | Per-batch logic, `from_config` constructors, pure helpers | A subclass built through `from_config` comes back as the parent class |
| `__repr__` and `__str__` | Log lines, error messages, debugger output | Logs show `<__main__.TableLoader object at 0x7f3a2c1b9e50>` and nothing about the table |
| Shared mutable state | Default arguments and class-level lists or dicts | Two loaders append to a single list, so tables receive each other's rows |
| Validated attributes with `@property` | Config values such as `batch_size` that many callers read and set | A `batch_size` of 0 is accepted and fails hours later as `ZeroDivisionError` |
| Context managers | Connections, locks, temporary tables | A failed load leaves the connection open and the lock held |


<br>

### The lookup rule underneath them

When code reads loader.table, Python looks in the instance's own namespace first, the dict at loader.__dict__, and falls back to the class only when the name is missing there. Methods are stored once, on the class, and receive the instance as self when called through it. Assignment follows a different rule: loader.retries = 5 always writes into the instance's dict, even when the class already defines retries.

```sql
class TableLoader:
    retries = 3

    def __init__(self, table):
        self.table = table


orders = TableLoader("orders")
refunds = TableLoader("refunds")
orders.retries = 5
print(orders.retries, refunds.retries, TableLoader.retries)
print(orders.__dict__)
print(refunds.__dict__)
```

The first print shows `5 3 3`. The assignment gave `orders` its own `retries`, which hides the class value for that instance alone, while `refunds` finds nothing in its own dict and reads 3 from the class. The dicts confirm it: `orders.__dict__` is `{'table': 'orders', 'retries': 5}` and `refunds.__dict__` is `{'table': 'refunds'}`.

```sql
class TableLoader:
    failed_rows = []

    def __init__(self, table):
        self.table = table

    def reject(self, row):
        self.failed_rows.append(row)


orders = TableLoader("orders")
refunds = TableLoader("refunds")
orders.reject({"order_id": 317})
print(refunds.failed_rows)
print("failed_rows" in orders.__dict__)
```

> Predict before reading on
>
> The refunds loader never rejected anything. Decide what each of the 2 print calls shows, and whether `orders` now has its own `failed_rows`.

It prints `[{'order_id': 317}]` and then `False`. The expression `self.failed_rows.append(row)` reads `failed_rows`, finds it on the class, and changes that list in place. Nothing was assigned through `self`, so no instance attribute was created, and every loader, including ones built tomorrow, sees the rejected order. The mutable default argument later in this lesson fails for the same reason, a single container reachable from many instances, and the cure in both cases is to build the container inside `__init__`.


<br>

### Naming the idea from the wording

How the questions are phrased

- **"Why do these 2 objects share data?"** *Shared mutable state*\
  Look for =[] or ={} in a signature, or a container assigned in the class body.
- **"Reject bad values, but don't change the callers."** *@property*\
  The constraint on callers rules out a new setter method. The answer has to keep attribute syntax.
- **"The connection leaks when the transform throws."** *Context manager*\
  Cleanup must run on the error path, which means __exit__ or a finally block.
- **"Add a way to build this from a config dict."** *Class method*\
  An alternate constructor takes cls, so a subclass gets its own type back.
- **"What does this line put in the log?"** *__repr__ and __str__*\
  Trace which method print, an f-string or a list calls, and what happens when that method is missing.

Questions in this format usually chain. An answer about the shared list invites a follow-up on how to test for it, then another on what happens to the connection when the load fails halfway. Preparing each topic in isolation leaves gaps at the joins, so the rest of this lesson keeps the same `TableLoader` and grows it one topic at a time.

#### A 4-step scan of any class they paste

- Read the signatures first: a container default is visible before any logic.
- Find every attribute assigned in the class body, and ask whether it can be mutated.
- Mark each method by its first parameter: self, cls or none.
- Look for resources opened without a with, and trace what happens if the next line raises.

> **TIP**
>
> A complete answer has 3 parts: what Python does mechanically, the fix, and 1 line of code that proves the fix works, such as checking `a.rows is b.rows` before and after. Interviewers listen for the mechanism, and a fix offered without it sounds memorized.


<br>

---

## Class Structure and Method Types

A pipeline class needs 3 kinds of behavior: logic that works on a single object's state, ways to build an object from outside input, and helpers that need neither. Python gives each its own method type, and what separates them is the first argument the method receives, which decides what the method can see.

| Method type | Decorator | First argument | Can read | Pipeline use |
| --- | --- | --- | --- | --- |
| Instance | none | `self`, the instance | Instance and class attributes | Count batches, buffer and flush rows |
| Class | `@classmethod` | `cls`, the class it was called on | Class attributes only | Build a loader from a config dict |
| Static | `@staticmethod` | none | Only its own arguments | Check a table name, parse a partition date |

https://github.com/user-attachments/assets/1e468b9a-5d45-4dad-a645-b43c824218fe

*A class method builds the loader, an instance method reads its state, a static method needs neither*

Walk the run in order. `from_config` receives `cls`, which is `TableLoader` here, and converts `"500"` to an int, because config values usually arrive as strings from environment variables or YAML. The object it returns prints through `__repr__` as `TableLoader(table='orders', batch_size=500)`. `batches_needed(1200)` reads `self.batch_size` and returns 3. `is_valid_table` returns `False` for `orders-2024`, since a hyphen is not allowed in an identifier, and it needed no instance to decide. `loaders_created` ends at 1, because the counter lives on the class and `__init__` updated it through the class name.

Updating through the class name is what makes the counter work. Had `__init__` written `self.loaders_created += 1`, the class counter would stay at 0. The augmented assignment reads `loaders_created` from the class, adds 1, and writes the sum into the instance's own dict, so every loader holds a private 1 and `TableLoader.loaders_created` never moves.


<br>

### Why the constructor takes cls

Writing `return TableLoader(...)` inside `from_config` works until someone subclasses the loader. A class method's `cls` is whatever class the call was made on, so the same method builds the right type for every subclass without an override. The same holds when config later moves from a dict to environment variables: a second class method, `from_env`, sits beside the first, and both return whatever class they were called on.

```sql
class TableLoader:
    def __init__(self, table, batch_size):
        self.table = table
        self.batch_size = batch_size

    @classmethod
    def from_config(cls, config):
        return cls(config["table"], int(config["batch_size"]))


class AuditedLoader(TableLoader):
    def flush(self):
        print(f"audit: flushing {self.table}")


loader = AuditedLoader.from_config({"table": "orders", "batch_size": "500"})
print(type(loader).__name__)
loader.flush()
```

This prints `AuditedLoader` and then `audit: flushing orders`. Replace `cls(...)` with `TableLoader(...)` and the first line becomes `TableLoader`, while the second fails with `AttributeError: 'TableLoader' object has no attribute 'flush'`, because the object that came back is the parent class, which never defined `flush`.

> Choosing the method type
>
> - Reads or changes a single object's data: instance method.
> - Returns a new instance built from other input: class method that calls `cls`.
> - Needs neither the instance nor the class: static method, or a plain module-level function.
> - A static method that names its own class inside is usually a class method written wrong.


<br>

### __repr__ and __str__ in your logs

With neither method defined, an object prints as `<__main__.TableLoader object at 0x7f3a2c1b9e50>`. The hex number is a memory address that changes on every run, so a log line built from it tells the on-call engineer nothing about which table failed. `__repr__` is the developer's view: unambiguous, and ideally a string that looks like the constructor call that would rebuild the object. `__str__` is the readable view, meant for messages people read.

```sql
class TableLoader:
    def __init__(self, table, batch_size):
        self.table = table
        self.batch_size = batch_size

    def __repr__(self):
        return f"TableLoader(table={self.table!r}, batch_size={self.batch_size})"

    def __str__(self):
        return f"loader for {self.table} in batches of {self.batch_size}"


loader = TableLoader("orders", 500)
print(loader)
print([loader])
print(f"{loader!r}")
```

The 3 calls print `loader for orders in batches of 500`, then `[TableLoader(table='orders', batch_size=500)]`, then the repr on its own. A list builds its text from the `__repr__` of each element, whatever that element's `__str__` returns, so a batch of loaders written to a log always shows the repr.

| Expression | Calls | When that method is missing |
| --- | --- | --- |
| `print(x)` | `__str__` | Falls back to `__repr__` |
| `f"{x}"` and `str(x)` | `__str__` | Falls back to `__repr__` |
| `repr(x)` and `f"{x!r}"` | `__repr__` | The default `<... object at 0x...>` |
| `print([x])` or `print({"k": x})` | `__repr__` of each element | The default `<... object at 0x...>` |
| Echo in the interactive shell | `__repr__` | The default `<... object at 0x...>` |

> Predict the output
>
> Delete `__repr__` from the class above and keep `__str__`. What do `print(loader)` and `print([loader])` show now?

`print(loader)` is unchanged, because `__str__` still exists. `print([loader])` drops to the default and shows `[<__main__.TableLoader object at 0x...>]`. The reverse case is safe: a class with only `__repr__` shows the repr everywhere, which is why `__repr__` is the one to write first.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Put the fields that identify the object in __repr__: table, partition, batch size<br><br>• Write __repr__ first, then add __str__ only when people read the output<br><br>• Keep __repr__ free of side effects, since debuggers and logs call it often | • Return a huge string, such as every buffered row, from __repr__<br><br>• Print secrets like passwords or tokens inside __repr__<br><br>• Leave the default repr on a class that appears in error messages |

> **TIP**
>
> Use `!r` on string fields inside `__repr__`. It adds quotes, so an empty table name shows as `table=''` rather than `table=` with nothing after it, and a stray trailing space shows up as `'orders '`.


<br>

---

## The Mutable Default Trap

A default value in a `def` line is evaluated once, when Python executes the `def`, and the resulting object is stored on the function. Every later call that leaves the argument out receives that same object. For an int or a string the sharing is harmless, because nothing can change those in place. For a list or a dict, every instance that took the default holds a reference to a single shared container, and an append through any of them shows up in all of them.

https://github.com/user-attachments/assets/7005f1e1-2dfe-407e-af6d-4902dcd921f0

*Both loaders hold the default list that lives on the function*

The first print shows `3 3`: 2 loaders, 3 rows, a single list. `orders.rows is refunds.rows` is `True`, and `__defaults__` shows where that list lives, inside the function object `TableLoader.__init__`, with all 3 rows in it. The refunds loader received both orders even though it was created before either was added, because the list was referenced, never copied.


<br>

### Why tests miss it

A unit test usually builds a loader, adds a few rows and checks the count, which passes. The bug needs 2 instances that both took the default, alive in the same process, and a long-running worker produces exactly that. Picture a worker that builds a loader per table for 40 tables, each buffering 500 rows, and flushes them all at the end of the run, where each flush writes `self.rows` and leaves the list as it is. The shared list holds 20,000 rows and every flush writes all of it, so each table receives 19,500 rows that belong to other tables. A flush that clears the list afterwards fails in a different way: the first table to flush receives all 20,000 rows and the other 39 receive none.

- **800,000** — rows written by the 40 flushes

A regression test for this bug builds 2 instances with the default in the same test and then checks identity with `assert a.rows is not b.rows`. Comparing lengths alone can pass by coincidence when both buffers happen to hold the same number of rows.




<br>

### The fix: None as the default

```sql
class TableLoader:
    def __init__(self, table, rows=None):
        self.table = table
        self.rows = [] if rows is None else list(rows)

    def add(self, row):
        self.rows.append(row)


orders = TableLoader("orders")
refunds = TableLoader("refunds")
orders.add({"order_id": 1})
print(len(orders.rows), len(refunds.rows))
print(orders.rows is refunds.rows)
```

Now it prints `1 0` and `False`. `None` is immutable, so sharing it is safe, and the `[]` inside the body runs on every call. 2 more details separate a correct answer from a nearly correct one.

- list(rows) copies what the caller passed. Without the copy, the loader appends into the caller's own list, which is the same sharing bug moved a step outward.
- The test is rows is None. Writing if not rows treats an explicit empty value as missing, and the same habit breaks an argument like max_errors=0, where 0 is a real setting.


<br>

### The same cause in other shapes

| Shape | What is shared | Fix |
| --- | --- | --- |
| `def __init__(self, rows=[])` | A list stored on the function | `rows=None`, build the list in the body |
| `def __init__(self, options={})` | A dict stored on the function | `options=None`, build the dict in the body |
| `class Loader: errors = []` | A list stored on the class | Assign `self.errors = []` in `__init__` |
| `def run(self, started=datetime.now())` | A timestamp fixed when the `def` ran at import | `started=None`, call `datetime.now()` in the body |

The last row holds no mutable object and fails for the same reason: every run reports the time the module was imported. Whenever a default is computed by an expression, ask when that expression runs, and the answer is always the moment the `def` executed.

```sql
def tag_batch(batch_id, tags=[]):
    tags.append(f"batch-{batch_id}")
    return tags


first = tag_batch(1)
second = tag_batch(2)
third = tag_batch(3, ["manual"])
print(first)
print(third)
print(first is second)
```

> Predict the output
>
> Write down all 3 printed lines before reading the answer. Note that `first` was assigned before the second call ran.

The output is `['batch-1', 'batch-2']`, then `['manual', 'batch-3']`, then `True`. `first` and `second` are 2 names for the default list, so printing `first` after the second call shows both tags. The third call passed its own list, which left the default alone.

> Explaining it in 3 sentences
>
> - Default values are evaluated once, when the `def` statement runs.
> - Every call that omits the argument gets that same object, so instances share it.
> - Use `None` as the default and build a fresh container inside the body.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Default container arguments to None and build them in the body<br><br>• Copy a container the caller passes in when the object will mutate it<br><br>• Build per-instance lists and dicts inside __init__ | • Write =[], ={} or =set() in a signature<br><br>• Put lists or dicts at class level when each instance needs its own<br><br>• Compute a timestamp or ID in a default value |

> **TIP**
>
> Common Python linters report a mutable default as a warning. In an interview, mention the linter rule after explaining the mechanism, as the step that stops the bug from coming back.


<br>

---

## Validation with @property

Suppose `TableLoader` is in production with a plain attribute, `self.batch_size = batch_size`, read and assigned in 30 places across the codebase. A config typo sets it to 0, and the assignment goes through without complaint. The job fails much later, when a division by the batch size raises `ZeroDivisionError` far from the line that caused it. The interview requirement is precise: reject a bad value at the moment it is set, and leave all 30 call sites as they are.

A property keeps the syntax `loader.batch_size` and `loader.batch_size = 2000` while running a method behind each one. The getter runs on every read and the setter on every assignment, and the value itself is stored in a separate attribute, self._batch_size by convention.

```sql
class TableLoader:
    def __init__(self, table, batch_size):
        self.table = table
        self.batch_size = batch_size

    @property
    def batch_size(self):
        return self._batch_size

    @batch_size.setter
    def batch_size(self, value):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"batch_size must be an int, got {type(value).__name__}")
        if not 1 <= value <= 10_000:
            raise ValueError(f"batch_size must be 1 to 10000, got {value}")
        self._batch_size = value
```


<br>

### 3 details interviewers check

- **__init__ assigns through the property**\
  self.batch_size = batch_size in the constructor calls the setter, so TableLoader("orders", 0) fails at construction. Writing self._batch_size there skips validation for every new object.
- **The stored name differs from the property name**\
  If the setter wrote self.batch_size = value, it would call itself until Python raised RecursionError.
- **bool is rejected first**\
  True is an instance of int in Python, so without that check batch_size=True would pass as a batch size of 1.

#### Raising the right exception type

The setter raises `TypeError` when the value is the wrong kind of object and `ValueError` when it's the right kind with an unusable value. Callers that read batch sizes from config often catch `ValueError` to fall back to a default, and a string where an int belongs should not be swallowed by that handler.

```sql
loader = TableLoader("orders", 500)
loader.batch_size = 2000
print(loader.batch_size)
loader.batch_size = 0
print("after the update")
```

> Predict the output
>
> Using the class above, decide what the 2 print calls show. One of them may never run.

The first print shows `2000`. The next assignment calls the setter with 0, which fails the range check, so the program stops with `ValueError: batch_size must be 1 to 10000, got 0`. The traceback points at `loader.batch_size = 0`, the line that introduced the bad value, and `after the update` never prints.

| Caller code | Plain attribute | With @property |
| --- | --- | --- |
| `loader.batch_size` | Returns the stored value | Getter returns `self._batch_size` |
| `loader.batch_size = 2000` | Stores 2000 | Setter checks it, then stores 2000 |
| `loader.batch_size = 0` | Stores 0, fails hours later | Raises `ValueError` on this line |
| `TableLoader("orders", "500")` | Stores the string `"500"` | Raises `TypeError` in `__init__` |


<br>

### Read-only and computed properties

A property with no setter cannot be assigned. That fits values fixed at construction, such as the target table, and values derived from other state, such as the number of buffered rows, which would go stale if stored as a separate attribute. Each read of `rows_buffered` calls `len` again, so the number is always current.

```sql
class TableLoader:
    def __init__(self, table):
        self._table = table
        self._rows = []

    @property
    def table(self):
        return self._table

    @property
    def rows_buffered(self):
        return len(self._rows)


loader = TableLoader("orders")
print(loader.table, loader.rows_buffered)
loader.table = "refunds"
```

It prints `orders 0` and then raises `AttributeError`. On Python 3.9 the message is `can't set attribute`, and from Python 3.11 it reads `property 'table' of 'TableLoader' object has no setter`. Python treats the _ prefix as a naming convention only, so `loader._table = "refunds"` still succeeds. A property guards the public path and documents intent, and saying so in an interview is more accurate than calling the value private.

Because a property keeps the attribute syntax, the decision can wait. Start with a plain attribute, and convert it to a property on the day a bad value fails far from where it was set, or the value has to be computed. No caller changes when you do, which is the reason the interview question insists on keeping the interface.

| ✓ Setter method: set_batch_size() | ✗ @property |
| --- | --- |
| • Every one of the 30 call sites has to change<br><br>• Old code that assigns loader.batch_size directly skips the check<br><br>• Readers see 2 names for a single value | • Call sites keep loader.batch_size = n unchanged<br><br>• Every assignment, including the one in __init__, runs the check<br><br>• The value keeps a single public name |


> **TIP**
>
> Put the check in the setter and route `__init__` through it. A check written only in the constructor runs once, and every later assignment bypasses it.


<br>

---

## Implementing a Context Manager

A loader that opens a warehouse connection, writes rows and closes it has a hidden failure path. If the write raises, the `close()` line never runs. In a worker that processes 40 tables, a handful of bad rows can leave connections open until the pool runs dry, and a staging lock left behind blocks the next night's run.

```sql
conn = WarehouseConnection("orders_db")
conn.open()
conn.load(rows)
conn.close()
```

A `try`/`finally` around the load fixes a single call site. A context manager moves that `try`/`finally` into the class, so every caller who writes `with` gets the cleanup without having to remember it.

| ✓ Cleanup at each call site | ✗ Cleanup in __exit__ |
| --- | --- |
| • Every caller writes its own try/finally<br><br>• A single forgotten block leaks a connection<br><br>• Cleanup logic is copied into every job | • Callers write with WarehouseConnection(...) as c:<br><br>• Every exit path runs the same release code<br><br>• A fix to cleanup lands in a single place |


<br>

### What the with statement does

| Step | What Python does |
| --- | --- |
| 1 | Evaluates the expression after `with` to get the manager object |
| 2 | Calls `__enter__()` and binds its return value to the name after `as` |
| 3 | Runs the indented body |
| 4a | Body finishes: calls `__exit__(None, None, None)` |
| 4b | Body raises: calls `__exit__` with the exception type, the exception and its traceback |
| 5 | A truthy return from `__exit__` suppresses the exception, and anything else lets it propagate |

https://github.com/user-attachments/assets/29e7cade-1494-4657-b186-697ad030b9e6

*__exit__ closes the connection before the outer except sees the error*

Read the printed lines in order. `close orders_db error: ValueError` appears before `caught: bad row 317`, so cleanup finished before the `except` block saw the exception. `still open? False` confirms the connection closed on the error path, and `never reached` is absent because the body stopped at the `raise`. `__exit__` returned `False`, so the exception continued out of the `with` block to the caller.

#### The with block written out by hand

For a body with no `return` or `break`, the `with` block in the animation behaves like the code below. The expansion makes 2 rules concrete: `__exit__` runs on both branches, and the exception is re-raised only when `__exit__` returns something falsy.

```sql
manager = WarehouseConnection("orders_db")
c = manager.__enter__()
try:
    print("loading 500 rows into", c.name)
    raise ValueError("bad row 317")
except BaseException as err:
    if not manager.__exit__(type(err), err, err.__traceback__):
        raise
else:
    manager.__exit__(None, None, None)
```


<br>

### Returning True hides the failure

> Predict the output
>
> Change `return False` to `return True` in `__exit__`. Which of the 5 lines still print, and what does the job look like to whoever reads its logs?

Of the 5 lines, 4 print: `open orders_db`, `loading 500 rows into orders_db`, `close orders_db error: ValueError` and `still open? False`. `caught: bad row 317` disappears, because a truthy return suppresses the exception and execution continues after the `with` block as if the load succeeded. The job finishes green with a partial table behind it. Return `False`, or nothing, unless the manager exists to handle a specific exception type, and in that case check `exc_type` before returning `True`.


<br>

### Commit or roll back in __exit__

`exc_type` tells `__exit__` which path it is on, which makes it the place for transaction handling. `__enter__` also has no obligation to return `self`. Here it returns the connection, so the body works directly with the object it needs.

```sql
class Transaction:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        self.conn.begin()
        return self.conn

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        return False


with Transaction(conn) as c:
    c.load(rows)
```

A successful body commits. Any exception rolls back and then propagates, so a failed batch leaves no partial rows in the table and the job still fails loudly.


<br>

### When __enter__ itself fails

If `__enter__` raises, `__exit__` is not called, because the `with` block never started. That decides where acquisition belongs. Open the resource inside `__enter__`, so an object that is created and never used in a `with` holds nothing open. And if `__enter__` acquires 2 resources and the second fails, it has to release the first itself before re-raising, since no `__exit__` is coming.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Acquire the resource in __enter__ and release it in __exit__<br><br>• Return False from __exit__ unless suppressing an error is the manager's job<br><br>• Write with a, b: for 2 resources, which exits b before a | • Open connections in the __init__ of a context manager<br><br>• Return True from __exit__ to keep a failing job green<br><br>• Let __exit__ raise a new error on the error path, which hides the original |


> **TIP**
>
> In an interview, trace the error path out loud: raise inside the `with`, then state the order of the prints and whether the exception reaches the caller. That single trace covers ordering, cleanup and suppression, the 3 things this question is built to check.


<br>

---

## Putting It All Together

A grocery delivery company runs a nightly job in a single worker process that loads 40 warehouse tables, orders, refunds and inventory among them, in batches of 500 rows. One morning the refunds table holds order rows, a log line reads <__main__.TableLoader object at 0x7f3a2c1b9e50> failed, and the next night's run is blocked by a staging lock left behind by a failed load.

- The order rows in refunds trace to rows = [ ] in the loader's constructor: all 40 loaders appended to a single list stored on TableLoader . __init__ .
- The unreadable log line is a missing __repr__ . Adding one that prints table and batch_size names the failing table.
- The stuck lock is cleanup that ran only on the success path. A context manager whose __exit__ releases the lock and returns False frees it and still surfaces the error.
- A batch_size property with a range check stops the next config typo at the assignment line instead of hours into the run.
- Building loaders through from_config ( cls , . . . ) lets an audited subclass reuse the same constructor without overriding it.


<br>

---

## Key Takeaways

- Attribute reads check the instance, then the class, while assignment through an instance always writes to the instance.
- Alternate constructors call cls so subclasses get their own type, and __repr__ comes first because lists and the shell use it.
- Default values are evaluated once, when the def runs, so container defaults are None and get built in the body.
- @property adds validation behind existing attribute syntax, and __init__ should assign through it.
- __exit__ runs on success and on error, before any outer except , and a truthy return swallows the exception.
