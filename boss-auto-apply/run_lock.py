import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
LOCK_PATH = DATA / "run.lock"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
                encoding="utf-8",
                errors="ignore",
            )
            return str(pid) in (result.stdout or "")
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_lock() -> dict | None:
    try:
        return json.loads(LOCK_PATH.read_text(encoding="utf-8")) if LOCK_PATH.exists() else None
    except Exception:
        return {"error": "invalid_lock", "path": str(LOCK_PATH)}


def status() -> dict:
    lock = read_lock()
    if not lock:
        return {"locked": False, "path": str(LOCK_PATH)}
    pid = int(lock.get("pid") or 0)
    alive = _pid_alive(pid)
    return {"locked": True, "alive": alive, "path": str(LOCK_PATH), **lock}


def acquire(kind: str = "start") -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    current = status()
    if current.get("locked") and current.get("alive"):
        print(f"[LOCKED] Existing boss-auto-apply run is active: pid={current.get('pid')} kind={current.get('kind')}")
        print("Use stop_apply.bat first if you want to restart.")
        return 2
    payload = {
        "pid": os.getpid(),
        "kind": kind,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cwd": str(ROOT),
    }
    LOCK_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[LOCK] acquired pid={payload['pid']} kind={kind}")
    return 0


def release() -> int:
    if LOCK_PATH.exists():
        LOCK_PATH.unlink()
        print("[LOCK] released")
    else:
        print("[LOCK] not present")
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "acquire":
        return acquire(sys.argv[2] if len(sys.argv) > 2 else "start")
    if cmd == "release":
        return release()
    if cmd == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=2))
        return 0
    print("usage: python run_lock.py acquire|release|status [kind]")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
