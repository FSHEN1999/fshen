# -*- coding: utf-8 -*-
"""AI assistant service for DPU mockapi."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv

from mock_sit import DatabaseExecutor
from web.services.dpu_knowledge import DPU_KNOWLEDGE_SUMMARY
from web.services.mock_adapter import WebDPUMockService
from web.services.session_manager import session_manager


DEFAULT_QWEN_BASE_URL = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
DEFAULT_QWEN_MODEL = "qwen3.6-plus"


@dataclass(frozen=True)
class QwenConfig:
    base_url: str
    api_key: str
    model: str
    timeout: int = 60
    temperature: float = 0.2


def load_qwen_config() -> QwenConfig:
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=True)
    return QwenConfig(
        base_url=os.getenv("QWEN_BASE_URL", DEFAULT_QWEN_BASE_URL).rstrip("/"),
        api_key=os.getenv("QWEN_API_KEY", "").strip(),
        model=os.getenv("QWEN_MODEL", DEFAULT_QWEN_MODEL).strip() or DEFAULT_QWEN_MODEL,
        timeout=int(os.getenv("QWEN_TIMEOUT", "60")),
        temperature=float(os.getenv("QWEN_TEMPERATURE", "0.2")),
    )


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _trim_text(value: Any, limit: int = 260) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _normalize_history(messages: list[dict[str, Any]], limit: int = 12) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in messages[-limit:]:
        role = item.get("role", "user")
        content = item.get("content", "")
        if role not in {"user", "assistant", "tool"}:
            continue
        normalized.append({"role": role, "content": _trim_text(content, 1200)})
    return normalized


def _compact_json(value: Any, limit: int = 2400) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, indent=2)
    except TypeError:
        text = _trim_text(value, limit)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _extract_json_payload(text: str) -> dict[str, Any]:
    raw = text.strip()
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.S)
    if fenced:
        try:
            payload = json.loads(fenced.group(1))
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass

    first = raw.find("{")
    last = raw.rfind("}")
    if first != -1 and last != -1 and last > first:
        candidate = raw[first : last + 1]
        try:
            payload = json.loads(candidate)
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass

    raise ValueError("Model output is not valid JSON")


def _safe_sql(sql: str) -> str:
    statement = sql.strip()
    return statement[:-1].rstrip() if statement.endswith(";") else statement


def _is_write_sql(sql: str) -> bool:
    prefix = sql.lstrip().lower()
    return not prefix.startswith(("select", "show", "describe", "desc", "explain", "with"))


def _is_direct_sql(message: str) -> bool:
    statement = _safe_sql(message)
    return bool(re.match(r"^\s*(select|show|describe|desc|explain|with|update|insert|delete)\b", statement, flags=re.I))


def _extract_phone_number(message: str) -> Optional[str]:
    match = re.search(r"\b(\d{8}|\d{11})\b", message)
    return match.group(1) if match else None


def _is_lookup_merchant_request(message: str) -> bool:
    text = _normalize_text(message)
    return (
        "merchant id" in text
        or "merchant_id" in text
        or ("merchant" in text and "phone" in text)
        or ("\u5546\u6237" in message and ("id" in text or "\u624b\u673a" in message))
    )


def _is_greeting_request(message: str) -> bool:
    text = _normalize_text(message)
    greetings = (
        "hello",
        "hi",
        "hey",
        "你好",
        "您好",
        "嗨",
        "在吗",
        "在不在",
        "早上好",
        "上午好",
        "下午好",
        "晚上好",
        "thanks",
        "thank you",
        "谢谢",
        "多谢",
    )
    return len(text) <= 20 and any(token.lower() in text for token in greetings if token.isascii()) or any(
        token in message for token in greetings if not token.isascii()
    )


def _extract_account_creation_slots(message: str) -> dict[str, Any]:
    text = _normalize_text(message)
    slots: dict[str, Any] = {}

    if any(token in text for token in ("200k", "tier 1", "tier1", "\u4e00\u6863")):
        slots["journey"] = "200K"
    elif any(token in text for token in ("500k", "tier 2", "tier2", "\u4e8c\u6863")):
        slots["journey"] = "500K"
    elif any(token in text for token in ("2000k", "2,000k", "tier 3", "tier3", "\u4e09\u6863")):
        slots["journey"] = "2000K"

    if "usd" in text or "\u7f8e\u5143" in message:
        slots["currency"] = "USD"
    elif "cny" in text or "rmb" in text or "\u4eba\u6c11\u5e01" in message:
        slots["currency"] = "CNY"

    if any(token in text for token in ("offline", "\u7ebf\u4e0b", "\u79bb\u7ebf")):
        slots["offline"] = True
    elif any(token in text for token in ("online", "\u7ebf\u4e0a")):
        slots["offline"] = False

    if any(token in text for token in ("funder", "lender", "fundpark", "hsbc", "\u8d44\u65b9", "\u653e\u6b3e\u65b9", "\u8d37\u65b9")):
        slots["funder"] = "mentioned"

    return slots


def _account_creation_missing_fields(slots: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if "journey" not in slots:
        missing.append("旅程")
    if "currency" not in slots:
        missing.append("币种")
    if "funder" not in slots:
        missing.append("资方")
    if "offline" not in slots:
        missing.append("线上还是线下")
    return missing


def _merge_register_args(model_args: dict[str, Any], account_slots: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    merged = dict(model_args or {})
    merged["env"] = context.get("selected_env") or merged.get("env") or "uat"
    merged["journey"] = account_slots.get("journey") or merged.get("journey") or context.get("selected_journey") or "500K"
    merged["currency"] = account_slots.get("currency") or merged.get("currency") or context.get("selected_currency") or "USD"
    if "offline" in account_slots:
        merged["offline"] = account_slots["offline"]
    elif "offline" not in merged:
        merged["offline"] = True
    return merged


class ToolExecutor:
    def __init__(self, context: dict[str, Any] | None = None):
        self.context = context or {}

    def resolve_env(self, payload: dict[str, Any] | None = None) -> str:
        payload = payload or {}
        selected_env = self.context.get("selected_env")
        if selected_env:
            return str(selected_env).lower()
        for key in ("env", "environment"):
            value = payload.get(key)
            if value:
                return str(value).lower()
        session = self.context.get("session") or {}
        session_env = session.get("env")
        if session_env:
            return str(session_env).lower()
        return "uat"

    def resolve_session_id(self, payload: dict[str, Any] | None = None) -> Optional[str]:
        payload = payload or {}
        if payload.get("session_id"):
            return str(payload["session_id"])
        session = self.context.get("session") or {}
        if session.get("session_id"):
            return str(session["session_id"])
        active_session_id = self.context.get("active_session_id")
        if active_session_id:
            return str(active_session_id)
        return None

    def execute(self, tool_name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        handlers = {
            "register_account": self._register_account,
            "connect_session": self._connect_session,
            "mock_action": self._mock_action,
            "execute_sql": self._execute_sql,
            "lookup_merchant_by_phone": self._lookup_merchant_by_phone,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return {
                "success": False,
                "tool_name": tool_name,
                "error": f"Unsupported tool: {tool_name}",
                "supported_tools": sorted(handlers),
            }
        return handler(payload)

    def _lookup_merchant_by_phone(self, payload: dict[str, Any]) -> dict[str, Any]:
        phone_number = str(payload.get("phone_number") or "").strip()
        if not phone_number:
            return {"success": False, "tool_name": "lookup_merchant_by_phone", "error": "phone_number is required"}

        env = self.resolve_env(payload)
        sql = (
            "SELECT merchant_id "
            "FROM dpu_users "
            f"WHERE phone_number = '{phone_number}' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        try:
            with DatabaseExecutor(env=env) as db:
                merchant_id = db.execute_sql(sql)
            return {
                "success": True,
                "tool_name": "lookup_merchant_by_phone",
                "env": env,
                "phone_number": phone_number,
                "merchant_id": merchant_id,
                "sql": sql,
            }
        except Exception as exc:
            return {
                "success": False,
                "tool_name": "lookup_merchant_by_phone",
                "env": env,
                "phone_number": phone_number,
                "sql": sql,
                "error": str(exc),
            }

    def _register_account(self, payload: dict[str, Any]) -> dict[str, Any]:
        env = self.resolve_env(payload)
        journey = str(payload.get("journey") or self.context.get("selected_journey") or "500K")
        currency = str(payload.get("currency") or self.context.get("selected_currency") or "USD").upper()
        offline = bool(payload.get("offline", True if payload.get("mode") == "offline" else False))

        result = WebDPUMockService.register_new_account_web(
            env=env,
            journey=journey,
            currency=currency,
            offline=offline,
        )

        session_result = None
        if result.get("success") and result.get("phone_number"):
            try:
                ctx = session_manager.create_session(env, result["phone_number"])
                session_result = {
                    "session_id": ctx.session_id,
                    "env": ctx.env,
                    "phone_number": ctx.phone_number,
                    "merchant_id": ctx.merchant_id,
                    "preferred_currency": ctx.preferred_currency,
                }
            except Exception as exc:
                session_result = {"error": str(exc)}

        return {
            "success": bool(result.get("success")),
            "tool_name": "register_account",
            "env": env,
            "input": {"journey": journey, "currency": currency, "offline": offline},
            "session": session_result,
            "result": result,
        }

    def _connect_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        env = self.resolve_env(payload)
        phone_number = str(payload.get("phone_number") or "").strip()
        if not phone_number:
            return {"success": False, "tool_name": "connect_session", "error": "phone_number is required"}
        try:
            ctx = session_manager.create_session(env, phone_number)
            return {
                "success": True,
                "tool_name": "connect_session",
                "result": {
                    "session_id": ctx.session_id,
                    "env": ctx.env,
                    "phone_number": ctx.phone_number,
                    "merchant_id": ctx.merchant_id,
                    "preferred_currency": ctx.preferred_currency,
                },
            }
        except Exception as exc:
            return {"success": False, "tool_name": "connect_session", "error": str(exc)}

    def _mock_action(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = self.resolve_session_id(payload)
        action = str(payload.get("action") or "").strip()
        params = payload.get("params") or {}
        if not session_id:
            return {"success": False, "tool_name": "mock_action", "error": "session_id is required"}

        ctx = session_manager.get_session(session_id)
        if not ctx:
            return {"success": False, "tool_name": "mock_action", "error": f"session not found: {session_id}"}

        service = ctx.service
        action_map = {
            "link_sp_3pl": lambda: service.mock_link_sp_3pl_shop(),
            "underwritten": lambda: service.mock_underwritten_status(amount=params.get("amount"), status=params.get("status")),
            "approved_offer": lambda: service.mock_approved_offer_status(
                amount=params.get("amount"),
                status=params.get("status"),
                failure_reason_index=params.get("failure_reason_index"),
                rejection_reason=params.get("rejection_reason"),
            ),
            "psp_start": lambda: service.mock_psp_start_status(status=params.get("status")),
            "psp_completed": lambda: service.mock_psp_completed_status(status=params.get("status")),
            "esign": lambda: service.mock_esign_status(signed_amount=params.get("signed_amount"), status=params.get("status")),
            "drawdown": lambda: service.mock_drawdown_status(
                amount=params.get("amount"),
                status=params.get("status"),
                failure_reason_index=params.get("failure_reason_index"),
            ),
            "repayment_start": lambda: service.mock_repayment_start_status(
                principal_amount=params.get("principal_amount"),
                outstanding_amount=params.get("outstanding_amount"),
            ),
            "repayment": lambda: service.mock_repayment_status(
                principal_amount=params.get("principal_amount"),
                outstanding_amount=params.get("outstanding_amount"),
                status=params.get("status"),
                failure_reason_index=params.get("failure_reason_index"),
            ),
            "multi_shop_binding": lambda: service.mock_multi_shop_binding(state=params.get("state")),
            "sp_status_update": lambda: service.mock_sp_status_update(
                platform_seller_id=params.get("platform_seller_id"),
                status=params.get("status"),
                failure_reason_index=params.get("failure_reason_index"),
            ),
            "multi_shop_3pl_redirect": lambda: service.mock_multi_shop_3pl_redirect(),
            "system_event": lambda: service.mock_system_event_notification(
                event_type=params.get("event_type"),
                application_unique_id=params.get("application_unique_id"),
                error_code=params.get("error_code"),
            ),
            "psp_hsbc_start": lambda: service.mock_psp_start_status_hsbc(),
            "psp_hsbc_completed": lambda: service.mock_psp_completed_status_hsbc(result=params.get("result")),
        }
        handler = action_map.get(action)
        if not handler:
            return {
                "success": False,
                "tool_name": "mock_action",
                "error": f"Unsupported mock action: {action}",
                "supported_actions": sorted(action_map),
            }
        try:
            result = handler()
            return {
                "success": bool(result.get("success")),
                "tool_name": "mock_action",
                "action": action,
                "session_id": session_id,
                "env": ctx.env,
                "result": result,
            }
        except Exception as exc:
            return {
                "success": False,
                "tool_name": "mock_action",
                "action": action,
                "session_id": session_id,
                "error": str(exc),
            }

    def _execute_sql(self, payload: dict[str, Any]) -> dict[str, Any]:
        sql = _safe_sql(str(payload.get("sql") or "").strip())
        if not sql:
            return {"success": False, "tool_name": "execute_sql", "error": "sql is required"}

        env = self.resolve_env(payload)
        try:
            with DatabaseExecutor(env=env) as db:
                db.cursor.execute(sql)
                if _is_write_sql(sql):
                    return {
                        "success": True,
                        "tool_name": "execute_sql",
                        "env": env,
                        "statement_type": "write",
                        "affected_rows": db.cursor.rowcount,
                        "lastrowid": getattr(db.cursor, "lastrowid", None),
                        "sql": sql,
                    }
                columns = [desc[0] for desc in (db.cursor.description or [])]
                rows = db.cursor.fetchall()
                records = [dict(zip(columns, row)) for row in rows[:50]] if columns else []
                return {
                    "success": True,
                    "tool_name": "execute_sql",
                    "env": env,
                    "statement_type": "query",
                    "row_count": len(rows),
                    "rows": records,
                    "truncated": len(rows) > len(records),
                    "sql": sql,
                }
        except Exception as exc:
            return {"success": False, "tool_name": "execute_sql", "env": env, "sql": sql, "error": str(exc)}


class DPUAIService:
    def __init__(self):
        self.config = load_qwen_config()

    def chat(
        self,
        message: str,
        history: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        history = history or []
        context = context or {}

        if _is_direct_sql(message):
            tool_args = {"sql": message, "env": context.get("selected_env") or context.get("session", {}).get("env")}
            tool_result = ToolExecutor(context).execute("execute_sql", tool_args)
            reply = self._format_sql_result(tool_result)
            return {
                "success": True,
                "mode": "tool",
                "reply": reply,
                "tool_name": "execute_sql",
                "tool_args": tool_args,
                "tool_result": tool_result,
                "decision": {"mode": "tool", "tool": {"name": "execute_sql", "args": tool_args}},
            }

        if _is_greeting_request(message):
            return {
                "success": True,
                "mode": "answer",
                "reply": "你好，我是DPU助手。你可以直接问我 DPU、mock、SQL，或者让我帮你执行操作。",
                "decision": {"mode": "answer", "answer": "你好，我是DPU助手。你可以直接问我 DPU、mock、SQL，或者让我帮你执行操作。"},
            }

        phone_number = _extract_phone_number(message)
        if phone_number and _is_lookup_merchant_request(message):
            tool_result = ToolExecutor(context).execute("lookup_merchant_by_phone", {"phone_number": phone_number})
            if tool_result.get("success") and tool_result.get("merchant_id"):
                reply = f"{phone_number} 的 merchant id 是 {tool_result['merchant_id']}。"
            elif tool_result.get("success"):
                reply = f"在 {tool_result.get('env')} 环境里没有查到 {phone_number} 对应的 merchant id。"
            else:
                reply = f"查询失败：{tool_result.get('error')}"
            return {
                "success": True,
                "mode": "tool",
                "reply": reply,
                "tool_name": "lookup_merchant_by_phone",
                "tool_args": {"phone_number": phone_number},
                "tool_result": tool_result,
                "decision": {"mode": "tool", "tool": {"name": "lookup_merchant_by_phone", "args": {"phone_number": phone_number}}},
            }

        intent_text = _normalize_text(message)
        account_slots = _extract_account_creation_slots(message)
        if any(token in intent_text for token in ("create account", "create an account", "register account", "signup", "account", "\u521b\u5efa", "\u8d26\u53f7", "\u6ce8\u518c")):
            missing_fields = _account_creation_missing_fields(account_slots)
            if missing_fields:
                question = "要创建账号的话，请先告诉我" + "、".join(missing_fields) + "。"
                return {
                    "success": True,
                    "mode": "clarify",
                    "reply": question,
                    "missing_fields": missing_fields,
                    "detected_slots": account_slots,
                }

            tool_args = _merge_register_args({}, account_slots, context)
            if account_slots.get("funder"):
                tool_args["funder"] = "fundpark" if "fundpark" in intent_text else "hsbc" if "hsbc" in intent_text else "provided"
            tool_result = ToolExecutor(context).execute("register_account", tool_args)
            reply = self._summarize_register_result(tool_result, tool_args)
            return {
                "success": True,
                "mode": "tool",
                "reply": reply,
                "tool_name": "register_account",
                "tool_args": tool_args,
                "tool_result": tool_result,
                "decision": {"mode": "tool", "tool": {"name": "register_account", "args": tool_args}},
            }

        if not self.config.api_key:
            return {"success": False, "mode": "error", "reply": "QWEN_API_KEY is not configured."}

        decision_messages = self._build_decision_messages(message, history, context)
        decision_text = self._call_model(decision_messages, temperature=0.1)
        decision = self._parse_decision(decision_text)

        if decision.get("mode") != "tool":
            reply = str(decision.get("answer") or decision.get("reply") or decision_text).strip()
            return {
                "success": True,
                "mode": "answer",
                "reply": reply,
                "raw_model_output": decision_text,
                "decision": decision,
            }

        tool = decision.get("tool") or {}
        tool_name = str(tool.get("name") or "").strip()
        tool_args = tool.get("args") or {}
        if tool_name == "register_account":
            tool_args = _merge_register_args(tool_args, account_slots, context)

        executor = ToolExecutor(context)
        tool_result = executor.execute(tool_name, tool_args)
        summary = self._summarize_tool_result(message, context, decision, tool_result)
        return {
            "success": True,
            "mode": "tool",
            "reply": summary,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "tool_result": tool_result,
            "raw_model_output": decision_text,
            "decision": decision,
        }

    def _summarize_register_result(self, tool_result: dict[str, Any], tool_args: dict[str, Any]) -> str:
        if not tool_result.get("success"):
            return f"创建账号失败：{tool_result.get('result', {}).get('error') or tool_result.get('error') or '未知错误'}"

        result = tool_result.get("result") or {}
        session = tool_result.get("session") or {}
        funder = tool_args.get("funder")
        funder_text = f"（资方：{funder}）" if funder and funder not in {"provided"} else ""
        mode_text = "线下" if tool_args.get("offline") else "线上"
        return (
            "账号已成功创建。\n"
            f"- **环境**：{tool_result.get('env')}\n"
            f"- **手机号**：{result.get('phone_number')}\n"
            f"- **邮箱**：{result.get('email')}\n"
            f"- **旅程/额度**：{tool_args.get('journey')}\n"
            f"- **币种**：{tool_args.get('currency')}\n"
            f"- **模式**：{mode_text}{funder_text}\n"
            f"- **商户ID**：{session.get('merchant_id')}\n"
            f"- **会话ID**：{session.get('session_id')}\n\n"
            "账号已准备就绪，可继续后续业务操作。"
        )

    def _format_sql_result(self, tool_result: dict[str, Any]) -> str:
        env = tool_result.get("env") or "-"
        if not tool_result.get("success"):
            return f"SQL 执行失败（环境：{env}）：{tool_result.get('error') or '未知错误'}"

        if tool_result.get("statement_type") == "write":
            return (
                f"SQL 已执行完成（环境：{env}）。\n"
                f"- 影响行数：{tool_result.get('affected_rows')}\n"
                f"- lastrowid：{tool_result.get('lastrowid')}"
            )

        rows = tool_result.get("rows") or []
        row_count = tool_result.get("row_count", 0)
        if not rows:
            return f"SQL 查询完成（环境：{env}），共 0 行。"
        truncated = "结果已截断。" if tool_result.get("truncated") else ""
        return f"SQL 查询完成（环境：{env}），共 {row_count} 行，下面显示前 {len(rows)} 行。{truncated}"

    def _build_decision_messages(self, message: str, history: list[dict[str, Any]], context: dict[str, Any]) -> list[dict[str, str]]:
        context_summary = {
            "active_session": context.get("session") or context.get("session_summary"),
            "active_session_id": context.get("active_session_id"),
            "selected_env": context.get("selected_env"),
            "selected_register_env": context.get("selected_register_env"),
            "selected_currency": context.get("selected_currency"),
            "selected_journey": context.get("selected_journey"),
            "recent_logs": context.get("recent_logs", [])[:20],
            "recent_activities": context.get("recent_activities", [])[:12],
        }
        system_prompt = (
            "You are a DPU assistant that understands DPU and mockapi behavior. "
            "Use the provided project knowledge and do not guess known DPU facts. "
            "If the user selected an execution environment, always use it. "
            "For account creation, ask for journey, currency, funder, and online/offline mode when missing. "
            "If the user asks about merchant id by phone, use the fixed merchant lookup tool and never invent SQL table names. "
            "SQL write operations are allowed only when the user explicitly asks for SQL execution. "
            "Output strict JSON only."
        )
        tools_prompt = (
            "Available tools:\n"
            "1. register_account -> {env, journey, currency, offline}\n"
            "2. connect_session -> {env, phone_number}\n"
            "3. mock_action -> {session_id?, action, params}\n"
            "4. execute_sql -> {env?, session_id?, sql}\n"
            "5. lookup_merchant_by_phone -> {phone_number}\n"
            "If no tool is needed, return {\"mode\":\"answer\",\"answer\":\"...\"}.\n"
            "If a tool is needed, return {\"mode\":\"tool\",\"tool\":{\"name\":\"...\",\"args\":{...}}}.\n"
        )
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": DPU_KNOWLEDGE_SUMMARY},
            {"role": "system", "content": tools_prompt},
            {"role": "system", "content": f"Current UI context:\n{_compact_json(context_summary)}"},
        ]
        messages.extend(_normalize_history(history))
        messages.append({"role": "user", "content": message})
        return messages

    def _summarize_tool_result(self, message: str, context: dict[str, Any], decision: dict[str, Any], tool_result: dict[str, Any]) -> str:
        summarize_messages = [
            {
                "role": "system",
                "content": (
                    "You are a DPU assistant. Summarize the tool result for the user in concise Chinese. "
                    "If the tool failed, explain the reason and suggest the next step. "
                    "Do not output JSON."
                ),
            },
            {"role": "system", "content": DPU_KNOWLEDGE_SUMMARY},
            {"role": "system", "content": f"User context:\n{_compact_json(context, 2000)}"},
            {
                "role": "user",
                "content": f"User message: {message}\nDecision: {_compact_json(decision, 2000)}\nTool result: {_compact_json(tool_result, 4000)}",
            },
        ]
        try:
            return self._call_model(summarize_messages, temperature=0.2).strip()
        except Exception:
            if tool_result.get("success"):
                return f"工具已完成：{_compact_json(tool_result, 800)}"
            return f"工具失败：{_compact_json(tool_result, 800)}"

    def _parse_decision(self, text: str) -> dict[str, Any]:
        try:
            return _extract_json_payload(text)
        except Exception:
            return {"mode": "answer", "answer": text}

    def _call_model(self, messages: list[dict[str, str]], temperature: float) -> str:
        url = f"{self.config.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
        }
        response = requests.post(url, headers=headers, json=payload, timeout=self.config.timeout)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise ValueError("Qwen response missing choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if content is None:
            raise ValueError("Qwen response missing message content")
        return str(content)


def build_ai_context(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    session = payload.get("session") or payload.get("session_summary") or {}
    return {
        "active_session_id": payload.get("active_session_id") or session.get("session_id"),
        "session": session,
        "selected_env": payload.get("selected_env"),
        "selected_register_env": payload.get("selected_register_env"),
        "selected_currency": payload.get("selected_currency"),
        "preferred_currency": payload.get("preferred_currency"),
        "selected_journey": payload.get("selected_journey"),
        "recent_logs": payload.get("recent_logs", []),
        "recent_activities": payload.get("recent_activities", []),
    }
