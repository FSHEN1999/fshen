from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dpu_common import find_dpu_root, resolve_repo_python

DPU_ROOT = find_dpu_root(Path(__file__))
PYTHON = resolve_repo_python(DPU_ROOT)


def run_command(args: list[str]) -> dict[str, object]:
    completed = subprocess.run(
        [str(PYTHON), "-m", "dpu_rag_mvp", *args],
        cwd=str(DPU_ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return {
        "command": [str(PYTHON), "-m", "dpu_rag_mvp", *args],
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def main() -> int:
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        print("Usage: run.py <query>")
        return 2

    status = run_command(["status"])
    search = run_command(["search", query])
    print(
        json.dumps(
            {
                "dpu_root": str(DPU_ROOT),
                "python": str(PYTHON),
                "status": status,
                "search": search,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if status["returncode"] == 0 and search["returncode"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
