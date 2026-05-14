import csv
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DB_PATH = DATA / "boss_data.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT,
  company TEXT,
  title TEXT,
  salary TEXT,
  url TEXT,
  status TEXT,
  note TEXT,
  UNIQUE(url, status, ts)
);

CREATE TABLE IF NOT EXISTS conversations (
  chat_key TEXT PRIMARY KEY,
  company TEXT,
  hr_name TEXT,
  job_title TEXT,
  intent TEXT,
  last_hr_text TEXT,
  my_last_reply TEXT,
  resume_status TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS ai_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT,
  provider TEXT,
  model TEXT,
  purpose TEXT,
  status TEXT,
  elapsed_ms INTEGER,
  reply_preview TEXT,
  reply_text TEXT
);

CREATE TABLE IF NOT EXISTS interviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company TEXT,
  job TEXT,
  hr_name TEXT,
  interview_type TEXT,
  time_str TEXT,
  location TEXT,
  raw_msg TEXT,
  created_at TEXT
);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def sync_applications(conn: sqlite3.Connection, data_dir: Path = DATA) -> int:
    path = data_dir / "jobs_log.csv"
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            conn.execute(
                """
                INSERT OR IGNORE INTO applications(ts, company, title, salary, url, status, note)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("时间", ""),
                    row.get("公司", ""),
                    row.get("职位", ""),
                    row.get("薪资", ""),
                    row.get("URL", ""),
                    row.get("状态", ""),
                    row.get("备注", ""),
                ),
            )
            count += 1
    return count


def sync_conversations(conn: sqlite3.Connection, data_dir: Path = DATA) -> int:
    path = data_dir / "chat_states.json"
    if not path.exists():
        return 0
    try:
        states = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    count = 0
    for key, state in (states or {}).items():
        extra = state.get("extra") or {}
        conn.execute(
            """
            INSERT INTO conversations(chat_key, company, hr_name, job_title, intent, last_hr_text, my_last_reply, resume_status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_key) DO UPDATE SET
              company=excluded.company,
              hr_name=excluded.hr_name,
              job_title=excluded.job_title,
              intent=excluded.intent,
              last_hr_text=excluded.last_hr_text,
              my_last_reply=excluded.my_last_reply,
              resume_status=excluded.resume_status,
              updated_at=excluded.updated_at
            """,
            (
                key,
                state.get("company", ""),
                state.get("hr_name", ""),
                state.get("job_title", ""),
                state.get("intent", ""),
                state.get("last_hr_text", ""),
                state.get("my_last_reply", ""),
                extra.get("resume_status", ""),
                state.get("updated_at", extra.get("resume_status_at", "")),
            ),
        )
        count += 1
    return count


def sync_ai_calls(conn: sqlite3.Connection, data_dir: Path = DATA) -> int:
    path = data_dir / "ai_calls.jsonl"
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        conn.execute(
            """
            INSERT OR IGNORE INTO ai_calls(ts, provider, model, purpose, status, elapsed_ms, reply_preview, reply_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.get("ts", ""),
                row.get("provider", ""),
                row.get("model", ""),
                row.get("purpose", ""),
                row.get("status", ""),
                row.get("elapsed_ms"),
                row.get("reply_preview", ""),
                row.get("reply_text", ""),
            ),
        )
        count += 1
    return count


def sync_interviews(conn: sqlite3.Connection, data_dir: Path = DATA) -> int:
    path = data_dir / "interviews.json"
    if not path.exists():
        return 0
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    count = 0
    for row in rows if isinstance(rows, list) else []:
        conn.execute(
            """
            INSERT INTO interviews(company, job, hr_name, interview_type, time_str, location, raw_msg, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.get("company", ""),
                row.get("job", ""),
                row.get("hr_name", ""),
                row.get("type", row.get("interview_type", "")),
                row.get("time", row.get("time_str", "")),
                row.get("location", ""),
                row.get("raw_msg", ""),
                row.get("created_at", ""),
            ),
        )
        count += 1
    return count


def sync_all(data_dir: Path = DATA, db_path: Path = DB_PATH) -> dict:
    with connect(db_path) as conn:
        result = {
            "applications": sync_applications(conn, data_dir),
            "conversations": sync_conversations(conn, data_dir),
            "ai_calls": sync_ai_calls(conn, data_dir),
            "interviews": sync_interviews(conn, data_dir),
            "db_path": str(db_path),
        }
        conn.commit()
        return result


def main() -> int:
    result = sync_all()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
