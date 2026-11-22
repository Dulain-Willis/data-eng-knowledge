# What the converter skips

`tools/lesson_to_md.py` does not copy everything on a lesson page. This file lists what it leaves out or changes, and where each switch lives. Exercise counts come from the site's challenges endpoint (`/proxy/challenges/<slug>`), fetched fresh for all 120 lessons in `lessons/` plus the 45 Spark slugs, the 60 Interview Python slugs (checked 2026-11-17) and the 48 Interview SQL slugs (checked 2026-11-21). For all 120 lessons the count equals the "N challenges" number in the header line, and for the 90 learn/interview lessons it also equals the number of `Exercise k of N` entries in the file.

## Exercises, by area

| Area | Lessons | Exercises | Kind (`challenge_type`, `form`) | What the converter does |
|---|---|---|---|---|
| Learn: architecture | 30 | 327 | `schema` | **Kept**, in `<topic>/_exercises/<slug>.md` |
| Learn: data modeling | 11 | 130 | `schema` | **Kept**, same layout |
| Interview: architecture | 26 | 79 | `schema` | **Kept**, same layout |
| Interview: data modeling | 8 | 38 | `schema` | **Kept**, same layout |
| Airflow | 15 | 110 | `airflow`: run_ledger 35, unstick 22, dag_repair 20, grid_match 16, render_the_run 12, backfill_proof 3, night_shift 2 | **All left out** (`INCLUDE_AIRFLOW_EXERCISES = False`); with the switch on only `dag_repair` (20) would be kept and the other 90 left out |
| dbt | 15 | 117 | `dbt`: compile_it 28, catch_the_defect 20, build_outcome 17, two_run_proof 16, select_the_nodes 15, model_it 15, draw_the_lineage 4, snapshot_timeline 2 | **Left out** (`SKIPPED_TOOL_EXERCISES`) |
| Kafka | 15 | 114 | `kafka`: log_cleanup 20, delivery_trace 19, replica_trace 16, read_the_tape 14, connector_config 13, assign_the_group 10, route_the_keys 8, durability_dial 6, lag_board 4, crash_point 3, schema_rollout 1 | **Left out** (`SKIPPED_TOOL_EXERCISES`) |
| Learn: Spark | 45 | 600 | `spark`, no `form` key | **To be left out.** The Spark lessons are not in `main`, and the separate Spark PR was not open when checked (`gh pr list --state all` shows PRs 1 to 6 only; no Spark branch on the remote). |
| Learn: Python | 42 | 811 | `python`, no `form` key; 720 have `{{ }}` blanks in `starter_code` (152 of them also a `tile_bank` of draggable snippets), 91 are `debug` tasks (`debug` key, no blanks); all have `test_examples` | **Left out** (`SKIPPED_TOOL_EXERCISES`) |
| Interview: Python | 60 | 169 | `python`, no `form` key; every one has `starter_code` with `{{ }}` blanks, `input_bindings` and `test_examples` (no seed tables, no tile bank) | **Left out** (`SKIPPED_TOOL_EXERCISES`) |
| Interview: SQL | 48 | 147 | `sql`, no `form` key; every one has `starter_sql` (99 with `{{ }}` blanks), `data_tables` and `sampleData` | **Left out** (`SKIPPED_TOOL_EXERCISES`) |
| Learn: SQL | 30 | 515 | `sql`, no `form` key (practice database tables, fill-in and write-the-query tasks) | **Left out** (`SKIPPED_TOOL_EXERCISES`) |

- **Kept exercises** (574 in total) are one file per lesson, numbered continuously (`Exercise 1 of N` to `N of N`). Each has the task, the starting canvas if there is one, and the solution in a collapsed fold. Inline multiple-choice questions are not exercises; they stay in the lesson.
- **Spark exercises** (600, 45 lessons x 3 tiers, none has a `form` key; all have PySpark `starter_code`):

  | Shape | Count |
  |---|---|
  | Fill-in-the-blank, `{{...}}` blanks in the starter code, seed `data_tables` | 301 |
  | Same, plus a `tile_bank` of draggable tiles | 61 |
  | Plain `data_tables` task, starter code has no `{{` blanks (write the code) | 91 |
  | `scale` (a job or run to optimise, `kind` job 110 / run 37), no seed tables, no blanks | 147 |

  So not every Spark exercise is a fill-in-the-blank: 362 are. 453 carry seed tables (`data_tables`, `sampleData`). Only 60 are anchored to a spot in the page (`anchored`); the rest have no position.
