from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKILLS_DIR = ROOT / "skills"


@dataclass
class Skill:
    name: str
    description: str
    tags: list[str]
    path: Path
    body: str

    @property
    def has_script(self) -> bool:
        return (self.path.parent / "scripts" / "run.py").exists()


def parse_skill(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    metadata: dict[str, str | list[str]] = {}
    body = text

    if text.startswith("---"):
        _, frontmatter, body = text.split("---", 2)
        current_key = None
        for raw_line in frontmatter.splitlines():
            line = raw_line.rstrip()
            if not line.strip():
                continue
            if line.startswith("  - ") and current_key:
                metadata.setdefault(current_key, [])
                assert isinstance(metadata[current_key], list)
                metadata[current_key].append(line[4:].strip())
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                current_key = key.strip()
                cleaned = value.strip().strip('"')
                metadata[current_key] = [] if not cleaned else cleaned

    return Skill(
        name=str(metadata.get("name") or path.parent.name),
        description=str(metadata.get("description") or ""),
        tags=list(metadata.get("tags") or []),
        path=path,
        body=body.strip(),
    )


def load_skills() -> list[Skill]:
    return [parse_skill(path) for path in SKILLS_DIR.glob("*/SKILL.md")]


def tokenize(text: str) -> set[str]:
    lowered = text.lower()
    ascii_tokens = set(re.findall(r"[a-z0-9_-]+", lowered))
    cjk_tokens = set(re.findall(r"[\u4e00-\u9fff]{1,4}", lowered))
    return ascii_tokens | cjk_tokens


def score(query: str, skill: Skill) -> tuple[int, list[str]]:
    q = query.lower()
    haystack = " ".join([skill.name, skill.description, " ".join(skill.tags), skill.body]).lower()
    reasons: list[str] = []
    points = 0

    if skill.name.lower() in q:
        points += 100
        reasons.append("name_in_query")
    if q in haystack:
        points += 90
        reasons.append("query_in_skill")

    query_tokens = tokenize(query)
    skill_tokens = tokenize(haystack)
    overlap = query_tokens & skill_tokens
    if overlap:
        points += min(80, len(overlap) * 18)
        reasons.append("token_overlap:" + ",".join(sorted(overlap)))

    for tag in skill.tags:
        if tag.lower() in q:
            points += 30
            reasons.append(f"tag:{tag}")

    return points, reasons


def route(query: str) -> list[dict[str, object]]:
    results = []
    for skill in load_skills():
        points, reasons = score(query, skill)
        if points:
            results.append(
                {
                    "name": skill.name,
                    "score": points,
                    "path": str(skill.path),
                    "description": skill.description,
                    "reasons": reasons,
                }
            )
    return sorted(results, key=lambda item: item["score"], reverse=True)


def run_skill(skill_name: str, args: list[str]) -> int:
    result = execute_skill(skill_name, args)
    if result["stdout"]:
        print(result["stdout"], end="" if result["stdout"].endswith("\n") else "\n")
    if result["stderr"]:
        print(result["stderr"], file=sys.stderr, end="" if result["stderr"].endswith("\n") else "\n")
    return int(result["returncode"])


def execute_skill(skill_name: str, args: list[str]) -> dict[str, object]:
    skill_dir = SKILLS_DIR / skill_name
    script = skill_dir / "scripts" / "run.py"
    if not script.exists():
        return {
            "skill": skill_name,
            "mode": "instruction",
            "returncode": 0,
            "stdout": (skill_dir / "SKILL.md").read_text(encoding="utf-8"),
            "stderr": "",
        }

    completed = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(ROOT),
        text=True,
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
    if len(sys.argv) < 2:
        print("Usage: python router.py <query> [--run arg1 arg2 ...]")
        return 2

    if "--run" in sys.argv:
        run_index = sys.argv.index("--run")
        query = " ".join(sys.argv[1:run_index])
        run_args = sys.argv[run_index + 1 :]
    else:
        query = " ".join(sys.argv[1:])
        run_args = []

    results = route(query)
    print(json.dumps({"query": query, "results": results[:5]}, ensure_ascii=False, indent=2))

    if run_args or "--run" in sys.argv:
        if not results:
            print("No matching skill to run.")
            return 1
        return run_skill(str(results[0]["name"]), run_args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
