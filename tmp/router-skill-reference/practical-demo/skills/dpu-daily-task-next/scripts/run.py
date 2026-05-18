from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dpu_common import find_dpu_root

DPU_ROOT = find_dpu_root(Path(__file__))


def find_task_file() -> Path | None:
    for name in ("daily_tasks.md", "DAILY_TASKS.md"):
        path = DPU_ROOT / name
        if path.exists():
            return path
    return None


def main() -> int:
    path = find_task_file()
    if path is None:
        print(json.dumps({"error": "no daily task file found"}, ensure_ascii=False))
        return 1

    text = path.read_text(encoding="utf-8", errors="replace")
    sections = list(re.finditer(r"(?m)^#{1,3}\s+(.+)$", text))
    newest = None
    first_unchecked = None

    for index, match in enumerate(sections):
        start = match.end()
        end = sections[index + 1].start() if index + 1 < len(sections) else len(text)
        body = text[start:end]
        unchecked = re.search(r"(?m)^-\s+\[\s\]\s+(.+)$", body)
        if unchecked:
            newest = match.group(1).strip()
            first_unchecked = unchecked.group(1).strip()

    print(
        json.dumps(
            {
                "file": str(path),
                "newest_section_with_unchecked_task": newest,
                "first_unchecked_task": first_unchecked,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
