# Decorators for Data Engineers: Beginner

A candidate sits down for a data engineering interview at Dropbox, whose engineers have written publicly about type checking 4 million lines of Python. The interviewer shares a file with 3 extract functions, each starting with `start = time.time()` and ending with a print of the elapsed seconds, and asks that every step report its runtime and record its failures while the step functions stay untouched. The candidate writes a wrapper, applies it with `@`, and runs the job through the team's task runner, whose report lists 3 steps, each named `wrapper`. Then come the follow-ups: why did the names vanish, why is `time.time()` the wrong clock, and should `from_dict` be a `@classmethod` or a `@staticmethod`? Each one probes the same skill: knowing exactly what a decorator does to the function underneath it.


<br>

### What you will be able to do

Recognize a cross-cutting concern behind an interview prompt and explain why a decorator fits it

Rewrite any @decorator line as the assignment it stands for, and write a wrapper that forwards any arguments

Use functools.wraps so a wrapped function still reports its own name and signature and keeps its docstring

From memory, write a timing decorator that uses perf_counter and logs and re-raises any failure

Pick @property, @staticmethod or @classmethod for each method of a pipeline config class


<br>

---

## Spotting Cross-Cutting Concerns

A cross-cutting concern is behavior that many functions need while none of them exists to provide it. A function named `extract_orders` exists to pull orders. Measuring how long it ran, logging what went wrong when it fails, retrying a flaky vendor call, recording who triggered it: those jobs cut across every step in a pipeline, and they look the same in each one. When an interview problem hands you several functions and asks for a single behavior added to all of them, you are looking at a decorator problem whether the word decorator appears.

```sql
import time


def extract_orders(day):
    start = time.time()
    rows = [{"order_id": 1, "day": day}]
    print(f"extract_orders took {time.time() - start:.2f}s")
    return rows


def extract_users(day):
    start = time.time()
    rows = [{"user_id": 7, "day": day}]
    print(f"extract_users took {time.time() - start:.2f}s")
    return rows


def extract_refunds(day):
    start = time.time()
    rows = [{"refund_id": 3, "day": day}]
    print(f"extract_refunds took {time.time() - start:.2f}s")
    return rows
```

Each function body holds 4 lines, and the start assignment and the print have nothing to do with the step's job. With 40 extract steps that is 80 copied lines, and every change of plan (a better clock, sending the number to a metrics system, logging failures) means 40 edits that must match exactly. The copies also share a bug: when building rows raises, the print never runs, so the failing step, the one you most need a number for, reports nothing.


<br>

### Three questions that expose the pattern

- Does the behavior happen before the call, after it, or around it, outside the function's own logic?
- Is it identical for every function it touches, apart from the name and arguments it reports?
- If you deleted it, would every function still compute the same result?

Three yes answers mark a cross-cutting concern. The table maps phrasings interviewers use to the concern each one hides and the moment that concern needs.

| What the prompt says | Concern | When it runs |
| --- | --- | --- |
| Every step should report how long it ran | Timing | Before and after the call |
| Log the arguments whenever a load fails | Error logging | Around the call, on an exception |
| The vendor API times out now and then, so try again | Retry | Around the call, more than once |
| Only the data platform team may trigger a backfill | Authorization | Before the call, and may block it |
| Don't query the dimension table twice for the same key | Caching | Before the call, and may skip it |
| Reject a batch with missing columns before it reaches the transform | Validation | Before the call, on the arguments |

The words that give the pattern away are usually 'for every', 'all of these' or 'without changing the functions'. The interviewer is checking whether you paste the same lines into each function or write the behavior once and attach it by name, and only the second answer still works when 3 steps become 40.

> The same pattern in design rounds
>
> - Add SLA alerts to all 200 tasks: timing plus a threshold, applied to every task
> - Every API client needs the same auth header and retry policy: a decorator on each call method
> - Record lineage for each write: a wrapper that reads the target table from the arguments


<br>

### When a decorator is the wrong tool

