# DPU Router + Skill Agent

This is a local, runnable router-skill agent framework for the DPU workspace.

It promotes the original reference demo into a project-level capability:

```text
User task
  -> Planner
  -> Router
  -> Skill Executor
  -> Verifier
  -> Memory
```

## Run

Route only:

```bash
python3 router_skill_agent/router.py "检查 mock_sit.py 语法"
python3 router_skill_agent/router.py "心情树洞前端页面设计"
```

Route and execute:

```bash
python3 router_skill_agent/agent.py "检查 mock_sit.py 语法" --run mock_sit.py
python3 router_skill_agent/agent.py "mock_sit 模拟服务体检"
python3 router_skill_agent/agent.py "继续任务 读取每日任务"
python3 router_skill_agent/agent.py "DPU RAG 检索 MeterSphere scenario_1" --run MeterSphere scenario_1
```

External calls are blocked unless explicitly allowed:

```bash
python3 router_skill_agent/agent.py "我要调用后端接口做健康检查" --run http://127.0.0.1:8000/api/health --allow-risk external_call
```

Use `--force` only when the router reports ambiguous candidates and you still want the highest-scoring executable skill to run.

## Skill Contract

Each skill lives under:

```text
skills/<skill-name>/
  SKILL.md
  scripts/run.py        # optional
```

`SKILL.md` frontmatter is machine-readable:

```yaml
---
name: dpu-script-check
description: Compile-check a DPU Python script without running its business workflow.
tags:
  - dpu
  - python
risk: read_only
inputs:
  - name: script_path
    type: file
    required: true
    description: Python script path relative to the DPU repository root.
---
```

## Risk Levels

| Risk | Meaning |
|---|---|
| `safe` | No execution; returns instructions only |
| `read_only` | Reads local files or runs read-only checks |
| `local_write` | Writes local files |
| `external_call` | Calls a local or remote service |
| `prod_sensitive` | Can touch production-like data or external business systems |

By default, executable skills are limited to `safe` and `read_only`.

## Router Policy

The router scores skills using:

- exact skill name match
- query text in skill body
- token overlap
- tag match
- DPU domain bonuses

It also enforces:

- minimum score threshold
- required input checks
- risk-level checks
- ambiguity detection when top candidates are too close

## Current DPU Skills

- `dpu-rag-search`: query local DPU RAG.
- `dpu-script-check`: compile-check a Python script.
- `dpu-daily-task-next`: read the newest checklist item.
- `dpu-mock-sit-health`: inspect `mock_sit.py` safely.
- `dpu-metersphere-preflight`: report MeterSphere run prerequisites without live execution.
- `frontend-designer`: return frontend design instructions.
- `csv-analyzer`: inspect a CSV file.
- `api-health-check`: call an HTTP health endpoint; requires `--allow-risk external_call`.

## Memory

Runs are appended to:

```text
router_skill_agent/memory/runs.jsonl
```

The last five runs are loaded as context for each new run.

