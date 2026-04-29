from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_DIRNAME = "codex_sessions_rag"
MAX_PART_CHARS = 350_000
MAX_TOOL_OUTPUT_CHARS = 12_000
MAX_TOOL_ARGUMENT_CHARS = 8_000


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).resolve()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    omitted = len(text) - max_chars
    return f"{text[:max_chars]}\n\n[truncated {omitted} chars]"


def json_preview(value: Any, max_chars: int) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, indent=2)
    except TypeError:
        text = str(value)
    return truncate(text, max_chars)


def text_from_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif isinstance(item.get("content"), str):
                    parts.append(item["content"])
                elif item.get("type") in {"image", "local_image"}:
                    target = item.get("path") or item.get("image_url") or "attached"
                    parts.append(f"[{item.get('type')}: {target}]")
                else:
                    parts.append(json_preview(item, 1200))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part).strip()
    if isinstance(content, dict):
        return json_preview(content, 2000)
    return str(content)


def safe_heading(text: str) -> str:
    return text.replace("\r", " ").replace("\n", " ").strip()


def md_block(title: str, content: str, fence: str = "") -> str:
    content = content.strip()
    if not content:
        return ""
    if fence:
        return f"### {title}\n\n```{fence}\n{content}\n```\n"
    return f"### {title}\n\n{content}\n"


def format_response_item(payload: dict[str, Any], timestamp: str | None) -> str:
    item_type = payload.get("type")
    prefix = f"{timestamp} " if timestamp else ""

    if item_type == "message":
        role = payload.get("role") or "message"
        text = text_from_content(payload.get("content"))
        return md_block(f"{prefix}{role}", text)

    if item_type == "function_call":
        name = payload.get("name") or payload.get("tool") or "function_call"
        namespace = payload.get("namespace")
        label = f"{namespace}.{name}" if namespace else str(name)
        args = payload.get("arguments", "")
        if isinstance(args, str):
            args_text = truncate(args, MAX_TOOL_ARGUMENT_CHARS)
        else:
            args_text = json_preview(args, MAX_TOOL_ARGUMENT_CHARS)
        return md_block(f"{prefix}tool call: {safe_heading(label)}", args_text, "json")

    if item_type == "function_call_output":
        output_text = text_from_content(payload.get("output", ""))
        call_id = payload.get("call_id") or ""
        return md_block(f"{prefix}tool output: {call_id}".strip(), truncate(output_text, MAX_TOOL_OUTPUT_CHARS))

    if item_type == "reasoning":
        text = text_from_content(payload.get("summary") or payload.get("content"))
        return md_block(f"{prefix}assistant reasoning summary", text)

    return ""


def parse_session(path: Path) -> tuple[dict[str, Any], list[str]]:
    meta: dict[str, Any] = {
        "source_path": str(path),
        "source_file": path.name,
    }
    sections: list[str] = []
    turn_count = 0

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return meta, sections

    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        record_type = record.get("type")
        payload = record.get("payload") or {}
        timestamp = record.get("timestamp")

        if record_type == "session_meta" and isinstance(payload, dict):
            for key in ("id", "timestamp", "cwd", "originator", "cli_version", "source", "model_provider"):
                if payload.get(key):
                    meta[key] = payload[key]
            continue

        if record_type == "turn_context" and isinstance(payload, dict):
            turn_count += 1
            if turn_count == 1:
                for key in ("cwd", "current_date", "timezone", "model", "personality", "effort"):
                    if payload.get(key):
                        meta.setdefault(key, payload[key])
            continue

        if record_type != "response_item" or not isinstance(payload, dict):
            continue

        formatted = format_response_item(payload, timestamp)
        if formatted:
            sections.append(formatted)

    meta["turn_count"] = turn_count
    meta["response_section_count"] = len(sections)
    return meta, sections