A wrapper sees the arguments going in and the return value or exception coming out, and nothing in between. A request to log the row count after the dedupe step inside `transform_orders` needs a moment in the middle of the function, so no wrapper can reach it. A rule like 'convert orders to USD but leave refunds alone' changes what each function computes, which makes it business logic. Forcing either into a decorator produces a wrapper full of `if func.__name__ == ...` branches, and those branches are the sign that the concern was never shared.

| ✓ Fits a decorator | ✗ Belongs inside the function |
| --- | --- |
| • Timing every extract step<br><br>• Logging any exception a load raises<br><br>• Retrying a call that timed out<br><br>• Returning a cached answer for a repeated key | • Logging the row count after the dedupe step<br><br>• Converting orders to USD but not refunds<br><br>• Picking a partition key per table<br><br>• Handling 1 source's odd date format |


<br>

### Try it: sort 5 requests

Decorator or not? Decide each one before reading the answers.

- **Request 1:** Every function that writes to the warehouse must record which table it was called with.
- **Request 2:** When load_events receives more than 1,000,000 rows, it should write them in 2 batches.
- **Request 3:** Count how many times each extract step runs per job.
- **Request 4:** Warn whenever any transform takes longer than 30 seconds.
- **Request 5:** Mask the email column after parsing and before writing.

| Request | Decorator? | Why |
| --- | --- | --- |
| 1 | Yes | The table name arrives as an argument, which the wrapper sees before the call |
| 2 | No | Batching changes how the function does its work |
| 3 | Yes | A counter bumped before each call, the same for every step |
| 4 | Yes | Compare the elapsed time after the call returns or raises |
| 5 | No | The moment sits between 2 internal steps, out of the wrapper's reach |

> **TIP**
>
> Name the pattern out loud before writing code: 'Timing is shared by every step, so I'll write it once as a decorator.' That sentence tells the interviewer you recognized the question, and it buys a few seconds to plan the wrapper.


<br>

---

## What @decorator Actually Does

A decorator is a function that takes a function and returns a function. The `@` line above a `def` is shorthand for an assignment Python runs right after it creates the function object, so the 2 definitions below bind the same thing to `load_orders`.

```sql
@timed
def load_orders(day):
    return [day]


def load_orders(day):
    return [day]


load_orders = timed(load_orders)
```

Three consequences follow from that assignment. `timed` runs once, when the `def` statement executes, which for a module-level function means import time. The name `load_orders` then refers to whatever `timed` returned, so every later call goes to that object. And when `timed` returns a new function that holds a reference to the original, the original still runs, from inside the new one. That new function is the wrapper, and it runs on every call.

*The same reassignment runs inside a class body, which is how the method decorators at the end of this lesson work.*


<br>

### Definition time and call time

Read this program and write down its 6 printed lines before checking the table under it.

```sql
def announce(func):
    print(f"decorating {func.__name__}")

    def wrapper(*args, **kwargs):
        print(f"calling {func.__name__}")
        return func(*args, **kwargs)

    return wrapper


@announce
def extract(day):
    return f"rows for {day}"


print("module loaded")
print(extract("2024-03-01"))
print(extract("2024-03-02"))
```

| Printed line | Why it prints there |
| --- | --- |
| `decorating extract` | `@announce` ran while the `def` executed, before any call |
| `module loaded` | The first top-level `print` after the definition |
| `calling extract` | First call: the wrapper runs before the original |
| `rows for 2024-03-01` | The value the wrapper passed back from the original |
| `calling extract` | Second call: the wrapper runs again and the decorator does not |
| `rows for 2024-03-02` | The second return value |

That split decides where each line belongs. Code in the decorator's own body runs once per decorated function, and code inside the wrapper runs once per call. A decorator that reads the clock in its outer body measures time since import, and one that opens a database connection there opens it during import, before the job has loaded its config. When a wrapper misbehaves, the first question is which of the 2 bodies the line sits in.

The animation decorates 2 functions, `load_orders` through the assignment and `load_users` through `@`, then calls both. Watch `calls` grow as each wrapper runs, and check the last printed line: after decoration, `load_orders.__name__` is the wrapper's name.

https://github.com/user-attachments/assets/75110e20-914a-4612-9b53-df59ea8e46f7

*The assignment and the @ line give the same result: a wrapper bound to the original name.*

