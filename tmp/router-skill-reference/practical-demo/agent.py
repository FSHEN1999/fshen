from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from router import ROOT, execute_skill, route


MEMORY_DIR = ROOT / "memory"
RUN_MEMORY = MEMORY_DIR / "runs.jsonl"


@dataclass
class PlanStep:
    id: str
    goal: str
    input_args: list[str]
    expected: str
    selected_skill: str | None = None
    status: str = "pending"


def load_context() -> dict[str, Any]:
    MEMORY_DIR.mkdir(exist_ok=True)
    recent_runs: list[dict[str, Any]] = []
    if RUN_MEMORY.exists():
        lines = RUN_MEMORY.read_text(encoding="utf-8").splitlines()[-5:]
        for line in lines:
            if line.strip():
                recent_runs.append(json.loads(line))
    return {"recent_runs": recent_runs}


def save_run(report: dict[str, Any]) -> None:
    MEMORY_DIR.mkdir(exist_ok=True)
    with RUN_MEMORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(report, ensure_ascii=False) + "\n")


def split_task(task: str, run_args: list[str]) -> list[PlanStep]:
    parts = [part.strip() for part in re.split(r"\s*(?:&&|;|；|然后|再|并且)\s*", task) if part.strip()]
    if not parts:
        parts = [task]

    steps: list[PlanStep] = []
    for index, part in enumerate(parts, start=1):
        args = run_args if len(parts) == 1 else []
        expected = infer_expected(part)
        steps.append(PlanStep(id=f"step-{index}", goal=part, input_args=args, expected=expected))
    return steps


def infer_expected(goal: str) -> str:
    lowered = goal.lower()
    if "health" in lowered or "健康" in goal or "接口" in goal:
        return "script_returncode_zero_and_http_200"
    if "rag" in lowered or "检索" in goal or "上下文" in goal:
        return "script_returncode_zero"
    if "语法" in goal or "compile" in lowered or "py_compile" in lowered:
        return "script_returncode_zero"
    if "每日任务" in goal or "继续任务" in goal:
        return "script_returncode_zero"
    if "metersphere" in lowered or "场景" in goal or "实跑" in goal:
        return "script_returncode_zero"
    if "mock_sit" in lowered or "模拟" in goal or "体检" in goal:
        return "script_returncode_zero"
    if "csv" in lowered or "数据" in goal or "表格" in goal:
        return "script_returncode_zero_and_json_output"
    if "设计" in goal or "frontend" in lowered or "前端" in goal:
        return "instruction_loaded"
    return "skill_selected"


def verify(step: PlanStep, execution: dict[str, Any] | None, routes: list[dict[str, Any]]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    skill_selected = bool(routes)
    checks.append({"name": "skill_selected", "passed": skill_selected})

    if not skill_selected:
        return {"passed": False, "checks": checks}

    if execution is None:
        return {"passed": True, "checks": checks}

    returncode_ok = execution.get("returncode") == 0
    checks.append({"name": "returncode_zero", "passed": returncode_ok})

    stdout = str(execution.get("stdout") or "")
    if step.expected == "script_returncode_zero_and_http_200":
        checks.append({"name": "http_200_in_output", "passed": '"status": 200' in stdout})
    elif step.expected == "script_returncode_zero_and_json_output":
        checks.append({"name": "json_like_output", "passed": stdout.strip().startswith("{")})
    elif step.expected == "instruction_loaded":
        checks.append({"name": "skill_instruction_loaded", "passed": "SKILL.md" in stdout or "#" in stdout})
    elif step.expected == "script_returncode_zero":
        checks.append({"name": "script_completed", "passed": returncode_ok})

    return {"passed": all(check["passed"] for check in checks), "checks": checks}


def run_agent(task: str, run_args: list[str]) -> dict[str, Any]:
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    context = load_context()
    plan = split_task(task, run_args)
    step_reports: list[dict[str, Any]] = []

    for step in plan:
        routes = route(step.goal)
        if not routes:
            step.status = "blocked"
            step_reports.append(
                {
                    "step": asdict(step),
                    "routes": [],
                    "execution": None,
                    "verification": {"passed": False, "checks": [{"name": "skill_selected", "passed": False}]},
                }
            )
            continue

        step.selected_skill = str(routes[0]["name"])
        execution = execute_skill(step.selected_skill, step.input_args)
        verification = verify(step, execution, routes)
        step.status = "completed" if verification["passed"] else "failed"
        step_reports.append(
            {
                "step": asdict(step),
                "routes": routes[:3],
                "execution": execution,
                "verification": verification,
            }
        )

    report = {
        "task": task,
        "started_at": started,
        "architecture": ["Planner", "Router", "SkillExecutor", "MemoryContext", "Verifier"],
        "context": {"recent_run_count": len(context["recent_runs"])},
        "plan": [asdict(step) for step in plan],
        "steps": step_reports,
        "status": "completed" if all(step.status == "completed" for step in plan) else "needs_attention",
    }
    save_run(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the practical router+skill agent pipeline.")
    parser.add_argument("task", nargs="+", help="User task to plan, route, execute, and verify.")
    parser.add_argument("--run", nargs="*", default=[], help="Arguments passed to a single selected script skill.")
    args = parser.parse_args()

    report = run_agent(" ".join(args.task), args.run)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
