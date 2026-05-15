from __future__ import annotations

import os
from pathlib import Path


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


PROJECT_ROOT = Path(os.environ.get("LOCAL_RAG_HOME", _default_project_root())).resolve()
DATA_DIR = PROJECT_ROOT / ".rag_mvp"
DB_PATH = Path(os.environ.get("LOCAL_RAG_DB", DATA_DIR / "rag.db")).resolve()
MEMORY_DB_PATH = Path(os.environ.get("LOCAL_RAG_MEMORY_DB", DATA_DIR / "memory.db")).resolve()
CODEX_SESSION_RAG_DIR = PROJECT_ROOT / "codex_sessions_rag"
TOPIC_PORTAL_DIRNAME = "dpu_topic_portals"
TOPIC_PORTAL_DIR = PROJECT_ROOT / TOPIC_PORTAL_DIRNAME

INDEX_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".ini",
    ".toml",
    ".yaml",
    ".yml",
    ".ps1",
    ".bat",
}
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".idea",
    ".claude",
    ".rag_mvp",
    "codex_sessions_rag",
    "node_modules",
    ".vite",
}
MAX_TEXT_FILE_BYTES = 1_500_000
CHUNK_SIZE = 1400
CHUNK_OVERLAP = 200
AUTOMATION_NAME_HINTS = (
    "mock",
    "mockapi",
    "migration_test",
    "migration",
    "offerid",
    "rollback",
    "register",
    "run",
    "signup",
    "psp",
    "drawdown",
    "repayment",
    "metersphere",
    "webhook",
    "locator",
)