The run shows `calls` recording `load_orders` and `load_users`. That works because each wrapper reads `func.__name__` from the function it closed over, while code outside sees only the wrapper and its name. That mismatch is the subject of the next section.


<br>

### A decorator does not have to wrap

Because `@` only assigns whatever the decorator returns, a decorator may hand back the original function untouched. That shape registers a function without adding any per-call cost:

```sql
TASKS = []


def register(func):
    TASKS.append(func)
    return func


@register
def extract_orders(day):
    return [day]
```

`register` runs once at definition time, and `extract_orders` stays the original function object, so it keeps its own name and adds no work to each call. Interviewers sometimes ask for this shape to see whether you know the wrapper is optional.


<br>

### A wrapper that accepts any arguments

A decorator is written once and applied to functions with different signatures, so the wrapper has to accept whatever the caller passes and hand it on untouched. `*args` collects positional arguments into a tuple, `**kwargs` collects keyword arguments into a dict, and `func(*args, **kwargs)` unpacks both back into the original call. The wrapper then returns the original's result, so callers receive the value they received before decoration.

```sql
def decorator(func):
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return result
    return wrapper
```

| Call | args | kwargs |
| --- | --- | --- |
| `load_orders("2024-03-01")` | `('2024-03-01',)` | `{}` |
| `load_orders("2024-03-01", limit=5)` | `('2024-03-01',)` | `{'limit': 5}` |
| `load_orders(day="2024-03-01", limit=5)` | `()` | `{'day': '2024-03-01', 'limit': 5}` |
| `load_orders()` | `()` | `{}` |

The wrapper passes bad calls through unchanged. The last row reaches the original, which raises `TypeError: load_orders() missing 1 required positional argument: 'day'`, the same message an undecorated call would produce, so decorating a function never changes how its callers get told they called it wrong.

> Try it: log every call's arguments
>
> Write `log_args`, a decorator that prints a call's positional and keyword arguments and then returns the original's result. Applied to `load_orders` and called as `load_orders("2024-03-01", limit=5)`, it should print `args=('2024-03-01',) kwargs={'limit': 5}` and return the same value as the undecorated call. Check your version against the solution below.

```sql
def log_args(func):
    def wrapper(*args, **kwargs):
        print(f"args={args} kwargs={kwargs}")
        return func(*args, **kwargs)
    return wrapper
```


<br>

### Four bugs and the errors they raise

| Bug in the decorator | What extract("2024-03-01") does |
| --- | --- |
| `def wrapper():` with no parameters | Raises `TypeError: timed.<locals>.wrapper() takes 0 positional arguments but 1 was given` (Python 3.9 names it `wrapper()`) |
| Wrapper calls `func()` with no arguments | Raises `TypeError: extract() missing 1 required positional argument: 'day'` |
| Decorator ends without `return wrapper` | `extract` is `None`, so the call raises `TypeError: 'NoneType' object is not callable` |
| Wrapper calls `func(\*args, \*\*kwargs)` without `return` | No error: every decorated function returns `None` |

> **TIP**
>
> The fourth bug is the one that reaches production, because nothing fails. A load step that returns `None` passes any check that only asks whether the job finished. Say 'and return the result' out loud as you type that line in an interview.


<br>

---

## Why functools.wraps Matters

Decoration rebinds the name, and the object it now points to is `wrapper`, carrying `wrapper`'s own metadata. Ask a decorated function about itself and the wrapper answers:

```sql
def timed(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


@timed
def load_orders(day: str) -> list:
    """Load a day of orders from the raw zone."""
    return [day]


print(load_orders.__name__)
print(load_orders.__doc__)
print(load_orders.__annotations__)
```

That prints `wrapper`, then `None`, then `{}`. The table sets each attribute beside what it reads once `functools.wraps` is added, which the rest of this section explains.

| Attribute | Without wraps | With wraps |
| --- | --- | --- |
| `__name__` | `wrapper` | `load_orders` |
| `__qualname__` | `timed.<locals>.wrapper` | `load_orders` |
| `__doc__` | `None` | `Load a day of orders from the raw zone.` |
| `__annotations__` | `{}` | `{'day': <class 'str'>, 'return': <class 'list'>}` |
| `inspect.signature(load_orders)` | `(\*args, \*\*kwargs)` | `(day: str) -> list` |

