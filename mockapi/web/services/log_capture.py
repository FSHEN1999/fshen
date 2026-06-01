# -*- coding: utf-8 -*-
"""日志捕获器：拦截 Python logging 输出并通过 WebSocket 推送到前端"""
import asyncio
import json
import logging
import re
import threading
import time
from collections import deque
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional


LOG_TIMEZONE = timezone(timedelta(hours=8), "Asia/Shanghai")
DEDUP_WINDOW_SECONDS = 1.0
SEPARATOR_RE = re.compile(r"^[=\-_*#\s]{20,}$")
GROUP_START_RE = re.compile(r"^【(?P<title>.+?)】(?P<section>完整请求信息|完整响应信息|请求异常详细信息)")
GROUP_TIMEOUT_SECONDS = 8.0
GROUP_TERMINAL_KEYWORDS = (
    "成功",
    "失败",
    "异常",
    "error",
    "failed",
    "success",
)
COMPACT_WINDOW_SECONDS = 5.0
COMPACT_FUNCTIONS = {"mock_multi_shop_3pl_redirect"}
COMPACT_MESSAGE_PREFIXES = (
    "3PL POST",
    "【多店铺】SP绑定ID",
    "【多店铺】platform_offer_id",
    "【多店铺】3PL重定向URL",
)
LOW_VALUE_MESSAGES = (
    "数据库连接成功",
    "创建会话:",
)


