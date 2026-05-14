import csv
import json
import os
import subprocess
import sys
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from manual_review import assess_manual_review


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)
START_ARGS = [
    "-u",
    "-B",
    "main.py",
    "--apply-watch",
    "--no-resume-sweep",
    "--limit",
    os.environ.get("BOSS_APPLY_LIMIT", "2"),
    "--interval",
    os.environ.get("BOSS_WATCH_INTERVAL", "180"),
    "--rounds",
    os.environ.get("BOSS_WATCH_ROUNDS", "0"),
]


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception as exc:
        return {"error": str(exc)}


def _tail_jsonl(path: Path, limit: int = 30) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
        for line in lines:
            try:
                rows.append(json.loads(line))
            except Exception:
                rows.append({"raw": line[:300]})
    except Exception as exc:
        rows.append({"error": str(exc)})
    return rows


def _tail_text(path: Path, limit: int = 120) -> list[str]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return [line.rstrip("\n") for line in deque(handle, maxlen=limit)]
    except Exception as exc:
        return [f"[tail error] {exc}"]


def _job_stats() -> dict:
    path = DATA / "jobs_log.csv"
    stats = {"total": 0, "success": 0, "skipped": 0, "failed": 0, "recent": []}
    if not path.exists():
        return stats
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            stats["total"] += 1
            status = row.get("状态", "")
            if status in stats:
                stats[status] += 1
        stats["recent"] = rows[-20:][::-1]
    except Exception as exc:
        stats["error"] = str(exc)
    return stats


def snapshot() -> dict:
    conversations = _read_json(DATA / "chat_states.json", {})
    jobs = _job_stats()
    todos = _conversation_todos(conversations)
    replied_companies = _replied_companies(conversations)
    manual_todos = [row for row in todos if row.get("manual_review")]
    strategy_todos = [row for row in replied_companies if row.get("ai_strategy_candidate")]
    return {
        "status": _read_json(DATA / "apply_status.json", {}),
        "jobs": jobs,
        "chat_state": _read_json(DATA / "chat_state.json", {}),
        "conversations": conversations,
        "todos": todos,
        "replied_companies": replied_companies,
        "manual_todos": manual_todos,
        "strategy_todos": strategy_todos,
        "ai_calls": _tail_jsonl(DATA / "ai_calls.jsonl"),
        "run_log_tail": _tail_text(DATA / "run.log"),
        "interviews": _read_json(DATA / "interviews.json", []),
        "lock": _lock_status(),
        "runner_processes": _runner_processes(),
        "todo_count": len(todos),
        "need_reply_count": sum(1 for row in todos if row.get("needs_reply")),
        "manual_review_count": len(manual_todos),
        "strategy_candidate_count": len(strategy_todos),
        "hr_reply_count": len(replied_companies),
    }


def _lock_status() -> dict:
    try:
        import run_lock
        return run_lock.status()
    except Exception as exc:
        return {"error": str(exc)}


