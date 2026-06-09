# -*- coding: utf-8 -*-
"""PostgreSQL-backed user/session/operation audit storage."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

log = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = "postgresql://mockapi:mockapi@127.0.0.1:54329/mockapi"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"


class AuditStore:
    def __init__(self) -> None:
        self.database_url = os.getenv("MOCKAPI_DATABASE_URL", DEFAULT_DATABASE_URL)
        self.enabled = os.getenv("MOCKAPI_AUDIT_ENABLED", "true").lower() != "false"

    @contextmanager
    def connect(self):
        conn = psycopg.connect(self.database_url, row_factory=dict_row)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        if not self.enabled:
            return
        try:
            with self.connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app_users (
                        id BIGSERIAL PRIMARY KEY,
                        username TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        last_login_at TIMESTAMPTZ
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        id BIGSERIAL PRIMARY KEY,
                        session_id UUID NOT NULL UNIQUE,
                        username TEXT NOT NULL REFERENCES app_users(username),
                        env TEXT NOT NULL,
                        phone_number TEXT NOT NULL,
                        merchant_id TEXT,
                        application_unique_id TEXT,
                        selected_application_unique_id TEXT,
                        session_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                        connected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        disconnected_at TIMESTAMPTZ
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_operations (
                        id BIGSERIAL PRIMARY KEY,
                        session_id UUID,
                        username TEXT REFERENCES app_users(username),
                        env TEXT,
                        phone_number TEXT,
                        merchant_id TEXT,
                        operation_name TEXT NOT NULL,
                        request_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                        response_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                        success BOOLEAN,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS contact_issues (
                        id BIGSERIAL PRIMARY KEY,
                        created_by TEXT REFERENCES app_users(username),
                        issue TEXT NOT NULL,
                        env TEXT,
                        phone_number TEXT,
                        session_id UUID,
                        merchant_id TEXT,
                        status TEXT NOT NULL DEFAULT '待回复',
                        reply TEXT,
                        replied_by TEXT REFERENCES app_users(username),
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        replied_at TIMESTAMPTZ,
                        deleted_at TIMESTAMPTZ
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_username ON user_sessions(username)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_phone ON user_sessions(phone_number)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_operations_session ON user_operations(session_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_operations_username ON user_operations(username)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_operations_created ON user_operations(created_at)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_contact_issues_status ON contact_issues(status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_contact_issues_created_by ON contact_issues(created_by)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_contact_issues_created ON contact_issues(created_at)")
                self.ensure_admin_user(conn)
            log.info("Mock API audit database schema ready")
        except Exception as exc:
            log.warning("Mock API audit database is unavailable: %s", exc)

    def ensure_admin_user(self, conn) -> None:
        row = conn.execute(
            "SELECT username FROM app_users WHERE username = %s",
            (ADMIN_USERNAME,),
        ).fetchone()
        if row:
            return
        conn.execute(
            """
            INSERT INTO app_users (username, password_hash, role)
            VALUES (%s, %s, 'admin')
            """,
            (ADMIN_USERNAME, self.hash_password(ADMIN_PASSWORD)),
        )

    def register_user(self, username: str, password: str) -> dict[str, Any]:
        username = username.strip()
        if username == ADMIN_USERNAME:
            raise ValueError("admin 为管理员账号，不能注册")
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT username FROM app_users WHERE username = %s",
                (username,),
            ).fetchone()
            if existing:
                raise ValueError("账号已存在，请返回登录")
            row = conn.execute(
                """
                INSERT INTO app_users (username, password_hash, role)
                VALUES (%s, %s, 'user')
                RETURNING username, role, created_at
                """,
                (username, self.hash_password(password)),
            ).fetchone()
        return dict(row)

    def authenticate_user(self, username: str, password: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT username, password_hash, role FROM app_users WHERE username = %s",
                (username,),
            ).fetchone()
            if not row or not self.verify_password(password, row["password_hash"]):
                return None
            conn.execute(
                "UPDATE app_users SET last_login_at = now() WHERE username = %s",
                (username,),
            )
        return {"username": row["username"], "role": row["role"]}

    def user_exists(self, username: str | None) -> bool:
        username = (username or "").strip()
        if not username:
            return False
        with self.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM app_users WHERE username = %s",
                (username,),
            ).fetchone()
        return bool(row)

    def record_session(self, username: str, session_data: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO user_sessions (
                    session_id, username, env, phone_number, merchant_id,
                    application_unique_id, selected_application_unique_id, session_payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (session_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    env = EXCLUDED.env,
                    phone_number = EXCLUDED.phone_number,
                    merchant_id = EXCLUDED.merchant_id,
                    application_unique_id = EXCLUDED.application_unique_id,
                    selected_application_unique_id = EXCLUDED.selected_application_unique_id,
                    session_payload = EXCLUDED.session_payload
                """,
                (
                    session_data.get("session_id"),
                    username,
                    session_data.get("env"),
                    session_data.get("phone_number"),
                    session_data.get("merchant_id"),
                    session_data.get("application_unique_id"),
                    session_data.get("selected_application_unique_id"),
                    self.json_dumps(session_data),
                ),
            )

    def mark_session_disconnected(self, session_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE user_sessions SET disconnected_at = now() WHERE session_id = %s",
                (session_id,),
            )

    def record_operation(
        self,
        *,
        username: str | None,
        session_data: dict[str, Any] | None,
        operation_name: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any],
        success: bool | None,
    ) -> None:
        username = (username or "").strip()
        if not username:
            raise ValueError("username is required for operation audit")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO user_operations (
                    session_id, username, env, phone_number, merchant_id,
                    operation_name, request_payload, response_payload, success
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                """,
                (
                    request_payload.get("session_id"),
                    username,
                    session_data.get("env") if session_data else None,
                    session_data.get("phone_number") if session_data else None,
                    session_data.get("merchant_id") if session_data else None,
                    operation_name,
                    self.json_dumps(request_payload),
                    self.json_dumps(response_payload),
                    success,
                ),
            )

    def create_contact_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """
                INSERT INTO contact_issues (
                    created_by, issue, env, phone_number, session_id, merchant_id
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, created_by, issue, env, phone_number, session_id, merchant_id,
                    status, reply, replied_by, created_at, replied_at
                """,
                (
                    payload.get("created_by"),
                    payload.get("issue"),
                    payload.get("env"),
                    payload.get("phone_number"),
                    payload.get("session_id") or None,
                    payload.get("merchant_id"),
                ),
            ).fetchone()
        return self.normalize_contact_issue(row)

    def list_contact_issues(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_by, issue, env, phone_number, session_id, merchant_id,
                    status, reply, replied_by, created_at, replied_at
                FROM contact_issues
                WHERE deleted_at IS NULL
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [self.normalize_contact_issue(row) for row in rows]

    def reply_contact_issue(self, issue_id: int, reply: str, replied_by: str | None) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                UPDATE contact_issues
                SET reply = %s,
                    replied_by = %s,
                    status = '已回复',
                    replied_at = now()
                WHERE id = %s AND deleted_at IS NULL
                RETURNING id, created_by, issue, env, phone_number, session_id, merchant_id,
                    status, reply, replied_by, created_at, replied_at
                """,
                (reply, replied_by, issue_id),
            ).fetchone()
        return self.normalize_contact_issue(row) if row else None

    def delete_contact_issue(self, issue_id: int) -> bool:
        with self.connect() as conn:
            result = conn.execute(
                """
                UPDATE contact_issues
                SET deleted_at = now()
                WHERE id = %s AND deleted_at IS NULL
                """,
                (issue_id,),
            )
        return result.rowcount > 0

    @staticmethod
    def normalize_contact_issue(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "created_by": row.get("created_by"),
            "issue": row.get("issue"),
            "env": row.get("env") or "-",
            "phone_number": row.get("phone_number") or "-",
            "session_id": str(row.get("session_id") or "-"),
            "merchant_id": row.get("merchant_id") or "-",
            "status": row.get("status") or "待回复",
            "reply": row.get("reply") or "",
            "replied_by": row.get("replied_by") or "",
            "created_at": row["created_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("created_at") else "",
            "replied_at": row["replied_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("replied_at") else "",
        }

    @staticmethod
    def hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
        return f"pbkdf2_sha256${salt}${digest.hex()}"

    @staticmethod
    def verify_password(password: str, encoded: str) -> bool:
        try:
            algorithm, salt, expected = encoded.split("$", 2)
            if algorithm != "pbkdf2_sha256":
                return False
            digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
            return hmac.compare_digest(digest.hex(), expected)
        except Exception:
            return False

    @staticmethod
    def json_dumps(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=str)


audit_store = AuditStore()
