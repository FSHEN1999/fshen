from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CODEX_HOME = Path.home() / ".codex"
CONFIG_PATH = CODEX_HOME / "config.toml"

SECTION_ORDER = [
    "mcp_servers.filesystem_dpu",
    "mcp_servers.git_dpu",
    "mcp_servers.git_dpu.env",
    "mcp_servers.fetch",
    "mcp_servers.fetch.env",
    "mcp_servers.local_rag_dpu",
    "mcp_servers.local_rag_dpu.env",
]


def toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def toml_list(values: list[str]) -> str:
    return "[" + ", ".join(toml_string(value) for value in values) + "]"


def build_section_map(repo_root: Path) -> dict[str, str]:
    rag_python = repo_root / ".rag_mvp" / "venv" / "Scripts" / "python.exe"
    rag_db = repo_root / ".rag_mvp" / "rag.db"
    repo = str(repo_root)
    rag_python_str = str(rag_python)
    rag_db_str = str(rag_db)

    return {
        "mcp_servers.filesystem_dpu": "\n".join(
            [
                "[mcp_servers.filesystem_dpu]",
                f"command = {toml_string('npx')}",
                f"args = {toml_list(['-y', '@modelcontextprotocol/server-filesystem', repo])}",
            ]
        ),
        "mcp_servers.git_dpu": "\n".join(
            [
                "[mcp_servers.git_dpu]",
                f"command = {toml_string(rag_python_str)}",
                f"args = {toml_list(['-m', 'mcp_server_git', '--repository', repo])}",
            ]
        ),
        "mcp_servers.git_dpu.env": "\n".join(
            [
                "[mcp_servers.git_dpu.env]",
                f"PYTHONIOENCODING = {toml_string('utf-8')}",
            ]
        ),
        "mcp_servers.fetch": "\n".join(
            [
                "[mcp_servers.fetch]",
                f"command = {toml_string(rag_python_str)}",
                f"args = {toml_list(['-m', 'mcp_server_fetch'])}",
            ]
        ),
        "mcp_servers.fetch.env": "\n".join(
            [
                "[mcp_servers.fetch.env]",
                f"PYTHONIOENCODING = {toml_string('utf-8')}",
            ]
        ),
        "mcp_servers.local_rag_dpu": "\n".join(
            [
                "[mcp_servers.local_rag_dpu]",
                f"command = {toml_string(rag_python_str)}",
                f"args = {toml_list(['-m', 'dpu_rag_mvp.mcp_server'])}",
            ]
        ),
        "mcp_servers.local_rag_dpu.env": "\n".join(
            [
                "[mcp_servers.local_rag_dpu.env]",
                f"LOCAL_RAG_HOME = {toml_string(repo)}",
                f"LOCAL_RAG_DB = {toml_string(rag_db_str)}",
                f"PYTHONIOENCODING = {toml_string('utf-8')}",
            ]
        ),
    }


def strip_section(text: str, section_name: str) -> str:
    pattern = re.compile(
        rf"(?:^|\n)\[{re.escape(section_name)}\]\n.*?(?=(?:\n\[[^\n]+\]\n)|\Z)",
        re.S,
    )
    return re.sub(pattern, "\n", text)


def main() -> int:
    if not CONFIG_PATH.exists():
        raise SystemExit(f"Codex config not found: {CONFIG_PATH}")

    original = CONFIG_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
    cleaned = original
    for section in SECTION_ORDER:
        cleaned = strip_section(cleaned, section)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).rstrip() + "\n"

    sections = build_section_map(REPO_ROOT)
    payload = "\n\n".join(sections[name] for name in SECTION_ORDER)

    feature_marker = "\n[features]"
    marker_index = cleaned.find(feature_marker)
    if marker_index >= 0:
        before = cleaned[:marker_index].rstrip()
        after = cleaned[marker_index:].lstrip("\n")
        updated = f"{before}\n\n{payload}\n\n{after}"
    else:
        updated = f"{cleaned.rstrip()}\n\n{payload}\n"

    updated = updated.replace("\r\n", "\n")
    if updated == original:
        print(f"No changes needed in {CONFIG_PATH}")
        return 0

    backup_path = CONFIG_PATH.with_name(
        f"{CONFIG_PATH.name}.bak_{datetime.now():%Y%m%d_%H%M%S}"
    )
    shutil.copy2(CONFIG_PATH, backup_path)
    CONFIG_PATH.write_text(updated, encoding="utf-8", newline="\n")

    print(f"Updated {CONFIG_PATH}")
    print(f"Backup: {backup_path}")
    print("Configured sections:")
    for section in SECTION_ORDER:
        print(f"- {section}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
