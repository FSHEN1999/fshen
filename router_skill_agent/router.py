from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SKILLS_DIR = ROOT / "skills"
DEFAULT_MIN_SCORE = 60
AMBIGUITY_MARGIN = 15
SAFE_RISK_LEVELS = {"safe", "read_only"}
RISK_ORDER = {
    "safe": 0,
    "read_only": 1,
    "local_write": 2,
    "external_call": 3,
    "prod_sensitive": 4,
}


@dataclass
class SkillInput:
    name: str
    type: str = "text"
    required: bool = False
    description: str = ""


@dataclass
class Skill:
    name: str
    description: str
    tags: list[str]
    risk: str
    inputs: list[SkillInput]
    path: Path
    body: str
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def skill_dir(self) -> Path:
        return self.path.parent

    @property
    def has_script(self) -> bool:
        return (self.skill_dir / "scripts" / "run.py").exists()


@dataclass
class RouteDecision:
    name: str
    score: int
    confidence: str
    risk: str
    executable: bool
    path: str
    description: str
    reasons: list[str]
    required_inputs: list[dict[str, Any]]
    missing_inputs: list[str]
    blocked_reason: str | None = None


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text

    _, frontmatter, body = text.split("---", 2)
    metadata: dict[str, Any] = {}
    current_key: str | None = None
    current_item: dict[str, Any] | None = None

    for raw_line in frontmatter.splitlines():
        if not raw_line.strip():
            continue
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("- ") and current_key:
            value = stripped[2:].strip()
            metadata.setdefault(current_key, [])
            if ":" in value:
                key, item_value = value.split(":", 1)
                current_item = {key.strip(): _clean_value(item_value)}
                metadata[current_key].append(current_item)
            else:
                current_item = None
                metadata[current_key].append(_clean_scalar(value))
            continue

        if raw_line.startswith("    ") and current_item is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            current_item[key.strip()] = _clean_value(value)
            continue

        if raw_line.startswith("  ") and current_key:
            metadata.setdefault(current_key, [])
            assert isinstance(metadata[current_key], list)
            value = stripped
            if value.startswith("- "):
                metadata[current_key].append(_clean_scalar(value[2:].strip()))
            continue

        if ":" in line:
            key, value = line.split(":", 1)
            current_key = key.strip()
            current_item = None
            cleaned = value.strip()
            metadata[current_key] = [] if not cleaned else _clean_scalar(cleaned)

    return metadata, body


def _clean_value(value: str) -> Any:
    return _clean_scalar(value.strip())


def _clean_scalar(value: str) -> Any:
    cleaned = value.strip().strip('"').strip("'")
    if cleaned.lower() == "true":
        return True
    if cleaned.lower() == "false":
        return False
    return cleaned


def parse_skill(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(text)
    inputs = []
    for item in metadata.get("inputs") or []:
        if isinstance(item, dict):
            inputs.append(
                SkillInput(
                    name=str(item.get("name") or ""),
                    type=str(item.get("type") or "text"),
                    required=bool(item.get("required")),
                    description=str(item.get("description") or ""),
                )
            )

    return Skill(
        name=str(metadata.get("name") or path.parent.name),
        description=str(metadata.get("description") or ""),
        tags=[str(tag) for tag in (metadata.get("tags") or [])],
        risk=str(metadata.get("risk") or "safe"),
        inputs=inputs,
        path=path,
        body=body.strip(),
        raw_metadata=metadata,
    )


def load_skills() -> list[Skill]:
    return [parse_skill(path) for path in sorted(SKILLS_DIR.glob("*/SKILL.md"))]


def tokenize(text: str) -> set[str]:
    lowered = text.lower()
    ascii_tokens = set(re.findall(r"[a-z0-9_-]+", lowered))
    cjk_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,4}", lowered))
    domain_tokens = {
        token
        for token in [
            "mock_sit",
            "metersphere",
            "scenario_1",
            "rag",
            "psp",
            "esign",
            "boss",
            "treehole",
            "csv",
        ]
        if token in lowered
    }
    return ascii_tokens | cjk_tokens | domain_tokens


def score(query: str, skill: Skill) -> tuple[int, list[str]]:
    q = query.lower()
    haystack = " ".join([skill.name, skill.description, " ".join(skill.tags), skill.body]).lower()
    reasons: list[str] = []
    points = 0

    if skill.name.lower() in q:
        points += 100
        reasons.append("name_in_query")
    if q and q in haystack:
        points += 90
        reasons.append("query_in_skill")

    query_tokens = tokenize(query)
    skill_tokens = tokenize(haystack)
    overlap = query_tokens & skill_tokens
    if overlap:
        points += min(90, len(overlap) * 18)
        reasons.append("token_overlap:" + ",".join(sorted(overlap)))

    for tag in skill.tags:
        if tag.lower() in q:
            points += 35
            reasons.append(f"tag:{tag}")

    for keyword, bonus in [
        ("继续任务", 45),
        ("每日任务", 45),
        ("mock_sit", 45),
        ("metersphere", 45),
        ("rag", 40),
        ("csv", 35),
        ("前端", 35),
        ("设计", 25),
    ]:
        if keyword in q and keyword in haystack:
            points += bonus
            reasons.append(f"domain:{keyword}")

    return points, reasons


