from __future__ import annotations

import json
import sys
import urllib.request


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: run.py <url>")
        return 2

    url = sys.argv[1]
    with urllib.request.urlopen(url, timeout=10) as response:
        body = response.read().decode("utf-8", errors="replace")
        print(
            json.dumps(
                {
                    "url": url,
                    "status": response.status,
                    "body": body,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

