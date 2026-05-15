from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET
from zipfile import ZipFile, is_zipfile

from .config import (
    AUTOMATION_NAME_HINTS,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DATA_DIR,
    DB_PATH,
    EXCLUDED_DIRS,
    INDEX_EXTENSIONS,
    MAX_TEXT_FILE_BYTES,
    PROJECT_ROOT,
    TOPIC_PORTAL_DIRNAME,
)
from .topic_portals import TopicPortalInfo, build_topic_portals


TEXT_ENCODINGS = ("utf-8", "utf-8-sig", "gb18030", "gbk", "utf-16")
AUTOMATION_KIND_TOKENS = (
    "mock_",
    "mockapi",
    "migration_test",
    "compare_",
    "rollback",
    "offerid",
    "metersphere",
    "webhook",
    "locator",
    "自动化",
)
WORDPROCESSINGML_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
WORDPROCESSINGML_MEMBERS = (
    "word/document.xml",
    "word/footnotes.xml",
    "word/endnotes.xml",
)
DEFAULT_RERANK_CANDIDATE_LIMIT = 80
NOISY_TOOL_OUTPUT_MARKERS = (
    "missing opening '(' after keyword",
    "empty pipe element is not allowed",
    "parsererror",
    "nativecommandfailed",
    "line       :",
    "linenumber :",
    "path       :",
    "exit code:",
    "wall time:",
)
CONVERSATION_QUERY_MARKERS = (
    "对话",
    "聊天",
    "之前",
    "刚才",
    "历史",
    "记忆",
    "memory",
    "conversation",
    "harness",
    "prompt engineering",
    "context engineering",
    "tool engineering",
    "eval engineering",
)


@dataclass
class SearchHit:
    rel_path: str
    chunk_index: int
    kind: str
    tags: list[str]
    score: float
    snippet: str
    rerank_score: float = 0.0
    matched_terms: list[str] = field(default_factory=list)
    rerank_reasons: list[str] = field(default_factory=list)


@dataclass
class AutomationSuggestion:
    rel_path: str
    title: str
    summary: str
    command_hint: str | None
    tags: list[str]
    score: float


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS files (
            rel_path TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            tags_json TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            mtime REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rel_path TEXT NOT NULL,
            kind TEXT NOT NULL,
            tags_json TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            rel_path,
            kind,
            tags,
            content,
            tokenize='unicode61'
        );

        CREATE TABLE IF NOT EXISTS automation_catalog (
            rel_path TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            command_hint TEXT,
            tags_json TEXT NOT NULL
        );
        """
    )
    conn.commit()


def reset_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DELETE FROM meta;
        DELETE FROM files;
        DELETE FROM chunks;
        DELETE FROM chunks_fts;
        DELETE FROM automation_catalog;
        """
    )
    conn.commit()


def iter_indexable_files(root: Path | None = None) -> Iterable[Path]:
    base = (root or PROJECT_ROOT).resolve()
    excluded = {entry.lower() for entry in EXCLUDED_DIRS}
    for current_root, dirnames, filenames in os.walk(base, topdown=True):
        dirnames[:] = [dirname for dirname in dirnames if dirname.lower() not in excluded]
        current_path = Path(current_root)
        for filename in filenames:
            path = current_path / filename
            if path.suffix.lower() not in INDEX_EXTENSIONS:
                continue
            try:
                if path.stat().st_size > MAX_TEXT_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield path


def _extract_wordprocessingml_text(data: bytes) -> str | None:
    try:
        with ZipFile(BytesIO(data)) as zf:
            member_names = zf.namelist()
            xml_members = [
                name
                for name in member_names
                if name in WORDPROCESSINGML_MEMBERS
                or name.startswith("word/header")
                or name.startswith("word/footer")
            ]
            if not xml_members:
                return None

            paragraphs: list[str] = []
            for member in xml_members:
                root = ET.fromstring(zf.read(member))
                for paragraph in root.findall(".//w:p", WORDPROCESSINGML_NS):
                    texts = [
                        node.text.strip()
                        for node in paragraph.findall(".//w:t", WORDPROCESSINGML_NS)
                        if node.text and node.text.strip()
                    ]
                    if texts:
                        paragraphs.append("".join(texts))

            text = "\n".join(paragraphs).strip()
            return text or None
    except Exception:
        return None


