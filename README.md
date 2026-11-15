# data-eng-knowledge

My data engineering study lessons as Markdown (with diagrams, schema screenshots and animation GIFs), plus the tooling around them: a converter, a lesson indexer, and an MCP server that lets an agent answer from the lessons instead of from training data.

## Layout

| Path | What |
|---|---|
| `lesson_preview/learn/{architecture,data_modeling}` | Learn lessons |
| `lesson_preview/interview/{architecture,data_modeling}` | Interview-prep lessons (`architecture` also has `INDEX.md` + `index/`) |
| `lesson_preview/tools/{airflow,dbt,kafka}` | Tool lessons |
| `tools/lesson_to_md.py` | Converts a lesson page to Markdown (`.claude/skills/lesson-to-md`) |
| `scripts/validate_lesson_index.py` | Checks an index against its lesson |
| `.claude/skills/index-lesson` | Skill that writes a lesson's section index |
| `docs/index-lesson` | Notes and evals from building the index approach |
| `server.py` | The MCP server |

Status: the indexes are currently stale (line ranges predate the lesson regeneration) and only exist for `interview/architecture`.

## MCP server

A small MCP server that lets an agent look up data engineering best practice in your own lessons instead of answering from training data.

Tools: `list_lessons` (top-level map), `get_lesson_index` (one lesson's sections and line ranges), `read_lesson` (a line range), `search` (keyword search over section headers), `grep_lessons` (regex over the lesson text).

## Run

The environment is local to this folder (`.venv`). Nothing is installed globally.

    uv venv .venv && uv pip install --python .venv/bin/python "mcp>=1.2"    # one time, already done here
    .venv/bin/python server.py                                              # stdio server

Content comes from `DATA_ENG_KNOWLEDGE_DIR` (default `lesson_preview/interview/architecture/` in this repo). It needs `INDEX.md`, the lesson `.md` files, and `index/<lesson>.md`.

## Register with Claude Code

    claude mcp add --scope user data-eng-knowledge -- ~/projects/data-eng-knowledge/.venv/bin/python ~/projects/data-eng-knowledge/server.py

Use `--scope project` instead to enable it for one project only.

## Adding knowledge

1. Put the new lesson `.md` in the content folder.
2. Run the `index-lesson` skill on it (writes `index/<lesson>.md` and the `INDEX.md` line).
3. `python3 scripts/validate_lesson_index.py <lesson>` must print OK.
