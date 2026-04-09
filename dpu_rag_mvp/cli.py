from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from .core import automation_catalog, build_index, get_status, search, suggest_automation


def cmd_build(_: argparse.Namespace) -> int:
    result = build_index()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    print(json.dumps(get_status(), indent=2, ensure_ascii=False))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    results = [asdict(item) for item in search(args.query, limit=args.limit, kind=args.kind)]
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


def cmd_catalog(args: argparse.Namespace) -> int:
    results = [asdict(item) for item in automation_catalog(limit=args.limit)]
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


def cmd_suggest(args: argparse.Namespace) -> int:
    results = [asdict(item) for item in suggest_automation(args.goal, limit=args.limit)]
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DPU local RAG MVP")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build or rebuild the local RAG index")
    build_parser.set_defaults(func=cmd_build)

    status_parser = subparsers.add_parser("status", help="Show index status")
    status_parser.set_defaults(func=cmd_status)

    search_parser = subparsers.add_parser("search", help="Search indexed project chunks")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=8)
    search_parser.add_argument("--kind", choices=("automation", "doc", "code", "config"))
    search_parser.set_defaults(func=cmd_search)

    catalog_parser = subparsers.add_parser("catalog", help="List automation-aware files")
    catalog_parser.add_argument("--limit", type=int, default=50)
    catalog_parser.set_defaults(func=cmd_catalog)

    suggest_parser = subparsers.add_parser("suggest", help="Suggest automation scripts for a goal")
    suggest_parser.add_argument("goal")
    suggest_parser.add_argument("--limit", type=int, default=8)
    suggest_parser.set_defaults(func=cmd_suggest)

    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