- **Interview Python exercises** (169 in 60 lessons, 2 to 11 per lesson; every one has `{{ }}` blanks in its `starter_code`). Per lesson, with the animations each lesson keeps:

  <details><summary>Per-lesson counts</summary>

  | Lesson | Card folder | Exercises left out | Animations kept |
  |---|---|---|---|
  | `py_pattern_two_pointers_beginner` | two_pointers | 4 | 3 |
  | `py_pattern_two_pointers_intermediate` | two_pointers | 2 | 5 |
  | `py_pattern_two_pointers` | two_pointers | 2 | 3 |
  | `py_pattern_sliding_window_beginner` | sliding_window | 2 | 3 |
  | `py_pattern_sliding_window_intermediate` | sliding_window | 11 | 5 |
  | `py_pattern_sliding_window_advanced` | sliding_window | 2 | 7 |
  | `py_pattern_tree_traversal_beginner` | tree_traversal | 2 | 5 |
  | `py_pattern_tree_traversal_intermediate` | tree_traversal | 2 | 5 |
  | `py_pattern_tree_traversal_advanced` | tree_traversal | 2 | 3 |
  | `py_pattern_heap_topk_beginner` | heap_and_top_k | 2 | 5 |
  | `py_pattern_heap_topk_intermediate` | heap_and_top_k | 2 | 5 |
  | `py_pattern_heap_topk_advanced` | heap_and_top_k | 2 | 5 |
  | `py_pattern_dynamic_programming_beginner` | dynamic_programming | 2 | 4 |
  | `py_pattern_dynamic_programming_intermediate` | dynamic_programming | 2 | 5 |
  | `py_pattern_dynamic_programming_advanced` | dynamic_programming | 2 | 4 |
  | `py_pattern_stacks_queues_beginner` | stacks_and_queues | 2 | 4 |
  | `py_pattern_stacks_queues_intermediate` | stacks_and_queues | 2 | 5 |
  | `py_pattern_stacks_queues_advanced` | stacks_and_queues | 2 | 1 |
  | `py_pattern_frequency_counting_beginner` | frequency_counting | 2 | 4 |
  | `py_pattern_frequency_counting_intermediate` | frequency_counting | 2 | 5 |
  | `py_pattern_frequency_counting_advanced` | frequency_counting | 2 | 4 |
  | `py_pattern_merge_intervals_beginner` | merge_intervals | 2 | 5 |
  | `py_pattern_merge_intervals_intermediate` | merge_intervals | 2 | 5 |
  | `py_pattern_merge_intervals_advanced` | merge_intervals | 2 | 4 |
  | `py_pattern_binary_search_beginner` | binary_search | 2 | 4 |
  | `py_pattern_binary_search_intermediate` | binary_search | 2 | 3 |
  | `py_pattern_binary_search_advanced` | binary_search | 2 | 5 |
  | `py_pattern_prefix_sum_beginner` | prefix_sum | 2 | 3 |
  | `py_pattern_prefix_sum_intermediate` | prefix_sum | 2 | 5 |
  | `py_pattern_prefix_sum_advanced` | prefix_sum | 2 | 4 |
  | `py_pattern_custom_sorting_beginner` | custom_sorting | 2 | 3 |
  | `py_pattern_custom_sorting_intermediate` | custom_sorting | 13 | 4 |
  | `py_pattern_custom_sorting_advanced` | custom_sorting | 2 | 6 |
  | `py_pattern_dict_manipulation_beginner` | dict_manipulation | 2 | 4 |
  | `py_pattern_dict_manipulation_intermediate` | dict_manipulation | 2 | 4 |
  | `py_pattern_dict_manipulation_advanced` | dict_manipulation | 2 | 6 |
  | `py_pattern_string_parsing_beginner` | log_and_text_parsing | 2 | 4 |
  | `py_pattern_string_parsing_intermediate` | log_and_text_parsing | 2 | 6 |
  | `py_pattern_string_parsing_advanced` | log_and_text_parsing | 2 | 3 |
  | `py_pattern_nested_json_beginner` | parsing_nested_json | 2 | 4 |
  | `py_pattern_nested_json_intermediate` | parsing_nested_json | 2 | 5 |
  | `py_pattern_nested_json_advanced` | parsing_nested_json | 2 | 5 |
  | `py_pattern_file_parsing_beginner` | file_formats | 2 | 3 |
  | `py_pattern_file_parsing_intermediate` | file_formats | 2 | 2 |
  | `py_pattern_file_parsing_advanced` | file_formats | 2 | 3 |
  | `py_pattern_generators_beginner` | python_generators | 2 | 4 |
  | `py_pattern_generators_intermediate` | python_generators | 2 | 5 |
  | `py_pattern_generators_advanced` | python_generators | 2 | 7 |
  | `py_pattern_decorators_beginner` | python_decorators | 2 | 3 |
  | `py_pattern_decorators_intermediate` | python_decorators | 2 | 5 |
  | `py_pattern_decorators_advanced` | python_decorators | 2 | 3 |
  | `py_pattern_oop_beginner` | oop_for_data_engineers | 2 | 3 |
  | `py_pattern_oop_intermediate` | oop_for_data_engineers | 2 | 5 |
  | `py_pattern_oop_advanced` | oop_for_data_engineers | 2 | 5 |
  | `py_pattern_error_handling_beginner` | exception_handling | 2 | 5 |
  | `py_pattern_error_handling_intermediate` | exception_handling | 2 | 5 |
  | `py_pattern_error_handling_advanced` | exception_handling | 2 | 5 |
  | `py_pattern_async_beginner` | async_python | 12 | 4 |
  | `py_pattern_async_intermediate` | async_python | 10 | 4 |
  | `py_pattern_async_advanced` | async_python | 11 | 2 |

  </details>
