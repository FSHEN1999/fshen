from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dpu_common import find_dpu_root

DPU_ROOT = find_dpu_root(Path(__file__))


def main() -> int:
    relative = sys.argv[1] if len(sys.argv) > 1 else "mock_sit.py"
    target = (DPU_ROOT / relative).resolve()
    if not str(target).lower().startswith(str(DPU_ROOT).lower()):
        print(json.dumps({"error": "target must stay inside DPU root", "target": str(target)}, ensure_ascii=False))
        return 2
    if not target.exists():
        print(json.dumps({"error": "file not found", "target": str(target)}, ensure_ascii=False))
        return 2

    completed = subprocess.run(
        [sys.executable, "-m", "py_compile", str(target)],
        cwd=str(DPU_ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    print(
        json.dumps(
            {
                "target": str(target),
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
