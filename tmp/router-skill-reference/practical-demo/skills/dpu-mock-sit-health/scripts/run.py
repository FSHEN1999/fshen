from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dpu_common import find_dpu_root

DPU_ROOT = find_dpu_root(Path(__file__))
TARGET = DPU_ROOT / "mock_sit.py"
IMPORTANT_KEYWORDS = [
    "approvedoffer.completed",
    "underwriting",
    "psp",
    "esign",
    "drawdown",
    "repayment",
    "failureReason",
]


def main() -> int:
    compile_result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(TARGET)],
        cwd=str(DPU_ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    text = TARGET.read_text(encoding="utf-8", errors="replace")
    functions = re.findall(r"(?m)^def\s+(mock_[a-zA-Z0-9_]+)\s*\(", text)
    keyword_presence = {keyword: (keyword in text) for keyword in IMPORTANT_KEYWORDS}

    print(
        json.dumps(
            {
                "target": str(TARGET),
                "compile": {
                    "returncode": compile_result.returncode,
                    "stdout": compile_result.stdout,
                    "stderr": compile_result.stderr,
                },
                "mock_function_count": len(functions),
                "mock_functions": functions[:50],
                "keyword_presence": keyword_presence,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return compile_result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
