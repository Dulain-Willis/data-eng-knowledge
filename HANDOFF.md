# HANDOFF (temporary file, the user will delete it later)

Written at the end of a long session so a fresh agent with no context can continue. Read all of it before acting.

## 0. How the user wants you to work (important)

- Answers: 1 to 2 sentences, ONE thing at a time (one category at a time). The user got annoyed at long answers. Plain language. Use they/them for the user.
- If something is ambiguous or "looks weird", STOP and ask in plain text. Accuracy beats speed. Do not use dialog/question tools; just ask in the reply.
- Use sub-agents for big work but start them as FRESH agents (subagent_type general-purpose) with fully self-contained prompts. NEVER use `subagent_type: "fork"`: forks copy the whole conversation and start at 300k+ tokens (the user noticed and was upset).
- PR rule: the user usually wants a PR link to review. Do NOT merge unless they say so. Small docs fixes: they said "push straight to main" is fine. Every PR body ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`; every commit message ends with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Before any PR is called done, the agent must check how it renders on GitHub with Playwright (open the rendered blob pages of the repo on github.com; the repo is public) and look at screenshots.
- Do not edit `lessons/interview/architecture/index/*` (generated indexes, already out of sync, the user said leave them) or `docs/index-lesson/` (historical eval records).
- The "N challenges" number in each lesson's first line is left as is even where exercises are left out (user decision).

## 1. What this repo is

`~/projects/data-eng-knowledge` (GitHub: Dulain-Willis/data-eng-knowledge, public). Data-engineering lessons copied from datadriven.io (`https://datadriven.io/learn/<slug>`) into Markdown by `tools/lesson_to_md.py`, plus an MCP server `server.py` (reads `lessons/interview/architecture/` by default). Read `.claude/skills/lesson-to-md/SKILL.md` and `BLOCK-TYPES.md` first, and `docs/skipped-blocks.md` (PR #6, see below).

Run the converter: `.venv/bin/python tools/lesson_to_md.py <slug> --screenshots`. The output folder comes from `tools/topics.json` (slug without tier suffix -> `<area>/<topic>` under `lessons/`); an unmapped slug stops with an error (on purpose). Playwright is installed in `.venv` (untracked) with chromium in `~/.cache/ms-playwright`.

Layout now on main: `lessons/<learn|interview|tools>/<area>/<card_folder>/<slug>.md`, images in `<card_folder>/_images/`, exercises (only for the 4 non-tool areas) in `<card_folder>/_exercises/<slug>.md` (one file per lesson, continuous numbering). Card folder names are the snake_case of the card titles shown in the site UI.

## 2. Done and merged on main

- Lessons for: Learn architecture (30), Learn data modeling (11), Interview architecture (26), Interview data modeling (8), Airflow (15), dbt (15), Kafka (15) = 120 lessons. Their exercises: kept for the 4 non-tool areas (574, now in `_exercises/`), left out for Airflow/dbt/Kafka. Inline multiple-choice questions always stay in the lesson.
- `lesson_preview/` was renamed to `lessons/`. `images/` was renamed to `_images/` everywhere. (PRs #1, #2, #3, #4 merged.)
- `tools/topics.json`: hand-kept map of slug stem -> folder. `tools/drops.json`: hand-kept text prefixes of blocks dropped when a lesson's exercises are left out (so no sentence is left pointing at a removed exercise). It applies only in the "exercises left out" mode and warns if an entry matches nothing. Current entries: 2 Kafka drill sentences, plus 2 dormant data-modeling ones.
- The "Official <tool> resources" panel is dropped for tool lessons (`data-tool-partner-panel`).
- Converter on main today: `SKIPPED_TOOL_EXERCISES = {"dbt","kafka"}`; `INCLUDE_AIRFLOW_EXERCISES = False`; the final `else` branch of `main()` writes exercises INLINE in the lesson (that inline path is not updated to write `_exercises/`; a converter follow-up is still TODO, but it is not needed while all new categories leave their exercises out).

## 3. In flight right now (do not duplicate)

- **PR #6** (open, never merged yet): `docs/skipped-blocks.md`, documents which exercises/blocks are skipped per area with counts. IT MUST BE EXTENDED for every new category (Spark/Python/SQL) in that category's PR, because the user wants a place to find skipped exercises to do later.
- **PR #5** (open, the user's own README header edit). Not yours.
- **Spark agent** (id `ac25001e87b43cf65`, a fresh agent, still running when this was written): working in the MAIN checkout `~/projects/data-eng-knowledge` on local branch `learn-spark-lessons` with uncommitted changes. It converts all 45 Learn Spark lessons, adds `executable_spark` handling, adds `spark` to `SKIPPED_TOOL_EXERCISES`, adds 2 drops.json entries, switches the converter to write `_images/`, fixes the animation recorder for lazily mounted `spark_animation` controls, and will push a branch + open a PR (not merged). DO NOT touch the main checkout's working tree or switch its branch until that agent is finished; check `git status` and `gh pr list` first. Use `git worktree add <path> -b <branch> origin/main` for your own work.
- **Review-screenshots PR**: REVIEW_PR_LINK_PLACEHOLDER (a never-merge draft PR showing screenshots of every Learn Python place the user must look at; see section 7).

## 4. Where things stand per category (the user thinks in these categories)

| | Learn | Interview |
|---|---|---|
| Architecture | done (30) | done (26) |
| Data modeling | done (11) | done (8) |
| Spark | PR in progress (45 lessons, 15 cards) | none exists in what the user gave |
| Python | mapped + scanned (42), needs new block rules + drops | mapped + scanned (60), CLEAN, queued |
| SQL | mapped + scanned (30), needs new block rules + drops | mapped + scanned (48), CLEAN, queued |

Plan (user agreed): when the Spark PR is up, do Interview Python (own PR, own worktree, stacked on the Spark branch because both edit the same converter lines), then Interview SQL stacked on that, then talk through Learn Python, then Learn SQL, ONE at a time. Each category's PR: add its stems to `tools/topics.json`, add its exercise kind to `SKIPPED_TOOL_EXERCISES`, convert with `--screenshots`, update `docs/skipped-blocks.md`, Playwright-check on GitHub, open PR, do not merge.

## 5. Slug map (all verified: page titles / section headings match the UI cards; each stem has `_beginner/_intermediate/_advanced`)

Source of truth for slugs: `https://datadriven.io/sitemap.xml` -> `/sitemap/0.xml` ... `/sitemap/5.xml` list every `/learn/` slug EXCEPT the interview ones (`py_pattern_*`, `sql_pattern_*`, `pa_pattern_*`, `dm_pattern_*`, which exist at `https://datadriven.io/learn/<slug>` but are not in the sitemap; they were found by probing, 404 vs 200). Learn SQL slugs have NO prefix. Spark has Learn only (no Spark interview set was given). The ONE irregular slug: Python interview Two Pointers Advanced is the untiered `py_pattern_two_pointers` (`py_pattern_two_pointers_advanced` 404s); its Beginner/Intermediate are `..._beginner/_intermediate`. Page titles differ from card names in a few places (checked by section headings): `py_pattern_string_parsing` = card "Log and Text Parsing", `py_pattern_file_parsing` = "File Formats", `py_pattern_error_handling` = "Exception Handling", `py_pattern_nested_json` = "Parsing Nested JSON", `sql_pattern_ctes` = "WITH Clauses", `spark_narrow_wide_shuffle` = "Shuffles", `spark_ui_debugging` = "The Spark UI", `python_functional` = "Functional Programming".

topics.json entries to add (stem -> folder under `lessons/`; Spark's 15 are already in the Spark agent's branch):

```json
{
  "spark_execution_model": "learn/spark/execution_model",
  "spark_lazy_evaluation": "learn/spark/lazy_evaluation",
  "spark_narrow_wide_shuffle": "learn/spark/shuffles",
  "spark_catalyst_tungsten": "learn/spark/catalyst_optimizer",
  "spark_partitioning_file_layout": "learn/spark/partitioning",
  "spark_joins": "learn/spark/joins",
  "spark_data_skew": "learn/spark/data_skew",
  "spark_memory_caching": "learn/spark/memory_and_caching",
  "spark_aqe": "learn/spark/adaptive_query_execution",
  "spark_storage_formats": "learn/spark/storage_formats",
  "spark_cluster_sizing": "learn/spark/cluster_sizing",
  "spark_ui_debugging": "learn/spark/the_spark_ui",
  "spark_streaming": "learn/spark/structured_streaming",
  "spark_udfs_serialization": "learn/spark/udfs_and_serialization",
  "spark_fault_tolerance": "learn/spark/fault_tolerance",
  "python_foundations": "learn/python/foundations",
  "python_expressions": "learn/python/expressions",
  "python_control_flow": "learn/python/control_flow",
  "python_loops": "learn/python/loops",
  "python_functions": "learn/python/functions",
  "python_strings": "learn/python/strings",
  "python_lists": "learn/python/lists",
  "python_dictionaries": "learn/python/dictionaries",
  "python_sets": "learn/python/sets",
  "python_collections": "learn/python/collections",
  "python_data_structures": "learn/python/data_structures",
  "python_problem_solving": "learn/python/problem_solving",
  "python_complexity": "learn/python/complexity",
  "python_functional": "learn/python/functional_programming",
  "query_structure": "learn/sql/query_structure",
  "data_types": "learn/sql/data_types",
  "filtering": "learn/sql/filtering",
  "aggregating": "learn/sql/aggregating",
  "null_values": "learn/sql/null_values",
  "joins": "learn/sql/joins",
  "string_functions": "learn/sql/string_functions",
  "dates": "learn/sql/dates",
  "complex_data": "learn/sql/complex_data",
  "window_functions": "learn/sql/window_functions",
  "py_pattern_two_pointers": "interview/python/two_pointers",
  "py_pattern_sliding_window": "interview/python/sliding_window",
  "py_pattern_tree_traversal": "interview/python/tree_traversal",
  "py_pattern_heap_topk": "interview/python/heap_and_top_k",
  "py_pattern_dynamic_programming": "interview/python/dynamic_programming",
  "py_pattern_stacks_queues": "interview/python/stacks_and_queues",
  "py_pattern_frequency_counting": "interview/python/frequency_counting",
  "py_pattern_merge_intervals": "interview/python/merge_intervals",
  "py_pattern_binary_search": "interview/python/binary_search",
  "py_pattern_prefix_sum": "interview/python/prefix_sum",
  "py_pattern_custom_sorting": "interview/python/custom_sorting",
  "py_pattern_dict_manipulation": "interview/python/dict_manipulation",
  "py_pattern_string_parsing": "interview/python/log_and_text_parsing",
  "py_pattern_nested_json": "interview/python/parsing_nested_json",
  "py_pattern_file_parsing": "interview/python/file_formats",
  "py_pattern_generators": "interview/python/python_generators",
  "py_pattern_decorators": "interview/python/python_decorators",
  "py_pattern_oop": "interview/python/oop_for_data_engineers",
  "py_pattern_error_handling": "interview/python/exception_handling",
  "py_pattern_async": "interview/python/async_python",
  "sql_pattern_top_n_per_group": "interview/sql/top_n_per_group",
  "sql_pattern_running_totals": "interview/sql/running_totals",
  "sql_pattern_period_over_period": "interview/sql/period_over_period",
  "sql_pattern_self_join": "interview/sql/self_join",
  "sql_pattern_anti_join": "interview/sql/anti_join",
  "sql_pattern_gaps_and_islands": "interview/sql/gaps_and_islands",
  "sql_pattern_retention": "interview/sql/retention_queries",
  "sql_pattern_conditional_agg": "interview/sql/conditional_aggregation",
  "sql_pattern_multi_table_joins": "interview/sql/multi_table_joins",
  "sql_pattern_ctes": "interview/sql/with_clauses",
  "sql_pattern_null_handling": "interview/sql/null_handling",
  "sql_pattern_date_arithmetic": "interview/sql/date_arithmetic",
  "sql_pattern_string_manipulation": "interview/sql/string_manipulation",
  "sql_pattern_deduplication": "interview/sql/deduplication",
  "sql_pattern_type_casting": "interview/sql/type_casting",
  "sql_pattern_semi_structured": "interview/sql/semi_structured_data"
}
```

Card counts: Spark 15, Python learn 14, SQL learn 10, Python interview 20, SQL interview 16 (75 cards, 225 lessons).

## 6. Scan results per remaining category (read-only scans of the live pages; raw files were in a scratchpad that may be gone, so redo a quick scan if you need detail)

General facts: every Python/SQL/Spark exercise (`https://datadriven.io/proxy/challenges/<slug>`) has `challenge_type` `python` / `sql` / `spark` and no `form`. Unless the type is added to `SKIPPED_TOOL_EXERCISES`, `main()` falls into the final `else` and wrongly dumps them at the end of the page. The user's decision: LEAVE ALL THESE EXERCISES OUT of the Markdown for now (they will do the exercises later; `docs/skipped-blocks.md` is how they find them). Animations (`*_animation` blocks, here `python_animation`, `sql_animation`, `spark_animation`) are fine: the existing recorder makes GIFs.

**Interview Python (60 lessons)**: no unknown block types, no run-cells, no partner panel, nothing for drops.json. Exercises: python (starter_code with `{{ }}` blanks, test_examples). Only action: add `python` to `SKIPPED_TOOL_EXERCISES`. Caveat: a few "Try it" items in `sliding_window_beginner` / `merge_intervals_beginner` etc. were not checked for an answer, but they read as self-contained lesson content (leave).

**Interview SQL (48 lessons)**: no new block types. Exercises: sql (starter_sql with `{{ }}`, data_tables, sampleData). Action: add `sql` to `SKIPPED_TOOL_EXERCISES`. One hand trim: in `sql_pattern_running_totals_beginner` the last sentence of a paragraph ("...which is why the capstones at the end of this lesson arrive in 4 different vocabularies.") points at removed exercises; the paragraph starts "The pull toward `GROUP BY` comes from the word total" and has real teaching text, so trim that one sentence by hand instead of dropping the block. (Matching prefixes for drops.json must be taken from the CONVERTED Markdown, not the raw HTML: backticks, escapes and `( * )` spacing differ.)

**Learn Python (42 lessons)**: 2 new content blocks.
1. `executable_python` (about 590 cells in all 42 lessons). Lesson content, not an exercise. Looks like a terminal window (3 dots) with a line-numbered code table, a `>>>` button at the bottom right and an Output area. The user's decision: treat EXACTLY like the Spark cell: click the `>>>` button with Playwright and take ONE screenshot of the whole cell (code + output) at 2x, save as `<slug>_cell_<n>.png` in `_images/`, embed it at the cell's position, and ALSO keep the code as a ```python fence under it (the Spark agent is implementing the same for `executable_spark`: reuse its helper). Output text is already present in the static HTML for most cells; some cells are "predict the output, then reveal". Generic conversion today is ugly (code as a 2-column table, `\>\>\>Output`).
2. `regex_cards`: cards with a pattern (e.g. `'Lake%'`), a description, and an example line ("'Lake' and 'Lakeview Cabin' -> both match"). Appears in exactly 3 lessons: `python_strings_advanced`, and (SQL) `filtering_intermediate`, `filtering_advanced`. User's decision: screenshot each card (or the whole stack) with Playwright, stack them like in the UI, embed, keep the pattern text next to it.
Exercises: python, 15 to 24 per lesson, `{{ }}` blanks, `tile_bank` (draggable snippets) and `debug` kinds; only about 5 per page are anchored to a `placed_challenge` stub ("Loading the challenge", dropped by SKIPPED_BLOCKS), the rest have no placement. Left out.
Prose to drop/trim (needs the user's eyes; see section 7 and the review PR). Open decision (asked, no answer yet): keep a hand-kept list in drops.json (about 20 Python entries) or a narrow rule ("block right before a removed exercise that names a drill/capstone/'below'"). The user said earlier that if the list gets too big they might want something else; they also said it is fine to just add to the list.

**Learn SQL (30 lessons)**: 5 new blocks:
1. `executable_sql` (~190 cells): lesson content, macOS-style window, 3 icon-only buttons (no "Run" text), a Result table and "N rows". Treat like `executable_spark` (click the run button, screenshot whole cell, keep ```sql fence; tell the user which button was clicked).
2. `sql_switcher` (~70): tabbed code examples (tabs like "Star | Named | New table"); the static HTML only has the ACTIVE tab, so the other tabs are lost. Prose says "The 3 tabs below..." (e.g. `dates_advanced:53`, `aggregating_beginner:189`, `aggregating_intermediate:24`, `data_types_intermediate:283`, `filtering_intermediate:163`, `filtering_advanced:156`). Open question for the user: click through every tab with Playwright and screenshot each?
3. `sql_parsons` (~36): a drag-the-tiles EXERCISE (not in the challenges API, not a placed_challenge); generic conversion is junk. Skip it like placed_challenge (add to skipped blocks).
4. `regex_cards` (2 lessons, see above).
5. `table_visualization` (5 in `aggregating_beginner`): animation-like (class `smv-*`, text "Preparing the animation" leaks into the Markdown at about line 86). Treat like an animation or add a rule.
Exercises: sql, 515 total, left out.
SQL drops candidates (slug: prefix of the converted text; "pure" = whole block is about the exercise, drop it):
- pure: `window_functions_beginner`: "The practice table `employees` in the platform", "Among the distractors, `ORDER BY department` run", "The blanks below ask for that shape on the pra", "Every distractor runs. `ORDER BY salary` gives", "The puzzle below is the inner query, split int"; `joins_beginner`: "The correct tile matches the item's `product_i", "The ON tile holds the pairing condition and th"; `query_structure_advanced`: "Drill: expand the features" (h3), "The drill hands over an accounts table with a", "Assemble the subtraction" (h3); `string_functions_beginner`: "Put the duplicate finder together yourself."; `data_types_beginner`: "The same query, descending, assembled from ti"; `aggregating_beginner`: "The leftover tile, `WHERE COUNT(*) > 2`, is th"; `filtering_beginner`: "The order that holds the query together is SE".
- mixed (an exercise sentence ends a real paragraph; trim the sentence by hand instead of dropping the block): `aggregating_beginner` "The argument to SUM can be arithmetic over", "A condition that could go in either place, su", "The result is 1 row, North with 3 completed o"; `data_types_beginner` "The practice database's `order_items` table st", "A quantity of 3 at a price of 19.99 returns 59"; `joins_beginner` "The practice database carries the same pattern", "The logical execution order from earlier less"; `query_structure_intermediate` "Across the 6 orders the average is 50.0, so th", "The ORDER BY at the end sorts the stacked res"; `query_structure_advanced` "The signup table counts attempts, so the query".
- uncertain: `aggregating_beginner` "SUM ( profit ) and AVG ( profit ) in the same"; `complex_data_advanced` h3 "Capstone: long tracks by id" + "The final query combines the lesson: 2 parallel"; `query_structure_beginner` "List those names after SELECT in the order the". "Capstone:" sections in `filtering_advanced` and `string_functions_beginner` are kept executable_sql content (fine).

## 7. Learn Python places the user must look at (for drops.json)

All links `https://datadriven.io/learn/<name>`. Format: name | section header | sub-heading | text starts with. DEFINITE (text points at a removed exercise):
```
python_foundations_beginner | Variables and Assignment | A name that was never bound | The program below computes a subtotal and stops   (LAST sentence of a long paragraph: trim by hand)
python_foundations_beginner | Variables and Assignment | A name that was never bound | The error names Subtotal_cents
python_foundations_beginner | Data Types | Converting between types | int for the quantity, because a count of items is
python_foundations_beginner | Print Statements | f-strings | sep is applied between arguments and end after the
python_foundations_beginner | Basic Operators | Precedence and augmented assignment | The broken line divides only discount_cents by 100
python_foundations_intermediate | (4 h3 "Practice": Indentation and Code Blocks; Importing Modules; Reading Input From the User; Reading a Traceback) | | Practice
python_foundations_intermediate | Trying Code in the Interactive Shell | Capstone | The capstone pulls the 5 sections into one short
python_control_flow_intermediate | Branching on Types With isinstance | Capstone: a reading through every tool | Capstone: a reading through every tool (h3); These last 2 drills put the whole lesson into a; The second capstone hinges on a habit worth keeping
python_expressions_beginner | Operators and Readability | Capstone practice | Capstone practice (h3); Each program below pulls on more than one section; A fixed fee plus a per-item cost needs no parenth
python_expressions_advanced | Walrus Operator (:=) | Capstone: one event, every operator | Capstone: one event, every operator (h3); The last 2 problems put the whole lesson into a; A pipeline step like this one usually breaks throug
python_dictionaries_intermediate | Iterating and Dictionary Views | Read or insert with setdefault | Put the views to work. The report below prints
python_dictionaries_intermediate | Merging Dictionaries | Why in-place merges leak | The runner below should let each job's setting
python_dictionaries_intermediate | Copying Dictionaries | Copy at the boundary | Functions are where shared state bites. A dict
python_collections_intermediate | Using zip() for Combining | Capstone: a ranking step end to end | h3 Capstone: a ranking step end to end; The code quiz below puts all 5 ideas into one
python_functional_beginner | Type Hints for Function Signatures | Capstone: One Pricing Pipeline | h3 Capstone: One Pricing Pipeline; The 2 drills below combine the sections
python_problem_solving_beginner | Testing Simple Cases | Capstone: one problem, all 5 habits | A logistics team asks: given a list of parcel
python_data_structures_beginner | Which Collections Keep Their Order | Practice | The drill below depends on how each collectio
python_data_structures_beginner | Choosing the Right Type | Capstones | The third capstone builds 2 collections from t; The last capstone depends on what square brack
python_data_structures_intermediate | Combining Structures for One Task | Capstone: from raw events to clean rows | The last practice runs the lesson's steps on a
python_sets_intermediate | Subset and Superset | Changing a set in place | The last exercise uses each operator from this
```
NEEDS A HUMAN SKIM (explanations right after a removed exercise, or headings that may be left empty):
```
python_expressions_beginner | Mixing Types in One Expression | Let print do the joining | Each operator needs the pair it accepts. A repeat
python_expressions_beginner | Operators and Readability | Capstone practice | String operators share the same precedence. In
python_loops_beginner | Iterating with for Loops | Practice: counting letters | A misplaced starting line fails without an error m
python_loops_beginner | range() Function | Getting the stop right | A countdown reads the same way with a negative ste
python_loops_beginner | Loops with while | Zero passes | A target such as
python_loops_beginner | Using break and continue | continue can skip the progress line in while | Swapping continue for break turns a filter into a
python_loops_beginner | Loop Variable Scope | Reusing a name | When a printed value belongs to the wrong loop, lo
python_strings_advanced | Splitting Strings | When the piece count is wrong | The 2 repairs differ when the separator is missing
python_strings_advanced | Joining Strings | Newlines at the seams | When only one value is a number, converting it ins
python_strings_advanced | Regular Expression Matching | Replacing matches | A pattern that quietly finds nothing is the usual
python_strings_advanced | Advanced Formatting | Templates with str.format | Centering splits the padding in 2, and when the pa
python_strings_advanced | String Encoding | Same text, different code points | len counts code points, which is not always what a
python_lists_advanced | In-Place vs Return Value | Capstone: a plan with undo | h3 Capstone: a plan with undo; The last problems use everything from the earlier sec
python_dictionaries_beginner | (4 h3 "Practice": Creating Your First Dictionary; Reading and Updating Values; Removing Items; Checking for Keys and Key Types) | | Practice  (the scan flagged only ONE as left empty after its exercise; not pinned down which)
python_problem_solving_advanced | Sort as Preprocessing | Capstone: the fullest gap | h3 Capstone: the fullest gap; This one combines 3 patterns
python_data_structures_beginner | Which Collections Can Change | Practice | The first exercise is about what a function ca
python_data_structures_beginner | Converting Between Collections | Practice | Both exercises hinge on what set
python_data_structures_beginner | Which Collections Allow Duplicates | Practice | The first exercise mixes a set literal and a d
python_data_structures_beginner | Choosing the Right Type | Capstones | That capstone kept a set beside a list so each
```
What the user asked for: instead of reading this list, a sub-agent screenshots each place on the live site (target block outlined, one block before and after for context) and puts the images in a never-to-merge draft PR so the user can eyeball them rendered. That PR is linked in section 3. After the user decides drop / keep / trim per place, put the "drop" ones in `tools/drops.json` and hand-trim the "mixed" sentences (the converter has no sentence-level drop; either extend `drops.json` or edit the converted Markdown by hand and say so).

## 8. Spark specifics (the in-flight PR)

15 cards, 45 lessons, slugs in section 5. Known facts: only unmapped block is `executable_spark` (1 to 5 per page; PySpark cell with seed-table list on the left, code editor, Run button, output table). Exercises: `spark` type (600 total; 362 have `{{ }}` blanks, 91 plain data-table tasks, 147 `scale` job/run tasks), left out. Two definite dangling sentences go in drops.json: slug `spark_execution_model_beginner` "The widget below asks for the same program" and `spark_narrow_wide_shuffle_advanced` "The drill hands you a program that already repartitions". Many sentences say "run the cell below on the practice data" and stay (the cells stay, with an output screenshot). "Capstone" headings in spark_aqe_*, spark_storage_formats_intermediate, spark_narrow_wide_shuffle_intermediate are kept multiple-choice questions (keep).

## 9. Suggested skills for the next agent

- `lesson-to-md` (project skill in `.claude/skills/lesson-to-md/`): how conversion and verification work here.
- `mattpocock-skills:pr` when writing PR bodies.
- `code-review` before opening a converter-changing PR (the converter touches 165+ lessons).
- `mattpocock-skills:diagnosing-bugs` if a converter run misbehaves (e.g. Playwright cell screenshots timing out).

## 10. First moves for you

1. `git status` / `gh pr list --state all` / `git branch -r` in `~/projects/data-eng-knowledge` to see whether the Spark agent has finished and what PRs exist.
2. Tell the user in 1 to 2 sentences where things stand, then ask which single category they want next (default order: Interview Python, Interview SQL, then Learn Python, then Learn SQL).
3. Do work only in git worktrees off `origin/main` (or stacked on the Spark branch), never in a dirty shared checkout.
