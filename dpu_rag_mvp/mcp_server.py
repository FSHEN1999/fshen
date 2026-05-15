from __future__ import annotations

from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from dpu_rag_mvp.core import automation_catalog, build_index, get_status, search, suggest_automation, topic_portals
from dpu_rag_mvp.memory import get_memory_status, search_memory, search_memory_cards
from dpu_rag_mvp.smart import smart_search


mcp = FastMCP("dpu-local-rag")


@mcp.tool()
def rag_status() -> dict:
    """Return local RAG index status for the current DPU test project."""
    return get_status()


@mcp.tool()
def rag_build_index() -> dict:
    """Build or rebuild the local RAG index for this project."""
    return build_index()


@mcp.tool()
def rag_search(query: str, limit: int = 8, kind: str = "", rerank: bool = True, candidate_limit: int = 80) -> list[dict]:
    """Search project code, docs, configs, and automation files with usefulness reranking by default."""
    kind_filter = kind or None
    return [
        asdict(item)
        for item in search(
            query,
            limit=limit,
            kind=kind_filter,
            rerank=rerank,
            candidate_limit=candidate_limit,
        )
    ]


@mcp.tool()
def rag_memory_status() -> dict:
    """Return lightweight Codex conversation memory index status."""
    return get_memory_status()


@mcp.tool()
def rag_memory_search(query: str, limit: int = 8, memory_type: str = "") -> list[dict]:
    """Search lightweight Codex conversation memory chunks."""
    return [asdict(item) for item in search_memory(query, limit=limit, memory_type=memory_type or None)]


@mcp.tool()
def rag_memory_cards(query: str, limit: int = 8) -> list[dict]:
    """Search structured Codex conversation decision cards."""
    return [asdict(item) for item in search_memory_cards(query, limit=limit)]


@mcp.tool()
def rag_smart_search(query: str, limit: int = 8) -> list[dict]:
    """Route a query across project RAG and conversation memory with DPU-aware expansion."""
    return [asdict(item) for item in smart_search(query, limit=limit)]


@mcp.tool()
def rag_automation_catalog(limit: int = 50) -> list[dict]:
    """List automation-relevant files and their suggested run commands."""
    return [asdict(item) for item in automation_catalog(limit=limit)]


@mcp.tool()
def rag_suggest_automation(goal: str, limit: int = 8) -> list[dict]:
    """Suggest relevant automation scripts and docs for a testing goal."""
    return [asdict(item) for item in suggest_automation(goal, limit=limit)]


@mcp.tool()
def rag_topic_portals() -> list[dict]:
    """List curated topic entrypoints for long DPU project context."""
    return [asdict(item) for item in topic_portals()]


if __name__ == "__main__":
    mcp.run()