- **Interview SQL exercises** (147 in 48 lessons, 2 to 5 per lesson; all `sql`; 99 have `{{ }}` blanks in `starter_sql`, the other 48 are write-the-query tasks; all carry seed tables). Per lesson, with the animations each lesson keeps (counted as animation blocks on the live page):

  <details><summary>Per-lesson counts</summary>

  | Lesson | Card folder | Exercises left out | Animations kept |
  |---|---|---|---|
  | `sql_pattern_top_n_per_group_beginner` | top_n_per_group | 4 | 1 |
  | `sql_pattern_top_n_per_group_intermediate` | top_n_per_group | 4 | 3 |
  | `sql_pattern_top_n_per_group_advanced` | top_n_per_group | 4 | 3 |
  | `sql_pattern_running_totals_beginner` | running_totals | 4 | 2 |
  | `sql_pattern_running_totals_intermediate` | running_totals | 4 | 4 |
  | `sql_pattern_running_totals_advanced` | running_totals | 5 | 3 |
  | `sql_pattern_period_over_period_beginner` | period_over_period | 4 | 3 |
  | `sql_pattern_period_over_period_intermediate` | period_over_period | 4 | 3 |
  | `sql_pattern_period_over_period_advanced` | period_over_period | 2 | 2 |
  | `sql_pattern_self_join_beginner` | self_join | 4 | 2 |
  | `sql_pattern_self_join_intermediate` | self_join | 5 | 3 |
  | `sql_pattern_self_join_advanced` | self_join | 2 | 3 |
  | `sql_pattern_anti_join_beginner` | anti_join | 4 | 2 |
  | `sql_pattern_anti_join_intermediate` | anti_join | 4 | 5 |
  | `sql_pattern_anti_join_advanced` | anti_join | 2 | 4 |
  | `sql_pattern_gaps_and_islands_beginner` | gaps_and_islands | 4 | 2 |
  | `sql_pattern_gaps_and_islands_intermediate` | gaps_and_islands | 4 | 2 |
  | `sql_pattern_gaps_and_islands_advanced` | gaps_and_islands | 2 | 4 |
  | `sql_pattern_retention_beginner` | retention_queries | 4 | 1 |
  | `sql_pattern_retention_intermediate` | retention_queries | 2 | 6 |
  | `sql_pattern_retention_advanced` | retention_queries | 2 | 2 |
  | `sql_pattern_conditional_agg_beginner` | conditional_aggregation | 4 | 5 |
  | `sql_pattern_conditional_agg_intermediate` | conditional_aggregation | 4 | 3 |
  | `sql_pattern_conditional_agg_advanced` | conditional_aggregation | 2 | 3 |
  | `sql_pattern_multi_table_joins_beginner` | multi_table_joins | 4 | 3 |
  | `sql_pattern_multi_table_joins_intermediate` | multi_table_joins | 2 | 2 |
  | `sql_pattern_multi_table_joins_advanced` | multi_table_joins | 2 | 1 |
  | `sql_pattern_ctes_beginner` | with_clauses | 4 | 3 |
  | `sql_pattern_ctes_intermediate` | with_clauses | 2 | 2 |
  | `sql_pattern_ctes_advanced` | with_clauses | 2 | 2 |
  | `sql_pattern_null_handling_beginner` | null_handling | 5 | 3 |
  | `sql_pattern_null_handling_intermediate` | null_handling | 2 | 5 |
  | `sql_pattern_null_handling_advanced` | null_handling | 2 | 3 |
  | `sql_pattern_date_arithmetic_beginner` | date_arithmetic | 4 | 4 |
  | `sql_pattern_date_arithmetic_intermediate` | date_arithmetic | 2 | 2 |
  | `sql_pattern_date_arithmetic_advanced` | date_arithmetic | 2 | 3 |
  | `sql_pattern_string_manipulation_beginner` | string_manipulation | 2 | 3 |
  | `sql_pattern_string_manipulation_intermediate` | string_manipulation | 2 | 2 |
  | `sql_pattern_string_manipulation_advanced` | string_manipulation | 2 | 1 |
  | `sql_pattern_deduplication_beginner` | deduplication | 4 | 5 |
  | `sql_pattern_deduplication_intermediate` | deduplication | 2 | 1 |
  | `sql_pattern_deduplication_advanced` | deduplication | 2 | 3 |
  | `sql_pattern_type_casting_beginner` | type_casting | 2 | 1 |
  | `sql_pattern_type_casting_intermediate` | type_casting | 2 | 6 |
  | `sql_pattern_type_casting_advanced` | type_casting | 2 | 1 |
  | `sql_pattern_semi_structured_beginner` | semi_structured_data | 4 | 1 |
  | `sql_pattern_semi_structured_intermediate` | semi_structured_data | 4 | 1 |
  | `sql_pattern_semi_structured_advanced` | semi_structured_data | 2 | 1 |

  </details>

  Totals: 147 exercises left out, 130 animation blocks kept (129 MP4 videos and 1 still image: `sql_pattern_ctes_advanced` animation 1 never mounts its player on the live site, so only its code and seed table are shown, like the four Spark still-image cases).
  One sentence was trimmed by hand in the Markdown (not by the converter): in `sql_pattern_running_totals_beginner`, the paragraph starting "The pull toward `GROUP BY`" lost its closing clause ", which is why the capstones at the end of this lesson arrive in 4 different vocabularies" because it pointed at removed exercises. Re-running the converter on that lesson brings the clause back.