Code that reads type hints from `__annotations__`, such as a validator that checks argument types, finds `{}` on an unwrapped decorated function and checks nothing.


<br>

### Where a lost name hurts in production

Four places the wrong name causes damage

- **Monitoring** *every step is called wrapper*\
  A scheduler reads the name off the object it was handed, and so do profilers and error reporters. That object is the wrapper, so every step appears as wrapper and the slow one can't be picked out.
- **Registries** *steps overwrite each other*\
  Code that collects tasks into a dict keyed by __name__ stores every decorated step under the key wrapper, and each new step replaces the one before it.
- **Process pools** *the function cannot be sent*\
  A process pool sends a function to its workers by pickling it, and pickle saves only a reference to the function: its module plus its __qualname__. The wrapper's qualified name points inside the local scope of timed, which pickle can't look up, so the send fails with an AttributeError saying it can't pickle a local object.
- **Help and docs** *the contract disappears*\
  help() and generated reference pages show an empty docstring and the signature (\*args, \*\*kwargs), so the next engineer has to read the source to learn what to pass.

The registry failure does the most damage because it raises nothing. Predict the 2 printed lines, then play the animation.

https://github.com/user-attachments/assets/83e28934-c7e0-40ee-a1f5-9174f0ecab5b

*The registry receives 2 steps but keeps 1 key, and the orders extract is gone.*

Both wrappers report the name `wrapper`, so the second assignment replaced the first, and `registry["wrapper"]()` runs the users extract. A scheduler that loops over this dict runs users every night and orders never, and the only symptom is an orders table that stops growing.


<br>

### Adding functools.wraps

```sql
import functools


def timed(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper
```

`functools.wraps(func)` returns a decorator, and that decorator is applied to `wrapper` the moment it is defined. It copies 5 attributes from `func` onto `wrapper`: `__module__`, `__name__`, `__qualname__`, `__doc__` and `__annotations__`. It also merges `func.__dict__` into `wrapper.__dict__` and sets `wrapper.__wrapped__` to `func`. That last attribute is how `inspect.signature` reports the original parameters: it follows `__wrapped__` back to the undecorated function. With the fix in place the registry holds both keys, monitoring shows real step names, and pickle finds `load_orders` at module level.

Rerun the registry program in your head with the fix applied. `list(registry)` now prints `['extract_orders', 'extract_users']`, and `registry["wrapper"]` raises `KeyError: 'wrapper'`, because no task carries that name anymore.

`wraps` changes identity and nothing about behavior. The wrapper still runs on every call and still accepts any arguments, and `load_orders` is still a different object from the function you wrote. If you need the undecorated function itself, `load_orders.__wrapped__` holds it.

The rule holds for every layer. When 2 decorators are stacked and the inner one skips `wraps`, the outer one copies its metadata from the inner wrapper, so the outer `wraps` faithfully preserves the name `wrapper`, the only name left to copy.


<br>

### Predict the traceback

A common slip puts the `wraps` line above the decorator instead of above the wrapper. Using the rule that `@` means reassignment, work out when this fails and with what error.

```sql
import functools


@functools.wraps(func)
def timed(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper
```

It fails at import, before anything is called: the `@` expression `functools.wraps(func)` is evaluated at module level, where no `func` exists, so Python raises `NameError: name 'func' is not defined`. The parameter `func` only exists inside `timed`, which is why the `wraps` line belongs on `wrapper`.

| ✓ Do | ✗ Don't |
| --- | --- |
| • Put @functools.wraps(func) on every wrapper you write, even a 3-line one<br><br>• Log func.__qualname__ so methods read as Class.method<br><br>• Assert __name__ on a decorated function in a unit test | • Copy __name__ and __doc__ by hand; that misses __qualname__ and __wrapped__<br><br>• Key a registry by name while any decorator in the stack skips wraps<br><br>• Treat a missing wraps as cosmetic; it breaks pickling and registries |

> **TIP**
>
> Asked what changes without `wraps`, give 3 concrete failures: monitoring labels every step `wrapper`, name-keyed registries collide, and process pools can't pickle the function. Concrete failures land better than 'it loses metadata'.


