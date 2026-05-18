from __future__ import annotations

import sys
from pathlib import Path


def find_dpu_root(start: Path) -> Path:
    for parent in [start.resolve(), *start.resolve().parents]:
        if (parent / "mock_sit.py").exists() and (parent / "AGENTS.md").exists():
            return parent
    raise RuntimeError(f"Could not find DPU root from {start}")


def resolve_repo_python(dpu_root: Path) -> Path:
    candidates = [
        dpu_root / ".venv" / "bin" / "python",
        dpu_root / ".venv" / "bin" / "python3",
        dpu_root / ".venv" / "Scripts" / "python.exe",
        dpu_root / ".venv" / "Scripts" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path(sys.executable)
