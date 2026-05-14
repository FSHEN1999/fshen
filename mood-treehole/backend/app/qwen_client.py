"""Qwen-compatible mood analysis client with local safety fallback."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import requests

from app.config import settings


RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
HIGH_RISK_PATTERNS = [
    "自杀",
    "轻生",
    "不想活",
    "活不下去",
    "结束生命",
    "伤害自己",
    "割腕",
    "跳楼",
    "杀了",
    "报复",
]
MEDIUM_RISK_PATTERNS = ["崩溃", "绝望", "抑郁", "失眠", "恐慌", "焦虑", "喘不过气"]


@dataclass
class MoodAnalysis:
    ai_reply: str
    summary: str
    emotion_label: str
    analysis_source: str
    risk_level: str
    risk_flags: list[str]


def local_risk_scan(content: str) -> tuple[str, list[str]]:
    flags: list[str] = []
    for keyword in HIGH_RISK_PATTERNS:
        if keyword in content:
            flags.append(f"high:{keyword}")
    if flags:
        return "high", flags

    for keyword in MEDIUM_RISK_PATTERNS:
        if keyword in content:
            flags.append(f"medium:{keyword}")
    if flags:
        return "medium", flags
    return "low", []


def fallback_analysis(content: str, mood: str) -> MoodAnalysis:
    local_level, flags = local_risk_scan(content)
    summary = content[:72] + ("..." if len(content) > 72 else "")
    if local_level == "high":
        reply = (
            "我先陪你停在这一刻。你现在承受的东西很重，但请不要一个人扛着。"
            "如果你可能伤害自己或别人，请立刻联系身边可信任的人，并拨打当地急救或报警电话。"
            "先把危险物品放远一点，走到有人在的地方，给自己争取接下来的十分钟。"
        )
    elif local_level == "medium":
        reply = (
            "我听见你真的很累。先不用急着把一切想明白，试着喝点水、把呼吸放慢，"
            "然后只挑一件最小的事去处理。你不是在失败，你是在撑过一个很难的时段。"
        )
    else:
        reply = (
            "谢谢你把这段心情放在这里。它不需要被立刻解决，也值得被认真看见。"
            "今晚可以先给自己一点空间，从一件很小、很具体的照顾开始。"
        )
    return MoodAnalysis(
        ai_reply=reply,
        summary=summary or "一段尚未命名的心情",
        emotion_label=mood,
        analysis_source="fallback",
        risk_level=local_level,
        risk_flags=flags,
    )


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end >= start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def _normalize_analysis(raw: dict, fallback: MoodAnalysis, content: str) -> MoodAnalysis:
    ai_reply = str(raw.get("ai_reply") or fallback.ai_reply).strip()
    summary = str(raw.get("summary") or fallback.summary).strip()[:120]
    emotion_label = str(raw.get("emotion_label") or fallback.emotion_label).strip()[:32]
    risk_level = str(raw.get("risk_level") or fallback.risk_level).strip().lower()
    if risk_level not in RISK_ORDER:
        risk_level = fallback.risk_level

    model_flags = raw.get("risk_flags") or []
    if isinstance(model_flags, str):
        model_flags = [model_flags]
    risk_flags = [str(item)[:64] for item in model_flags if str(item).strip()]

    local_level, local_flags = local_risk_scan(content)
    if RISK_ORDER[local_level] > RISK_ORDER[risk_level]:
        risk_level = local_level
    risk_flags = list(dict.fromkeys(risk_flags + local_flags))

    return MoodAnalysis(
        ai_reply=ai_reply[:1200] or fallback.ai_reply,
        summary=summary or fallback.summary,
        emotion_label=emotion_label or fallback.emotion_label,
        analysis_source="qwen",
        risk_level=risk_level,
        risk_flags=risk_flags,
    )


class QwenMoodAnalyzer:
    def analyze(self, content: str, mood: str) -> MoodAnalysis:
        fallback = fallback_analysis(content, mood)
        if not settings.qwen_api_key:
            return fallback

        endpoint = f"{settings.qwen_base_url.rstrip('/')}/chat/completions"
        system_prompt = (
            "你是一个中文心情树洞的支持性回复助手。"
            "请只输出 JSON，不要输出 Markdown。"
            "字段必须包含 ai_reply, summary, emotion_label, risk_level, risk_flags。"
            "risk_level 只能是 low, medium, high。"
            "如果内容涉及自伤、伤害他人、急性危机，risk_level 必须是 high，回复要温和、直接、鼓励立刻寻求现实帮助。"
            "不要做诊断，不要承诺替代专业帮助。"
        )
        user_prompt = (
            f"用户选择的心情：{mood}\n"
            f"树洞内容：{content}\n"
            "请给出一段 80 到 180 字的中文安慰回复、一句 30 字内摘要、一个情绪标签和风险判断。"
        )
        payload = {
            "model": settings.qwen_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
        }
        headers = {
            "Authorization": f"Bearer {settings.qwen_api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                endpoint,
                headers=headers,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                timeout=settings.qwen_timeout_seconds,
            )
            response.raise_for_status()
            message = response.json()["choices"][0]["message"]["content"]
            return _normalize_analysis(_extract_json(message), fallback, content)
        except Exception:
            return fallback


qwen_analyzer = QwenMoodAnalyzer()