<br>

---

## The Canonical Timing Decorator

Interviewers reach for a timing decorator because it packs the previous 2 sections into about 20 lines and adds 3 decisions: which clock to read, what happens when the function raises, and where the log line goes. Here is the version worth being able to write cold:

```sql
import functools
import logging
import time

logger = logging.getLogger(__name__)


def timed(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.exception("%s failed", func.__qualname__)
            raise
        finally:
            elapsed = time.perf_counter() - start
            logger.info("%s took %.3fs", func.__qualname__, elapsed)
    return wrapper
```


<br>

### Choosing the clock

A duration needs a clock that moves only forward. Python's `time` module offers 3 candidates, and only 1 of them fits a pipeline step.

| Clock | What it measures | Fit for timing a step |
| --- | --- | --- |
| `time.time()` | Wall-clock seconds since the epoch | Poor: time sync can step the system clock backward, so a duration can come out negative |
| `time.process_time()` | CPU time used by this process | Poor: waiting is left out, so a step that spends 40 seconds on a warehouse query reads near 0 |
| `time.perf_counter()` | A monotonic counter at the highest resolution available | Good: it includes time spent waiting and sleeping, the same time the caller waits |

Only the difference between 2 perf_counter() readings means anything, because the value counts from an undefined reference point, so it never belongs in a table. time.get_clock_info("perf_counter").monotonic returns True, confirming it can't run backward. Keep time.time() for timestamps, such as the loaded_at column a load writes.


<br>

### Why try, except and finally

The duration is logged in `finally`, so it's recorded whether `func` returns or raises, and the slow failures are the runs you most need a number for. The `except` block calls `logger.exception`, which logs at ERROR level and attaches the traceback, then a bare `raise` re-raises the same exception with its original traceback, so the orchestrator still sees the step fail and can retry or alert. Inside `try`, `return func(*args, **kwargs)` hands the value back: Python computes the return value and runs `finally` before it gives the value to the caller.

`except Exception` lets `KeyboardInterrupt` and `SystemExit` pass without a failure record, so stopping a job by hand doesn't page anyone, and both still travel through `finally`, so the duration is logged either way.

The animation swaps the real clock for a `deque` of fake readings so every run shows the same numbers, and a list stands in for the logger. Watch the order in which `log` fills: the failure line lands before the timing line, because `except` runs first and `finally` runs on the way out.

https://github.com/user-attachments/assets/3688de93-b6c0-4de4-ae25-97b22afd2142

*Fake readings make the run repeatable: 2.500s for the success, 0.250s for the failure.*

Run the canonical version with the same readings, and the 2 calls leave these records:

| Outcome | ERROR record | INFO record | Caller receives |
| --- | --- | --- | --- |
| `load_orders` returns 3 | None | `load_orders took 2.500s` | The value 3 |
| `load_refunds` raises `ValueError` | `load_refunds failed` plus the traceback | `load_refunds took 0.250s` | The same `ValueError`, original traceback intact |


<br>

### Two mistakes interviewers wait for

This version logs the failure and drops the `raise`. Predict what a decorated `load_refunds()` returns when its body raises `ValueError("bad row")`.

```sql
import time


def timed(func):
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            print(f"{func.__name__} failed: {exc}")
        finally:
            print(f"took {time.perf_counter() - start:.3f}s")
    return wrapper
```

It prints the failure and the duration, then returns `None`. The `except` block handled the exception, so the wrapper ran off its end with no return value, and the caller sees a successful call. The orchestrator marks the step green, the next step loads 0 rows, and nobody is paged. The second mistake hides in `finally`: writing `return elapsed` there discards any exception on its way out, because a `return` in `finally` replaces any exception or return value the `try` block was finishing with.


<br>

### A case this decorator gets wrong

If you decorate a generator function like `def read_rows(lines): ... yield row`, the timer reports close to 0 seconds no matter how many rows it produces. Calling a generator function only creates the generator; the reading happens later, when the caller iterates, long after `finally` has run. Time the loop that consumes the rows, or the step that drains the generator, instead.


<br>

