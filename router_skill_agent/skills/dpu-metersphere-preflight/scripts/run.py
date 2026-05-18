from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dpu_common import find_dpu_root

DPU_ROOT = find_dpu_root(Path(__file__))
HARNESS_PATTERNS = [
    "run_metersphere*.py",
    "run_scenario_*.py",
    "scenario_1*.py",
]
ENV_KEYS = ["MS_TOKEN", "MS_CSRF", "MS_SCENARIO_ID", "MS_BASE_URL"]


def main() -> int:
    scripts: list[str] = []
    for pattern in HARNESS_PATTERNS:
        scripts.extend(str(path.relative_to(DPU_ROOT)) for path in DPU_ROOT.glob(pattern))
    env = {key: bool(os.environ.get(key)) for key in ENV_KEYS}

    print(
        json.dumps(
            {
                "dpu_root": str(DPU_ROOT),
                "harness_scripts": sorted(set(scripts)),
                "environment_ready": env,
                "safe_default": "preflight_only_no_live_execution",
                "next_command_shape": "set MS_SCENARIO_ID=<id>; python <harness_script>",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
