from __future__ import annotations

from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from dpu_rag_mvp.core import automation_catalog, build_index, get_status, search, suggest_automation


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
def rag_search(query: str, limit: int = 8, kind: str = "") -> list[dict]:
    """Search project code, docs, configs, and automation files."""
    kind_filter = kind or None
    return [asdict(item) for item in search(query, limit=limit, kind=kind_filter)]


@mcp.tool()
def rag_automation_catalog(limit: int = 50) -> list[dict]:
    """List automation-relevant files and their suggested run commands."""
    return [asdict(item) for item in automation_catalog(limit=limit)]


@mcp.tool()
def rag_suggest_automation(goal: str, limit: int = 8) -> list[dict]:
    """Suggest relevant automation scripts and docs for a testing goal."""
    return [asdict(item) for item in suggest_automation(goal, limit=limit)]


if __name__ == "__main__":
    mcp.run()