def read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None

    if not data:
        return ""

    if is_zipfile(BytesIO(data)):
        office_text = _extract_wordprocessingml_text(data)
        if office_text:
            return office_text
        return None

    for encoding in TEXT_ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    if path.suffix.lower() in {".py", ".md", ".txt", ".json", ".ini", ".toml", ".yaml", ".yml", ".ps1", ".bat"}:
        return data.decode("utf-8", errors="replace")
    return None


def summarize_text(text: str, max_lines: int = 6) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    summary = " | ".join(lines[:max_lines])
    return summary[:600]


def infer_kind(rel_path: str, text: str) -> str:
    name = rel_path.lower()
    if any(token in name for token in AUTOMATION_KIND_TOKENS):
        return "automation"
    if name.endswith((".md", ".txt")):
        return "doc"
    if name.endswith((".json", ".ini", ".toml", ".yaml", ".yml")):
        return "config"
    return "code"


def infer_tags(rel_path: str, text: str, kind: str) -> list[str]:
    tags: set[str] = {kind}
    lower_rel = rel_path.lower()
    lower_text = text.lower()

    for env in ("sit", "uat", "dev", "preprod", "reg", "local"):
        if env in lower_rel or f'"{env}"' in lower_text or f"'{env}'" in lower_text:
            tags.add(env)

    if "dpu_topic_portals/" in lower_rel:
        tags.add("topic-portal")
    if "codex_sessions_rag/" in lower_rel:
        tags.update({"codex-session", "conversation", "memory"})
    if "hsbc" in lower_rel or "hsbc" in lower_text:
        tags.add("hsbc")
    if "psp" in lower_rel or "psp" in lower_text:
        tags.add("psp")
    if "drawdown" in lower_rel or "drawdown" in lower_text:
        tags.add("drawdown")
    if "repayment" in lower_rel or "repayment" in lower_text:
        tags.add("repayment")
    if "migration" in lower_rel or "migration" in lower_text:
        tags.add("migration")
    if "metersphere" in lower_rel or "metersphere" in lower_text:
        tags.add("metersphere")
    if "mockapi" in lower_rel or "mockapi" in lower_text:
        tags.add("mockapi")
    if "webhook" in lower_rel or "webhook" in lower_text:
        tags.add("webhook")
    if "locator" in lower_rel or "locator" in lower_text:
        tags.add("locator")
    if "underwritten" in lower_rel or "approved" in lower_rel:
        tags.add("workflow")
    if any(hint in lower_rel for hint in AUTOMATION_NAME_HINTS):
        tags.add("automation")
    if any(token in rel_path for token in ("SOP", "用户故事", "task.md")):
        tags.add("runbook")
    if "selenium" in lower_text:
        tags.add("selenium")
    if "fastapi" in lower_text:
        tags.add("api")

    return sorted(tags)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    normalized = text.replace("\r\n", "\n")
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        if end < len(normalized):
            newline = normalized.rfind("\n", start, end)
            if newline > start + chunk_size // 2:
                end = newline
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks


def extract_query_terms(query: str) -> list[str]:
    lowered = query.lower()
    ascii_terms = re.findall(r"[a-z0-9_./-]+", lowered)
    chinese_terms = re.findall(r"[\u4e00-\u9fff]{2,}", query)
    terms = [term.strip() for term in chinese_terms + ascii_terms if term.strip()]
    if not terms and query.strip():
        terms = [query.strip().lower()]
    deduped = list(dict.fromkeys(terms))
    return sorted(deduped, key=len, reverse=True)


def make_command_hint(rel_path: str, kind: str) -> str | None:
    if rel_path.endswith(".py"):
        return f"& '.\\.venv\\Scripts\\python.exe' '{rel_path}'"
    if rel_path.endswith(".ps1"):
        return f"& '{rel_path}'"
    if kind == "doc":
        return None
    return None


