"""
跟进引擎 —— 扫chat_states，对超时未回的会话执行轻推或告警

策略:
  HR没回我:
    24h: 第1次轻推 "周末好/在忙吗，那边方便看下简历吗?"
    72h: 第2次轻推 "如果不太合适也没关系，祝顺利"
    >7d: 标 dead
  我没回HR:
    >6h: 写入 alert.log + 推送飞书提醒（如果配置了）

跟进文案克制，不骚扰；同一会话最多2次轻推。
"""
from __future__ import annotations
import json
import time
from datetime import datetime
from pathlib import Path

from conversation_state import (
    _load as _load_states, update_state, mark_dead, _now,
)

ALERT_LOG = Path(__file__).parent / "data" / "followup_alerts.log"
ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)

# 轻推文案（克制、不骚扰）
NUDGE_TEMPLATES = {
    1: "您好，上次发的简历这边方便看下吗？随时可面。",
    2: "如这边岗位不太匹配也没关系，祝招聘顺利～",
}


def _log_alert(msg: str) -> None:
    with open(ALERT_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{_now()}] {msg}\n")


def sweep(
    *,
    nudge_after_h: int = 24,
    second_nudge_after_h: int = 72,
    dead_after_h: int = 24 * 7,
    me_alert_after_h: int = 6,
    dry_run: bool = True,
) -> dict:
    """
    扫描所有会话，返回需执行的动作列表
    Returns:
      {
        "nudges": [{"key", "company", "hr_name", "round", "text"}],
        "dead": [{"key", "company", "reason"}],
        "alerts": [{"key", "company", "hr_name", "last_hr_text", "idle_h"}],
      }
    """
    data = _load_states()
    now_ts = time.time()
    nudges, deads, alerts = [], [], []

    for key, s in data.items():
        if s.get("stage") in ("dead", "interview_scheduled"):
            continue

        hr_ts = _ts(s.get("last_hr_ts"))
        my_ts = _ts(s.get("my_last_ts"))
        nudge_count = int((s.get("extra") or {}).get("nudge_count", 0))

        # 1) 我发完HR没回 — 考虑轻推
        if my_ts and (not hr_ts or my_ts > hr_ts):
            idle_h = (now_ts - my_ts) / 3600

            if idle_h >= dead_after_h:
                deads.append({
                    "key": key, "company": s.get("company", ""),
                    "reason": f"HR静默{int(idle_h)}h",
                })
                if not dry_run:
                    mark_dead(key, reason=f"HR静默{int(idle_h)}h")

            elif nudge_count == 0 and idle_h >= nudge_after_h:
                nudges.append({
                    "key": key, "company": s.get("company", ""),
                    "hr_name": s.get("hr_name", ""), "job_title": s.get("job_title", ""),
                    "round": 1, "text": NUDGE_TEMPLATES[1], "idle_h": round(idle_h, 1),
                })

            elif nudge_count == 1 and idle_h >= second_nudge_after_h:
                nudges.append({
                    "key": key, "company": s.get("company", ""),
                    "hr_name": s.get("hr_name", ""), "job_title": s.get("job_title", ""),
                    "round": 2, "text": NUDGE_TEMPLATES[2], "idle_h": round(idle_h, 1),
                })

        # 2) HR发完我没回 — 告警
        elif hr_ts and (not my_ts or hr_ts > my_ts):
            idle_h = (now_ts - hr_ts) / 3600
            if idle_h >= me_alert_after_h:
                alerts.append({
                    "key": key, "company": s.get("company", ""),
                    "hr_name": s.get("hr_name", ""),
                    "last_hr_text": s.get("last_hr_text", "")[:80],
                    "idle_h": round(idle_h, 1),
                })

    return {"nudges": nudges, "dead": deads, "alerts": alerts}


def mark_nudge_sent(key: str, round_num: int) -> None:
    """跟进发出后回写state"""
    update_state(
        key,
        my_last_reply=NUDGE_TEMPLATES.get(round_num, ""),
        extra={"nudge_count": round_num, "last_nudge_at": _now()},
    )


def write_alerts_to_log(alerts: list) -> None:
    if not alerts:
        return
    for a in alerts:
        _log_alert(
            f"⚠ 漏接 {a['company']} {a['hr_name']} 静默{a['idle_h']}h: {a['last_hr_text']}"
        )


def _ts(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").timestamp()
    except Exception:
        return None


def format_report(result: dict) -> str:
    lines = ["=== 跟进引擎扫描结果 ==="]
    n = result.get("nudges") or []
    d = result.get("dead") or []
    a = result.get("alerts") or []
    lines.append(f"待轻推: {len(n)}  待标dead: {len(d)}  漏接告警: {len(a)}")
    if n:
        lines.append("\n[轻推]")
        for x in n[:10]:
            lines.append(f"  R{x['round']} {x['company']} {x['hr_name']} ({x['idle_h']}h)")
    if a:
        lines.append("\n[漏接 ⚠]")
        for x in a[:10]:
            lines.append(f"  {x['company']} {x['hr_name']} ({x['idle_h']}h): {x['last_hr_text']}")
    if d:
        lines.append("\n[标dead]")
        for x in d[:10]:
            lines.append(f"  {x['company']}: {x['reason']}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    dry = "--apply" not in sys.argv
    res = sweep(dry_run=dry)
    print(format_report(res))
    if not dry:
        write_alerts_to_log(res.get("alerts") or [])
        print(f"\n✅ 告警已写入 {ALERT_LOG}")
        print("注: 轻推消息需通过UI实际发送（chat_processor集成）")