def format_log_time(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, LOG_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")


class ShanghaiFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        dt = datetime.fromtimestamp(record.created, LOG_TIMEZONE)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat(timespec="seconds")


class WebSocketLogHandler(logging.Handler):
    """自定义日志处理器：将日志条目发送到对应 session 的 WebSocket 队列"""

    def __init__(self):
        super().__init__()
        self.setFormatter(ShanghaiFormatter(
            "[%(asctime)s] [%(levelname)s] %(funcName)s:%(lineno)d %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        self._queues: Dict[str, asyncio.Queue] = {}
        self._loop: asyncio.AbstractEventLoop = None
        self._history = deque(maxlen=5000)
        self._last_emit_key: Optional[tuple] = None
        self._last_emit_at = 0.0
        self._groups: Dict[tuple, dict] = {}
        self._compact_groups: Dict[tuple, dict] = {}
        self._persist_lock = threading.Lock()
        self._log_file = Path(__file__).resolve().parents[2] / "logs" / "mockapi-web.log.jsonl"

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
        message = record.getMessage()
        if self._should_skip(record, message) or self._is_duplicate(record, message):
            return
        if self._handle_grouped_log(record, message):
            return
        if self._handle_compact_log(record, message):
            return

        msg = self.format(record)
        log_entry = {
            "timestamp": format_log_time(record.created),
            "created": record.created,
            "timezone": "Asia/Shanghai",
            "level": record.levelname,
            "message": message,
            "formatted": msg,
            "funcName": record.funcName,
            "lineno": record.lineno,
            "logger": record.name,
        }
        self._publish(log_entry)

    def _publish(self, log_entry: dict):
        self._flush_stale_compact_groups()
        self._history.append(log_entry)
        self._append_to_file(log_entry)

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

    def _append_to_file(self, log_entry: dict):
        try:
            self._log_file.parent.mkdir(parents=True, exist_ok=True)
            with self._persist_lock:
                with self._log_file.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(log_entry, ensure_ascii=False, default=str) + "\n")
        except Exception:
            self.handleError(logging.LogRecord(
                name=__name__,
                level=logging.ERROR,
                pathname=__file__,
                lineno=0,
                msg="Failed to persist mockapi web log entry",
                args=(),
                exc_info=None,
            ))

    def _read_persisted_logs(self) -> list[dict]:
        if not self._log_file.exists():
            return []

        entries = []
        try:
            with self._persist_lock:
                with self._log_file.open("r", encoding="utf-8") as file:
                    for line in file:
                        text = line.strip()
                        if not text:
                            continue
                        try:
                            entry = json.loads(text)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(entry, dict):
                            entries.append(entry)
        except Exception:
            return []
        return entries

    @staticmethod
    def _entry_key(entry: dict) -> tuple:
        return (
            entry.get("created"),
            entry.get("logger"),
            entry.get("funcName"),
            entry.get("lineno"),
            entry.get("message"),
            entry.get("formatted"),
        )

    def _handle_grouped_log(self, record: logging.LogRecord, message: str) -> bool:
        """Coalesce verbose request/response blocks into one UI log entry."""
        key = (record.thread, record.name)
        text = (message or "").strip()
        start_match = GROUP_START_RE.match(text)
        group = self._groups.get(key)
        now = time.monotonic()

        if start_match:
            if group and group["title"] == start_match.group("title"):
                group["messages"].append(message)
                group["updated_at"] = now
                return True
            if group:
                self._flush_group(key)
            self._groups[key] = {
                "title": start_match.group("title"),
                "created": record.created,
                "updated_at": now,
                "logger": record.name,
                "funcName": record.funcName,
                "lineno": record.lineno,
                "level": record.levelname,
                "levelno": record.levelno,
                "messages": [message],
            }
            return True

        if not group:
            return False

        if now - group["updated_at"] > GROUP_TIMEOUT_SECONDS:
            self._flush_group(key)
            return False

        group["messages"].append(message)
        group["updated_at"] = now
        group["levelno"] = max(group["levelno"], record.levelno)
        group["level"] = logging.getLevelName(group["levelno"])

        if self._is_group_terminal(record, message):
            self._flush_group(key)
        return True

    def _flush_group(self, key: tuple):
        group = self._groups.pop(key, None)
        if not group:
            return

        message = self._format_group_message(group)
        created = group["created"]
        level = group["level"]
        log_entry = {
            "timestamp": format_log_time(created),
            "created": created,
            "timezone": "Asia/Shanghai",
            "level": level,
            "message": message,
            "formatted": f"[{format_log_time(created)}] [{level}] {group['funcName']}:{group['lineno']} {message}",
            "funcName": group["funcName"],
            "lineno": group["lineno"],
            "logger": group["logger"],
            "grouped": True,
            "groupTitle": group["title"],
            "groupSize": len(group["messages"]),
        }
        self._publish(log_entry)

    def _handle_compact_log(self, record: logging.LogRecord, message: str) -> bool:
        if not self._is_compactable_entry({
            "funcName": record.funcName,
            "message": message,
        }):
            return False

        key = (record.thread, record.name, record.funcName)
        now = time.monotonic()
        group = self._compact_groups.get(key)
        if group and now - group["updated_at"] > COMPACT_WINDOW_SECONDS:
            self._flush_compact_group(key)
            group = None

        if not group:
            group = {
                "title": self._compact_title(record.funcName),
                "created": record.created,
                "updated_at": now,
                "logger": record.name,
                "funcName": record.funcName,
                "lineno": record.lineno,
                "level": record.levelname,
                "levelno": record.levelno,
                "messages": [],
            }
            self._compact_groups[key] = group

        group["messages"].append(message)
        group["updated_at"] = now
        group["levelno"] = max(group["levelno"], record.levelno)
        group["level"] = logging.getLevelName(group["levelno"])
        if self._is_compact_terminal(record, message):
            self._flush_compact_group(key)
        return True

    def _flush_stale_compact_groups(self):
        now = time.monotonic()
        for key, group in list(self._compact_groups.items()):
            if now - group["updated_at"] > COMPACT_WINDOW_SECONDS:
                self._flush_compact_group(key)

    def _flush_compact_group(self, key: tuple):
        group = self._compact_groups.pop(key, None)
        if not group:
            return
        entry = self._build_compact_entry(group)
        self._history.append(entry)
        self._append_to_file(entry)

        for session_id, queue in list(self._queues.items()):
            try:
                queue.put_nowait(entry)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait(entry)
                except Exception:
                    pass

    def _build_compact_entry(self, group: dict) -> dict:
        created = group["created"]
        level = group["level"]
        message = self._format_compact_message(group)
        return {
            "timestamp": format_log_time(created),
            "created": created,
            "timezone": "Asia/Shanghai",
            "level": level,
            "message": message,
            "formatted": f"[{format_log_time(created)}] [{level}] {group['funcName']}:{group['lineno']} {message}",
            "funcName": group["funcName"],
            "lineno": group["lineno"],
            "logger": group["logger"],
            "grouped": True,
            "groupTitle": group["title"],
            "groupSize": len(group["messages"]),
            "compact": True,
        }

    @staticmethod
    def _format_group_message(group: dict) -> str:
        title = group["title"]
        lines = []
        for raw_message in group["messages"]:
            text = (raw_message or "").strip("\n")
            if not text:
                continue
            match = GROUP_START_RE.match(text.strip())
            if match:
                lines.append(f"【{title}】{match.group('section')}")
            else:
                lines.append(text)
        return "\n".join(lines)

    @staticmethod
    def _is_group_terminal(record: logging.LogRecord, message: str) -> bool:
        text = (message or "").strip().lower()
        if record.levelno >= logging.ERROR:
            return True
        if "完整响应信息" in text or "完整请求信息" in text:
            return False
        return any(keyword in text for keyword in GROUP_TERMINAL_KEYWORDS)

    @staticmethod
    def _should_skip(record: logging.LogRecord, message: str) -> bool:
        text = (message or "").strip()
        if not text:
            return True
        if bool(SEPARATOR_RE.fullmatch(text)):
            return True
        return WebSocketLogHandler._is_low_value_entry({
            "level": record.levelname,
            "message": text,
        })

    def _is_duplicate(self, record: logging.LogRecord, message: str) -> bool:
        key = (record.name, record.levelno, record.funcName, record.lineno, message)
        now = time.monotonic()
        if key == self._last_emit_key and (now - self._last_emit_at) <= DEDUP_WINDOW_SECONDS:
            return True
        self._last_emit_key = key
        self._last_emit_at = now
        return False

    @staticmethod
    def _is_low_value_entry(entry: dict) -> bool:
        level = str(entry.get("level", "")).upper()
        if level in {"ERROR", "CRITICAL", "WARNING"}:
            return False
        message = str(entry.get("message") or entry.get("formatted") or "").strip()
        return any(pattern in message for pattern in LOW_VALUE_MESSAGES)

    @staticmethod
    def _is_compactable_entry(entry: dict) -> bool:
        func_name = str(entry.get("funcName") or "")
        message = str(entry.get("message") or "")
        if func_name not in COMPACT_FUNCTIONS:
            return False
        return any(message.startswith(prefix) for prefix in COMPACT_MESSAGE_PREFIXES)

    @staticmethod
    def _is_compact_terminal(record: logging.LogRecord, message: str) -> bool:
        if record.levelno >= logging.ERROR:
            return True
        return message.startswith("3PL POST response") or message.startswith("3PL POST failed")

    @staticmethod
    def _compact_title(func_name: str) -> str:
        if func_name == "mock_multi_shop_3pl_redirect":
            return "多店铺 3PL 重定向"
        return func_name

    @staticmethod
    def _format_compact_message(group: dict) -> str:
        lines = []
        for raw_message in group["messages"]:
            text = (raw_message or "").strip()
            if not text:
                continue
            lines.append(text)
        return "\n".join(lines)

    def _compact_entries(self, entries: list[dict]) -> list[dict]:
        compacted = []
        group = None

        def flush_group():
            nonlocal group
            if group:
                compacted.append(self._build_compact_entry(group))
                group = None

        for entry in sorted(entries, key=lambda item: item.get("created", 0) or 0):
            if self._is_low_value_entry(entry):
                continue
            if entry.get("compact") or entry.get("grouped") or not self._is_compactable_entry(entry):
                flush_group()
                compacted.append(entry)
                continue

            created = entry.get("created", 0) or 0
            if (
                group
                and group["funcName"] == entry.get("funcName")
                and group["logger"] == entry.get("logger")
                and created - group["last_created"] <= COMPACT_WINDOW_SECONDS
            ):
                group["messages"].append(entry.get("message", ""))
                group["last_created"] = created
                group["levelno"] = max(group["levelno"], logging._nameToLevel.get(str(entry.get("level", "INFO")), logging.INFO))
                group["level"] = logging.getLevelName(group["levelno"])
            else:
                flush_group()
                level_name = str(entry.get("level", "INFO"))
                group = {
                    "title": self._compact_title(str(entry.get("funcName") or "")),
                    "created": created,
                    "last_created": created,
                    "logger": entry.get("logger", ""),
                    "funcName": entry.get("funcName", ""),
                    "lineno": entry.get("lineno", ""),
                    "level": level_name,
                    "levelno": logging._nameToLevel.get(level_name, logging.INFO),
                    "messages": [entry.get("message", "")],
                }
        flush_group()
        return compacted

    @staticmethod
    def _parse_time(value: Optional[str]) -> Optional[float]:
        if not value:
            return None
        normalized = value.strip().replace("T", " ")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                parsed = datetime.strptime(normalized[:19], fmt)
                return parsed.replace(tzinfo=LOG_TIMEZONE).timestamp()
            except ValueError:
                continue
        return None

    def query_logs(
        self,
        keyword: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 500,
    ) -> list[dict]:
        """Query retained logs by fuzzy keyword and optional time range."""
        self.flush_pending_groups()
        keyword_text = (keyword or "").strip().lower()
        start_ts = self._parse_time(start_time)
        end_ts = self._parse_time(end_time)
        session_text = (session_id or "").strip().lower()
        max_items = max(1, min(limit, 2000))

        results = []
        seen = set()
        combined = list(self._read_persisted_logs()) + list(self._history)
        unique_entries = []
        for entry in combined:
            entry_key = self._entry_key(entry)
            if entry_key in seen:
                continue
            seen.add(entry_key)
            unique_entries.append(entry)
        for entry in reversed(self._compact_entries(unique_entries)):
            created = entry.get("created", 0)
            haystack = f"{entry.get('formatted', '')}\n{entry.get('message', '')}".lower()
            if start_ts is not None and created < start_ts:
                continue
            if end_ts is not None and created > end_ts:
                continue
            if keyword_text and keyword_text not in haystack:
                continue
            if session_text and session_text not in haystack:
                continue
            results.append(dict(entry))
            if len(results) >= max_items:
                break
        return results

    def flush_pending_groups(self):
        for key in list(self._groups.keys()):
            self._flush_group(key)
        for key in list(self._compact_groups.keys()):
            self._flush_compact_group(key)


# 全局单例
ws_log_handler = WebSocketLogHandler()
