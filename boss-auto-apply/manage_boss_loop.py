from __future__ import annotations

import sys
from pathlib import Path

TEAM_DIR = Path("/root/.hermes/team")
if str(TEAM_DIR) not in sys.path:
    sys.path.insert(0, str(TEAM_DIR))

from boss_control import main as boss_control_main


if __name__ == "__main__":
    raise SystemExit(boss_control_main(caller_dir=Path(__file__).parent))