### Rebuilding it from memory

- Import functools, logging and time, and create a module-level logger
- Put @functools.wraps(func) on the wrapper
- Accept \*args, \*\*kwargs so any step can be decorated
- Read time.perf_counter() into start before the try
- Return func(\*args, \*\*kwargs) from inside the try
- In except Exception, call logger.exception and then a bare raise
- Log the elapsed time in finally, and never return there
- End the decorator with return wrapper

The log lines use `func.__qualname__`, so a method shows up as `OrderLoader.run` where `__name__` would give only `run`, and 2 classes with a `run` method stay distinguishable.

> **TIP**
>
> Pass values to `logger` as `%s` arguments, as the canonical version does, instead of building an f-string. The logging module formats the message only when the record will be emitted, so a disabled INFO level costs a level check per call.


<br>

---

## Built-in Method Decorators

Python ships 3 decorators for methods, and each changes what the method receives as its first argument. Interviewers reach them through config classes: a prompt like 'design a class that holds a pipeline's settings' checks whether each piece of behavior lands in the right kind of method.

| Decorator | First argument | Called as | Use it when |
| --- | --- | --- | --- |
| None (regular method) | `self`, the instance | `cfg.validate()` | The method reads or changes this object's data |
| `@property` | `self` | `cfg.output_path`, no parentheses | A cheap value derived from the instance that reads like an attribute |
| `@classmethod` | `cls`, the class | `PipelineConfig.from_dict(raw)` | Building an instance another way, including for subclasses |
| `@staticmethod` | Nothing | `PipelineConfig.is_valid_table("orders")` | A helper that needs neither the instance nor the class |

Each one obeys the rule that `@` means reassignment. `@property` above `def output_path` runs `output_path = property(output_path)` inside the class body, replacing the function with a `property` object that calls it on attribute access. `@staticmethod` and `@classmethod` wrap the function in objects that change what Python passes as the first argument when the method is looked up.

```sql
import re


class PipelineConfig:
    def __init__(self, table, run_date, env="dev"):
        if not self.is_valid_table(table):
            raise ValueError(f"bad table name: {table}")
        self.table = table
        self.run_date = run_date
        self.env = env

    @property
    def output_path(self):
        return f"lake/{self.env}/{self.table}/dt={self.run_date}"

    @staticmethod
    def is_valid_table(name):
        return re.fullmatch(r"[a-z_]+", name) is not None

    @classmethod
    def from_dict(cls, raw):
        return cls(raw["table"], raw["run_date"], raw.get("env", "dev"))
```

*@property, @staticmethod and @classmethod are builtins, so they need no import, unlike functools.wraps.*


<br>

### @property: a derived value read like an attribute

`output_path` is computed on every read, so it always matches the current `env` and `table`. A property with no setter can't be assigned. Predict the 2 printed lines and what the last line does:

```sql
cfg = PipelineConfig("orders", "2024-03-01")
print(cfg.output_path)
cfg.env = "prod"
print(cfg.output_path)
cfg.output_path = "tmp/orders"
```

It prints `lake/dev/orders/dt=2024-03-01`, then `lake/prod/orders/dt=2024-03-01`, because the second read used the new `env`. The last line raises `AttributeError: property 'output_path' of 'PipelineConfig' object has no setter`; versions before 3.11 print the shorter `can't set attribute`. Adding parentheses fails differently: `cfg.output_path()` calls the string the property already returned, raising `TypeError: 'str' object is not callable`. Keep properties cheap and free of side effects. A value that needs a warehouse query or a file listing belongs in a regular method, because attribute syntax promises a cheap read and every access reruns the work.

#### Adding a setter for validation

When an attribute needs checking on assignment, a property with a setter runs the check every time, including the assignment in `__init__`. The value is stored under the private name `_env` so that it does not collide with the property:

```sql
class PipelineConfig:
    @property
    def env(self):
        return self._env

    @env.setter
    def env(self, value):
        if value not in ("dev", "prod"):
            raise ValueError(f"unknown env: {value}")
        self._env = value
```

With this added, `PipelineConfig("orders", "2024-03-01", env="qa")` raises `ValueError: unknown env: qa` at construction, before any path is built from a mistyped environment.


