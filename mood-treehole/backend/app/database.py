"""Database connection and session helpers."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_sqlite()


def _migrate_sqlite() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "entries" not in table_names:
        return

    entry_columns = {column["name"] for column in inspector.get_columns("entries")}
    with engine.begin() as connection:
        if "conversation_id" not in entry_columns:
            connection.execute(text("ALTER TABLE entries ADD COLUMN conversation_id VARCHAR(64)"))
        if "is_farewell" not in entry_columns:
            connection.execute(text("ALTER TABLE entries ADD COLUMN is_farewell BOOLEAN NOT NULL DEFAULT 0"))

        legacy_entries = connection.execute(
            text(
                """
                SELECT id, user_id, visitor_id, created_at, updated_at
                FROM entries
                WHERE conversation_id IS NULL OR conversation_id = ''
                """
            )
        ).mappings()
        for row in legacy_entries:
            conversation_id = str(uuid4())
            created_at = row["created_at"]
            updated_at = row["updated_at"] or created_at
            connection.execute(
                text(
                    """
                    INSERT INTO conversations (
                        id, user_id, visitor_id, status, closed_reason, created_at, updated_at, closed_at
                    )
                    VALUES (
                        :id, :user_id, :visitor_id, 'active', NULL, :created_at, :updated_at, NULL
                    )
                    """
                ),
                {
                    "id": conversation_id,
                    "user_id": row["user_id"],
                    "visitor_id": row["visitor_id"],
                    "created_at": created_at,
                    "updated_at": updated_at,
                },
            )
            connection.execute(
                text("UPDATE entries SET conversation_id = :conversation_id WHERE id = :entry_id"),
                {"conversation_id": conversation_id, "entry_id": row["id"]},
            )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