def build_index(root: Path | None = None) -> dict[str, Any]:
    base = (root or PROJECT_ROOT).resolve()
    topic_portals = build_topic_portals(base, base / TOPIC_PORTAL_DIRNAME)

    conn = get_connection()
    init_db(conn)
    reset_db(conn)

    file_count = 0
    chunk_count = 0
    automation_count = 0

    with conn:
        for path in iter_indexable_files(base):
            text = read_text(path)
            if text is None:
                continue

            rel_path = path.relative_to(base).as_posix()
            kind = infer_kind(rel_path, text)
            tags = infer_tags(rel_path, text, kind)
            stat = path.stat()

            conn.execute(
                """
                INSERT INTO files(rel_path, kind, tags_json, size_bytes, mtime)
                VALUES (?, ?, ?, ?, ?)
                """,
                (rel_path, kind, json.dumps(tags, ensure_ascii=False), stat.st_size, stat.st_mtime),
            )
            file_count += 1

            chunks = chunk_text(text)
            for index, chunk in enumerate(chunks):
                cursor = conn.execute(
                    """
                    INSERT INTO chunks(rel_path, kind, tags_json, chunk_index, content)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (rel_path, kind, json.dumps(tags, ensure_ascii=False), index, chunk),
                )
                rowid = cursor.lastrowid
                conn.execute(
                    """
                    INSERT INTO chunks_fts(rowid, rel_path, kind, tags, content)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (rowid, rel_path, kind, " ".join(tags), chunk),
                )
                chunk_count += 1

            if "automation" in tags or kind in {"automation", "doc"}:
                summary = summarize_text(text)
                if summary:
                    conn.execute(
                        """
                        INSERT INTO automation_catalog(rel_path, title, summary, command_hint, tags_json)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (rel_path, path.name, summary, make_command_hint(rel_path, kind), json.dumps(tags, ensure_ascii=False)),
                    )
                    automation_count += 1

        meta = {
            "project_root": str(base),
            "db_path": str(DB_PATH),
            "built_at": utc_now_iso(),
            "file_count": file_count,
            "chunk_count": chunk_count,
            "automation_count": automation_count,
            "topic_portal_count": len(topic_portals),
        }
        conn.executemany(
            "INSERT INTO meta(key, value) VALUES (?, ?)",
            [(key, str(value)) for key, value in meta.items()],
        )

    conn.close()
    return meta


def get_status() -> dict[str, Any]:
    if not DB_PATH.exists():
        return {
            "project_root": str(PROJECT_ROOT),
            "db_path": str(DB_PATH),
            "ready": False,
        }

    conn = get_connection()
    init_db(conn)
    meta = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM meta")}
    conn.close()
    if not meta:
        return {
            "project_root": str(PROJECT_ROOT),
            "db_path": str(DB_PATH),
            "ready": False,
        }

    meta["ready"] = True
    return meta


def ensure_index() -> dict[str, Any]:
    status = get_status()
    if status.get("ready"):
        return status
    return build_index()


def topic_portals(root: Path | None = None) -> list[TopicPortalInfo]:
    base = (root or PROJECT_ROOT).resolve()
    return build_topic_portals(base, base / TOPIC_PORTAL_DIRNAME)


def _snippet(text: str, terms: list[str]) -> str:
    normalized = text.replace("\n", " ").strip()
    if not normalized:
        return ""
    for term in terms:
        idx = normalized.lower().find(term.lower())
        if idx >= 0:
            start = max(0, idx - 80)
            end = min(len(normalized), idx + 220)
            return normalized[start:end]
    return normalized[:240]


def _normalized_query(query: str) -> str:
    return " ".join(query.lower().split())


def _contains_conversation_marker(query: str) -> bool:
    lowered = query.lower()
    return any(marker in lowered for marker in CONVERSATION_QUERY_MARKERS)


def _bounded_count(text: str, term: str, cap: int = 8) -> int:
    if not term:
        return 0
    count = text.count(term)
    return min(count, cap)


def _term_positions(text: str, terms: list[str]) -> list[int]:
    positions: list[int] = []
    for term in terms:
        index = text.find(term.lower())
        if index >= 0:
            positions.append(index)
    return positions


def _rerank_candidate(
    query: str,
    terms: list[str],
    rel_path: str,
    tags: list[str],
    content: str,
) -> tuple[float, list[str], list[str]]:
    """Score usefulness after broad lexical retrieval.

    The first-pass search is intentionally broad; this second pass rewards
    chunks that answer the whole query compactly and demotes noisy tool-output
    fragments that merely contain the same words.
    """

    lowered_query = _normalized_query(query)
    lowered_content = content.lower()
    lowered_path = rel_path.lower()
    lowered_tags = " ".join(tags).lower()
    searchable = f"{lowered_path} {lowered_tags} {lowered_content}"

    matched_terms = [term for term in terms if term.lower() in searchable]
    reasons: list[str] = []
    score = 0.0

    if lowered_query and len(lowered_query) >= 4:
        if lowered_query in lowered_content:
            score += 90.0
            reasons.append("exact-query-in-content")
        if lowered_query in lowered_path:
            score += 55.0
            reasons.append("exact-query-in-path")

    if terms:
        coverage = len(matched_terms) / len(terms)
        if coverage:
            score += 60.0 * coverage
            reasons.append(f"term-coverage={coverage:.2f}")
        if len(matched_terms) == len(terms):
            score += 35.0
            reasons.append("all-query-terms")

    for term in terms:
        lowered_term = term.lower()
        if not lowered_term:
            continue
        term_weight = min(len(lowered_term), 32) * 0.8
        if lowered_term in lowered_content:
            occurrences = _bounded_count(lowered_content, lowered_term)
            score += 10.0 + term_weight + occurrences * 2.5
        if lowered_term in lowered_path:
            score += 24.0 + min(len(lowered_term), 24) * 0.5
            reasons.append(f"path-match:{term}")
        if lowered_term in lowered_tags:
            score += 14.0
            reasons.append(f"tag-match:{term}")

    positions = _term_positions(lowered_content, matched_terms)
    if len(positions) >= 2:
        span = max(positions) - min(positions)
        if span <= 300:
            score += 45.0
            reasons.append("tight-term-proximity")
        elif span <= 900:
            score += 20.0
            reasons.append("near-term-proximity")

    first_lines = "\n".join(content.splitlines()[:5]).lower()
    if any(term.lower() in first_lines for term in matched_terms):
        score += 18.0
        reasons.append("early-section-match")

    if "topic-portal" in tags:
        score += 18.0
        reasons.append("topic-portal")
    if "automation" in tags and any(term in lowered_query for term in ("run", "脚本", "自动化", "automation", "执行")):
        score += 15.0
        reasons.append("automation-intent")
    if "codex-session" in tags:
        if _contains_conversation_marker(query):
            score += 20.0
            reasons.append("conversation-memory")
        else:
            score -= 8.0
            reasons.append("conversation-soft-penalty")
        if "### " in content and " assistant" in lowered_content:
            score += 28.0
            reasons.append("assistant-message")
        if "### " in content and " user" in lowered_content:
            score += 18.0
            reasons.append("user-message")

    if rel_path.startswith("dpu_rag_mvp/") and "rag" not in lowered_query:
        score -= 55.0
        reasons.append("rag-internals-penalty")
    if rel_path.startswith("output/") or "/output/" in lowered_path:
        score -= 85.0
        reasons.append("output-artifact-penalty")
    if rel_path.startswith("codex_sessions_rag/"):
        score -= 40.0
        reasons.append("raw-session-penalty")
    if lowered_path.endswith(".json") and any(token in lowered_query for token in ("代码", "script", "脚本", "mock_sit", "function")):
        score -= 45.0
        reasons.append("json-artifact-penalty")
    if lowered_path in {"mock_sit.py", "mockapi/mock_sit.py"} and "mock_sit" in lowered_query:
        score += 70.0
        reasons.append("canonical-mock-sit")
    if "mockapi/web/services/mock_adapter.py" in lowered_path and any(token in lowered_query for token in ("mockapi", "web", "接口")):
        score += 45.0
        reasons.append("canonical-mockapi-adapter")

    if any(marker in lowered_content for marker in NOISY_TOOL_OUTPUT_MARKERS):
        score -= 65.0
        reasons.append("tool-error-noise-penalty")
    tool_fragment_count = lowered_content.count("tool call") + lowered_content.count("tool output")
    if tool_fragment_count:
        penalty = min(70.0, 15.0 * tool_fragment_count)
        score -= penalty
        reasons.append("tool-fragment-penalty")
    if lowered_content.count("### ") >= 8 and "assistant" not in lowered_content[:1200]:
        score -= 18.0
        reasons.append("dense-log-fragment-penalty")

    return score, matched_terms, reasons[:8]


def search(
    query: str,
    limit: int = 8,
    kind: str | None = None,
    rerank: bool = True,
    candidate_limit: int = DEFAULT_RERANK_CANDIDATE_LIMIT,
) -> list[SearchHit]:
    ensure_index()
    terms = extract_query_terms(query)
    conn = get_connection()
    candidate_limit = max(limit, candidate_limit)

    fts_rows: list[sqlite3.Row] = []
    if terms:
        match_query = " OR ".join(f'"{term}"' for term in terms)
        sql = """
            SELECT c.rel_path, c.chunk_index, c.kind, c.tags_json, c.content, bm25(chunks_fts) AS rank
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.rowid
            WHERE chunks_fts MATCH ?
        """
        params: list[Any] = [match_query]
        if kind:
            sql += " AND c.kind = ?"
            params.append(kind)
        sql += " ORDER BY rank LIMIT ?"
        params.append(candidate_limit)
        try:
            fts_rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            fts_rows = []

    like_rows: list[sqlite3.Row] = []
    for term in terms[:6]:
        sql = """
            SELECT rel_path, chunk_index, kind, tags_json, content, 0.0 AS rank
            FROM chunks
            WHERE (rel_path LIKE ? OR content LIKE ?)
        """
        like_params: list[Any] = [f"%{term}%", f"%{term}%"]
        if kind:
            sql += " AND kind = ?"
            like_params.append(kind)
        sql += " LIMIT ?"
        like_params.append(candidate_limit)
        like_rows.extend(conn.execute(sql, like_params).fetchall())

    conn.close()

    merged: dict[tuple[str, int], SearchHit] = {}
    for row in list(fts_rows) + list(like_rows):
        row_terms = terms or [query]
        tags = json.loads(row["tags_json"])
        base_score = 1000.0 - float(row["rank"])
        rel_path = row["rel_path"]
        path_lower = rel_path.lower()
        content_lower = row["content"].lower()
        for term in row_terms:
            if term.lower() in path_lower:
                base_score += 30.0
            if term.lower() in content_lower:
                base_score += 8.0 + min(len(term), 30) * 0.5
            if term.lower() in " ".join(tags).lower():
                base_score += 12.0
        if "automation" in tags:
            base_score += 4.0
        if "codex-session" in tags:
            base_score += 3.0
        if "topic-portal" in tags:
            base_score += 6.0
        if rel_path.startswith("dpu_rag_mvp/"):
            base_score -= 120.0
        rerank_score = 0.0
        matched_terms: list[str] = []
        rerank_reasons: list[str] = []
        if rerank:
            rerank_score, matched_terms, rerank_reasons = _rerank_candidate(
                query=query,
                terms=row_terms,
                rel_path=rel_path,
                tags=tags,
                content=row["content"],
            )
            base_score += rerank_score
        key = (rel_path, row["chunk_index"])
        current = merged.get(key)
        hit = SearchHit(
            rel_path=rel_path,
            chunk_index=row["chunk_index"],
            kind=row["kind"],
            tags=tags,
            score=base_score,
            snippet=_snippet(row["content"], row_terms),
            rerank_score=rerank_score,
            matched_terms=matched_terms,
            rerank_reasons=rerank_reasons,
        )
        if current is None or hit.score > current.score:
            merged[key] = hit

    results = sorted(merged.values(), key=lambda item: item.score, reverse=True)
    return results[:limit]


def automation_catalog(limit: int = 50) -> list[AutomationSuggestion]:
    ensure_index()
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT rel_path, title, summary, command_hint, tags_json
        FROM automation_catalog
        ORDER BY rel_path
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [
        AutomationSuggestion(
            rel_path=row["rel_path"],
            title=row["title"],
            summary=row["summary"],
            command_hint=row["command_hint"],
            tags=json.loads(row["tags_json"]),
            score=0.0,
        )
        for row in rows
    ]


def suggest_automation(goal: str, limit: int = 8) -> list[AutomationSuggestion]:
    ensure_index()
    terms = extract_query_terms(goal)
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT rel_path, title, summary, command_hint, tags_json
        FROM automation_catalog
        """
    ).fetchall()
    conn.close()

    suggestions: list[AutomationSuggestion] = []
    for row in rows:
        rel_path = row["rel_path"]
        tags = json.loads(row["tags_json"])
        summary = row["summary"]
        score = 0.0
        text = f"{rel_path} {summary} {' '.join(tags)}".lower()
        for term in terms:
            if term.lower() in text:
                score += 12.0
            if term.lower() in rel_path.lower():
                score += 18.0
        if "automation" in tags:
            score += 10.0
        if "runbook" in tags:
            score += 4.0
        if "topic-portal" in tags:
            score += 6.0
        if "hsbc" in goal.lower() and "hsbc" in tags:
            score += 10.0
        if "psp" in goal.lower() and "psp" in tags:
            score += 10.0
        if "metersphere" in goal.lower() and "metersphere" in tags:
            score += 10.0
        if "migration" in goal.lower() and "migration" in tags:
            score += 10.0
        if score <= 0:
            continue
        suggestions.append(
            AutomationSuggestion(
                rel_path=rel_path,
                title=row["title"],
                summary=summary,
                command_hint=row["command_hint"],
                tags=tags,
                score=score,
            )
        )

    suggestions.sort(key=lambda item: item.score, reverse=True)
    return suggestions[:limit]
