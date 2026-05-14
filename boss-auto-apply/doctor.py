import json
import os
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def _ok(label: str, value: str = "") -> dict:
    return {"name": label, "status": "ok", "detail": value}


def _warn(label: str, value: str = "") -> dict:
    return {"name": label, "status": "warn", "detail": value}


def _fail(label: str, value: str = "") -> dict:
    return {"name": label, "status": "fail", "detail": value}


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def run_checks() -> list[dict]:
    checks = []

    checks.append(_ok("python", sys.version.split()[0]))

    try:
        import DrissionPage  # noqa: F401
        checks.append(_ok("DrissionPage", "installed"))
    except Exception as exc:
        checks.append(_fail("DrissionPage", str(exc)))

    config = ROOT / "config.yaml"
    checks.append(_ok("config.yaml", "exists") if config.exists() else _fail("config.yaml", "missing"))

    profile_name = os.environ.get("BOSS_PROFILE_NAME", "chrome_profile_fengshen")
    profile = DATA / profile_name
    checks.append(_ok("chrome profile", str(profile)) if profile.exists() else _warn("chrome profile", f"not found: {profile}"))

    port = int(os.environ.get("BOSS_CHROME_PORT", "9222") or "9222")
    checks.append(_ok("chrome debug port", f"127.0.0.1:{port} listening") if _port_open("127.0.0.1", port) else _warn("chrome debug port", f"127.0.0.1:{port} not listening"))

    ai_enabled = os.environ.get("BOSS_AI_REPLY", "0") == "1"
    provider = os.environ.get("BOSS_AI_PROVIDER", "qwen")
    checks.append(_ok("AI reply", f"enabled provider={provider}") if ai_enabled else _warn("AI reply", "disabled; set BOSS_AI_REPLY=1"))

    if provider.lower() == "qwen":
        model = os.environ.get("BOSS_QWEN_MODEL", "qwen3.6-plus")
        base_url = os.environ.get("BOSS_QWEN_BASE_URL", "")
        api_key = os.environ.get("BOSS_QWEN_API_KEY", "")
        if base_url and api_key and model:
            checks.append(_ok("Qwen config", f"model={model} base_url_set=True api_key_set=True"))
        else:
            checks.append(_warn("Qwen config", f"model={model} base_url_set={bool(base_url)} api_key_set={bool(api_key)}"))

    for name in ("apply_status.json", "chat_state.json", "chat_states.json", "ai_calls.jsonl"):
        path = DATA / name
        checks.append(_ok(name, "exists") if path.exists() else _warn(name, "not found yet"))

    try:
        import run_lock
        lock = run_lock.status()
        if lock.get("locked") and lock.get("alive"):
            checks.append(_warn("run lock", f"active pid={lock.get('pid')} kind={lock.get('kind')}"))
        elif lock.get("locked"):
            checks.append(_warn("run lock", f"stale pid={lock.get('pid')}"))
        else:
            checks.append(_ok("run lock", "not locked"))
    except Exception as exc:
        checks.append(_warn("run lock", str(exc)))

    return checks


def main() -> int:
    checks = run_checks()
    if "--json" in sys.argv:
        print(json.dumps(checks, ensure_ascii=False, indent=2))
        return 0
    print("=== boss-auto-apply doctor ===")
    for item in checks:
        marker = {"ok": "[OK]", "warn": "[WARN]", "fail": "[FAIL]"}[item["status"]]
        print(f"{marker} {item['name']}: {item['detail']}")
    return 1 if any(c["status"] == "fail" for c in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
