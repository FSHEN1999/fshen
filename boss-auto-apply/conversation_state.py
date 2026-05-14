"""
对话状态机 —— 跟踪每个HR会话的阶段、时间戳、JD指纹，供跟进引擎和决策引擎使用。

设计原则:
  - 文件存储(data/chat_states.json)，简单可靠，无需DB
  - 幂等update，key=chat_id(或公司+HR名 hash)
  - 状态机驱动 followup_engine 和 reply_engine 决策

阶段:
  greeted            已打招呼发简历，等HR首复
  evaluating         HR已回复正在问问题(薪资/经验/项目等)
  contact_exchanged  已交换电话/微信
  interview_pending  HR提面试，等确定时间
  interview_scheduled已定面试时间
  dead               被拒/外包拒/静默超时
"""
from __future__ import annotations
import json, hashlib, os, time
try:
    import fcntl  # POSIX only
except ImportError:  # Windows
    fcntl = None
from pathlib import Path
from datetime import datetime
from typing import Optional
from file_ops import safe_write_json

STATE_FILE = Path(__file__).parent / "data" / "chat_states.json"
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

STAGES = (
    "greeted", "evaluating", "contact_exchanged",
    "interview_pending", "interview_scheduled", "dead",
)

# 意图→目标阶段映射 (优先级最高的阶段覆盖)
INTENT_TO_STAGE = {
    "greeting": "greeted",
    "ask_resume": "greeted",
    "ask_salary": "evaluating",
    "ask_experience": "evaluating",
    "ask_skills": "evaluating",
    "ask_education": "evaluating",
    "ask_project": "evaluating",
    "ask_tech_detail": "evaluating",
    "ask_available": "evaluating",
    "ask_location": "evaluating",
    "ask_outsource": "evaluating",
    "ask_age": "evaluating",
    "ask_overtime": "evaluating",
    "ask_identity_info": "evaluating",
    "ask_contact": "contact_exchanged",
    "interview_invite": "interview_pending",
    "rejection": "dead",
    "scam_recruit": "dead",
    "system_noise": "dead",
}

# 阶段优先级（高→低），高阶段不被低阶段覆盖
STAGE_RANK = {
    "dead": 0,
    "greeted": 1,
    "evaluating": 2,
    "contact_exchanged": 3,
    "interview_pending": 4,
    "interview_scheduled": 5,
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    # Keep a best-effort flock on POSIX, then rely on retrying replace for Windows readers.
    if os.name != "nt" and fcntl is not None:
        tmp = STATE_FILE.with_name(f"{STATE_FILE.name}.{os.getpid()}.lock.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX)
            except Exception:
                pass
            json.dump(data, f, ensure_ascii=False, indent=2)
        try:
            os.replace(tmp, STATE_FILE)
            return
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
    safe_write_json(STATE_FILE, data)


def chat_key(company: str, hr_name: str = "", job_title: str = "") -> str:
    """稳定key：公司+HR名+岗位，hash防特殊字符"""
    raw = f"{(company or '').strip()}|{(hr_name or '').strip()}|{(job_title or '').strip()}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


def get_state(key: str) -> Optional[dict]:
    return _load().get(key)


def update_state(
    key: str,
    *,
    company: str = "",
    hr_name: str = "",
    job_title: str = "",
    stage: Optional[str] = None,
    intent: Optional[str] = None,
    last_hr_text: Optional[str] = None,
    my_last_reply: Optional[str] = None,
    jd_hash: Optional[str] = None,
    extra: Optional[dict] = None,
) -> dict:
    """更新单个会话状态；stage不传则按intent推断；低阶段不覆盖高阶段"""
    data = _load()
    cur = data.get(key, {})

    # 阶段推断
    target_stage = stage
    if not target_stage and intent:
        target_stage = INTENT_TO_STAGE.get(intent)

    old_stage = cur.get("stage")
    if target_stage:
        # 不让低阶段覆盖高阶段（除非明确转dead）
        if target_stage == "dead":
            new_stage = "dead"
        elif old_stage and STAGE_RANK.get(target_stage, 0) < STAGE_RANK.get(old_stage, 0):
            new_stage = old_stage
        else:
            new_stage = target_stage
    else:
        new_stage = old_stage or "greeted"

    cur.update({
        "company": company or cur.get("company", ""),
        "hr_name": hr_name or cur.get("hr_name", ""),
        "job_title": job_title or cur.get("job_title", ""),
        "stage": new_stage,
        "last_intent": intent or cur.get("last_intent"),
        "updated_at": _now(),
    })
    cur.setdefault("created_at", _now())

    if last_hr_text is not None:
        cur["last_hr_text"] = last_hr_text[:200]
        cur["last_hr_ts"] = _now()
    if my_last_reply is not None:
        cur["my_last_reply"] = my_last_reply[:200]
        cur["my_last_ts"] = _now()
    if jd_hash:
        cur["jd_hash"] = jd_hash
    if extra:
        cur.setdefault("extra", {}).update(extra)

    # 阶段转换日志
    if old_stage and old_stage != new_stage:
        cur.setdefault("history", []).append({
            "from": old_stage, "to": new_stage, "at": _now(), "intent": intent,
        })
        cur["history"] = cur["history"][-10:]  # 最多留10条

    data[key] = cur
    _save(data)
    return cur


def mark_dead(key: str, reason: str = "") -> None:
    update_state(key, stage="dead", extra={"dead_reason": reason})


def list_stuck(hr_silent_hours: int = 48, me_silent_hours: int = 6) -> dict:
    """
    返回需要跟进的会话
    {
      "hr_no_reply": [...],   # HR超过hr_silent_hours没回我（轻推或放弃）
      "me_no_reply": [...],   # 我超过me_silent_hours没回HR（告警，漏接）
    }
    """
    data = _load()
    now_ts = time.time()
    hr_no_reply, me_no_reply = [], []

    for key, s in data.items():
        if s.get("stage") == "dead":
            continue

        hr_ts = _parse_ts(s.get("last_hr_ts"))
        my_ts = _parse_ts(s.get("my_last_ts"))

        # 场景1: 我发完HR没回
        if my_ts and (not hr_ts or my_ts > hr_ts):
            idle_h = (now_ts - my_ts) / 3600
            if idle_h >= hr_silent_hours:
                hr_no_reply.append({"key": key, "idle_hours": round(idle_h, 1), **s})

        # 场景2: HR发完我没回（漏接）
        elif hr_ts and (not my_ts or hr_ts > my_ts):
            idle_h = (now_ts - hr_ts) / 3600
            if idle_h >= me_silent_hours:
                me_no_reply.append({"key": key, "idle_hours": round(idle_h, 1), **s})

    return {"hr_no_reply": hr_no_reply, "me_no_reply": me_no_reply}


def _parse_ts(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").timestamp()
    except Exception:
        return None


def stats() -> dict:
    """聚合看板用"""
    data = _load()
    counter = {st: 0 for st in STAGES}
    for s in data.values():
        counter[s.get("stage", "greeted")] = counter.get(s.get("stage", "greeted"), 0) + 1
    return {"total": len(data), "by_stage": counter}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        print(json.dumps(stats(), ensure_ascii=False, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "stuck":
        print(json.dumps(list_stuck(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(_load(), ensure_ascii=False, indent=2))
