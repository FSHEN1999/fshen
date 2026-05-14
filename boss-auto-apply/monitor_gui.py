"""Desktop monitor window for boss-auto-apply."""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import webbrowser
from collections import deque
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText


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
REFRESH_MS = int(os.environ.get("BOSS_MONITOR_REFRESH_MS", "3000") or "3000")
LOG_TAIL = int(os.environ.get("BOSS_MONITOR_LOG_TAIL", "140") or "140")
JOB_TAIL = int(os.environ.get("BOSS_MONITOR_JOB_TAIL", "25") or "25")
AI_TAIL = int(os.environ.get("BOSS_MONITOR_AI_TAIL", "20") or "20")
TODO_TAIL = int(os.environ.get("BOSS_MONITOR_TODO_TAIL", "30") or "30")


def read_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": str(exc)}
    return default


def tail_lines(path: Path, limit: int) -> list[str]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return [line.rstrip("\n") for line in deque(handle, maxlen=limit)]
    except Exception as exc:
        return [f"[tail error] {exc}"]


def recent_csv_rows(path: Path, limit: int) -> list[dict]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return list(deque(reader, maxlen=limit))
    except Exception as exc:
        return [{"时间": "", "公司": "", "职位": "", "状态": "error", "备注": str(exc)}]


def tail_jsonl(path: Path, limit: int) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in deque(handle, maxlen=limit):
                try:
                    rows.append(json.loads(line))
                except Exception:
                    rows.append({"raw": line[:240]})
    except Exception as exc:
        rows.append({"error": str(exc)})
    return rows


def load_jobs_summary() -> dict:
    rows = recent_csv_rows(DATA / "jobs_log.csv", 99999)
    stats = {"total": 0, "success": 0, "skipped": 0, "failed": 0}
    for row in rows:
        stats["total"] += 1
        status = row.get("状态", "")
        if status in stats:
            stats[status] += 1
    return stats


def load_conversations() -> dict:
    return read_json(DATA / "chat_states.json", {})


def build_todos(conversations: dict) -> list[dict]:
    todos = []
    if not isinstance(conversations, dict):
        return todos
    for key, row in conversations.items():
        extra = row.get("extra") or {}
        last_hr = row.get("last_hr_text") or ""
        my_last = row.get("my_last_reply") or ""
        stage = row.get("stage") or ""
        manual = bool(extra.get("manual_review_required"))
        if stage == "dead":
            continue
        needs_reply = bool(last_hr and row.get("last_hr_ts", "") >= row.get("my_last_ts", ""))
        resume_status = extra.get("resume_status", "")
        if needs_reply or not resume_status or manual:
            todos.append(
                {
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
                    "manual_reason": extra.get("manual_review_reason", ""),
                }
            )
    return sorted(todos, key=lambda x: x.get("updated_at", ""), reverse=True)[:TODO_TAIL]


def detect_runners() -> list[dict]:
    runners = []
    try:
        import psutil

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmd = " ".join(proc.info.get("cmdline") or [])
                if "boss-auto-apply" in cmd and "main.py" in cmd:
                    runners.append({"pid": proc.info.get("pid"), "cmd": cmd})
            except Exception:
                continue
    except Exception:
        pass
    return runners


def start_runner() -> tuple[bool, str]:
    runners = detect_runners()
    if runners:
        return False, f"already running: {', '.join(str(r.get('pid')) for r in runners)}"
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
        return True, "started main.py --apply-watch"
    except Exception as exc:
        return False, str(exc)


def stop_runner() -> tuple[bool, str]:
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
        return False, str(exc)
    try:
        import run_lock
        run_lock.release()
    except Exception:
        pass
    return True, "stopped " + (", ".join(stopped) if stopped else "none")


def open_dashboard() -> None:
    webbrowser.open("http://127.0.0.1:8765")


def safe_text(value) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        return str(value)


def clear_tree(tree: ttk.Treeview) -> None:
    for item in tree.get_children():
        tree.delete(item)


