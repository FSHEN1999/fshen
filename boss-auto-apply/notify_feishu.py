"""飞书通知推送 - 直连飞书 OpenAPI，不依赖 Hermes 网关

优先用环境变量里的 FEISHU_APP_ID / FEISHU_APP_SECRET；
目标频道 = FEISHU_HOME_CHANNEL（用户家频道）或显式传入。

用法：
  from notify_feishu import notify
  notify("⚠ 漏接 XX 公司 静默 7h: HR说...")

错误静默，不影响主流程。
"""
from __future__ import annotations
import json
import os
import time
import urllib.request
import urllib.error
from typing import Optional

_TOKEN_CACHE = {"token": "", "expire_at": 0.0}

HOME_CHAT_ID = os.environ.get("FEISHU_HOME_CHANNEL", "oc_ad699ba9db6cd679b6a04a2cacd9c1e3")
APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
BASE = "https://open.feishu.cn/open-apis"


def _http_post(url: str, payload: dict, headers: Optional[dict] = None, timeout: int = 8) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="ignore")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8", errors="ignore"))
        except Exception:
            return {"code": -1, "msg": str(e)}
    except Exception as e:
        return {"code": -1, "msg": str(e)}


def _get_tenant_token() -> str:
    now = time.time()
    if _TOKEN_CACHE["token"] and _TOKEN_CACHE["expire_at"] > now + 60:
        return _TOKEN_CACHE["token"]
    if not APP_ID or not APP_SECRET:
        return ""
    res = _http_post(
        f"{BASE}/auth/v3/tenant_access_token/internal",
        {"app_id": APP_ID, "app_secret": APP_SECRET},
    )
    tok = res.get("tenant_access_token", "")
    if tok:
        _TOKEN_CACHE["token"] = tok
        _TOKEN_CACHE["expire_at"] = now + int(res.get("expire", 7200)) - 300
    return tok


def notify(text: str, chat_id: Optional[str] = None) -> bool:
    """推一条纯文本到飞书家频道。失败静默返回 False。"""
    if not text:
        return False
    text = text.strip()
    if len(text) > 3500:
        text = text[:3500] + "\n...(截断)"
    token = _get_tenant_token()
    if not token:
        return False
    target = chat_id or HOME_CHAT_ID
    if not target:
        return False
    res = _http_post(
        f"{BASE}/im/v1/messages?receive_id_type=chat_id",
        {
            "receive_id": target,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    return res.get("code") == 0


def notify_alerts(alerts: list) -> None:
    """把漏接告警合并成一条发飞书。"""
    if not alerts:
        return
    lines = [f"⚠ BOSS 漏接告警 ({len(alerts)} 条)"]
    for a in alerts[:15]:
        lines.append(
            f"• {a.get('company','?')} / {a.get('hr_name','?')} "
            f"静默 {a.get('idle_h','?')}h: {(a.get('last_hr_text') or '')[:60]}"
        )
    if len(alerts) > 15:
        lines.append(f"...另有 {len(alerts)-15} 条")
    notify("\n".join(lines))


def notify_interview(company: str, title: str, hr_name: str, when: str = "", where: str = "") -> bool:
    """新增面试邀约时推一条。"""
    msg = f"🎯 BOSS 新面试邀约\n公司: {company}\n岗位: {title}\nHR: {hr_name}"
    if when:
        msg += f"\n时间: {when}"
    if where:
        msg += f"\n地点: {where}"
    return notify(msg)


def notify_summary(stats: dict) -> None:
    """每轮结束的简要汇报。stats = {applied, replied, interviews, round}"""
    msg = (
        f"📊 BOSS 第{stats.get('round','?')}轮\n"
        f"投递累计: {stats.get('applied_total',0)} | "
        f"回复: {stats.get('replied_total',0)} | "
        f"面试: {stats.get('interview_total',0)}"
    )
    notify(msg)


if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) or "notify_feishu self-test"
    ok = notify(text)
    print(f"notify -> {ok}")