- **Learn SQL exercises** (515 in 30 lessons, 10 cards x 3 tiers; all `sql`). Per lesson, with the run cells (`executable_sql`, 191 in all) that stay, the drag-the-tiles blocks (`sql_parsons`) left out, the animation blocks kept (all MP4 except 1 still) and the tab blocks (`sql_switcher`, every tab kept as text, see below):

  <details><summary>Per-lesson counts</summary>

  | Lesson | Card folder | Exercises left out | Run cells kept | Tile puzzles left out | Animations kept | Tab blocks (all tabs kept) | Regex blocks |
  |---|---|---|---|---|---|---|---|
  | `query_structure_beginner` | query_structure | 13 | 8 | 1 | 2 | 1 | 0 |
  | `query_structure_intermediate` | query_structure | 22 | 3 | 1 | 5 | 1 | 0 |
  | `query_structure_advanced` | query_structure | 14 | 3 | 1 | 2 | 2 | 0 |
  | `data_types_beginner` | data_types | 10 | 5 | 1 | 1 | 1 | 0 |
  | `data_types_intermediate` | data_types | 15 | 7 | 0 | 1 | 1 | 0 |
  | `data_types_advanced` | data_types | 12 | 7 | 1 | 1 | 1 | 0 |
  | `filtering_beginner` | filtering | 18 | 4 | 1 | 5 | 1 | 0 |
  | `filtering_intermediate` | filtering | 18 | 3 | 1 | 3 | 4 | 1 |
  | `filtering_advanced` | filtering | 19 | 4 | 1 | 4 | 2 | 1 |
  | `aggregating_beginner` | aggregating | 28 | 3 | 1 | 8 | 1 | 0 |
  | `aggregating_intermediate` | aggregating | 21 | 4 | 2 | 2 | 3 | 0 |
  | `aggregating_advanced` | aggregating | 19 | 8 | 1 | 2 | 5 | 0 |
  | `null_values_beginner` | null_values | 11 | 5 | 0 | 4 | 2 | 0 |
  | `null_values_intermediate` | null_values | 13 | 12 | 3 | 5 | 1 | 0 |
  | `null_values_advanced` | null_values | 18 | 5 | 1 | 2 | 4 | 0 |
  | `joins_beginner` | joins | 10 | 2 | 1 | 4 | 1 | 0 |
  | `joins_intermediate` | joins | 17 | 4 | 1 | 7 | 4 | 0 |
  | `joins_advanced` | joins | 15 | 8 | 1 | 3 | 1 | 0 |
  | `string_functions_beginner` | string_functions | 21 | 9 | 1 | 5 | 1 | 0 |
  | `string_functions_intermediate` | string_functions | 17 | 8 | 2 | 2 | 2 | 0 |
  | `string_functions_advanced` | string_functions | 19 | 9 | 1 | 2 | 2 | 0 |
  | `dates_beginner` | dates | 13 | 9 | 1 | 5 | 1 | 0 |
  | `dates_intermediate` | dates | 22 | 6 | 2 | 2 | 5 | 0 |
  | `dates_advanced` | dates | 19 | 13 | 2 | 1 | 4 | 0 |
  | `complex_data_beginner` | complex_data | 19 | 9 | 1 | 3 | 0 | 0 |
  | `complex_data_intermediate` | complex_data | 14 | 11 | 1 | 1 | 2 | 0 |
  | `complex_data_advanced` | complex_data | 19 | 3 | 1 | 1 | 1 | 0 |
  | `window_functions_beginner` | window_functions | 19 | 4 | 1 | 5 | 1 | 0 |
  | `window_functions_intermediate` | window_functions | 21 | 7 | 1 | 4 | 2 | 0 |
  | `window_functions_advanced` | window_functions | 19 | 8 | 1 | 1 | 1 | 0 |

  </details>

  Totals: 515 exercises left out, 34 tile puzzles left out, 93 animation blocks kept (92 MP4 videos and 1 still image: `complex_data_advanced` animation 1 never mounts its player on the live site, so only its code and seed table are shown, the same fallback as `sql_pattern_ctes_advanced`), 191 run cells kept as a screenshot of the whole cell after the table-icon "Show result" button was clicked (the other 2 buttons, "Animate this query" and "Edit and run this query", are never clicked) plus the code as a ```` ```sql ```` fence, 2 regex-cards blocks (`filtering_intermediate`, `filtering_advanced`) kept as a screenshot plus the pattern text. 5 of the 93 animations are `table_visualization` blocks (all in `aggregating_beginner`), which share the `sql_animation` player and are recorded the same way; the other 3 players in that lesson are `sql_animation`. 11 recordings failed the recorder's first-frame check ("no step counter drawn") and were re-recorded automatically.

- **Learn SQL tabs, kept as text (Option A of draft PR #24, applied by default in ticket #22).** 58 `sql_switcher` blocks (152 tabs) are no longer pending: nothing is left out. Each tab became a bold label with its name, its caption, its SQL as a ```sql fence and its result as text (`switcher_markdown` in `tools/lesson_to_md.py`), with no per-tab screenshot. The live page was read with every tab clicked; the sections were spliced into the existing lessons in place of each block's first-tab-only content (matched by order and the first tab's code), without re-running the converter, so the hand trims below are untouched. Lesson prose that said "tab" or "switcher" now says "version" / "examples" (the one caption that says "first tab" is the site's own text and stays). To switch to another option see `docs/OWNER-REVIEW.md`. Per lesson, the tab names of each block:

  <details><summary>Tab blocks (58 blocks, 152 tabs)</summary>

  | Lesson | Block | Tabs |
  |---|---|---|
  | `query_structure_beginner` | 1 | Star, Named, New table |
  | `query_structure_intermediate` | 1 | Top 3, No ORDER BY, Page 2 |
  | `query_structure_advanced` | 1 | EXCEPT, Reversed, Counted |
  | `query_structure_advanced` | 2 | Registered, Paying, Counted |
  | `data_types_beginner` | 1 | Text sort, Number sort, Text filter |
  | `data_types_intermediate` | 1 | Wall clock, With zone |
  | `data_types_advanced` | 1 | As VARCHAR, As INTEGER |
  | `filtering_beginner` | 1 | Match, Exclude, Lowercase |
  | `filtering_intermediate` | 1 | Implicit, Grouped, Explicit |
  | `filtering_intermediate` | 2 | Prefix, Contains, Any first |
  | `filtering_intermediate` | 3 | Page 1, Page 2, Page 3 |
  | `filtering_intermediate` | 4 | BETWEEN, Half-open |
  | `filtering_advanced` | 1 | No orders, No paid, Paid only |
  | `filtering_advanced` | 2 | NOT IN, NOT EXISTS, IN |
  | `aggregating_beginner` | 1 | COUNT(*), COUNT(col), DISTINCT |
  | `aggregating_intermediate` | 1 | Row-level, Aggregate, Grouped |
  | `aggregating_intermediate` | 2 | Exact, Approximate, Tighter |
  | `aggregating_intermediate` | 3 | Alias, Expression, Position, Unselected |
  | `aggregating_advanced` | 1 | All values, DISTINCT |
  | `aggregating_advanced` | 2 | MAP_AGG, Arrays first |
  | `aggregating_advanced` | 3 | No ORDER BY, By time, By length |
  | `aggregating_advanced` | 4 | WHERE, COUNT_IF |
  | `aggregating_advanced` | 5 | As rows, As columns |
  | `null_values_beginner` | 1 | = 'US', <> 'US', both |
  | `null_values_beginner` | 2 | AVG, SUM/COUNT(*), SUM/COUNT(x) |
  | `null_values_intermediate` | 1 | Filter only, With IS NULL |
  | `null_values_advanced` | 1 | UNION ALL, UNION, With source |
  | `null_values_advanced` | 2 | Using <>, IS DISTINCT |
  | `null_values_advanced` | 3 | No fix, Fix output, Fix input |
  | `null_values_advanced` | 4 | NOT IN, Filtered, NOT EXISTS, EXCEPT |
  | `joins_beginner` | 1 | Right key, Wrong key, Cast text |
  | `joins_intermediate` | 1 | Key column, Total column |
  | `joins_intermediate` | 2 | Right: ON, Right: WHERE, Left: ON, Left: WHERE |
  | `joins_intermediate` | 3 | INNER last, LEFT last |
  | `joins_intermediate` | 4 | Two joins, CTE first |
  | `joins_advanced` | 1 | BETWEEN, Touching, Half-open |
  | `string_functions_beginner` | 1 | CONCAT, Pipes, With CAST |
  | `string_functions_intermediate` | 1 | Negative, LENGTH math, Off by one |
  | `string_functions_intermediate` | 2 | Raw join, TRIM in ON |
  | `string_functions_advanced` | 1 | Raw ;, REPLACE, Wider delim |
  | `string_functions_advanced` | 2 | String =, LOWER, Bytes = |
  | `dates_beginner` | 1 | Nights, Hours |
  | `dates_intermediate` | 1 | Month only, Year + month |
  | `dates_intermediate` | 2 | Days passed, Midnights, Months |
  | `dates_intermediate` | 3 | Divided, Int divide, Not divided |
  | `dates_intermediate` | 4 | Month only, Year + month |
  | `dates_intermediate` | 5 | Week start, Month start |
  | `dates_advanced` | 1 | Named zone, Fixed offset |
  | `dates_advanced` | 2 | month(), date_trunc |
  | `dates_advanced` | 3 | Month first, Day first |
  | `dates_advanced` | 4 | By label, By date |
  | `complex_data_intermediate` | 1 | NOT contains, COALESCE |
  | `complex_data_intermediate` | 2 | Text sort, Cast first |
  | `complex_data_advanced` | 1 | lambdas, unnest |
  | `window_functions_beginner` | 1 | Plain SUM, GROUP BY, SUM OVER () |
  | `window_functions_intermediate` | 1 | Default, Full window, Flip order |
  | `window_functions_intermediate` | 2 | ROWS, RANGE |
  | `window_functions_advanced` | 1 | Two keys, One key, Filter first |

  </details>

- **Learn SQL drops and trims.** Drops are in `tools/drops.json` under the comment key `_comment_sql_learn` (14 places): the drag-the-tiles puzzles and the prose that only introduces or explains them. The trims are hand edits of the Markdown in their own commit ("Learn SQL hand trims"); re-running the converter on those lessons brings the sentences back.

  <details><summary>Drops (14 places)</summary>

  | Lesson | Block starts with |
  |---|---|
  | `window_functions_beginner` | "The practice table employees in the platform" |
  | `window_functions_beginner` | "Among the distractors, ORDER BY department runs" |
  | `window_functions_beginner` | "The blanks below ask for that shape on the practice" |
  | `window_functions_beginner` | "Every distractor runs. ORDER BY salary gives a" |
  | `window_functions_beginner` | "The puzzle below is the inner query, split into" |
  | `joins_beginner` | "The correct tile matches the item's product_id to" |
  | `joins_beginner` | "The ON tile holds the pairing condition and the" |
  | `query_structure_advanced` | "Drill: expand the features" |
  | `query_structure_advanced` | "The drill hands over an accounts table with a" |
  | `query_structure_advanced` | "Assemble the subtraction" |
  | `string_functions_beginner` | "Put the duplicate finder together yourself. The" |
  | `data_types_beginner` | "The same query, descending, assembled from tiles." |
  | `aggregating_beginner` | "The leftover tile, WHERE COUNT ( * ) > 2 , is the" |
  | `filtering_beginner` | "The order that holds the query together is SELECT ," |

  </details>

  <details><summary>Hand trims (10 sentences in 5 lessons)</summary>

  | Lesson | Cut |
  |---|---|
  | `aggregating_beginner` | "The practice `orders` table has a `profit` per order and a `region`; fill in the 2 aggregates that give total and average profit per region." |
  | `aggregating_beginner` | "The practice `orders` table has a `region` and a `profit` per order; complete the query that keeps only regions with more than 1 order." |
  | `aggregating_beginner` | "Assemble the same query from its pieces below; 1 tile does not belong." |
  | `data_types_beginner` | "Supply the operator." |
  | `joins_beginner` | clause ", and the blank below is that condition" (the paragraph now ends at "primary key on the product side.") |
  | `joins_beginner` | "The tiles below assemble a join followed by a filter over the practice database's `stores` and `retail_orders` tables, in the order the engine reads them." |
  | `query_structure_intermediate` | "The blank below is the same construction over the practice database." |
  | `query_structure_intermediate` | "The practice database splits notification sends between `push_notifs` and `push_notifs_2fa`. Both tables have the same columns, which is the shape the next widget stacks." |
  | `query_structure_advanced` | "Arrange the tiles. Two of them do not belong." |

  </details>

  Left in on purpose, flagged for the owner's review: `data_types_beginner` "A `quantity` of 3 at a price of 19.99 returns 59.97..."; `aggregating_beginner` "`SUM(profit)` and `AVG(profit)` in the same row..."; `complex_data_advanced` h3 "Capstone: long tracks by id" with "The final query combines the lesson..."; `query_structure_beginner` "List those names after `SELECT` in the order the..."; `query_structure_advanced` "The signup table counts attempts..." (a headingless sentence after the dropped h3).

- **Learn Python exercises** (811 in 42 lessons, 14 cards x 3 tiers; all `python`; 720 fill-in-the-blank, 152 of those with a `tile_bank`, 91 `debug`). Per lesson, with the animations each lesson keeps and the run cells (`executable_python`, 548 in all) that stay:

  <details><summary>Per-lesson counts</summary>

  | Lesson | Card folder | Exercises left out | Animations kept |
  |---|---|---|---|
  | `python_foundations_beginner` | foundations | 17 | 1 |
  | `python_foundations_intermediate` | foundations | 18 | 3 |
  | `python_foundations_advanced` | foundations | 18 | 4 |
  | `python_expressions_beginner` | expressions | 22 | 3 |
  | `python_expressions_intermediate` | expressions | 20 | 1 |
  | `python_expressions_advanced` | expressions | 19 | 3 |
  | `python_control_flow_beginner` | control_flow | 19 | 6 |
  | `python_control_flow_intermediate` | control_flow | 22 | 2 |
  | `python_control_flow_advanced` | control_flow | 18 | 1 |
  | `python_loops_beginner` | loops | 24 | 9 |
  | `python_loops_intermediate` | loops | 19 | 8 |
  | `python_loops_advanced` | loops | 17 | 6 |
  | `python_functions_beginner` | functions | 18 | 5 |
  | `python_functions_intermediate` | functions | 20 | 3 |
  | `python_functions_advanced` | functions | 18 | 4 |
  | `python_strings_beginner` | strings | 20 | 3 |
  | `python_strings_intermediate` | strings | 23 | 4 |
  | `python_strings_advanced` | strings | 23 | 1 |
  | `python_lists_beginner` | lists | 20 | 10 |
  | `python_lists_intermediate` | lists | 18 | 4 |
  | `python_lists_advanced` | lists | 21 | 8 |
  | `python_dictionaries_beginner` | dictionaries | 23 | 4 |
  | `python_dictionaries_intermediate` | dictionaries | 19 | 2 |
  | `python_dictionaries_advanced` | dictionaries | 20 | 1 |
  | `python_sets_beginner` | sets | 19 | 3 |
  | `python_sets_intermediate` | sets | 18 | 2 |
  | `python_sets_advanced` | sets | 17 | 1 |
  | `python_collections_beginner` | collections | 20 | 2 |
  | `python_collections_intermediate` | collections | 19 | 3 |
  | `python_collections_advanced` | collections | 18 | 8 |
  | `python_data_structures_beginner` | data_structures | 19 | 5 |
  | `python_data_structures_intermediate` | data_structures | 21 | 2 |
  | `python_data_structures_advanced` | data_structures | 20 | 2 |
  | `python_problem_solving_beginner` | problem_solving | 19 | 3 |
  | `python_problem_solving_intermediate` | problem_solving | 18 | 3 |
  | `python_problem_solving_advanced` | problem_solving | 20 | 5 |
  | `python_complexity_beginner` | complexity | 15 | 2 |
  | `python_complexity_intermediate` | complexity | 17 | 4 |
  | `python_complexity_advanced` | complexity | 16 | 3 |
  | `python_functional_beginner` | functional_programming | 20 | 2 |
  | `python_functional_intermediate` | functional_programming | 19 | 3 |
  | `python_functional_advanced` | functional_programming | 20 | 2 |

  </details>

  Totals: 811 exercises left out, 151 animation blocks kept (151 MP4 videos), 548 run cells kept as a screenshot of the whole cell after the `>>>` button was clicked plus the code as a ```` ```python ```` fence, 1 regex-cards block (`python_strings_advanced`) kept as a screenshot of the stacked cards plus the pattern text as bullets.
- **Learn Python drops and trims (proposed defaults of review PR #25, pending owner decision).** Drops are in `tools/drops.json` under the comment key `_comment_python_learn` (27 places, 24 prefixes, since `Practice` in `python_foundations_intermediate` matches 4 headings). To change a decision, delete or add the entry and re-run the lesson. The 8 trims are hand edits of the Markdown in their own commit ("Learn Python hand trims"); re-running the converter overwrites them. The 21 places proposed as keep are left as they are.

  <details><summary>Drops (27 places)</summary>

  | Lesson | Block starts with |
  |---|---|
  | `python_foundations_beginner` | "int for the quantity, because a count of items is whole and" |
  | `python_foundations_beginner` | "sep is applied between arguments and end after the last" |
  | `python_foundations_beginner` | "The broken line divides only discount_cents by 100, because" |
  | `python_foundations_intermediate` | "Practice" |
  | `python_control_flow_intermediate` | "These last 2 drills put the whole lesson into a single" |
  | `python_expressions_beginner` | "Capstone practice" |
  | `python_expressions_beginner` | "Each program below pulls on more than one section at once," |
  | `python_expressions_advanced` | "Capstone: one event, every operator" |
  | `python_expressions_advanced` | "The last 2 problems put the whole lesson into a single" |
  | `python_dictionaries_intermediate` | "Put the views to work. The report below prints the largest" |
  | `python_dictionaries_intermediate` | "The runner below should let each job's settings beat the" |
  | `python_collections_intermediate` | "Capstone: a ranking step end to end" |
  | `python_collections_intermediate` | "The code quiz below puts all 5 ideas into one pipeline" |
  | `python_functional_beginner` | "Capstone: One Pricing Pipeline" |
  | `python_functional_beginner` | "The 2 drills below combine the sections: a pure" |
  | `python_data_structures_beginner` | "The third capstone builds 2 collections from the same list" |
  | `python_data_structures_beginner` | "The last capstone depends on what square brackets mean on a" |
  | `python_data_structures_beginner` | "The first exercise is about what a function can do to a" |
  | `python_data_structures_beginner` | "Both exercises hinge on what set" |
  | `python_data_structures_beginner` | "The first exercise mixes a set literal and a dict literal" |
  | `python_data_structures_intermediate` | "The last practice runs the lesson's steps on a handful of" |
  | `python_sets_intermediate` | "The last exercise uses each operator from this lesson." |
  | `python_problem_solving_advanced` | "Capstone: the fullest gap" |
  | `python_problem_solving_advanced` | "This one combines 3 patterns: sort the input, walk 2" |

  </details>

  <details><summary>Hand trims (8 places)</summary>

  | Place | Lesson | Change |
  |---|---|---|
  | 1 | `python_foundations_beginner` | cut last sentence "The program below computes a subtotal and stops on its last line." |
  | 2 | `python_foundations_beginner` | cut opening sentence "The error names `Subtotal_cents`, with a capital S, ..." |
  | 13 | `python_control_flow_intermediate` | "The second capstone hinges on a habit worth keeping for any type ladder:" became "A habit worth keeping for any type ladder:" |
  | 21 | `python_expressions_advanced` | cut "The next program contains one of each." |
  | 24 | `python_dictionaries_intermediate` | cut "The function below tags replayed events and was meant to leave its input alone." |
  | 29 | `python_problem_solving_beginner` | "... before the drill below hands you a version with a mistake in it:" became "... of this lesson:" |
  | 30 | `python_data_structures_beginner` | cut "The drill below depends on how each collection starts and grows." |
  | 36 | `python_data_structures_beginner` | cut "That capstone kept a set beside a list so each answered its own question. The next one hands you a need and no code."; "Run the 4 questions on it in order" became "Run the 4 questions in order" (so "it" does not dangle) |

  </details>

- **Airflow today:** the `dag_repair` conversion code (20 exercises, in 4 lessons) still exists in `main()` but is switched off, so Airflow lessons contain no exercises. Reason recorded in the code: the exercises are buggy and Run/Submit need a login.
- **Header line:** every lesson starts with `<tier>·<area> · N min · N challenges`. The converter leaves it as is, so for Airflow, dbt, Kafka (and Spark) lessons it states a number of exercises that are not in the file.

## Other content dropped or changed

| What | Where it happens | Why |
|---|---|---|
| Star ratings ("Daily Life", "Interviews") | `convert()` | Drawn on a canvas by JavaScript; the page source has no values |
| `placed_challenge` stubs ("Loading the challenge") | `SKIPPED_BLOCKS` | Empty placeholder where an exercise widget would load; none left in the committed lessons |
| Python run cells (`executable_python`, 548) | `record_cells` + `spark_cell` | Kept as lesson content: click `>>>` (reveals the output), one 2x screenshot of the whole cell, code as a fence under it |
| SQL run cells (`executable_sql`, 191) | `record_cells` + `CELL_FENCE` | Kept as lesson content: click the table-icon "Show result" button, one 2x screenshot of the whole cell, code as a ```` ```sql ```` fence under it |
| `sql_parsons` (34, drag-the-tiles) | `SKIPPED_BLOCKS` | Interactive puzzle, answers not in the page; the prose that only introduces them is in `tools/drops.json` |
| `table_visualization` (5, `aggregating_beginner`) | `ANIMATION_RE` / `ANIMATION_SELECTOR` | Same player as `sql_animation`, recorded as MP4 |
| `sql_switcher` (58, 152 tabs) | `switcher_markdown` (tabs read by `sql_switcher_tabs`) | Every tab as text: bold name, caption, SQL fence, result (see above) |
| `regex_cards` (3: 1 in `python_strings_advanced`, 2 in Learn SQL) | `record_regex_cards` + `regex_cards` | Screenshot of the stacked cards, pattern text kept as bullets |
| `schema_story` blocks | `SKIPPED_BLOCKS` | Interactive, no answers in the page, so only a dangling question would remain |
| "Official <tool> resources" panel (logo, version, quote, doc buttons) on Airflow, dbt, Kafka | `clean()` drops `[data-tool-partner-panel]` | Not wanted. The trademark line after it stays. |
| Prose that introduces a dropped exercise | `tools/drops.json` (hand-kept, applied only when exercises are left out) | See below |
| Interactive pipeline/schema widgets | Screenshots or text | A live widget cannot be copied, so diagrams become 2x screenshots |

**`tools/drops.json` today (4 Interview/Kafka/data modeling entries, 27 Learn Python places, 14 Learn SQL places; the 4 below are matched on the start of the block text; the Python and SQL ones are listed in their own sections above):**

| Lesson | Block starts with |
|---|---|
| `kafka_the_log_advanced` | "Try it. The drill below hands you 1 partition" |
| `kafka_the_log_advanced` | "The drill below gives you a partition with 1 future stamp" |
| `data_modeling_dimensional` | "The story below makes the grain choice for" |
| `data_modeling_relationships` | "Capstone: design the reactions model" |

The two data-modeling entries do nothing today: `drops.json` is applied only when a lesson's exercises are left out, and those lessons keep theirs. An entry that matches nothing prints a warning. Odd, not resolved: those two sentences are on the live page and a fresh conversion keeps them, but they are absent from the committed lesson files (grep finds neither), so those lessons were apparently edited or converted differently.

**Kept on purpose:** `multiple_choice` (question, lettered options and a Solution fold, read from the page's embedded JSON); animations of every `*_animation` type (recorded as hosted MP4s; Interview Python has 255, all `python_animation`); tips, callouts, tables, code and diagrams.

**Block types the converter maps today:** `static_code`, `big_number`, `tip`, `callout`, `fun_fact`, `key_takeaways`, `synthesis`, `icon_list`, `info_list`, `pipeline_diagram`, `schema_diagram`, `multiple_choice`, `best_practices`, `comparison`, plus plain ones (`lesson_title`, `learning_objectives`, `section_header`, `h3`, `h4`, `body_text`, `rich_text`, `static_table`, `side_by_side_tables`, `note_text`, `rich_info_list`, `full_width`) `executable_sql` (run cell), `table_visualization` (as an animation), `sql_parsons` (skipped) and any block type ending in `_animation`. Anything else prints `warning: no rule for block type '<type>'` and falls back to generic conversion. `sql_switcher` (Learn SQL tabbed examples) is mapped: every tab is kept as text. The Spark lessons contain one such type, `executable_spark` (a runnable code cell); the Spark PR is meant to add a rule for it.

## How to change it

| To change | Edit |
|---|---|
| Bring Airflow exercises back | `INCLUDE_AIRFLOW_EXERCISES` in `tools/lesson_to_md.py` (only `dag_repair` has conversion code; the other forms have none) |
| Leave out (or bring back) a tool's exercises | `SKIPPED_TOOL_EXERCISES` (matched on `challenge_type`; currently `dbt`, `kafka`, `spark`, `python`, `sql`; the Learn Python lessons use `python` too) |
| Drop a block type | `SKIPPED_BLOCKS` |
| Drop one paragraph that points at a removed exercise | add an entry to `tools/drops.json` |
| Drop the tool resources panel | the `[data-tool-partner-panel]` rule in `clean()` |
| Map a new block type | `CUSTOM_BLOCKS` or `GENERIC_BLOCKS`, plus a rule in `convert()`; see `.claude/skills/lesson-to-md/BLOCK-TYPES.md` |

Not verified here: how the exercise pages look on the live site, and whether the converter run today reproduces every committed lesson byte for byte. `BLOCK-TYPES.md` is out of date on one point: it says `pipeline_animation` is "not handled yet", but the code handles every `*_animation` and learn architecture has 16 animation GIFs.
