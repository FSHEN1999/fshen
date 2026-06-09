# -*- coding: utf-8 -*-
"""会话管理器：管理数据库连接和 DDPUMockService 实例的生命周期"""
import time
import uuid
import threading
import logging
from typing import Dict, Optional
from dataclasses import dataclass, field

try:
    from web.services.log_capture import format_log_time
except ModuleNotFoundError:
    from mockapi.web.services.log_capture import format_log_time

log = logging.getLogger(__name__)

# 会话超时时间（秒），30 分钟无活动自动清理
SESSION_TIMEOUT = 1800
SNAPSHOT_REFRESH_INTERVAL = 10
SNAPSHOT_FAILURE_COOLDOWN = 60


@dataclass
class SessionContext:
    """单个会话上下文"""
    session_id: str
    env: str
    phone_number: str
    db_executor: object  # DatabaseExecutor 实例
    service: object  # WebDPUMockService 实例
    merchant_id: Optional[str] = None
    preferred_currency: str = "USD"
    application_unique_id: Optional[str] = None
    selected_application_unique_id: Optional[str] = None
    applications: list[dict] = field(default_factory=list)
    lender_code: Optional[str] = None
    application_status: Optional[str] = None
    snapshot_refresh_at: float = 0
    snapshot_failed_until: float = 0
    snapshot_error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    def touch(self):
        """更新最后活跃时间"""
        self.last_active = time.time()

    def is_expired(self) -> bool:
        """检查会话是否已过期"""
        return (time.time() - self.last_active) > SESSION_TIMEOUT


