"""Compatibility shim for the legacy auto_loop entrypoint."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
PYTHON = sys.executable


def main(rounds: int = 5, sleep_between: int = 15, batch_apply: int = 40) -> int:
    cmd = [
        PYTHON,
        "-B",
        "-X",
        "utf8",
        "main.py",
        "--monitor",
        "--interval",
        str(sleep_between * 60),
        "--rounds",
        str(rounds),
        "--sleep",
        str(sleep_between),
        "--batch",
        str(batch_apply),
    ]
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    sleep_m = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    batch = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    raise SystemExit(main(rounds, sleep_m, batch))