<br>

### @classmethod: constructors that respect subclasses

`from_dict` receives the class it was called on as `cls`, and `cls(...)` builds an instance of that class. The difference shows the moment someone subclasses the config:

```sql
class BackfillConfig(PipelineConfig):
    @property
    def output_path(self):
        return f"lake/backfill/{self.table}/dt={self.run_date}"


cfg = BackfillConfig.from_dict({"table": "orders", "run_date": "2024-03-01"})
print(type(cfg).__name__)
print(cfg.output_path)
```

This prints `BackfillConfig` and `lake/backfill/orders/dt=2024-03-01`. Had `from_dict` been a `@staticmethod` ending in `return PipelineConfig(...)`, the same call would build the parent class, and the backfill would write into `lake/dev/orders/`, on top of the daily partitions. Alternate constructors such as `from_dict` and `from_env` are the main reason to use `@classmethod`, and interviewers expect to see `cls` in them.


<br>

### @staticmethod: a helper filed under its class

`is_valid_table` reads neither `self` nor `cls`. It sits on the class because table-name rules are part of what a config means, and callers can use it before any instance exists, for instance to check a command-line argument with `PipelineConfig.is_valid_table("orders")`. A module-level function would behave the same, so choose `@staticmethod` when the helper belongs to the class's public vocabulary, and keep it module-level when other modules need it without the class.


<br>

### Try it: pick the decorator

An IngestJob class needs these 5 methods. Choose a regular method, @property, @classmethod or @staticmethod for each.

- from_settings(raw) builds a job from a dict of settings
- partition_key returns the table name and run date joined by a slash
- quote_identifier(name) wraps a column name in double quotes
- row_estimate runs `SELECT COUNT(*)` against the source table
- run loads the data and returns the number of rows written

| Method | Decorator | Reason |
| --- | --- | --- |
| `from_settings` | `@classmethod` | An alternate constructor, and `cls` keeps subclasses working |
| `partition_key` | `@property` | Cheap, derived from instance data, takes no arguments |
| `quote_identifier` | `@staticmethod` | Uses neither the instance nor the class |
| `row_estimate` | Regular method | Runs a query each time, which attribute syntax would hide |
| `run` | Regular method | Has side effects and reads the instance |

> **TIP**
>
> If the interviewer asks why `from_dict` shouldn't be a `@staticmethod`, answer with the subclass: a static constructor names a class and always builds that class, while a class method builds whichever class it was called on.


<br>

---

## Putting It All Together

A food delivery marketplace runs a nightly job that pulls orders, couriers and refunds from 3 vendor APIs, fans the extracts out across a process pool, and builds each step's settings from a config dict. One morning the refunds partition is empty and the run finished 40 minutes late, and the on-call engineer has to say which step failed and which one was slow.

- Timing and failure logging are needed by every extract step, so they belong in a single @timed decorator applied by name to all 3 steps.
- Because @timed means extract_refunds = timed ( extract_refunds ) , the wrapper runs on every call and must forward \* args , \*\* kwargs and return the rows.
- Without functools . wraps , the process pool cannot pickle the steps and the run report labels each one wrapper .
- Reading perf_counter in finally and re-raising in except turns the empty partition into an ERROR record with a traceback and a duration for the refunds step.
- ExtractConfig . from_dict as a @classmethod lets a backfill subclass build itself, and output_path as a @property keeps the partition path in step with env .


<br>

---

## Key Takeaways

- When every function needs the same code run before or after its calls, that's a decorator problem however the prompt words it.
- @timed above a def is name = timed ( name ) : the decorator runs once at definition, and the wrapper runs on every call.
- A wrapper takes \* args , \*\* kwargs and forwards both. It must also return the original's result, or every decorated step returns None .
- functools . wraps ( func ) copies __name__ and __qualname__ onto the wrapper, along with __doc__ , and keeps the original signature visible. A task registry keyed by name needs that, and so do monitoring and pickling.
- Time with perf_counter , log the duration in finally , and re-raise with a bare raise so failures stay failures.
- Use @property for cheap derived values, @classmethod for alternate constructors, and @staticmethod for helpers that need neither.