class SessionManager:
    """管理所有会话的生命周期"""

    def __init__(self):
        self._sessions: Dict[str, SessionContext] = {}
        self._lock = threading.Lock()

    def create_session(self, env: str, phone_number: str) -> SessionContext:
        """创建新会话：连接数据库 + 实例化 WebDPUMockService"""
        # 延迟导入避免循环引用
        import sys
        from pathlib import Path
        project_root = str(Path(__file__).parent.parent.parent)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        from mock_sit import DatabaseExecutor
        try:
            from web.services.mock_adapter import WebDPUMockService
        except ModuleNotFoundError:
            from mockapi.web.services.mock_adapter import WebDPUMockService

        session_id = str(uuid.uuid4())

        # 创建数据库连接
        db_executor = DatabaseExecutor(env=env)
        db_executor.connect()

        # 创建适配器实例
        service = WebDPUMockService(phone_number, db_executor)
        if not service.merchant_id:
            try:
                db_executor.close()
            except Exception:
                try:
                    db_executor.__exit__(None, None, None)
                except Exception:
                    pass
            raise LookupError(f"phone number not found: {phone_number}")
        ctx = SessionContext(
            session_id=session_id,
            env=env,
            phone_number=phone_number,
            db_executor=db_executor,
            service=service,
            merchant_id=service.merchant_id,
            preferred_currency=service.preferred_currency,
        )
        self._refresh_application_snapshot(ctx)

        with self._lock:
            self._sessions[session_id] = ctx

        log.info(f"创建会话: {session_id} | 环境={env} | 手机号={phone_number} | merchant_id={service.merchant_id}")
        return ctx

    @staticmethod
    def _sql_literal(value: Optional[str]) -> str:
        if value is None:
            return "NULL"
        return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"

    def _get_application_rows(self, ctx: SessionContext, *, force: bool = False) -> tuple[list[dict], bool]:
        if not ctx.merchant_id:
            ctx.snapshot_error = None
            ctx.snapshot_refresh_at = time.time()
            return [], False

        now = time.time()
        if not force:
            if ctx.snapshot_failed_until and now < ctx.snapshot_failed_until:
                return ctx.applications, True
            if ctx.snapshot_refresh_at and now - ctx.snapshot_refresh_at < SNAPSHOT_REFRESH_INTERVAL:
                return ctx.applications, False

        try:
            rows = ctx.db_executor.execute_query_all(f"""
                SELECT application_unique_id, finance_product_currency, lender_code, application_status, created_at, updated_at
                FROM dpu_application
                WHERE merchant_id = {self._sql_literal(ctx.merchant_id)}
                ORDER BY created_at DESC
            """, retry=1)
            ctx.snapshot_error = None
            ctx.snapshot_failed_until = 0
            ctx.snapshot_refresh_at = now
            if isinstance(rows, dict):
                return [rows], False
            return rows or [], False
        except Exception as exc:
            ctx.snapshot_error = str(exc)
            ctx.snapshot_failed_until = now + SNAPSHOT_FAILURE_COOLDOWN
            ctx.snapshot_refresh_at = now
            log.debug(
                "Application snapshot refresh paused | session_id=%s | merchant_id=%s | retry_after=%ss | %s",
                ctx.session_id,
                ctx.merchant_id,
                SNAPSHOT_FAILURE_COOLDOWN,
                exc,
            )
            return ctx.applications, True

    def _get_application_rows_for_merchant(self, db_executor: object, merchant_id: Optional[str]) -> list[dict]:
        if not merchant_id:
            return []
        try:
            rows = db_executor.execute_query_all(f"""
                SELECT application_unique_id, finance_product_currency, lender_code, application_status, created_at, updated_at
                FROM dpu_application
                WHERE merchant_id = {self._sql_literal(merchant_id)}
                ORDER BY created_at DESC
            """)
            if isinstance(rows, dict):
                return [rows]
            return rows or []
        except Exception as exc:
            log.warning(f"Query application list failed | merchant_id={merchant_id} | {exc}")
            return []

    def _refresh_application_snapshot(self, ctx: SessionContext) -> None:
        rows, failed = self._get_application_rows(ctx)
        if failed:
            return
        ctx.applications = rows
        selected_id = ctx.selected_application_unique_id
        if selected_id and not any(row.get("application_unique_id") == selected_id for row in rows):
            selected_id = None
        snapshot = next(
            (row for row in rows if row.get("application_unique_id") == selected_id),
            rows[0] if rows else {},
        )
        ctx.application_unique_id = snapshot.get("application_unique_id")
        ctx.selected_application_unique_id = ctx.application_unique_id
        application_currency = snapshot.get("finance_product_currency")
        ctx.lender_code = snapshot.get("lender_code")
        ctx.application_status = snapshot.get("application_status")
        try:
            if not ctx.application_unique_id:
                ctx.application_unique_id = ctx.service.application_unique_id
                ctx.selected_application_unique_id = ctx.application_unique_id
            if hasattr(ctx.service, "select_application"):
                ctx.service.select_application(ctx.selected_application_unique_id)
            if application_currency:
                ctx.preferred_currency = application_currency
                if hasattr(ctx.service, "preferred_currency"):
                    ctx.service.preferred_currency = application_currency
            else:
                ctx.preferred_currency = ctx.service.preferred_currency
        except Exception as exc:
            log.warning(f"Refresh session snapshot failed | session_id={ctx.session_id} | {exc}")

    def select_application(self, session_id: str, application_unique_id: str) -> SessionContext:
        ctx = self.get_session(session_id)
        if not ctx:
            raise KeyError("session not found")

        rows, failed = self._get_application_rows(ctx, force=True)
        if failed:
            raise RuntimeError(f"application list refresh failed: {ctx.snapshot_error}")
        if not any(row.get("application_unique_id") == application_unique_id for row in rows):
            raise ValueError(f"application_unique_id not found in current session: {application_unique_id}")

        ctx.applications = rows
        ctx.selected_application_unique_id = application_unique_id
        if hasattr(ctx.service, "select_application"):
            ctx.service.select_application(application_unique_id)
        self._refresh_application_snapshot(ctx)
        return ctx

    def serialize_session(self, ctx: SessionContext) -> dict:
        self._refresh_application_snapshot(ctx)
        return {
            "session_id": ctx.session_id,
            "env": ctx.env,
            "phone_number": ctx.phone_number,
            "merchant_id": ctx.merchant_id,
            "preferred_currency": ctx.preferred_currency,
            "application_unique_id": ctx.application_unique_id,
            "selected_application_unique_id": ctx.selected_application_unique_id,
            "applications": ctx.applications,
            "finance_product_currency": (
                next(
                    (
                        row.get("finance_product_currency")
                        for row in ctx.applications
                        if row.get("application_unique_id") == ctx.selected_application_unique_id
                    ),
                    None,
                )
                or ctx.preferred_currency
            ),
            "lender_code": ctx.lender_code,
            "application_status": ctx.application_status,
            "application_snapshot_error": ctx.snapshot_error,
            "application_snapshot_retry_at": (
                format_log_time(ctx.snapshot_failed_until)
                if ctx.snapshot_failed_until and time.time() < ctx.snapshot_failed_until
                else None
            ),
            "created_at": format_log_time(ctx.created_at),
            "last_active": format_log_time(ctx.last_active),
        }

    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """获取会话（自动刷新活跃时间）"""
        with self._lock:
            ctx = self._sessions.get(session_id)
        if ctx:
            if ctx.is_expired():
                log.warning(f"会话已过期: {session_id}")
                self.destroy_session(session_id)
                return None
            ctx.touch()
        return ctx

    def destroy_session(self, session_id: str) -> bool:
        """销毁会话：关闭数据库连接"""
        with self._lock:
            ctx = self._sessions.pop(session_id, None)
        if ctx:
            try:
                ctx.db_executor.close()
            except Exception:
                try:
                    ctx.db_executor.__exit__(None, None, None)
                except Exception:
                    pass
            log.info(f"销毁会话: {session_id}")
            return True
        return False

    def cleanup_expired(self):
        """清理所有过期会话"""
        with self._lock:
            expired_ids = [sid for sid, ctx in self._sessions.items() if ctx.is_expired()]
        for sid in expired_ids:
            self.destroy_session(sid)
        if expired_ids:
            log.info(f"清理过期会话: {len(expired_ids)} 个")

    def list_sessions(self) -> list:
        """列出所有活跃会话"""
        self.cleanup_expired()
        with self._lock:
            sessions = list(self._sessions.values())
        return [self.serialize_session(ctx) for ctx in sessions]

    def list_session(self, session_id: str) -> list:
        ctx = self.get_session(session_id)
        if not ctx:
            return []
        return [self.serialize_session(ctx)]


# 全局单例
session_manager = SessionManager()
