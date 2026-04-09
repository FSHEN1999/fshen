from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

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
)


TEXT_ENCODINGS = ("utf-8", "utf-8-sig", "gbk", "gb18030")


@dataclass
class SearchHit:
    rel_path: str
    chunk_index: int
    kind: str
    tags: list[str]
    score: float
    snippet: str


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
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in INDEX_EXTENSIONS:
            continue
        try:
            if path.stat().st_size > MAX_TEXT_FILE_BYTES:
                continue
        except OSError:
            continue
        yield path


def read_text(path: Path) -> str | None:
    for encoding in TEXT_ENCODINGS:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        except OSError:
            return None
    try:
        return path.read_text(encoding="latin-1")
    except OSError:
        return None


def summarize_text(text: str, max_lines: int = 6) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    summary = " | ".join(lines[:max_lines])
    return summary[:600]


def infer_kind(rel_path: str, text: str) -> str:
    name = rel_path.lower()
    if any(token in name for token in ("mock_", "自动化", "migration_test", "compare_", "rollback", "offerid")):
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

    for env in ("sit", "uat", "dev", "preprod", "local"):
        if env in lower_rel or f'"{env}"' in lower_text or f"'{env}'" in lower_text:
            tags.add(env)

    if "hsbc" in lower_rel or "hsbc" in lower_text:
        tags.add("hsbc")
    if "psp" in lower_rel or "psp" in lower_text:
        tags.add("psp")
    if "drawdown" in lower_rel or "drawdown" in lower_text:
        tags.add("drawdown")
    if "repayment" in lower_rel or "repayment" in lower_text:
        tags.add("repayment")
    if "underwritten" in lower_rel or "approved" in lower_rel:
        tags.add("workflow")
    if any(hint in lower_rel for hint in AUTOMATION_NAME_HINTS):
        tags.add("automation")
    if any(token in rel_path for token in ("SOP", "用户故事")):
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
    terms = [term.strip() for term in ascii_terms + chinese_terms if term.strip()]
    if not terms and query.strip():
        terms = [query.strip().lower()]
    return list(dict.fromkeys(terms))


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
    conn = get_connection()
    init_db(conn)
    reset_db(conn)

    file_count = 0
    chunk_count = 0
    automation_count = 0

    with conn:
        for path in iter_indexable_files(base):
            text = read_text(path)
            if not text:
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


def search(query: str, limit: int = 8, kind: str | None = None) -> list[SearchHit]:
    ensure_index()
    terms = extract_query_terms(query)
    conn = get_connection()

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
        sql += " ORDER BY rank LIMIT 50"
        try:
            fts_rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            fts_rows = []

    like_rows: list[sqlite3.Row] = []
    like_params: list[Any] = []
    like_clauses: list[str] = []
    for term in terms[:6]:
        like_clauses.append("(rel_path LIKE ? OR content LIKE ?)")
        like_params.extend([f"%{term}%", f"%{term}%"])
    if like_clauses:
        sql = """
            SELECT rel_path, chunk_index, kind, tags_json, content, 999.0 AS rank
            FROM chunks
            WHERE
        """
        sql += " OR ".join(like_clauses)
        if kind:
            sql += " AND kind = ?"
            like_params.append(kind)
        sql += " LIMIT 50"
        like_rows = conn.execute(sql, like_params).fetchall()

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
                base_score += 8.0
            if term.lower() in " ".join(tags).lower():
                base_score += 12.0
        if "automation" in tags:
            base_score += 4.0
        key = (rel_path, row["chunk_index"])
        current = merged.get(key)
        hit = SearchHit(
            rel_path=rel_path,
            chunk_index=row["chunk_index"],
            kind=row["kind"],
            tags=tags,
            score=base_score,
            snippet=_snippet(row["content"], row_terms),
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
        if "hsbc" in goal.lower() and "hsbc" in tags:
            score += 10.0
        if "psp" in goal.lower() and "psp" in tags:
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

