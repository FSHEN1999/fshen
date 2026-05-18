# Router + Skill Practical Demo

This is a small runnable reference based on two GitHub projects:

- `skill-router`: route a user request to the best matching `SKILL.md`.
- `agent-skills`: keep each skill self-contained with instructions plus optional scripts/resources.

Run:

```powershell
python router.py "帮我分析一份CSV"
python router.py "心情树洞前端页面设计"
python router.py "我要调用后端接口做健康检查"
```

Run the full agent pipeline:

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

Shape:

```text
router.py
skills/
  csv-analyzer/
    SKILL.md
    scripts/run.py
  frontend-designer/
    SKILL.md
  api-health-check/
    SKILL.md
    scripts/run.py
  dpu-rag-search/
  dpu-script-check/
  dpu-daily-task-next/
  dpu-mock-sit-health/
  dpu-metersphere-preflight/
agent.py
memory/runs.jsonl
```

See `ARCHITECTURE.md` for the Planner -> Router -> Executor -> Memory -> Verifier flow.

## DPU Skills

- `dpu-rag-search`: query the local DPU RAG index before opening large context.
- `dpu-script-check`: compile-check a DPU Python script without running business flow.
- `dpu-daily-task-next`: read `daily_tasks.md` / `DAILY_TASKS.md` and return the next unchecked item.
- `dpu-mock-sit-health`: safe health inspection for `mock_sit.py`.
- `dpu-metersphere-preflight`: locate MeterSphere harness scripts and required env vars without live execution.
