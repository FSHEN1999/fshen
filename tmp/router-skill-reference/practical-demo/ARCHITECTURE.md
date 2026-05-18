# Agent Architecture

This demo upgrades simple skill routing into a small agent pipeline.

## Flow

```text
User Task
  -> Planner
  -> Router
  -> Skill Executor
  -> Verifier
  -> Memory / Context
```

## Components

### Planner

Implemented in `agent.py` as `split_task()`.

It turns one user request into ordered `PlanStep` objects:

- `id`
- `goal`
- `input_args`
- `expected`
- `selected_skill`
- `status`

The demo planner uses simple separators such as `然后`, `再`, `&&`, and `;`.

### Router

Implemented in `router.py`.

It scans `skills/*/SKILL.md`, parses frontmatter, and scores each skill by:

- exact name match
- query in skill text
- token overlap
- tag match

### Skill Executor

Implemented in `router.py` as `execute_skill()`.

Two modes are supported:

- `script`: runs `skills/<name>/scripts/run.py`
- `instruction`: returns the skill's `SKILL.md` content for the agent to follow

### Memory / Context

Implemented in `agent.py` with `memory/runs.jsonl`.

Every run appends one JSON report containing:

- original task
- plan
- selected skills
- execution output
- verification result

### Verifier

Implemented in `agent.py` as `verify()`.

The current verifier checks:

- skill was selected
- script returned exit code 0
- health checks include HTTP 200
- CSV skills return JSON-like output
- instruction skills successfully load instructions

## Try It

```powershell
python agent.py "帮我分析一份CSV数据" --run sample.csv
python agent.py "心情树洞前端页面设计"
python agent.py "我要调用后端接口做健康检查" --run http://127.0.0.1:8000/api/health
python agent.py "检查 mock_sit.py 语法" --run mock_sit.py
python agent.py "mock_sit 模拟服务体检"
python agent.py "继续任务 读取每日任务"
python agent.py "MeterSphere 场景实跑前检查"
python agent.py "DPU RAG 检索 MeterSphere scenario_1" --run MeterSphere scenario_1
```

## DPU Capability Layer

The DPU skills are wrappers around the real repository, not duplicated business code.

- `dpu-rag-search` delegates to `.venv\Scripts\python.exe -m dpu_rag_mvp`.
- `dpu-script-check` delegates to Python `py_compile`.
- `dpu-daily-task-next` reads the repository task checklist.
- `dpu-mock-sit-health` inspects `mock_sit.py` without sending webhooks.
- `dpu-metersphere-preflight` lists known MeterSphere harness scripts and required env vars without running a live scenario.

The live-run boundary is intentional: the router can prepare and verify context automatically, while actions that hit external DPU/MeterSphere environments can be added as explicit opt-in skills later.
