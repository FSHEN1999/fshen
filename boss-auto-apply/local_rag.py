"""Lightweight local RAG for BOSS AI replies.

No external vector DB is required. The goal is to add a few high-signal
resume/interview knowledge chunks into each LLM prompt.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from candidate_profile import load_resume


BASE_DIR = Path(__file__).parent
DOCS_DIR = BASE_DIR / "docs"
MAX_DOC_CHARS = int(os.environ.get("BOSS_RAG_MAX_DOC_CHARS", "240000") or "240000")

def _static_chunks() -> list[tuple[str, str]]:
    resume = load_resume()
    return [
        (
            "profile:positioning",
            f"定位：{resume['name']}，{resume['experience']}，{resume['city']}，"
            f"目标方向是{resume['target_direction']}。技能：{'、'.join(resume['skills'])}。",
        ),
        (
            "project:highlights",
            "项目亮点：" + "；".join(resume["highlights"]),
        ),
        (
            "rag:talking_points",
            "RAG表达：RAG是检索增强链路，不是知识库本身。链路包括文档切分、embedding、向量召回、关键词补召回、"
            "rerank/topK、把召回片段放进Prompt、生成结构化结果，并通过召回率、topK命中率、误召回率和最终误判率评估。",
        ),
    ]


def _tokenize(text: str) -> set[str]:
    lowered = (text or "").lower()
    latin = re.findall(r"[a-z0-9+#.]{2,}", lowered)
    chinese_terms = re.findall(
        r"ai agent|spring cloud|spring boot|langchain4j|spring ai|rag|llm|mcp|java|redis|kafka|mysql|rocketmq|dubbo|"
        r"大模型|智能体|检索|向量|质检|金融|清算|风控|支付|贷款|后端|微服务|分布式|高并发|缓存|消息队列|异步|幂等|补偿|面试|简历",
        lowered,
    )
    chars = re.findall(r"[\u4e00-\u9fff]{2,4}", text or "")
    return set(latin + chinese_terms + chars)


def _split_markdown(path: Path, text: str) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    current_title = path.name
    current: list[str] = []

    def flush() -> None:
        if not current:
            return
        body = "\n".join(current).strip()
        if len(body) >= 80:
            chunks.append((f"{path.name}:{current_title}", body[:1200]))

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("#"):
            flush()
            current = []
            current_title = line.strip("# ").strip() or path.name
            continue
        current.append(line)
        if sum(len(x) for x in current) > 1100:
            flush()
            current = []
    flush()
    return chunks


@lru_cache(maxsize=1)
def _load_chunks() -> list[tuple[str, str, set[str]]]:
    chunks: list[tuple[str, str]] = _static_chunks()
    if DOCS_DIR.exists():
        doc_paths = sorted(DOCS_DIR.glob("*.md")) if os.environ.get("BOSS_RAG_LOAD_DOCS", "0") == "1" else []
        for path in doc_paths:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")[:MAX_DOC_CHARS]
            except Exception:
                continue
            chunks.extend(_split_markdown(path, text))
    return [(source, body, _tokenize(f"{source}\n{body}")) for source, body in chunks]


def retrieve_context(intent: str, messages: list | None, job_info: dict | None, limit: int = 5) -> str:
    """Return compact RAG context for the LLM prompt."""
    if os.environ.get("BOSS_RAG_ENABLE", "1") != "1":
        return ""

    job_info = job_info or {}
    query_parts = [
        intent or "",
        str(job_info.get("title", "")),
        str(job_info.get("company", "")),
        str(job_info.get("salary", "")),
        " ".join(job_info.get("tags", []) or []),
        str(job_info.get("jd", ""))[:1200],
    ]
    for msg in (messages or [])[-8:]:
        query_parts.append(str(msg.get("text", "")))
    query = "\n".join(query_parts)
    query_tokens = _tokenize(query)
    if not query_tokens:
        return ""

    ranked = []
    for source, body, tokens in _load_chunks():
        overlap = query_tokens & tokens
        if not overlap:
            continue
        score = len(overlap)
        if intent == "greeting" and source.startswith(("project:", "profile:")):
            score += 2
        if any(word in query.lower() for word in ("rag", "agent", "llm", "大模型", "智能体")) and "rag" in source.lower():
            score += 4
        ranked.append((score, source, body))

    ranked.sort(key=lambda item: item[0], reverse=True)
    selected = ranked[:limit]
    if not selected:
        selected = [(1, source, body) for source, body, _ in _load_chunks()[:3]]

    lines = []
    for _, source, body in selected:
        compact = re.sub(r"\n{3,}", "\n\n", body).strip()
        lines.append(f"- 来源 {source}:\n{compact[:700]}")
    return "\n".join(lines)

