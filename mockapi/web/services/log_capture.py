# -*- coding: utf-8 -*-
"""日志捕获器：拦截 Python logging 输出并通过 WebSocket 推送到前端"""
import asyncio
import logging
import time
from collections import defaultdict
from typing import Dict


class WebSocketLogHandler(logging.Handler):
    """自定义日志处理器：将日志条目发送到对应 session 的 WebSocket 队列"""

    def __init__(self):
        super().__init__()
        self.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(funcName)s:%(lineno)d %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        self._queues: Dict[str, asyncio.Queue] = {}
        self._loop: asyncio.AbstractEventLoop = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """设置事件循环引用（在 FastAPI startup 时调用）"""
        self._loop = loop

    def register_session(self, session_id: str) -> asyncio.Queue:
        """注册会话，返回日志队列"""
        queue = asyncio.Queue(maxsize=2000)
        self._queues[session_id] = queue
        return queue

    def unregister_session(self, session_id: str):
        """注销会话"""
        self._queues.pop(session_id, None)

    def emit(self, record: logging.LogRecord):
        """将日志记录放入所有活跃会话的队列（全局广播）"""
        msg = self.format(record)
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "message": record.getMessage(),
            "formatted": msg,
            "funcName": record.funcName,
            "lineno": record.lineno,
        }

        for session_id, queue in list(self._queues.items()):
            try:
                queue.put_nowait(log_entry)
            except asyncio.QueueFull:
                # 队列满时丢弃最旧的消息
                try:
                    queue.get_nowait()
                    queue.put_nowait(log_entry)
                except Exception:
                    pass


# 全局单例
ws_log_handler = WebSocketLogHandler()
