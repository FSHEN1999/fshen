"""
Manual review tagging for HR conversations.

This module keeps risk labels out of chat_processor so new categories can be
added without scattering if/else blocks across the runtime flow.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ManualReviewDecision:
    required: bool = False
    tag: str = ""
    label: str = ""
    risk: str = "low"
    action: str = "AI可处理"
    note: str = ""
    ai_strategy_candidate: bool = False
    block_auto_reply: bool = False
    block_auto_actions: bool = False

    def as_extra(self) -> dict:
        return {
            "manual_review_required": self.required,
            "manual_review_tag": self.tag,
            "manual_review_label": self.label,
            "manual_review_risk": self.risk,
            "manual_review_action": self.action,
            "manual_review_note": self.note,
            "ai_strategy_candidate": self.ai_strategy_candidate,
        }


def assess_manual_review(intent: str, last_hr_text: str, confidence: str = "") -> ManualReviewDecision:
    text = last_hr_text or ""
    intent = intent or ""
    confidence = confidence or ""

    if _has_identity_info(text) or intent == "ask_identity_info":
        if _has_certificate_info(text) and not _has_identity_info(text):
            return ManualReviewDecision(
                required=True,
                tag="certificate_info",
                label="证书/学历材料",
                risk="high",
                action="人工回复",
                note="涉及毕业证、学位证、学信网截图或证书编号，先人工确认再决定是否提供。",
                block_auto_reply=True,
                block_auto_actions=True,
            )
        return ManualReviewDecision(
            required=True,
            tag="identity_info",
            label="身份证/证件",
            risk="high",
            action="人工回复",
            note="涉及身份证、证件号、实名信息或证件照片，禁止自动发送敏感信息。",
            block_auto_reply=True,
            block_auto_actions=True,
        )

    if _has_contact_exchange(text) or intent == "ask_contact":
        return ManualReviewDecision(
            required=True,
            tag="contact_exchange",
            label="联系方式",
            risk="medium",
            action="人工回复",
            note="HR索要电话、微信或其他联系方式时，不自动发送联系方式，交给人工确认。",
            block_auto_reply=True,
            block_auto_actions=True,
        )

    if _has_ai_suspicion(text) or intent == "ai_suspect":
        return ManualReviewDecision(
            required=True,
            tag="ai_suspect",
            label="疑似识别AI",
            risk="high",
            action="人工回复",
            note="HR已经怀疑在和AI沟通，暂停自动回复，改为人工接管。",
            block_auto_reply=True,
            block_auto_actions=True,
        )

    if intent == "unknown" and confidence == "low":
        return ManualReviewDecision(
            required=True,
            tag="unknown_low_confidence",
            label="低置信度",
            risk="medium",
            action="人工确认",
            note="意图识别不明确，先人工看一眼，避免自动回复偏题。",
            ai_strategy_candidate=True,
            block_auto_reply=True,
            block_auto_actions=True,
        )

    if intent == "interview_invite" or _has_interview_time(text):
        return ManualReviewDecision(
            required=False,
            tag="interview_time_confirm",
            label="面试时间确认",
            risk="medium",
            action="AI可回复-前端关注",
            note="涉及面试时间、地点或会议链接，AI可先回复，但需要在前端留痕方便人工确认。",
            ai_strategy_candidate=True,
        )

    if intent == "ask_salary" and _has_salary_sensitive(text):
        return ManualReviewDecision(
            required=False,
            tag="salary_sensitive",
            label="薪资敏感",
            risk="medium",
            action="AI可回复-策略优化",
            note="涉及薪资底线、当前薪资、压薪或薪资证明，建议后续沉淀更细回复策略。",
            ai_strategy_candidate=True,
        )

    if intent in {"ask_outsource", "od_outsource"} or _has_outsource_risk(text):
        return ManualReviewDecision(
            required=False,
            tag="outsource_risk",
            label="疑似外包/派遣",
            risk="medium",
            action="AI可回复-策略优化",
            note="涉及外包、外派、驻场、第三方合同或OD模式，前端标记便于复盘。",
            ai_strategy_candidate=True,
        )

    if intent in {"system_noise", "scam_recruit"}:
        return ManualReviewDecision(
            required=False,
            tag="scam_or_noise",
            label="诈骗/系统噪音",
            risk="low",
            action="自动静默",
            note="系统通知或明显非目标招聘，不进入人工主列表。",
        )

    return ManualReviewDecision()


def _has_identity_info(text: str) -> bool:
    return bool(re.search(
        r"身份证|身份证号|证件号|证件号码|身份信息|实名信息|身份证照片|身份证正反面|手持身份证|"
        r"id\s*card|national\s*id",
        text,
        re.IGNORECASE,
    ))


def _has_certificate_info(text: str) -> bool:
    return bool(re.search(
        r"毕业证编号|毕业证书编号|学位证编号|证书编号|证书照片|毕业证照片|学位证照片|"
        r"学信网截图|学历截图|学历证明|学历认证",
        text,
        re.IGNORECASE,
    ))


def _has_salary_sensitive(text: str) -> bool:
    return bool(re.search(
        r"最低.*薪|薪资.*底线|底薪|底线|当前薪资|现在薪资|薪资证明|流水|银行流水|"
        r"给不到|压薪|预算.*不够|预算有限|接受.*降薪|降薪",
        text,
        re.IGNORECASE,
    ))


def _has_interview_time(text: str) -> bool:
    return bool(re.search(
        r"面试|约面|视频面|电话面|线下面|到公司|会议链接|腾讯会议|飞书会议|"
        r"明天|今天|后天|周[一二三四五六日天]|上午|下午|晚上|\d{1,2}点",
        text,
        re.IGNORECASE,
    ))


def _has_outsource_risk(text: str) -> bool:
    return bool(re.search(
        r"外包|外派|驻场|人力外包|项目外包|派遣|劳务|第三方.*合同|第三方.*用工|OD岗位|OD模式",
        text,
        re.IGNORECASE,
    ))


def _has_contact_exchange(text: str) -> bool:
    return bool(re.search(
        r"微信|微信号|加微信|wx|WX|电话|手机号|联系方式|方便.*沟通|方便.*联系",
        text,
        re.IGNORECASE,
    ))


def _has_ai_suspicion(text: str) -> bool:
    return bool(re.search(
        r"AI|机器人|真人吗|你是真人吗|是不是AI|是不是机器人|太像AI|不像真人",
        text,
        re.IGNORECASE,
    ))
