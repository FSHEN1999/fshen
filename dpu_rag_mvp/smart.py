from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .core import search
from .memory import search_memory, search_memory_cards
from .query import route_query


@dataclass
class SmartSearchResult:
    source: str
    route: str
    route_reasons: list[str]
    score: float
    item: dict[str, Any]


def smart_search(query: str, limit: int = 8) -> list[SmartSearchResult]:
    route = route_query(query)
    expanded = route.expanded_query
    per_source_limit = max(limit, 5)
    results: list[SmartSearchResult] = []

    if route.route in {"memory", "hybrid"}:
        for card in search_memory_cards(expanded, limit=per_source_limit):
            results.append(
                SmartSearchResult(
                    source="memory-card",
                    route=route.route,
                    route_reasons=route.reasons,
                    score=card.score + 80.0,
                    item=asdict(card),
                )
            )
        for hit in search_memory(expanded, limit=per_source_limit):
            results.append(
                SmartSearchResult(
                    source="memory",
                    route=route.route,
                    route_reasons=route.reasons,
                    score=hit.score + 20.0,
                    item=asdict(hit),
                )
            )

    if route.route in {"project", "hybrid"}:
        for hit in search(expanded, limit=per_source_limit, candidate_limit=120):
            results.append(
                SmartSearchResult(
                    source="project",
                    route=route.route,
                    route_reasons=route.reasons,
                    score=hit.score,
                    item=asdict(hit),
                )
            )

    deduped: dict[tuple[str, str], SmartSearchResult] = {}
    for result in results:
        item_path = str(result.item.get("rel_path", ""))
        item_key = (result.source, item_path)
        current = deduped.get(item_key)
        if current is None or result.score > current.score:
            deduped[item_key] = result

    return sorted(deduped.values(), key=lambda item: item.score, reverse=True)[:limit]
