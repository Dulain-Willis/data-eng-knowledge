# What the converter skips

`tools/lesson_to_md.py` does not copy everything on a lesson page. This file lists what it leaves out or changes, and where each switch lives. Exercise counts come from the site's challenges endpoint (`/proxy/challenges/<slug>`); they match the "N challenges" number in the header line of all 120 lessons already in `lessons/`.

## Exercises, by area

| Area | Lessons | Exercises | Kind (`challenge_type`, `form`) | What the converter does |
|---|---|---|---|---|
| Learn: architecture | 30 | 327 | `schema` | **Kept**, in `<topic>/_exercises/<slug>.md` |
| Learn: data modeling | 11 | 130 | `schema` | **Kept**, same layout |
| Interview: architecture | 26 | 79 | `schema` | **Kept**, same layout |
| Interview: data modeling | 8 | 38 | `schema` | **Kept**, same layout |
| Airflow | 15 | 110 | `airflow`: run_ledger 35, unstick 22, dag_repair 20, grid_match 16, render_the_run 12, backfill_proof 3, night_shift 2 | **All left out** (`INCLUDE_AIRFLOW_EXERCISES = False`) |
| dbt | 15 | 117 | `dbt`: compile_it 28, catch_the_defect 20, build_outcome 17, two_run_proof 16, select_the_nodes 15, model_it 15, draw_the_lineage 4, snapshot_timeline 2 | **Left out** (`SKIPPED_TOOL_EXERCISES`) |
| Kafka | 15 | 114 | `kafka`: log_cleanup 20, delivery_trace 19, replica_trace 16, read_the_tape 14, connector_config 13, assign_the_group 10, route_the_keys 8, durability_dial 6, lag_board 4, crash_point 3, schema_rollout 1 | **Left out** (`SKIPPED_TOOL_EXERCISES`) |
| Learn: Spark (45 lessons) | 45 | 600 | `spark`, no `form` key | **To be left out.** The Spark lessons are not in `main` yet; they come in a separate PR. |

- **Kept exercises** (574 in total) are one file per lesson, numbered continuously (`Exercise 1 of N` to `N of N`). Each has the task, the starting canvas if there is one, and the solution in a collapsed fold. Inline multiple-choice questions are not exercises; they stay in the lesson.
- **Airflow:** the code that converts the 20 `dag_repair` exercises (4 lessons: dag_anatomy x3, tasks_and_data_advanced) still exists in `main()`, but the switch is off, so Airflow lessons contain no exercises at all. The reason recorded in the code: the exercises are buggy and Run/Submit need a login.
- **Spark exercises:** every one has PySpark `starter_code` with `{{...}}` blanks; 453 also carry seed tables (`data_tables`, `sampleData`), 147 a `scale`, 61 a `tile_bank`. Only 60 of the 600 are anchored to a spot on the page (a "Loading the challenge" stub); the rest are not placed in the page at all.
- **Header line:** every lesson starts with `<tier>·<area> · N min · N challenges`. The converter leaves it as is, so for Airflow, dbt, Kafka (and Spark) lessons it states a number of exercises that are not in the file.

## Other content dropped or changed

| What | Where it happens | Why |
|---|---|---|
| Star ratings ("Daily Life", "Interviews") | `convert()` | Drawn on a canvas by JavaScript; the page source has no values |
| `placed_challenge` stubs ("Loading the challenge") | `SKIPPED_BLOCKS` | Empty placeholder where an exercise widget would load |
| `schema_story` blocks | `SKIPPED_BLOCKS` | Interactive, no answers in the page, so only a dangling question would remain |
| "Official <tool> resources" panel (logo, version, quote, doc buttons) on Airflow, dbt, Kafka | `clean()` drops `[data-tool-partner-panel]` | Not wanted. The trademark line after it stays. |
| Prose that introduces a dropped exercise | `tools/drops.json` (hand-kept, applied only when exercises are left out) | See below |
| Interactive pipeline/schema widgets | Screenshots or text | A live widget cannot be copied, so diagrams become 2x screenshots |

**`tools/drops.json` today (4 entries, matched on the start of the block text):**

| Lesson | Block starts with |
|---|---|
| `kafka_the_log_advanced` | "Try it. The drill below hands you 1 partition" |
| `kafka_the_log_advanced` | "The drill below gives you a partition with 1 future stamp" |
| `data_modeling_dimensional` | "The story below makes the grain choice for" |
| `data_modeling_relationships` | "Capstone: design the reactions model" |

The two data-modeling entries do nothing today, because those lessons keep their exercises. They take effect only if exercises are ever left out of those lessons. An entry that matches nothing prints a warning.

**Kept on purpose:** `multiple_choice` (question, lettered options and a Solution fold, read from the page's embedded JSON); animations of every `*_animation` type (recorded as GIFs: 16 in learn architecture, 124 in the tool lessons); tips, callouts, tables, code and diagrams.

**Block types the converter maps today:** `static_code`, `big_number`, `tip`, `callout`, `fun_fact`, `key_takeaways`, `synthesis`, `icon_list`, `info_list`, `pipeline_diagram`, `schema_diagram`, `multiple_choice`, `best_practices`, `comparison`, plus plain ones (`lesson_title`, `learning_objectives`, `section_header`, `h3`, `h4`, `body_text`, `rich_text`, `static_table`, `side_by_side_tables`, `note_text`, `rich_info_list`, `full_width`) and any block type ending in `_animation`. Anything else prints `warning: no rule for block type '<type>'` and falls back to generic conversion. The Spark lessons contain one such type, `executable_spark` (a runnable code cell); the Spark PR is meant to add a rule for it.

## How to change it

| To change | Edit |
|---|---|
| Bring Airflow exercises back | `INCLUDE_AIRFLOW_EXERCISES` in `tools/lesson_to_md.py` (only `dag_repair` has conversion code; the other forms have none) |
| Leave out (or bring back) a tool's exercises | `SKIPPED_TOOL_EXERCISES` (matched on `challenge_type`; currently `dbt`, `kafka`) |
| Drop a block type | `SKIPPED_BLOCKS` |
| Drop one paragraph that points at a removed exercise | add an entry to `tools/drops.json` |
| Drop the tool resources panel | the `[data-tool-partner-panel]` rule in `clean()` |
| Map a new block type | `CUSTOM_BLOCKS` or `GENERIC_BLOCKS`, plus a rule in `convert()`; see `.claude/skills/lesson-to-md/BLOCK-TYPES.md` |

Not verified here: how the exercise pages look on the live site, and whether `BLOCK-TYPES.md` is fully current. Its line saying `pipeline_animation` is "not handled yet" looks out of date, since learn architecture now has animation GIFs.