def session_markdown(meta: dict[str, Any], sections: list[str], part_index: int, part_count: int) -> str:
    title_id = meta.get("id") or meta.get("source_file", "unknown")
    header = [
        f"# Codex Session {title_id}",
        "",
        "This file is generated from local Codex session JSONL for DPU RAG retrieval.",
        "",
        "## Metadata",
        "",
    ]
    for key in (
        "id",
        "timestamp",
        "cwd",
        "current_date",
        "timezone",
        "model",
        "effort",
        "originator",
        "source",
        "model_provider",
        "source_file",
        "source_path",
        "turn_count",
        "response_section_count",
    ):
        value = meta.get(key)
        if value is not None:
            header.append(f"- {key}: {value}")
    header.extend(
        [
            f"- generated_at: {utc_now_iso()}",
            f"- part: {part_index + 1}/{part_count}",
            "",
            "## Conversation",
            "",
        ]
    )
    return "\n".join(header) + "\n".join(sections).strip() + "\n"


def clean_session_outputs(output_dir: Path, session_stem: str) -> None:
    for old_file in output_dir.glob(f"{session_stem}*.md"):
        old_file.unlink()


def split_sections(sections: list[str], max_chars: int) -> list[list[str]]:
    if not sections:
        return []
    parts: list[list[str]] = []
    current: list[str] = []
    current_len = 0
    for section in sections:
        section_len = len(section)
        if current and current_len + section_len > max_chars:
            parts.append(current)
            current = []
            current_len = 0
        current.append(section)
        current_len += section_len
    if current:
        parts.append(current)
    return parts


def export_session(path: Path, output_dir: Path, max_part_chars: int) -> int:
    meta, sections = parse_session(path)
    if not sections:
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    session_stem = path.stem
    clean_session_outputs(output_dir, session_stem)

    parts = split_sections(sections, max_part_chars)
    for index, part_sections in enumerate(parts):
        suffix = "" if len(parts) == 1 else f"-part{index + 1:02d}"
        output_path = output_dir / f"{session_stem}{suffix}.md"
        output_path.write_text(session_markdown(meta, part_sections, index, len(parts)), encoding="utf-8")
    return len(parts)


def iter_session_files(sessions_dir: Path) -> list[Path]:
    if not sessions_dir.exists():
        return []
    return sorted(sessions_dir.rglob("*.jsonl"), key=lambda path: str(path).lower())


def should_export(path: Path, state: dict[str, Any], force: bool) -> bool:
    if force:
        return True
    try:
        stat = path.stat()
    except OSError:
        return False
    files = state.get("files") or {}
    previous = files.get(str(path))
    return not previous or previous.get("mtime") != stat.st_mtime or previous.get("size") != stat.st_size


def update_state_for(path: Path, state: dict[str, Any], exported_parts: int) -> None:
    stat = path.stat()
    files = state.setdefault("files", {})
    files[str(path)] = {
        "mtime": stat.st_mtime,
        "size": stat.st_size,
        "exported_parts": exported_parts,
        "exported_at": utc_now_iso(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export local Codex session JSONL into Markdown files indexed by DPU RAG.")
    parser.add_argument("--sessions-dir", type=Path, default=default_codex_home() / "sessions")
    parser.add_argument("--output-dir", type=Path, default=repo_root() / DEFAULT_OUTPUT_DIRNAME)
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--max-part-chars", type=int, default=MAX_PART_CHARS)
    parser.add_argument("--force", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    state_file = (args.state_file or (output_dir / "_sync_state.json")).resolve()
    state = load_json(state_file)

    exported_sessions = 0
    exported_parts = 0
    skipped_sessions = 0
    for session_path in iter_session_files(args.sessions_dir.resolve()):
        if not should_export(session_path, state, args.force):
            skipped_sessions += 1
            continue
        part_count = export_session(session_path, output_dir, args.max_part_chars)
        update_state_for(session_path, state, part_count)
        if part_count:
            exported_sessions += 1
            exported_parts += part_count

    state["last_sync_at"] = utc_now_iso()
    state["sessions_dir"] = str(args.sessions_dir.resolve())
    state["output_dir"] = str(output_dir)
    write_json(state_file, state)

    print(
        json.dumps(
            {
                "sessions_dir": str(args.sessions_dir.resolve()),
                "output_dir": str(output_dir),
                "state_file": str(state_file),
                "exported_sessions": exported_sessions,
                "exported_parts": exported_parts,
                "skipped_sessions": skipped_sessions,
                "last_sync_at": state["last_sync_at"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
