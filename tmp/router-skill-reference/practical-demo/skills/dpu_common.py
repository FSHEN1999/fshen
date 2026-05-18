from __future__ import annotations

from pathlib import Path


def find_dpu_root(start: Path) -> Path:
    for parent in [start.resolve(), *start.resolve().parents]:
        if (parent / "mock_sit.py").exists() and (parent / "AGENTS.md").exists():
            return parent
    raise RuntimeError(f"Could not find DPU root from {start}")

