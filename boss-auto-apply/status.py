import json
import csv
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
STATUS = DATA / "apply_status.json"
LOG = DATA / "jobs_log.csv"

def load_status():
    if not STATUS.exists():
        return {"stage": "NO_STATUS", "updated_at": "-", "job": {}}
    try:
        return json.loads(STATUS.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"stage": "STATUS_ERROR", "updated_at": "-", "job": {}, "error": str(exc)}

def today_stats():
    today = datetime.now().strftime("%Y-%m-%d")
    stats = {"total": 0, "success": 0, "skipped": 0, "failed": 0}
    if not LOG.exists():
        return stats
    with LOG.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            if not row or not row[0].startswith(today):
                continue
            stats["total"] += 1
            if len(row) > 5 and row[5] in stats:
                stats[row[5]] += 1
    return stats

def main():
    status = load_status()
    job = status.get("job") or {}
    stats = today_stats()
    print("=== Boss Auto Apply Status ===")
    print(f"updated_at : {status.get('updated_at', '-')}")
    print(f"stage      : {status.get('stage', '-')}")
    print(f"dry_run    : {status.get('dry_run', False)}")
    print(f"keyword    : {status.get('keyword', '-')}")
    print(f"progress   : {status.get('applied', '-')}/{status.get('target', '-')}")
    print(f"today      : total={stats['total']} success={stats['success']} skipped={stats['skipped']} failed={stats['failed']}")
    if job:
        print("--- current job ---")
        print(f"company    : {job.get('company', '')}")
        print(f"title      : {job.get('title', '')}")
        print(f"salary     : {job.get('salary', '')}")
        print(f"score      : {job.get('match_score', '')}")
        print(f"reason     : {job.get('match_reason', '')}")
        greeting = job.get("greeting_preview") or status.get("greeting") or ""
        if greeting:
            print(f"greeting   : {greeting}")
        print(f"url        : {job.get('url', '')}")
    if status.get("note"):
        print(f"note       : {status.get('note')}")
    if status.get("error"):
        print(f"error      : {status.get('error')}")

if __name__ == "__main__":
    main()
