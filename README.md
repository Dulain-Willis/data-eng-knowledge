<p align="center">
  <img alt="Data Engineering Knowledge" width="100%" src="assets/banner.png">
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white">
  <img alt="Markdown" src="https://img.shields.io/badge/Markdown-000000?logo=markdown&logoColor=white">
  <img alt="MCP server" src="https://img.shields.io/badge/MCP-server-6E56CF">
  <img alt="Last commit" src="https://img.shields.io/github/last-commit/Dulain-Willis/data-eng-knowledge">
</p>

<h1 align="center">Data Engineering Knowledge</h1>

<h3 align="center">Data engineering lessons for people and agents</h3>

<div align="center">

[Lessons »](lessons) | [MCP server »](server.py)

</div>
<br>

**Data engineering lessons from DataDriven as Markdown, with diagrams, animations, and an MCP server so an agent can answer from them.**

Everything is plain files. Read the lessons here, grep them, open them in any editor, or point an agent at them. The interview architecture lessons also have section indexes with line ranges, which is what lets the agent jump straight to the right passage.

https://github.com/user-attachments/assets/9647a564-275a-423a-b192-8d2cc67f057f

## What is data-eng-knowledge?

A collection of 345 data engineering lessons, plus the tools that build and serve them:

1. The lessons cover pipeline architecture, data modeling, Spark, Python, SQL, Airflow, dbt and Kafka, written for learning and for interview prep, with diagrams, schema screenshots and animations that render right on GitHub.
2. `tools/lesson_to_md.py` converts a lesson page into clean Markdown, screenshots and animation frames included.
3. An MCP server (`server.py`) lets an agent search the lessons, read only the section it needs and cite the exact lines, instead of answering from training data.


## Lessons

| Area | Lessons |
|---|---|
| [Learn: architecture](lessons/learn/architecture) | 30 |
| [Learn: data modeling](lessons/learn/data_modeling) | 11 |
| [Learn: Python](lessons/learn/python) | 42 |
| [Learn: Spark](lessons/learn/spark) | 45 |
| [Learn: SQL](lessons/learn/sql) | 30 |
| [Interview: architecture](lessons/interview/architecture) | 26 |
| [Interview: data modeling](lessons/interview/data_modeling) | 8 |
| [Interview: Python](lessons/interview/python) | 60 |
| [Interview: SQL](lessons/interview/sql) | 48 |
| [Airflow](lessons/tools/airflow) | 15 |
| [dbt](lessons/tools/dbt) | 15 |
| [Kafka](lessons/tools/kafka) | 15 |

## MCP server

Tools: `list_lessons`, `get_lesson_index`, `read_lesson`, `search`, `grep_lessons`.

```bash
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt
claude mcp add --scope user data-eng-knowledge -- "$PWD/.venv/bin/python" "$PWD/server.py"
```

It reads `lessons/interview/architecture/` by default; set `DATA_ENG_KNOWLEDGE_DIR` to point it somewhere else.
