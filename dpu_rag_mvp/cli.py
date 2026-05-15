from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from .core import automation_catalog, build_index, get_status, search, suggest_automation, topic_portals
from .memory import build_memory_index, get_memory_status, search_memory, search_memory_cards
from .smart import smart_search


def cmd_build(_: argparse.Namespace) -> int:
    result = build_index()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    print(json.dumps(get_status(), indent=2, ensure_ascii=False))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    results = [
        asdict(item)
        for item in search(
            args.query,
            limit=args.limit,
            kind=args.kind,
            rerank=not args.no_rerank,
            candidate_limit=args.candidate_limit,
        )
    ]
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


def cmd_topics(_: argparse.Namespace) -> int:
    results = [asdict(item) for item in topic_portals()]
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


def cmd_memory_build(_: argparse.Namespace) -> int:
    print(json.dumps(build_memory_index(), indent=2, ensure_ascii=False))
    return 0


def cmd_memory_status(_: argparse.Namespace) -> int:
    print(json.dumps(get_memory_status(), indent=2, ensure_ascii=False))
    return 0


def cmd_memory_search(args: argparse.Namespace) -> int:
    results = [
        asdict(item)
        for item in search_memory(
            args.query,
            limit=args.limit,
            memory_type=args.type,
        )
    ]
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


def cmd_memory_cards(args: argparse.Namespace) -> int:
    results = [asdict(item) for item in search_memory_cards(args.query, limit=args.limit)]
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


def cmd_smart_search(args: argparse.Namespace) -> int:
    results = [asdict(item) for item in smart_search(args.query, limit=args.limit)]
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
    search_parser.add_argument(
        "--candidate-limit",
        type=int,
        default=80,
        help="Number of broad first-pass candidates to rerank before returning results",
    )
    search_parser.add_argument(
        "--no-rerank",
        action="store_true",
        help="Return the broad lexical ranking without the usefulness reranker",
    )
    search_parser.set_defaults(func=cmd_search)

    catalog_parser = subparsers.add_parser("catalog", help="List automation-aware files")
    catalog_parser.add_argument("--limit", type=int, default=50)
    catalog_parser.set_defaults(func=cmd_catalog)

    suggest_parser = subparsers.add_parser("suggest", help="Suggest automation scripts for a goal")
    suggest_parser.add_argument("goal")
    suggest_parser.add_argument("--limit", type=int, default=8)
    suggest_parser.set_defaults(func=cmd_suggest)

    topics_parser = subparsers.add_parser("topics", help="List generated DPU topic portals")
    topics_parser.set_defaults(func=cmd_topics)

    memory_build_parser = subparsers.add_parser("memory-build", help="Build lightweight Codex conversation memory index")
    memory_build_parser.set_defaults(func=cmd_memory_build)

    memory_status_parser = subparsers.add_parser("memory-status", help="Show lightweight memory index status")
    memory_status_parser.set_defaults(func=cmd_memory_status)

    memory_search_parser = subparsers.add_parser("memory-search", help="Search lightweight Codex conversation memory")
    memory_search_parser.add_argument("query")
    memory_search_parser.add_argument("--limit", type=int, default=8)
    memory_search_parser.add_argument("--type", choices=("summary", "evidence"))
    memory_search_parser.set_defaults(func=cmd_memory_search)

    memory_cards_parser = subparsers.add_parser("memory-cards", help="Search structured Codex conversation decision cards")
    memory_cards_parser.add_argument("query")
    memory_cards_parser.add_argument("--limit", type=int, default=8)
    memory_cards_parser.set_defaults(func=cmd_memory_cards)

    smart_search_parser = subparsers.add_parser("smart-search", help="Route a query across project RAG and conversation memory")
    smart_search_parser.add_argument("query")
    smart_search_parser.add_argument("--limit", type=int, default=8)
    smart_search_parser.set_defaults(func=cmd_smart_search)

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