def confidence(score_value: int) -> str:
    if score_value >= 120:
        return "high"
    if score_value >= DEFAULT_MIN_SCORE:
        return "medium"
    return "low"


def missing_required_inputs(skill: Skill, args: list[str]) -> list[str]:
    missing = []
    for item in skill.inputs:
        if item.required and not args:
            missing.append(item.name)
    return missing


def is_risk_allowed(skill: Skill, allow_risk: str | None, execute: bool) -> tuple[bool, str | None]:
    if not execute:
        return True, None
    if skill.risk in SAFE_RISK_LEVELS:
        return True, None
    allowed_level = RISK_ORDER.get(allow_risk or "", -1)
    skill_level = RISK_ORDER.get(skill.risk, 99)
    if allowed_level >= skill_level:
        return True, None
    return False, f"skill risk '{skill.risk}' requires --allow-risk {skill.risk} or higher"


def route(query: str, args: list[str] | None = None, min_score: int = DEFAULT_MIN_SCORE, allow_risk: str | None = None, execute: bool = False) -> list[dict[str, object]]:
    args = args or []
    decisions: list[RouteDecision] = []
    for skill in load_skills():
        points, reasons = score(query, skill)
        if points < min_score:
            continue
        missing = missing_required_inputs(skill, args)
        risk_ok, blocked_reason = is_risk_allowed(skill, allow_risk, execute)
        executable = not missing and risk_ok
        if missing:
            blocked_reason = f"missing required inputs: {', '.join(missing)}"
        decisions.append(
            RouteDecision(
                name=skill.name,
                score=points,
                confidence=confidence(points),
                risk=skill.risk,
                executable=executable,
                path=str(skill.path),
                description=skill.description,
                reasons=reasons,
                required_inputs=[asdict(item) for item in skill.inputs if item.required],
                missing_inputs=missing,
                blocked_reason=blocked_reason,
            )
        )
    return [asdict(item) for item in sorted(decisions, key=lambda item: item.score, reverse=True)]


def choose_best(routes: list[dict[str, object]]) -> tuple[dict[str, object] | None, bool]:
    executable = [item for item in routes if item.get("executable")]
    if not executable:
        return None, False
    best = executable[0]
    if len(executable) < 2:
        return best, False
    ambiguous = int(best["score"]) - int(executable[1]["score"]) <= AMBIGUITY_MARGIN
    return best, ambiguous


def run_skill(skill_name: str, args: list[str]) -> int:
    result = execute_skill(skill_name, args)
    if result["stdout"]:
        print(result["stdout"], end="" if str(result["stdout"]).endswith("\n") else "\n")
    if result["stderr"]:
        print(result["stderr"], file=sys.stderr, end="" if str(result["stderr"]).endswith("\n") else "\n")
    return int(result["returncode"])


def execute_skill(skill_name: str, args: list[str]) -> dict[str, object]:
    skill_dir = SKILLS_DIR / skill_name
    script = skill_dir / "scripts" / "run.py"
    if not script.exists():
        skill_file = skill_dir / "SKILL.md"
        return {
            "skill": skill_name,
            "mode": "instruction",
            "returncode": 0,
            "stdout": skill_file.read_text(encoding="utf-8"),
            "stderr": "",
        }

    completed = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(ROOT.parent),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return {
        "skill": skill_name,
        "mode": "script",
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Route a task to the best matching skill.")
    parser.add_argument("query", nargs="+")
    parser.add_argument("--run", nargs="*", default=None)
    parser.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--allow-risk", choices=list(RISK_ORDER), default=None)
    parser.add_argument("--force", action="store_true", help="Run even when top candidates are ambiguous.")
    args = parser.parse_args()

    query = " ".join(args.query)
    run_args = args.run or []
    should_run = args.run is not None
    routes = route(query, run_args, min_score=args.min_score, allow_risk=args.allow_risk, execute=should_run)
    best, ambiguous = choose_best(routes)
    response = {
        "query": query,
        "min_score": args.min_score,
        "should_run": should_run,
        "best": best,
        "ambiguous": ambiguous,
        "results": routes[:5],
    }
    print(json.dumps(response, ensure_ascii=False, indent=2))

    if should_run:
        if best is None:
            print("No executable skill selected.", file=sys.stderr)
            return 1
        if ambiguous and not args.force:
            print("Top candidates are ambiguous. Re-run with --force or refine the query.", file=sys.stderr)
            return 2
        return run_skill(str(best["name"]), run_args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
