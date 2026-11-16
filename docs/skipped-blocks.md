# What the converter skips

`tools/lesson_to_md.py` does not copy everything on a lesson page. This file lists what it leaves out or changes, and where each switch lives. Exercise counts come from the site's challenges endpoint (`/proxy/challenges/<slug>`), fetched fresh for all 120 lessons in `lessons/` plus the 45 Spark slugs (checked 2026-11-15). For all 120 lessons the count equals the "N challenges" number in the header line, and for the 90 learn/interview lessons it also equals the number of `Exercise k of N` entries in the file.

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

- **Kept exercises** (574 in total) are one file per lesson, numbered continuously (`Exercise 1 of N` to `N of N`). Each has the task, the starting canvas if there is one, and the solution in a collapsed fold. Inline multiple-choice questions are not exercises; they stay in the lesson.
- **Spark exercises** (600, 45 lessons x 3 tiers, none has a `form` key; all have PySpark `starter_code`):

  | Shape | Count |
  |---|---|
  | Fill-in-the-blank, `{{...}}` blanks in the starter code, seed `data_tables` | 301 |
  | Same, plus a `tile_bank` of draggable tiles | 61 |
  | Plain `data_tables` task, starter code has no `{{` blanks (write the code) | 91 |
  | `scale` (a job or run to optimise, `kind` job 110 / run 37), no seed tables, no blanks | 147 |

  So not every Spark exercise is a fill-in-the-blank: 362 are. 453 carry seed tables (`data_tables`, `sampleData`). Only 60 are anchored to a spot in the page (`anchored`); the rest have no position.
- **Airflow today:** the `dag_repair` conversion code (20 exercises, in 4 lessons) still exists in `main()` but is switched off, so Airflow lessons contain no exercises. Reason recorded in the code: the exercises are buggy and Run/Submit need a login.
- **Header line:** every lesson starts with `<tier>·<area> · N min · N challenges`. The converter leaves it as is, so for Airflow, dbt, Kafka (and Spark) lessons it states a number of exercises that are not in the file.

## Other content dropped or changed

| What | Where it happens | Why |
|---|---|---|
| Star ratings ("Daily Life", "Interviews") | `convert()` | Drawn on a canvas by JavaScript; the page source has no values |
| `placed_challenge` stubs ("Loading the challenge") | `SKIPPED_BLOCKS` | Empty placeholder where an exercise widget would load; none left in the committed lessons |
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

The two data-modeling entries do nothing today: `drops.json` is applied only when a lesson's exercises are left out, and those lessons keep theirs. An entry that matches nothing prints a warning. Odd, not resolved: those two sentences are on the live page and a fresh conversion keeps them, but they are absent from the committed lesson files (grep finds neither), so those lessons were apparently edited or converted differently.

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

Not verified here: how the exercise pages look on the live site, and whether the converter run today reproduces every committed lesson byte for byte. `BLOCK-TYPES.md` is out of date on one point: it says `pipeline_animation` is "not handled yet", but the code handles every `*_animation` and learn architecture has 16 animation GIFs.