def _runner_processes() -> list[dict]:
    runners = []
    try:
        import psutil

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmd = " ".join(proc.info.get("cmdline") or [])
                if "boss-auto-apply" in cmd and "main.py" in cmd:
                    runners.append(
                        {
                            "pid": proc.info.get("pid"),
                            "name": proc.info.get("name", ""),
                            "cmd": cmd[:260],
                        }
                    )
            except Exception:
                continue
    except Exception:
        if os.name == "nt":
            try:
                result = subprocess.run(
                    [
                        "wmic",
                        "process",
                        "where",
                        "name='python.exe'",
                        "get",
                        "ProcessId,CommandLine",
                        "/format:csv",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    encoding="utf-8",
                    errors="ignore",
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                )
                for line in (result.stdout or "").splitlines():
                    if "boss-auto-apply" not in line or "main.py" not in line:
                        continue
                    parts = line.rsplit(",", 1)
                    if len(parts) != 2:
                        continue
                    runners.append({"pid": parts[1].strip(), "name": "python.exe", "cmd": parts[0][-260:]})
            except Exception:
                pass
    return runners


def _conversation_todos(conversations) -> list[dict]:
    todos = []
    if not isinstance(conversations, dict):
        return todos
    for key, row in conversations.items():
        extra = row.get("extra") or {}
        last_hr = row.get("last_hr_text") or ""
        my_last = row.get("my_last_reply") or ""
        stage = row.get("stage") or ""
        if stage == "dead":
            continue
        manual = bool(extra.get("manual_review_required"))
        needs_reply = bool(last_hr and row.get("last_hr_ts", "") >= row.get("my_last_ts", ""))
        resume_status = extra.get("resume_status", "")
        if needs_reply or not resume_status or manual:
            inferred = _review_fields(row, extra)
            tag = inferred["manual_tag"]
            label = inferred["manual_label"]
            todos.append({
                "key": key,
                "company": row.get("company", ""),
                "hr_name": row.get("hr_name", ""),
                "job_title": row.get("job_title", ""),
                "stage": stage,
                "last_intent": row.get("last_intent", ""),
                "last_hr_text": last_hr,
                "my_last_reply": my_last,
                "resume_status": resume_status,
                "updated_at": row.get("updated_at", ""),
                "needs_reply": needs_reply,
                "manual_review": manual,
                **inferred,
            })
    return sorted(todos, key=lambda x: x.get("updated_at", ""), reverse=True)[:30]


def _replied_companies(conversations) -> list[dict]:
    rows = []
    if not isinstance(conversations, dict):
        return rows
    for key, row in conversations.items():
        last_hr = row.get("last_hr_text") or ""
        if not last_hr:
            continue
        extra = row.get("extra") or {}
        inferred = _review_fields(row, extra)
        rows.append({
            "key": key,
            "company": row.get("company", ""),
            "hr_name": row.get("hr_name", ""),
            "job_title": row.get("job_title", ""),
            "stage": row.get("stage", ""),
            "last_intent": row.get("last_intent", ""),
            "last_hr_text": last_hr,
            "my_last_reply": row.get("my_last_reply", ""),
            "resume_status": extra.get("resume_status", ""),
            "updated_at": row.get("updated_at", ""),
            "manual_review": bool(extra.get("manual_review_required")),
            **inferred,
        })
    return sorted(rows, key=lambda x: x.get("updated_at", ""), reverse=True)[:50]


def _review_fields(row: dict, extra: dict) -> dict:
    tag = extra.get("manual_review_tag", "")
    if not tag:
        decision = assess_manual_review(
            row.get("last_intent", ""),
            row.get("last_hr_text", ""),
            extra.get("intent_confidence", ""),
        )
        if decision.tag:
            return {
                "manual_tag": decision.tag,
                "manual_label": decision.label,
                "manual_risk": decision.risk,
                "manual_action": decision.action,
                "manual_reason": extra.get("manual_review_reason", ""),
                "manual_note": decision.note,
                "ai_strategy_candidate": decision.ai_strategy_candidate,
            }
    label = extra.get("manual_review_label", "") or tag or extra.get("manual_review_reason", "")
    return {
        "manual_tag": tag,
        "manual_label": label,
        "manual_risk": extra.get("manual_review_risk", ""),
        "manual_action": extra.get("manual_review_action", ""),
        "manual_reason": extra.get("manual_review_reason", ""),
        "manual_note": extra.get("manual_review_note", ""),
        "ai_strategy_candidate": bool(extra.get("ai_strategy_candidate")),
    }


def _start_runner() -> tuple[int, str]:
    existing = _runner_processes()
    if existing:
        return 409, f"already running: {', '.join(str(p.get('pid')) for p in existing)}"
    try:
        env = dict(os.environ)
        env.update({
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "BOSS_FAST_MODE": "1",
            "BOSS_PROFILE_NAME": env.get("BOSS_PROFILE_NAME", "chrome_profile_fengshen"),
            "BOSS_CHROME_PORT": env.get("BOSS_CHROME_PORT", "9222"),
            "BOSS_COOKIE_FALLBACK": env.get("BOSS_COOKIE_FALLBACK", "0"),
            "BOSS_AI_REPLY": env.get("BOSS_AI_REPLY", "1"),
            "BOSS_RAG_ENABLE": env.get("BOSS_RAG_ENABLE", "1"),
            "BOSS_AI_PROVIDER": env.get("BOSS_AI_PROVIDER", "qwen"),
            "BOSS_QWEN_BASE_URL": env.get(
                "BOSS_QWEN_BASE_URL",
                "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
            ),
            "BOSS_QWEN_MODEL": env.get("BOSS_QWEN_MODEL", "qwen3.6-plus"),
        })
        subprocess.Popen(
            [str(PYTHON), *START_ARGS],
            cwd=str(ROOT),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return 200, "started main.py --apply-watch"
    except Exception as exc:
        return 500, str(exc)


def _stop_runner() -> tuple[int, str]:
    stopped = []
    try:
        import psutil

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmd = " ".join(proc.info.get("cmdline") or [])
                if "boss-auto-apply" in cmd and "main.py" in cmd:
                    stopped.append(str(proc.info.get("pid")))
                    proc.kill()
            except Exception:
                continue
    except Exception as exc:
        if os.name != "nt":
            return 500, str(exc)
        try:
            result = subprocess.run(
                [
                    "wmic",
                    "process",
                    "where",
                    "name='python.exe'",
                    "get",
                    "ProcessId,CommandLine",
                    "/format:csv",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                encoding="utf-8",
                errors="ignore",
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            for line in (result.stdout or "").splitlines():
                if "boss-auto-apply" not in line or "main.py" not in line:
                    continue
                pid = line.rsplit(",", 1)[-1].strip()
                if not pid.isdigit():
                    continue
                stopped.append(pid)
                subprocess.run(
                    ["taskkill", "/PID", pid, "/F", "/T"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                )
        except Exception as fallback_exc:
            return 500, f"{exc}; fallback failed: {fallback_exc}"
    try:
        import run_lock
        run_lock.release()
    except Exception:
        pass
    return 200, "stopped " + (", ".join(stopped) if stopped else "none")


HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BOSS Auto Apply Dashboard</title>
  <style>
    :root {
      --bg: #f4f7fb;
      --panel: #ffffff;
      --panel-2: #f8fbfe;
      --border: #d6e0ea;
      --text: #15202b;
      --muted: #64748b;
      --accent: #0f766e;
      --accent-2: #2563eb;
      --warn: #b45309;
      --danger: #be123c;
      --shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      color: var(--text);
      background:
        linear-gradient(180deg, rgba(255,255,255,.55), rgba(255,255,255,0)),
        linear-gradient(180deg, #f7fafc, #edf3f8 45%, #f8fbfd);
    }
    .topbar {
      position: sticky;
      top: 0;
      z-index: 20;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 18px;
      border-bottom: 1px solid var(--border);
      background: rgba(248, 250, 252, 0.92);
      backdrop-filter: blur(10px);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }
    .brand-title { font-size: 18px; font-weight: 800; letter-spacing: 0; }
    .brand-sub { font-size: 12px; color: var(--muted); margin-top: 2px; }
    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 7px 10px;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: var(--panel);
      font-size: 12px;
      color: var(--muted);
      white-space: nowrap;
    }
    .dot {
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: #94a3b8;
    }
    .dot.live { background: #16a34a; box-shadow: 0 0 0 4px rgba(22,163,74,.12); }
    .actions {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    button, input[type="search"] {
      font: inherit;
    }
    button {
      appearance: none;
      border: 1px solid var(--border);
      background: var(--panel);
      color: var(--text);
      border-radius: 8px;
      padding: 9px 12px;
      cursor: pointer;
      box-shadow: var(--shadow);
    }
    button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
    button.danger { background: #fff1f2; border-color: #fecdd3; color: var(--danger); }
    button:hover { filter: brightness(0.985); }
    .layout {
      max-width: 1600px;
      margin: 0 auto;
      padding: 16px;
      display: grid;
      grid-template-columns: 330px minmax(0, 1fr);
      gap: 16px;
    }
    .sidebar {
      position: sticky;
      top: 80px;
      align-self: start;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .panel, .metric, .runner, .mini-box {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      box-shadow: var(--shadow);
    }
    .panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 13px 15px;
      border-bottom: 1px solid var(--border);
      background: linear-gradient(180deg, var(--panel), var(--panel-2));
    }
    .panel-head h3, .panel-head h4 { margin: 0; font-size: 15px; }
    .panel-body { padding: 14px 15px; }
    .metric-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .metric {
      padding: 12px;
      min-height: 84px;
    }
    .metric .label { font-size: 12px; color: var(--muted); }
    .metric .value { font-size: 22px; font-weight: 800; margin-top: 5px; line-height: 1.1; }
    .metric .hint { font-size: 11px; color: var(--muted); margin-top: 4px; }
    .stack { display: grid; gap: 10px; }
    .status-pre, .log-pre {
      margin: 0;
      padding: 14px 15px;
      background: #0f172a;
      color: #dbeafe;
      border-radius: 10px;
      white-space: pre-wrap;
      word-break: break-word;
      overflow: auto;
      min-height: 210px;
      max-height: 360px;
      font-size: 12px;
      line-height: 1.5;
    }
    .runner-list { display: grid; gap: 8px; }
    .runner {
      padding: 10px 12px;
      font-size: 12px;
      line-height: 1.4;
    }
    .runner .muted { color: var(--muted); }
    .main {
      display: grid;
      gap: 16px;
      min-width: 0;
    }
    .section {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    .section-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 15px;
      border-bottom: 1px solid var(--border);
      background: linear-gradient(180deg, #ffffff, #f8fbfe);
    }
    .section-head h3 { margin: 0; font-size: 15px; }
    .section-tools { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    input[type="search"] {
      min-width: 240px;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 9px 11px;
      background: #fff;
      box-shadow: inset 0 1px 0 rgba(15, 23, 42, 0.03);
    }
    .section-body { padding: 0; }
    .table-wrap {
      overflow: auto;
      max-height: 380px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      border-bottom: 1px solid #e6edf3;
      padding: 10px 9px;
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
    }
    th {
      position: sticky;
      top: 0;
      background: #fff;
      z-index: 1;
      color: #475569;
      font-weight: 700;
    }
    tbody tr:hover { background: #f8fbfd; }
    td.wrap { white-space: normal; word-break: break-word; }
    .pill {
      display: inline-flex;
      align-items: center;
      padding: 3px 8px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
    }
    .pill.reply { background: #eff6ff; color: #1d4ed8; }
    .pill.manual { background: #fff1f2; color: var(--danger); }
    .pill.ok { background: #ecfdf5; color: #047857; }
    .progress {
      height: 10px;
      background: #e7eef6;
      border-radius: 999px;
      overflow: hidden;
      margin-top: 8px;
    }
    .progress > span {
      display: block;
      height: 100%;
      background: linear-gradient(90deg, var(--accent), var(--accent-2));
    }
    .small { font-size: 12px; color: var(--muted); }
    .error-banner {
      display: none;
      padding: 10px 14px;
      border: 1px solid #fecaca;
      background: #fef2f2;
      color: #991b1b;
      border-radius: 10px;
      margin: 0 0 16px 0;
    }
    @media (max-width: 1120px) {
      .layout { grid-template-columns: 1fr; }
      .sidebar { position: static; }
      input[type="search"] { min-width: 160px; width: 100%; }
      .topbar { flex-wrap: wrap; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand">
      <div>
        <div class="brand-title">BOSS Auto Apply</div>
        <div class="brand-sub">本地监控前端 - 投递批次、HR回复、人工接管、日志、运行进程一屏看完</div>
      </div>
      <span id="liveBadge" class="status-pill"><span class="dot" id="liveDot"></span><span id="liveText">Loading</span></span>
    </div>
    <div class="actions">
      <button class="primary" onclick="action('/api/start')">Start</button>
      <button class="danger" onclick="action('/api/stop')">Stop</button>
      <button onclick="refresh()">Refresh</button>
    </div>
  </header>

  <div class="layout">
    <aside class="sidebar">
      <div class="metric-grid" id="metrics"></div>

      <section class="section">
        <div class="section-head"><h3>Current Run</h3><span class="small" id="refreshTime">-</span></div>
        <div class="section-body"><pre class="status-pre" id="status">Loading...</pre></div>
      </section>

      <section class="section">
        <div class="section-head"><h3>Runner Processes</h3><span class="small" id="runnerCount">0</span></div>
        <div class="section-body">
          <div class="panel-body">
            <div class="runner-list" id="runnerList"></div>
          </div>
        </div>
      </section>

      <section class="section">
        <div class="section-head"><h3>Today Summary</h3><span class="small" id="todaySummary">-</span></div>
        <div class="section-body">
          <div class="panel-body">
            <div class="small">Success rate</div>
            <div class="progress"><span id="progressBar" style="width:0%"></span></div>
            <div class="small" id="progressText">0 / 0</div>
          </div>
        </div>
      </section>
    </aside>

    <main class="main">
      <div id="errorBanner" class="error-banner"></div>

      <section class="section">
        <div class="section-head">
          <h3>HR 待处理</h3>
          <div class="section-tools">
            <input id="todoFilter" type="search" placeholder="过滤公司 / HR / 岗位 / 消息">
          </div>
        </div>
        <div class="section-body table-wrap">
          <table>
            <thead>
              <tr><th>状态</th><th>公司</th><th>HR</th><th>岗位</th><th>原因/意图</th><th>简历</th><th>HR消息</th><th>我的回复</th><th>更新时间</th></tr>
            </thead>
            <tbody id="todoBody"></tbody>
          </table>
        </div>
      </section>

      <section class="section">
        <div class="section-head">
          <h3>需要人工回复</h3>
          <div class="section-tools">
            <span class="small" id="manualSummary">0 家</span>
          </div>
        </div>
        <div class="section-body table-wrap">
          <table>
            <thead>
              <tr><th>公司</th><th>HR</th><th>岗位</th><th>人工原因</th><th>HR消息</th><th>备注</th><th>更新时间</th></tr>
            </thead>
            <tbody id="manualBody"></tbody>
          </table>
        </div>
      </section>

      <section class="section">
        <div class="section-head">
          <h3>AI 策略候选</h3>
          <div class="section-tools">
            <span class="small" id="strategySummary">0 条</span>
          </div>
        </div>
        <div class="section-body table-wrap">
          <table>
            <thead>
              <tr><th>标签</th><th>公司</th><th>HR</th><th>岗位</th><th>HR消息</th><th>当前动作</th><th>更新时间</th></tr>
            </thead>
            <tbody id="strategyBody"></tbody>
          </table>
        </div>
      </section>

      <section class="section">
        <div class="section-head">
          <h3>HR 已回复公司</h3>
          <div class="section-tools">
            <input id="replyFilter" type="search" placeholder="过滤公司 / HR / 岗位 / 消息">
          </div>
        </div>
        <div class="section-body table-wrap">
          <table>
            <thead>
              <tr><th>公司</th><th>HR</th><th>岗位</th><th>阶段</th><th>意图</th><th>简历</th><th>HR消息</th><th>我的回复</th><th>更新时间</th></tr>
            </thead>
            <tbody id="replyBody"></tbody>
          </table>
        </div>
      </section>

      <section class="section">
        <div class="section-head">
          <h3>最近投递记录</h3>
          <div class="section-tools">
            <input id="jobFilter" type="search" placeholder="过滤公司 / 职位 / 备注">
          </div>
        </div>
        <div class="section-body table-wrap">
          <table>
            <thead>
              <tr><th>时间</th><th>公司</th><th>职位</th><th>状态</th><th>备注</th></tr>
            </thead>
            <tbody id="jobBody"></tbody>
          </table>
        </div>
      </section>

      <section class="section">
        <div class="section-head">
          <h3>AI 调用记录</h3>
          <div class="section-tools">
            <input id="aiFilter" type="search" placeholder="过滤 provider / purpose / 回复">
          </div>
        </div>
        <div class="section-body table-wrap">
          <table>
            <thead>
              <tr><th>时间</th><th>Provider</th><th>Purpose</th><th>Status</th><th>Preview</th></tr>
            </thead>
            <tbody id="aiBody"></tbody>
          </table>
        </div>
      </section>

      <section class="section">
        <div class="section-head">
          <h3>运行日志</h3>
          <div class="section-tools">
            <input id="logFilter" type="search" placeholder="过滤日志关键字">
          </div>
        </div>
        <div class="section-body" style="padding:14px 15px;">
          <pre class="log-pre" id="logBody"></pre>
        </div>
      </section>
    </main>
  </div>

<script>
const state = { snapshot: null, filters: { todo: '', reply: '', job: '', ai: '', log: '' } };

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[ch]);
}

function short(value, max = 110) {
  const text = String(value ?? '').trim().replace(/\\s+/g, ' ');
  return text.length > max ? text.slice(0, max - 1) + '…' : text;
}

function includesAny(row, query, fields) {
  if (!query) return true;
  const needle = query.toLowerCase();
  return fields.some((field) => String(row[field] ?? '').toLowerCase().includes(needle));
}

async function action(path) {
  const res = await fetch(path, { method: 'POST' });
  const text = await res.text();
  const banner = document.getElementById('errorBanner');
  banner.style.display = 'block';
  banner.style.borderColor = res.ok ? '#bbf7d0' : '#fecaca';
  banner.style.background = res.ok ? '#f0fdf4' : '#fef2f2';
  banner.style.color = res.ok ? '#166534' : '#991b1b';
  banner.textContent = text;
  refresh();
}

function renderMetrics(data) {
  const jobs = data.jobs || {};
  const lock = data.lock || {};
  const items = [
    ['总记录', jobs.total || 0, '全部投递记录'],
    ['成功', jobs.success || 0, '成功投递'],
    ['跳过', jobs.skipped || 0, '过滤或静默'],
    ['失败', jobs.failed || 0, '执行失败'],
    ['HR已回复', data.hr_reply_count || 0, '有HR消息的公司'],
    ['待回复', data.need_reply_count || 0, 'HR消息待处理'],
    ['人工', data.manual_review_count || 0, '需要人工接管'],
    ['策略', data.strategy_candidate_count || 0, '可优化AI策略'],
    ['运行', lock.locked ? (lock.alive ? '在线' : '陈旧') : '未锁定', '进程状态']
  ];
  const total = Number(jobs.total || 0);
  const success = Number(jobs.success || 0);
  const rate = total ? Math.round((success / total) * 100) : 0;
  document.getElementById('metrics').innerHTML = items.map(([k, v, h]) => `
    <div class="metric">
      <div class="label">${k}</div>
      <div class="value">${v}</div>
      <div class="hint">${h}</div>
    </div>`).join('');
  document.getElementById('todaySummary').textContent = `${success}/${total} 成功率 ${rate}%`;
  document.getElementById('progressBar').style.width = `${rate}%`;
  document.getElementById('progressText').textContent = `${success} / ${total}`;
}

function renderStatus(data) {
  document.getElementById('status').textContent = JSON.stringify(data.status || {}, null, 2);
  const ts = data.status && data.status.updated_at ? data.status.updated_at : '-';
  document.getElementById('refreshTime').textContent = `Updated ${ts}`;

  const runners = data.runner_processes || [];
  document.getElementById('runnerCount').textContent = `${runners.length} active`;
  document.getElementById('runnerList').innerHTML = runners.length ? runners.map((r) => `
    <div class="runner">
      <div><strong>PID ${r.pid}</strong> <span class="small">${escapeHtml(r.name || '')}</span></div>
      <div class="muted">${escapeHtml(short(r.cmd, 240))}</div>
    </div>`).join('') : `<div class="runner"><div class="muted">No active boss-auto-apply process found.</div></div>`;

  const lock = data.lock || {};
  const live = document.getElementById('liveBadge');
  const dot = document.getElementById('liveDot');
  const liveText = document.getElementById('liveText');
  if (runners.length || (lock.locked && lock.alive)) {
    liveText.textContent = 'LIVE';
    dot.className = 'dot live';
  } else {
    liveText.textContent = 'Idle';
    dot.className = 'dot';
  }
}

function renderTodos(data) {
  const query = state.filters.todo.trim();
  const rows = (data.todos || []).filter((row) => includesAny(row, query, ['company', 'hr_name', 'job_title', 'last_intent', 'resume_status', 'last_hr_text', 'manual_reason', 'manual_label']));
  document.getElementById('todoBody').innerHTML = rows.map((r) => `
    <tr>
      <td>${r.manual_review ? '<span class="pill manual">人工</span>' : (r.needs_reply ? '<span class="pill reply">待回复</span>' : '<span class="pill ok">待确认</span>')}</td>
      <td>${escapeHtml(r.company || '')}</td>
      <td>${escapeHtml(r.hr_name || '')}</td>
      <td class="wrap">${escapeHtml(r.job_title || '')}</td>
      <td>${escapeHtml(r.manual_review ? (r.manual_label || r.manual_tag || '人工') : (r.manual_label || r.last_intent || ''))}</td>
      <td>${escapeHtml(r.resume_status || '')}</td>
      <td class="wrap">${escapeHtml(short(r.last_hr_text || '', 150))}</td>
      <td class="wrap">${escapeHtml(short(r.my_last_reply || '', 120))}</td>
      <td>${escapeHtml(r.updated_at || '')}</td>
    </tr>`).join('') || `<tr><td colspan="9" class="small">暂无待处理项。</td></tr>`;
}

function renderManual(data) {
  const rows = data.manual_todos || [];
  document.getElementById('manualSummary').textContent = `${rows.length} 家`;
  document.getElementById('manualBody').innerHTML = rows.map((r) => `
    <tr>
      <td>${escapeHtml(r.company || '')}</td>
      <td>${escapeHtml(r.hr_name || '')}</td>
      <td class="wrap">${escapeHtml(r.job_title || '')}</td>
      <td>${escapeHtml(r.manual_label || r.manual_tag || '人工')}</td>
      <td class="wrap">${escapeHtml(short(r.last_hr_text || '', 170))}</td>
      <td class="wrap">${escapeHtml(short(r.manual_note || '', 120))}</td>
      <td>${escapeHtml(r.updated_at || '')}</td>
    </tr>`).join('') || `<tr><td colspan="7" class="small">暂无需要人工接管的公司。</td></tr>`;
}

function renderStrategies(data) {
  const rows = data.strategy_todos || [];
  document.getElementById('strategySummary').textContent = `${rows.length} 条`;
  document.getElementById('strategyBody').innerHTML = rows.map((r) => `
    <tr>
      <td>${escapeHtml(r.manual_label || r.manual_tag || '')}</td>
      <td>${escapeHtml(r.company || '')}</td>
      <td>${escapeHtml(r.hr_name || '')}</td>
      <td class="wrap">${escapeHtml(r.job_title || '')}</td>
      <td class="wrap">${escapeHtml(short(r.last_hr_text || '', 170))}</td>
      <td>${escapeHtml(r.manual_action || '')}</td>
      <td>${escapeHtml(r.updated_at || '')}</td>
    </tr>`).join('') || `<tr><td colspan="7" class="small">暂无 AI 策略候选。</td></tr>`;
}

function renderReplies(data) {
  const query = state.filters.reply.trim();
  const rows = (data.replied_companies || []).filter((row) => includesAny(row, query, ['company', 'hr_name', 'job_title', 'stage', 'last_intent', 'resume_status', 'last_hr_text', 'my_last_reply', 'manual_label']));
  document.getElementById('replyBody').innerHTML = rows.map((r) => `
    <tr>
      <td>${escapeHtml(r.company || '')}${r.manual_review ? ' <span class="pill manual">人工</span>' : ''}</td>
      <td>${escapeHtml(r.hr_name || '')}</td>
      <td class="wrap">${escapeHtml(r.job_title || '')}</td>
      <td>${escapeHtml(r.stage || '')}</td>
      <td>${escapeHtml(r.manual_label || r.last_intent || '')}</td>
      <td>${escapeHtml(r.resume_status || '')}</td>
      <td class="wrap">${escapeHtml(short(r.last_hr_text || '', 160))}</td>
      <td class="wrap">${escapeHtml(short(r.my_last_reply || '', 130))}</td>
      <td>${escapeHtml(r.updated_at || '')}</td>
    </tr>`).join('') || `<tr><td colspan="9" class="small">暂无 HR 回复记录。</td></tr>`;
}

function renderJobs(data) {
  const query = state.filters.job.trim();
  const rows = ((data.jobs || {}).recent || []).filter((row) => includesAny(row, query, ['时间', '公司', '职位', '状态', '备注']));
  document.getElementById('jobBody').innerHTML = rows.map((r) => `
    <tr>
      <td>${escapeHtml(r['时间'] || '')}</td>
      <td>${escapeHtml(r['公司'] || '')}</td>
      <td class="wrap">${escapeHtml(r['职位'] || '')}</td>
      <td>${escapeHtml(r['状态'] || '')}</td>
      <td class="wrap">${escapeHtml(short(r['备注'] || '', 150))}</td>
    </tr>`).join('') || `<tr><td colspan="5" class="small">No recent jobs.</td></tr>`;
}

function renderAi(data) {
  const query = state.filters.ai.trim();
  const rows = (data.ai_calls || []).filter((row) => includesAny(row, query, ['ts', 'provider', 'purpose', 'status', 'reply_preview', 'raw']));
  document.getElementById('aiBody').innerHTML = rows.map((r) => `
    <tr>
      <td>${escapeHtml(r.ts || '')}</td>
      <td>${escapeHtml(r.provider || '')}</td>
      <td>${escapeHtml(r.purpose || '')}</td>
      <td>${escapeHtml(r.status || '')}</td>
      <td class="wrap">${escapeHtml(short(r.reply_preview || r.raw || '', 180))}</td>
    </tr>`).join('') || `<tr><td colspan="5" class="small">No AI calls yet.</td></tr>`;
}

function renderLog(data) {
  const query = state.filters.log.trim().toLowerCase();
  const lines = (data.run_log_tail || []).filter((line) => !query || String(line).toLowerCase().includes(query));
  document.getElementById('logBody').textContent = lines.join('\\n');
}

function renderAll(data) {
  renderMetrics(data);
  renderStatus(data);
  renderTodos(data);
  renderManual(data);
  renderStrategies(data);
  renderReplies(data);
  renderJobs(data);
  renderAi(data);
  renderLog(data);
}

async function refresh() {
  try {
    const data = await fetch('/api/snapshot').then((r) => r.json());
    state.snapshot = data;
    renderAll(data);
  } catch (err) {
    document.getElementById('errorBanner').style.display = 'block';
    document.getElementById('errorBanner').textContent = `Refresh failed: ${err}`;
  }
}

document.getElementById('todoFilter').addEventListener('input', (e) => { state.filters.todo = e.target.value; if (state.snapshot) renderTodos(state.snapshot); });
document.getElementById('replyFilter').addEventListener('input', (e) => { state.filters.reply = e.target.value; if (state.snapshot) renderReplies(state.snapshot); });
document.getElementById('jobFilter').addEventListener('input', (e) => { state.filters.job = e.target.value; if (state.snapshot) renderJobs(state.snapshot); });
document.getElementById('aiFilter').addEventListener('input', (e) => { state.filters.ai = e.target.value; if (state.snapshot) renderAi(state.snapshot); });
document.getElementById('logFilter').addEventListener('input', (e) => { state.filters.log = e.target.value; if (state.snapshot) renderLog(state.snapshot); });

refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/start":
            code, msg = _start_runner()
        elif path == "/api/stop":
            code, msg = _stop_runner()
        else:
            code, msg = 404, "not found"
        body = msg.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/snapshot":
            body = json.dumps(snapshot(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def main():
    host = "127.0.0.1"
    port = int(__import__("os").environ.get("BOSS_DASHBOARD_PORT", "8765") or "8765")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Dashboard: http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
