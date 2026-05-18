from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: run.py <csv-path>")
        return 2

    path = Path(sys.argv[1])
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    print(
        json.dumps(
            {
                "file": str(path),
                "row_count": len(rows),
                "columns": reader.fieldnames or [],
                "sample": rows[:3],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

