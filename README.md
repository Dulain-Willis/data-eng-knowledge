<h1 align="center">data-eng-knowledge</h1>

<h3 align="center">Data engineering lessons for people and agents</h3>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white">
  <img alt="Markdown" src="https://img.shields.io/badge/Markdown-000000?logo=markdown&logoColor=white">
  <img alt="MCP server" src="https://img.shields.io/badge/MCP-server-6E56CF">
  <img alt="Last commit" src="https://img.shields.io/github/last-commit/Dulain-Willis/data-eng-knowledge">
</p>

<div align="center">

[Lessons »](lesson_preview) | [MCP server »](server.py)

</div>
<br>

**My data engineering study notes as Markdown, with diagrams and animations, and an MCP server so an agent can answer from them.**

## What is data-eng-knowledge?

A collection of 120 data engineering lessons, plus the tools that build and serve them:

1. The lessons cover pipeline architecture, data modeling, Airflow, dbt and Kafka, written for learning and for interview prep, with diagrams, schema screenshots and animations that render right on GitHub.
2. `tools/lesson_to_md.py` converts a lesson page into clean Markdown, screenshots and animation frames included.
3. An MCP server (`server.py`) lets an agent search the lessons, read only the section it needs and cite the exact lines, instead of answering from training data.

Everything is plain files. Read the lessons here, grep them, open them in any editor, or point an agent at them. The interview architecture lessons also have section indexes with line ranges, which is what lets the agent jump straight to the right passage.

https://github.com/user-attachments/assets/9647a564-275a-423a-b192-8d2cc67f057f

## Lessons

| Area | Lessons |
|---|---|
| [Learn: architecture](lesson_preview/learn/architecture) | 30 |
| [Learn: data modeling](lesson_preview/learn/data_modeling) | 11 |
| [Interview: architecture](lesson_preview/interview/architecture) | 26 |
| [Interview: data modeling](lesson_preview/interview/data_modeling) | 8 |
| [Airflow](lesson_preview/tools/airflow) | 15 |
| [dbt](lesson_preview/tools/dbt) | 15 |
| [Kafka](lesson_preview/tools/kafka) | 15 |

## MCP server

Tools: `list_lessons`, `get_lesson_index`, `read_lesson`, `search`, `grep_lessons`.

```bash
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt
claude mcp add --scope user data-eng-knowledge -- "$PWD/.venv/bin/python" "$PWD/server.py"
```

It reads `lesson_preview/interview/architecture/` by default; set `DATA_ENG_KNOWLEDGE_DIR` to point it somewhere else.
