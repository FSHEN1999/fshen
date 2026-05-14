"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


def _default_sqlite_url() -> str:
    return f"sqlite:///{(BASE_DIR / 'mood_treehole.db').as_posix()}"


def _split_origins(raw: str) -> list[str]:
    values = [item.strip() for item in raw.split(",") if item.strip()]
    defaults = [f"http://localhost:{port}" for port in range(5173, 5177)] + [
        f"http://127.0.0.1:{port}" for port in range(5173, 5177)
    ]
    merged = list(dict.fromkeys(values + defaults))
    return merged or defaults


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", _default_sqlite_url())
    cors_origins: list[str] = None
    qwen_base_url: str = os.getenv(
        "QWEN_BASE_URL",
        "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    )
    qwen_api_key: str = os.getenv("QWEN_API_KEY", "")
    qwen_model: str = os.getenv("QWEN_MODEL", "qwen3.6-plus")
    qwen_timeout_seconds: int = int(os.getenv("QWEN_TIMEOUT_SECONDS", "30"))
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "admin123456")
    session_hours: int = int(os.getenv("SESSION_HOURS", "168"))

    def __post_init__(self) -> None:
        if self.cors_origins is None:
            object.__setattr__(
                self,
                "cors_origins",
                _split_origins(os.getenv("CORS_ORIGINS", "")),
            )


settings = Settings()
