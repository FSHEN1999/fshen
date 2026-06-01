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

        ctx = SessionContext(
            session_id=session_id,
            env=env,
            phone_number=phone_number,
            db_executor=db_executor,
            service=service,
            merchant_id=service.merchant_id,
            preferred_currency=service.preferred_currency,
        )

        with self._lock:
            self._sessions[session_id] = ctx

        log.info(f"创建会话: {session_id} | 环境={env} | 手机号={phone_number} | merchant_id={service.merchant_id}")
        return ctx

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
        with self._lock:
            return [
                {
                    "session_id": ctx.session_id,
                    "env": ctx.env,
                    "phone_number": ctx.phone_number,
                    "merchant_id": ctx.merchant_id,
                    "created_at": format_log_time(ctx.created_at),
                    "last_active": format_log_time(ctx.last_active),
                }
                for ctx in self._sessions.values()
            ]


# 全局单例
session_manager = SessionManager()
