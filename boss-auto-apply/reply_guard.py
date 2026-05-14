import re
from candidate_profile import load_resume


MANUAL_CONTACT_PATTERNS = [
    r"\[?\s*微信号\s*\]?",
    r"微信\s*[:：]",
    r"微信同号",
    r"加.*微信",
    r"手机\s*\d",
    r"电话\s*\d",
    r"手机号",
    r"联系方式",
]


BLOCK_PATTERNS = [
    r"我是AI",
    r"作为AI",
    r"无法提供",
    r"不方便透露",
    r"随时都可以入职",
    r"保证",
    r"百分百",
    r"年薪百万",
]


def sanitize_reply(reply: str, *, intent: str = "", fallback: str = "") -> tuple[str, list[str]]:
    """Final safety pass before sending a message to HR."""
    text = " ".join((reply or "").strip().split())
    notes: list[str] = []
    if not text:
        return "", ["empty"]

    for pattern in MANUAL_CONTACT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            notes.append("manual_contact_info")
            return "", notes

    for pattern in BLOCK_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            notes.append(f"blocked:{pattern}")
            text = fallback or _fallback_for_intent(intent)
            break

    if len(text) > 180:
        notes.append("trimmed")
        text = text[:177].rstrip("，。；、 ") + "。"

    if text.count("\n") >= 2 or text.count("：") >= 2 or text.count(":") >= 2:
        notes.append("too_structured")
        first_sentence = re.split(r"[。！？!?]", text, maxsplit=1)[0].strip()
        text = (first_sentence or text[:60]).strip("，,；; ") + "。"

    question_marks = text.count("？") + text.count("?")
    if question_marks >= 2:
        notes.append("too_many_questions")
        parts = re.split(r"[？?]", text)
        text = (parts[0] + "。").strip()

    if intent in {"ask_salary", "ask_available", "ask_contact", "ask_resume"} and "方便聊" in text:
        notes.append("removed_generic_chat_prompt")
        text = text.replace("方便聊聊吗", "").replace("方便聊下吗", "").replace("方便聊", "").strip("，。 ")
        if text:
            text += "。"

    return text, notes


def _fallback_for_intent(intent: str) -> str:
    if intent == "ask_salary":
        return "我的期望薪资在18-30K范围，具体可以结合岗位职责和福利面谈。"
    if intent == "ask_resume":
        return "好，简历发您。"
    if intent == "ask_contact":
        phone = load_resume().get("phone", "").strip()
        return f"手机{phone}，微信同号。" if phone else "电话和微信可以发您，稍后我补充联系方式。"
    if intent == "ask_available":
        return "我目前在职看机会，合适的话可以尽快推进面试。"
    return "收到，我这边是5年测试开发/测试负责人经验，主要看接口自动化、数据一致性和质量闭环方向。"
