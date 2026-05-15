from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import CODEX_SESSION_RAG_DIR, DATA_DIR, MEMORY_DB_PATH
from .core import extract_query_terms, utc_now_iso
from .query import expand_query


SUMMARY_TITLES = ("assistant", "user")
EVIDENCE_TITLES = ("tool output", "tool call")
MAX_SECTION_CHARS = 2_400
MAX_TOOL_SECTION_CHARS = 900
MAX_MEMORY_CHARS_PER_FILE = 28_000
NOISY_LINES = (
    "wall time:",
    "exit code:",
    "total output lines:",
    "warning:",
    "exception ignored on flushing",
)


@dataclass
class MemoryHit:
    rel_path: str
    section_index: int
    memory_type: str
    score: float
    snippet: str
    matched_terms: list[str] = field(default_factory=list)


@dataclass
class MemoryCard:
    rel_path: str
    title: str
    status: str
    keywords: list[str]
    summary: str
    evidence: list[str]
    score: float = 0.0
    matched_terms: list[str] = field(default_factory=list)


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(MEMORY_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memory_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rel_path TEXT NOT NULL,
            section_index INTEGER NOT NULL,
            memory_type TEXT NOT NULL,
            content TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memory_cards (
            rel_path TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            keywords_json TEXT NOT NULL,
            summary TEXT NOT NULL,
            evidence_json TEXT NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
            rel_path,
            memory_type,
            content,
            tokenize='unicode61'
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS memory_cards_fts USING fts5(
            rel_path,
            title,
            status,
            keywords,
            summary,
            evidence,
            tokenize='unicode61'
        );
        """
    )
    conn.commit()


def _reset_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DELETE FROM meta;
        DELETE FROM memory_chunks;
        DELETE FROM memory_fts;
        DELETE FROM memory_cards;
        DELETE FROM memory_cards_fts;
        """
    )
    conn.commit()


def _iter_session_markdown(session_dir: Path = CODEX_SESSION_RAG_DIR) -> list[Path]:
    if not session_dir.exists():
        return []
    return sorted(
        path for path in session_dir.glob("*.md") if not path.name.startswith("_")
    )


def _split_markdown_sections(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^###\s+(.+?)\s*$", text, flags=re.MULTILINE))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        title = match.group(1).strip()
        body = text[start:end].strip()
        if body:
            sections.append((title, body))
    return sections


def _memory_type(title: str) -> str | None:
    lowered = title.lower()
    if any(token in lowered for token in SUMMARY_TITLES):
        return "summary"
    if any(token in lowered for token in EVIDENCE_TITLES):
        return "evidence"
    return None


def _clean_body(body: str, memory_type: str) -> str:
    lines = []
    for line in body.splitlines():
        lowered = line.strip().lower()
        if any(marker in lowered for marker in NOISY_LINES):
            continue
        lines.append(line.rstrip())
    cleaned = "\n".join(lines).strip()
    limit = MAX_TOOL_SECTION_CHARS if memory_type == "evidence" else MAX_SECTION_CHARS
    if len(cleaned) > limit:
        cleaned = cleaned[:limit].rstrip() + "\n[truncated]"
    return cleaned


def _extract_memory_chunks(path: Path, base: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    chunks: list[tuple[str, str]] = []
    total_chars = 0
    for title, body in _split_markdown_sections(text):
        memory_type = _memory_type(title)
        if memory_type is None:
            continue
        cleaned = _clean_body(body, memory_type)
        if not cleaned:
            continue
        chunk = f"{title}\n\n{cleaned}"
        if total_chars + len(chunk) > MAX_MEMORY_CHARS_PER_FILE:
            break
        chunks.append((memory_type, chunk))
        total_chars += len(chunk)
    return chunks


def _extract_metadata(text: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    match = re.search(r"## Metadata\s+(.*?)\s+## Conversation", text, flags=re.DOTALL)
    if not match:
        return metadata
    for line in match.group(1).splitlines():
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def _extract_keywords(text: str, rel_path: str) -> list[str]:
    candidates = (
        "scenario_1",
        "reg",
        "mock_sit",
        "mockapi",
        "MeterSphere",
        "esign",
        "approved-offer",
        "underwritten",
        "psp",
        "drawdown",
        "migration",
        "multi-shop",
        "locator",
        "selenium",
        "RAG",
        "memory",
        "DataGrip",
        "config.toml",
    )
    lowered = f"{rel_path}\n{text}".lower()
    keywords = [item for item in candidates if item.lower() in lowered]
    chinese_terms = re.findall(r"[\u4e00-\u9fff]{2,8}", text[:8000])
    for term in chinese_terms[:30]:
        if term not in keywords and len(term) >= 2:
            keywords.append(term)
        if len(keywords) >= 18:
            break
    return keywords[:18]


def _infer_status(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ("outcome=success", "成功", "passed", "pass")):
        return "success"
    if any(token in lowered for token in ("blocked", "阻塞", "blocker")):
        return "blocked"
    if any(token in lowered for token in ("partial", "部分", "pending")):
        return "partial"
    return "unknown"


def _first_summary(chunks: list[tuple[str, str]]) -> str:
    for memory_type, content in chunks:
        if memory_type == "summary":
            summary = " ".join(content.split())
            return summary[:900]
    return ""


def _evidence_lines(chunks: list[tuple[str, str]]) -> list[str]:
    evidence: list[str] = []
    for memory_type, content in chunks:
        if memory_type != "evidence":
            continue
        flattened = " ".join(content.split())
        if flattened:
            evidence.append(flattened[:260])
        if len(evidence) >= 4:
            break
    return evidence


def _build_memory_card(path: Path, rel_path: str, chunks: list[tuple[str, str]]) -> MemoryCard:
    text = path.read_text(encoding="utf-8", errors="replace")
    metadata = _extract_metadata(text)
    title = metadata.get("id") or path.stem
    summary = _first_summary(chunks)
    return MemoryCard(
        rel_path=rel_path,
        title=title,
        status=_infer_status(text),
        keywords=_extract_keywords(text, rel_path),
        summary=summary,
        evidence=_evidence_lines(chunks),
    )


def build_memory_index(session_dir: Path = CODEX_SESSION_RAG_DIR) -> dict[str, Any]:
    base = session_dir.resolve()
    files = _iter_session_markdown(base)
    conn = _connect()
    _init_db(conn)
    _reset_db(conn)

    file_count = 0
    chunk_count = 0
    card_count = 0
    with conn:
        for path in files:
            rel_path = path.relative_to(base.parent).as_posix()
            chunks = _extract_memory_chunks(path, base.parent)
            if not chunks:
                continue
            file_count += 1
            card = _build_memory_card(path, rel_path, chunks)
            conn.execute(
                """
                INSERT INTO memory_cards(rel_path, title, status, keywords_json, summary, evidence_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    card.rel_path,
                    card.title,
                    card.status,
                    json.dumps(card.keywords, ensure_ascii=False),
                    card.summary,
                    json.dumps(card.evidence, ensure_ascii=False),
                ),
            )
            conn.execute(
                """
                INSERT INTO memory_cards_fts(rel_path, title, status, keywords, summary, evidence)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    card.rel_path,
                    card.title,
                    card.status,
                    " ".join(card.keywords),
                    card.summary,
                    " ".join(card.evidence),
                ),
            )
            card_count += 1
            for index, (memory_type, content) in enumerate(chunks):
                cursor = conn.execute(
                    """
                    INSERT INTO memory_chunks(rel_path, section_index, memory_type, content)
                    VALUES (?, ?, ?, ?)
                    """,
                    (rel_path, index, memory_type, content),
                )
                conn.execute(
                    """
                    INSERT INTO memory_fts(rowid, rel_path, memory_type, content)
                    VALUES (?, ?, ?, ?)
                    """,
                    (cursor.lastrowid, rel_path, memory_type, content),
                )
                chunk_count += 1

        meta = {
            "session_dir": str(base),
            "db_path": str(MEMORY_DB_PATH),
            "built_at": utc_now_iso(),
            "file_count": file_count,
            "chunk_count": chunk_count,
            "card_count": card_count,
        }
        conn.executemany(
            "INSERT INTO meta(key, value) VALUES (?, ?)",
            [(key, str(value)) for key, value in meta.items()],
        )
    conn.close()
    return meta


def get_memory_status() -> dict[str, Any]:
    if not MEMORY_DB_PATH.exists():
        return {
            "session_dir": str(CODEX_SESSION_RAG_DIR),
            "db_path": str(MEMORY_DB_PATH),
            "ready": False,
        }
    conn = _connect()
    _init_db(conn)
    meta = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM meta")}
    conn.close()
    if not meta:
        return {
            "session_dir": str(CODEX_SESSION_RAG_DIR),
            "db_path": str(MEMORY_DB_PATH),
            "ready": False,
        }
    meta["ready"] = True
    return meta


def ensure_memory_index() -> dict[str, Any]:
    status = get_memory_status()
    if status.get("ready"):
        return status
    return build_memory_index()


def _snippet(text: str, terms: list[str]) -> str:
    normalized = " ".join(text.split())
    for term in terms:
        index = normalized.lower().find(term.lower())
        if index >= 0:
            start = max(0, index - 90)
            end = min(len(normalized), index + 260)
            return normalized[start:end]
    return normalized[:280]


def search_memory(query: str, limit: int = 8, memory_type: str | None = None) -> list[MemoryHit]:
    ensure_memory_index()
    expanded_query = expand_query(query)
    terms = extract_query_terms(expanded_query)
    candidate_limit = max(limit * 8, 40)
    conn = _connect()

    rows: list[sqlite3.Row] = []
    if terms:
        match_query = " OR ".join(f'"{term}"' for term in terms)
        sql = """
            SELECT m.rel_path, m.section_index, m.memory_type, m.content, bm25(memory_fts) AS rank
            FROM memory_fts
            JOIN memory_chunks m ON m.id = memory_fts.rowid
            WHERE memory_fts MATCH ?
        """
        params: list[Any] = [match_query]
        if memory_type:
            sql += " AND m.memory_type = ?"
            params.append(memory_type)
        sql += " ORDER BY rank LIMIT ?"
        params.append(candidate_limit)
        try:
            rows.extend(conn.execute(sql, params).fetchall())
        except sqlite3.OperationalError:
            rows = []

    for term in terms[:6]:
        sql = """
            SELECT rel_path, section_index, memory_type, content, 0.0 AS rank
            FROM memory_chunks
            WHERE (rel_path LIKE ? OR content LIKE ?)
        """
        params = [f"%{term}%", f"%{term}%"]
        if memory_type:
            sql += " AND memory_type = ?"
            params.append(memory_type)
        sql += " LIMIT ?"
        params.append(candidate_limit)
        rows.extend(conn.execute(sql, params).fetchall())
    conn.close()

    merged: dict[tuple[str, int], MemoryHit] = {}
    for row in rows:
        content = row["content"]
        content_lower = content.lower()
        rel_path = row["rel_path"]
        matched_terms = [term for term in terms if term.lower() in content_lower or term.lower() in rel_path.lower()]
        score = 1000.0 - float(row["rank"]) + len(matched_terms) * 18.0
        if row["memory_type"] == "summary":
            score += 30.0
        if "tool output" in content_lower:
            score -= 20.0
        key = (rel_path, row["section_index"])
        hit = MemoryHit(
            rel_path=rel_path,
            section_index=row["section_index"],
            memory_type=row["memory_type"],
            score=score,
            snippet=_snippet(content, terms or [query]),
            matched_terms=matched_terms,
        )
        current = merged.get(key)
        if current is None or hit.score > current.score:
            merged[key] = hit

    return sorted(merged.values(), key=lambda item: item.score, reverse=True)[:limit]


def search_memory_cards(query: str, limit: int = 8) -> list[MemoryCard]:
    ensure_memory_index()
    expanded_query = expand_query(query)
    terms = extract_query_terms(expanded_query)
    candidate_limit = max(limit * 5, 30)
    conn = _connect()
    rows: list[sqlite3.Row] = []
    if terms:
        match_query = " OR ".join(f'"{term}"' for term in terms)
        sql = """
            SELECT c.rel_path, c.title, c.status, c.keywords_json, c.summary, c.evidence_json,
                   bm25(memory_cards_fts) AS rank
            FROM memory_cards_fts
            JOIN memory_cards c ON c.rel_path = memory_cards_fts.rel_path
            WHERE memory_cards_fts MATCH ?
            ORDER BY rank LIMIT ?
        """
        try:
            rows.extend(conn.execute(sql, (match_query, candidate_limit)).fetchall())
        except sqlite3.OperationalError:
            rows = []
    for term in terms[:6]:
        rows.extend(
            conn.execute(
                """
                SELECT rel_path, title, status, keywords_json, summary, evidence_json, 0.0 AS rank
                FROM memory_cards
                WHERE rel_path LIKE ? OR title LIKE ? OR summary LIKE ? OR keywords_json LIKE ?
                LIMIT ?
                """,
                (f"%{term}%", f"%{term}%", f"%{term}%", f"%{term}%", candidate_limit),
            ).fetchall()
        )
    conn.close()

    merged: dict[str, MemoryCard] = {}
    for row in rows:
        keywords = json.loads(row["keywords_json"])
        evidence = json.loads(row["evidence_json"])
        searchable = f"{row['rel_path']} {row['title']} {row['status']} {' '.join(keywords)} {row['summary']} {' '.join(evidence)}".lower()
        matched_terms = [term for term in terms if term.lower() in searchable]
        score = 1000.0 - float(row["rank"]) + len(matched_terms) * 22.0
        if row["status"] == "success":
            score += 28.0
        elif row["status"] == "partial":
            score += 8.0
        if matched_terms and all(term.lower() in searchable for term in extract_query_terms(query)[:4]):
            score += 35.0
        card = MemoryCard(
            rel_path=row["rel_path"],
            title=row["title"],
            status=row["status"],
            keywords=keywords,
            summary=row["summary"],
            evidence=evidence,
            score=score,
            matched_terms=matched_terms,
        )
        current = merged.get(card.rel_path)
        if current is None or card.score > current.score:
            merged[card.rel_path] = card
    return sorted(merged.values(), key=lambda item: item.score, reverse=True)[:limit]