def fill_tree(tree: ttk.Treeview, rows: list[dict], columns: list[str], value_getter) -> None:
    clear_tree(tree)
    for idx, row in enumerate(rows):
        values = [str(value_getter(row, col) or "") for col in columns]
        tags = ()
        if row.get("manual_review"):
            tags = ("manual",)
        elif row.get("needs_reply"):
            tags = ("reply",)
        tree.insert("", "end", values=values, tags=tags)
    tree.tag_configure("manual", background="#fff1f2")
    tree.tag_configure("reply", background="#eff6ff")


class MonitorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("BOSS Auto Apply Monitor")
        self.geometry("1450x930")
        self.minsize(1220, 780)

        self.auto_top = tk.BooleanVar(value=False)
        self.last_refresh = tk.StringVar(value="-")
        self.stage_var = tk.StringVar(value="-")
        self.lock_var = tk.StringVar(value="-")
        self.runner_var = tk.StringVar(value="-")
        self.jobs_var = tk.StringVar(value="-")
        self.ai_var = tk.StringVar(value="-")
        self.todo_var = tk.StringVar(value="-")
        self.manual_var = tk.StringVar(value="-")
        self.action_var = tk.StringVar(value="")

        self._build_ui()
        self.after(300, self.refresh)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        top = ttk.Frame(self, padding=(12, 10))
        top.pack(fill="x")
        ttk.Label(top, text="BOSS Auto Apply Monitor", font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Label(top, textvariable=self.action_var, foreground="#0f766e").pack(side="right")

        actions = ttk.Frame(self, padding=(12, 0, 12, 8))
        actions.pack(fill="x")
        ttk.Button(actions, text="Start", command=self.start_worker).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Stop", command=self.stop_worker).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Open Dashboard", command=open_dashboard).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Refresh", command=self.refresh).pack(side="left", padx=(0, 6))
        ttk.Checkbutton(actions, text="Always on top", variable=self.auto_top, command=self._toggle_topmost).pack(side="left", padx=(12, 0))
        ttk.Label(actions, textvariable=self.last_refresh).pack(side="right")

        metrics = ttk.Frame(self, padding=(12, 0, 12, 8))
        metrics.pack(fill="x")
        self._metric(metrics, "Stage", self.stage_var, 0)
        self._metric(metrics, "Lock", self.lock_var, 1)
        self._metric(metrics, "Runner", self.runner_var, 2)
        self._metric(metrics, "Jobs", self.jobs_var, 3)
        self._metric(metrics, "AI", self.ai_var, 4)
        self._metric(metrics, "HR Todo", self.todo_var, 5)
        self._metric(metrics, "Manual", self.manual_var, 6)

        body = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=3)
        body.add(right, weight=5)

        self.status_text = ScrolledText(left, height=14, wrap="word", font=("Consolas", 10))
        self.status_text.pack(fill="both", expand=True)
        self.status_text.insert("end", "状态会在刷新后显示。\n")
        self.status_text.configure(state="disabled")

        notebook = ttk.Notebook(right)
        notebook.pack(fill="both", expand=True)

        self.jobs_tree = self._tree_tab(notebook, "Recent Jobs", ["时间", "公司", "职位", "状态", "备注"], [140, 180, 300, 90, 420])
        self.todo_tree = self._tree_tab(notebook, "HR Todo", ["状态", "公司", "HR", "岗位", "意图", "简历", "最后消息"], [90, 150, 110, 230, 120, 110, 380])
        self.ai_tree = self._tree_tab(notebook, "AI Calls", ["ts", "provider", "purpose", "status", "reply_preview"], [160, 110, 130, 90, 560])
        self.log_text = self._text_tab(notebook, "Run Log")

    def _metric(self, parent, label: str, var: tk.StringVar, column: int) -> None:
        box = ttk.Frame(parent, padding=8, relief="solid")
        box.grid(row=0, column=column, padx=5, sticky="nsew")
        parent.grid_columnconfigure(column, weight=1)
        ttk.Label(box, text=label, foreground="#64748b").pack(anchor="w")
        ttk.Label(box, textvariable=var, font=("Segoe UI", 13, "bold")).pack(anchor="w")

    def _tree_tab(self, notebook, title: str, columns: list[str], widths: list[int]) -> ttk.Treeview:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=title)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=14)
        for col, width in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor="w", stretch=True)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        return tree

    def _text_tab(self, notebook, title: str) -> ScrolledText:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=title)
        txt = ScrolledText(frame, wrap="word", font=("Consolas", 10))
        txt.pack(fill="both", expand=True)
        txt.configure(state="disabled")
        return txt

    def _set_text(self, widget: ScrolledText, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", value)
        widget.configure(state="disabled")

    def _toggle_topmost(self) -> None:
        self.attributes("-topmost", bool(self.auto_top.get()))

    def start_worker(self) -> None:
        ok, msg = start_runner()
        self.action_var.set(msg)
        if not ok:
            self.bell()

    def stop_worker(self) -> None:
        ok, msg = stop_runner()
        self.action_var.set(msg)
        if not ok:
            self.bell()

    def refresh(self) -> None:
        try:
            status = read_json(DATA / "apply_status.json", {})
            jobs_summary = load_jobs_summary()
            conversations = load_conversations()
            todos = build_todos(conversations)
            ai_calls = tail_jsonl(DATA / "ai_calls.jsonl", AI_TAIL)
            log_tail = tail_lines(DATA / "run.log", LOG_TAIL)
            runners = detect_runners()
            lock = read_json(DATA / "boss_monitor_state.json", {})

            self.stage_var.set(status.get("stage", "-") or "-")
            self.lock_var.set("running" if runners else "idle")
            self.runner_var.set(f"{len(runners)} active" if runners else "0 active")
            self.jobs_var.set(f"{jobs_summary['success']}/{jobs_summary['total']} success")
            self.ai_var.set(str(len(ai_calls)))
            self.todo_var.set(str(len([x for x in todos if x.get('needs_reply')])))
            self.manual_var.set(str(len([x for x in todos if x.get('manual_review')])))

            status_view = {
                "apply_status": status,
                "runner_processes": runners,
                "jobs_summary": jobs_summary,
                "todos_count": len(todos),
                "manual_review_count": len([x for x in todos if x.get("manual_review")]),
                "ai_calls_tail": ai_calls[:5],
            }
            self._set_text(self.status_text, safe_text(status_view))

            fill_tree(
                self.jobs_tree,
                recent_csv_rows(DATA / "jobs_log.csv", JOB_TAIL)[::-1],
                ["时间", "公司", "职位", "状态", "备注"],
                lambda row, col: row.get(col, ""),
            )
            fill_tree(
                self.todo_tree,
                todos,
                ["状态", "公司", "HR", "岗位", "意图", "简历", "最后消息"],
                lambda row, col: {
                    "状态": "人工" if row.get("manual_review") else ("待回复" if row.get("needs_reply") else "待确认"),
                    "公司": row.get("company", ""),
                    "HR": row.get("hr_name", ""),
                    "岗位": row.get("job_title", ""),
                    "意图": row.get("manual_reason", row.get("last_intent", "")),
                    "简历": row.get("resume_status", ""),
                    "最后消息": row.get("last_hr_text", "")[:120],
                }.get(col, ""),
            )
            fill_tree(
                self.ai_tree,
                ai_calls[::-1],
                ["时间", "Provider", "Purpose", "Status", "Preview"],
                lambda row, col: {
                    "时间": row.get("ts", ""),
                    "Provider": row.get("provider", ""),
                    "Purpose": row.get("purpose", ""),
                    "Status": row.get("status", ""),
                    "Preview": row.get("reply_preview", row.get("raw", "")),
                }.get(col, ""),
            )
            self._set_text(self.log_text, "\n".join(log_tail))
            self.last_refresh.set(f"Last refresh: {status.get('updated_at', '-')}")
        except Exception as exc:
            self.action_var.set(f"refresh error: {exc}")
            self._set_text(self.status_text, f"刷新失败: {exc}")
        finally:
            self.after(REFRESH_MS, self.refresh)


def main() -> int:
    app = MonitorApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
