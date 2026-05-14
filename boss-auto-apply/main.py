"""
BOSS直聘自动投递工具 - 主入口
用法:
  python main.py --login     # 首次登录（扫码）
  python main.py --run       # 开始自动投递
  python main.py --report    # 查看投递报告
"""
import argparse
import io
import json
import os
import sys
import time
import yaml
from pathlib import Path
from file_ops import safe_write_json

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Also log to file for debugging
import logging
logging.raiseExceptions = False
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(message)s',
    handlers=[
        logging.FileHandler(str(Path(__file__).parent / "data" / "run.log"), encoding='utf-8', mode='a'),
        logging.StreamHandler(sys.stdout)
    ]
)
_log = logging.getLogger("boss")
# Monkey-patch print GLOBALLY so all modules log to file
import builtins
_orig_print = builtins.print
_in_patched_print = False
def _patched_print(*args, **kwargs):
    global _in_patched_print
    if _in_patched_print:
        kwargs.pop('flush', None)
        _orig_print(*args, flush=True, **kwargs)
        return
    _in_patched_print = True
    try:
        msg = " ".join(str(a) for a in args)
        try:
            _log.info(msg)
        except Exception:
            pass
    finally:
        _in_patched_print = False
    kwargs.pop('flush', None)
    _orig_print(*args, flush=True, **kwargs)
builtins.print = _patched_print
print = _patched_print

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.yaml"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def _runtime_dir() -> Path:
    raw = ""
    if os.name == "nt":
        raw = os.getenv("HERMES_BOSS_RUNTIME_DIR_WIN", "").strip()
    if not raw:
        raw = os.getenv("HERMES_BOSS_RUNTIME_DIR", "").strip()
    path = Path(raw) if raw else DATA_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _monitor_state_path() -> Path:
    return _runtime_dir() / "boss_monitor_state.json"


def _write_monitor_state(current_stage: str, **extra) -> None:
    payload = {
        "current_stage": current_stage,
        "last_progress_at": time.time(),
    }
    payload.update(extra)
    path = _monitor_state_path()
    safe_write_json(path, payload)

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def cmd_login():
    from auth import BossAuth
    auth = BossAuth(DATA_DIR)
    auth.login()

def cmd_run(limit: int | None = None, dry_run: bool = False, auth=None):
    from auth import BossAuth
    from search import JobSearcher
    from apply import DailyCommunicationLimitReached, JobApplier
    from logger import ApplyLogger
    from candidate_profile import missing_required_fields

    config = load_config()
    missing_profile = missing_required_fields()
    if missing_profile and not dry_run:
        print(f" 候选人画像未配置完整，拒绝真实投递: {', '.join(missing_profile)}")
        print(" 请先填写 .env.local.ps1，或先使用 --dry-run 预览。")
        return {"applied": 0, "summary": {"total": 0, "success": 0, "skipped": 0, "failed": 0}}

    auth = auth or BossAuth(DATA_DIR)
    
    if not auth.check_login():
        print(" 未登录或Cookie已失效，请先运行: python main.py --login")
        sys.exit(1)

    logger = ApplyLogger(DATA_DIR)
    logger.update_status("START", dry_run=dry_run, limit=limit)
    searcher = JobSearcher(auth.page, config)
    applier = JobApplier(auth.page, config, logger, dry_run=dry_run)

    total_applied = 0
    stop_reason = None
    daily_max = config["limits"]["daily_max"]
    target_max = min(daily_max, limit) if isinstance(limit, int) and limit > 0 else daily_max

    for keyword in config["search"]["keywords"]:
        if stop_reason:
            break
        if total_applied >= target_max:
            print(f" 已达本次投递上限 {target_max}，停止投递")
            break
        
        print(f"\n 搜索关键词: {keyword}")
        logger.update_status("SEARCHING", keyword=keyword, dry_run=dry_run, applied=total_applied, target=target_max)
        jobs = searcher.search(keyword)
        print(f"  找到 {len(jobs)} 个职位")
        logger.update_status("SEARCH_DONE", keyword=keyword, found=len(jobs), dry_run=dry_run, applied=total_applied, target=target_max)

        for job in jobs:
            if total_applied >= target_max:
                break
            if logger.is_applied(job["url"]):
                continue
            
            try:
                result = applier.apply(job)
            except DailyCommunicationLimitReached as exc:
                stop_reason = str(exc)
                print(f" 今日沟通上限已达，停止投递阶段，准备进入聊天轮询: {stop_reason}")
                logger.update_status("APPLY_STOPPED_DAILY_LIMIT", job=job, reason=stop_reason, dry_run=dry_run, applied=total_applied, target=target_max)
                break
            if result:
                total_applied += 1

    # 打印报告
    summary = logger.daily_summary()
    logger.update_status("DONE", dry_run=dry_run, applied=total_applied, summary=summary, stop_reason=stop_reason)
    print(f"\n 今日投递报告:")
    print(f"  投递: {summary['total']} | 成功: {summary['success']} | 跳过: {summary['skipped']} | 失败: {summary['failed']}")

    # [2026-04-20] 投递报告主动推飞书（hermes CLI 转发）
    try:
        if not dry_run:
            _push_feishu_report(summary, total_applied, logger)
    except Exception as _fe:
        print(f" ⚠ 飞书推送异常: {_fe}")

    return {"applied": total_applied, "summary": summary}


def _read_feishu_creds() -> tuple:
    """从 WSL 端 ~/.hermes/.env 读 FEISHU_APP_ID/SECRET。"""
    import subprocess
    wsl_exe = r"C:\Windows\System32\wsl.exe"
    try:
        if os.name == "nt" and os.path.exists(wsl_exe):
            r = subprocess.run([wsl_exe, "--", "bash", "-c",
                                "grep -E '^FEISHU_(APP_ID|APP_SECRET)=' /root/.hermes/.env"],
                               capture_output=True, text=True, timeout=10,
                               encoding="utf-8", errors="ignore")
            out = r.stdout
        else:
            from pathlib import Path as _P
            env_p = _P.home() / ".hermes" / ".env"
            out = env_p.read_text(encoding="utf-8") if env_p.exists() else ""
        app_id = app_secret = None
        for line in out.splitlines():
            if line.startswith("FEISHU_APP_ID="):
                app_id = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("FEISHU_APP_SECRET="):
                app_secret = line.split("=", 1)[1].strip().strip('"').strip("'")
        return app_id, app_secret
    except Exception:
        return None, None


def _push_feishu_report(summary: dict, total_applied: int, logger) -> None:
    """直接 POST 飞书 IM API 把投递报告发到 home channel。"""
    import urllib.request, urllib.error
    chan = os.environ.get("BOSS_FEISHU_CHAN", "oc_ad699ba9db6cd679b6a04a2cacd9c1e3")
    app_id, app_secret = _read_feishu_creds()
    if not (app_id and app_secret):
        print(" ⚠ 飞书凭证缺失，跳过推送")
        return
    # 拉今日投递明细（公司+岗位+分数）
    details = []
    try:
        today = time.strftime("%Y-%m-%d")
        log_file = Path(__file__).parent / "data" / f"apply_log_{today}.jsonl"
        if log_file.exists():
            for line in log_file.read_text(encoding="utf-8").splitlines():
                try:
                    rec = json.loads(line)
                    if rec.get("status") == "success":
                        details.append(f"· {rec.get('company','?')} / {rec.get('title','?')} ({rec.get('salary','?')}) — {rec.get('reason','')[:30]}")
                except Exception:
                    pass
    except Exception:
        pass

    msg_lines = [
        f"📮 BOSS投递完成报告 {time.strftime('%m-%d %H:%M')}",
        f"本次投递: {total_applied}",
        f"今日累计: 总{summary['total']} / 成功{summary['success']} / 跳过{summary['skipped']} / 失败{summary['failed']}",
        "",
    ]
    if details:
        msg_lines.append(f"✅ 成功投递 {len(details)} 家:")
        msg_lines.extend(details[:20])
        if len(details) > 20:
            msg_lines.append(f"… 另 {len(details)-20} 家")
    else:
        msg_lines.append("(无成功记录)")
    msg = "\n".join(msg_lines)

    # 1) 取 tenant_access_token
    try:
        req = urllib.request.Request(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            tok_data = json.loads(resp.read().decode("utf-8"))
        token = tok_data.get("tenant_access_token")
        if not token:
            print(f" ⚠ 取token失败: {tok_data}")
            return
    except Exception as e:
        print(f" ⚠ 取token异常: {e}")
        return

    # 2) 发消息
    try:
        body = {
            "receive_id": chan,
            "msg_type": "text",
            "content": json.dumps({"text": msg}, ensure_ascii=False),
        }
        req2 = urllib.request.Request(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=15) as resp:
            r_data = json.loads(resp.read().decode("utf-8"))
        if r_data.get("code") == 0:
            print(" ✅ 飞书推送成功")
        else:
            print(f" ⚠ 飞书返回: {r_data}")
    except Exception as e:
        print(f" ⚠ 飞书推送失败: {e}")

def cmd_report():
    from logger import ApplyLogger
    logger = ApplyLogger(DATA_DIR)
    logger.print_report()

def cmd_doctor():
    import doctor
    return doctor.main()

def cmd_chat(dry_run: bool = False, mode: str = "unread", auto_resume_on_hr_message: bool = False, auth=None):
    """扫描聊天并自动回复"""
    from auth import BossAuth
    from chat_processor import ChatProcessor
    from candidate_profile import missing_required_fields

    missing_profile = missing_required_fields()
    if missing_profile and not dry_run:
        print(f" 候选人画像未配置完整，拒绝真实自动回复: {', '.join(missing_profile)}")
        print(" 请先填写 .env.local.ps1，或先使用 --chat-dry 预览。")
        return {"scanned": 0, "replied": 0, "interviews": 0, "skipped": 0, "actions": 0}

    auth = auth or BossAuth(DATA_DIR)
    if not auth.check_login():
        print(" 未登录，请先运行: python main.py --login")
        sys.exit(1)

    processor = ChatProcessor(auth.page, DATA_DIR, dry_run=dry_run, auto_resume_on_hr_message=auto_resume_on_hr_message)
    return processor.run(mode=mode)

def cmd_resume_sweep(dry_run: bool = False, max_process: int = 200, auth=None):
    """扫描历史聊天，给有HR消息但没确认发过简历的会话补发在线简历。"""
    from auth import BossAuth
    from chat_processor import ChatProcessor
    from candidate_profile import missing_required_fields

    missing_profile = missing_required_fields()
    if missing_profile and not dry_run:
        print(f" 候选人画像未配置完整，拒绝真实补发简历: {', '.join(missing_profile)}")
        print(" 请先填写 .env.local.ps1，或先使用 --resume-sweep-dry 预览。")
        return {"scanned": 0, "replied": 0, "interviews": 0, "skipped": 0, "actions": 0}

    auth = auth or BossAuth(DATA_DIR)
    if not auth.check_login():
        print(" 未登录，请先运行: python main.py --login")
        sys.exit(1)

    processor = ChatProcessor(auth.page, DATA_DIR, dry_run=dry_run)
    return processor.sweep_missing_resumes(max_process=max_process)

def cmd_apply_then_watch(limit: int | None = None, interval: int = 180, rounds: int = 0, resume_sweep: bool = False):
    """循环执行：每轮投递一批，再处理未读聊天，等待 interval 秒后继续。"""
    import time
    from auth import BossAuth
    from logger import ApplyLogger

    logger = ApplyLogger(DATA_DIR)
    batch_limit = limit if isinstance(limit, int) and limit > 0 else 2
    logger.update_status("APPLY_WATCH_START", batch_limit=batch_limit, interval=interval, rounds=rounds)
    auth = BossAuth(DATA_DIR)
    if not auth.check_login():
        print(" 未登录，请先运行: python main.py --login")
        sys.exit(1)

    if resume_sweep:
        print("\n📎 === 启动兜底: 扫描历史聊天，补发漏掉的在线简历 ===")
        logger.update_status("APPLY_WATCH_RESUME_SWEEP", batch_limit=batch_limit, interval=interval, rounds=rounds)
        try:
            sweep_stats = cmd_resume_sweep(dry_run=False, max_process=200, auth=auth) or {}
            print(f"  简历补漏: scanned={sweep_stats.get('scanned',0)} actions={sweep_stats.get('actions',0)} skipped={sweep_stats.get('skipped',0)}")
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"  ⚠ 简历补漏异常，继续进入聊天轮询: {exc}")
            logger.update_status("RESUME_SWEEP_ERROR", error=str(exc), limit=limit, interval=interval, rounds=rounds)
        finally:
            try:
                if auth.recover_chat_page():
                    print("  ✅ 已恢复到聊天页，准备进入批量投递循环")
                else:
                    print("  ⚠ 聊天页恢复后未确认登录态，后续循环会再次校验")
            except Exception as exc:
                print(f"  ⚠ 聊天页恢复异常，后续循环会再次校验: {exc}")

    print(f"\n🚀 === 进入循环: 每轮投递 {batch_limit} 个，尽量清空全部未读聊天，然后等待 {interval} 秒 ===")
    current_round = 0
    total_applied = 0
    total_replied = 0
    total_actions = 0
    while True:
        if rounds and current_round >= rounds:
            break
        current_round += 1

        round_label = f"{current_round}{('/' + str(rounds)) if rounds else ''}"
        print(f"\n📦 === 循环 {round_label}: 投递阶段，目标 {batch_limit} 个 ===")
        logger.update_status(
            "APPLY_WATCH_ROUND_APPLY",
            round=current_round,
            batch_limit=batch_limit,
            interval=interval,
            rounds=rounds,
            total_applied=total_applied,
            total_replied=total_replied,
            total_actions=total_actions,
        )
        try:
            run_stats = cmd_run(limit=batch_limit, dry_run=False, auth=auth) or {}
            total_applied += int(run_stats.get("applied", 0) or 0)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"\n⚠ 本轮投递阶段停止/异常，继续进入聊天轮询: {exc}")
            logger.update_status(
                "APPLY_WATCH_APPLY_ERROR",
                round=current_round,
                error=str(exc),
                batch_limit=batch_limit,
                interval=interval,
                rounds=rounds,
                total_applied=total_applied,
                total_replied=total_replied,
                total_actions=total_actions,
            )

        print(f"\n💬 === 循环 {round_label}: 慢轮询未读聊天/HR新消息 ===")
        logger.update_status(
            "APPLY_WATCH_ROUND_CHAT",
            round=current_round,
            batch_limit=batch_limit,
            interval=interval,
            rounds=rounds,
            total_applied=total_applied,
            total_replied=total_replied,
            total_actions=total_actions,
        )
        try:
            stats = cmd_chat(dry_run=False, mode="unread", auto_resume_on_hr_message=True, auth=auth) or {}
            total_replied += int(stats.get("replied", 0) or 0)
            total_actions += int(stats.get("actions", 0) or 0)
            print(f"  本轮聊天: scanned={stats.get('scanned',0)} replied={stats.get('replied',0)} actions={stats.get('actions',0)} skipped={stats.get('skipped',0)}")
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"  ⚠ 聊天轮询异常: {exc}")
            logger.update_status(
                "APPLY_WATCH_CHAT_ERROR",
                round=current_round,
                error=str(exc),
                batch_limit=batch_limit,
                interval=interval,
                rounds=rounds,
                total_applied=total_applied,
                total_replied=total_replied,
                total_actions=total_actions,
            )

        if rounds and current_round >= rounds:
            break
        logger.update_status(
            "APPLY_WATCH_SLEEPING",
            round=current_round,
            next_round=current_round + 1,
            batch_limit=batch_limit,
            interval=interval,
            rounds=rounds,
            total_applied=total_applied,
            total_replied=total_replied,
            total_actions=total_actions,
        )
        print(f"  等待 {interval} 秒后继续下一轮投递...")
        time.sleep(interval)

    logger.update_status(
        "APPLY_WATCH_DONE",
        rounds=current_round,
        batch_limit=batch_limit,
        total_applied=total_applied,
        total_replied=total_replied,
        total_actions=total_actions,
    )
    print(f"\n✅ 循环结束。总计: 投递 {total_applied} | 自动回复 {total_replied} | 聊天动作 {total_actions}")

def cmd_chat_watch(interval: int = 180, rounds: int = 0):
    """只轮询未读聊天；HR有新消息时自动回复并补发简历，不新增投递。"""
    from auth import BossAuth
    from logger import ApplyLogger

    logger = ApplyLogger(DATA_DIR)
    auth = BossAuth(DATA_DIR)
    if not auth.check_login():
        print(" 未登录，请先运行: python main.py --login")
        sys.exit(1)

    current_round = 0
    print("\n💬 === 只轮询未读聊天，HR有新消息则发简历 ===")
    while True:
        if rounds and current_round >= rounds:
            break
        current_round += 1
        logger.update_status("WATCH_UNREAD_CHATS", round=current_round, interval=interval, rounds=rounds)
        print(f"\n--- 聊天轮询 {current_round}{('/' + str(rounds)) if rounds else ''} ---")
        try:
            stats = cmd_chat(dry_run=False, mode="unread", auto_resume_on_hr_message=True, auth=auth) or {}
            print(f"  本轮聊天: scanned={stats.get('scanned',0)} replied={stats.get('replied',0)} actions={stats.get('actions',0)} skipped={stats.get('skipped',0)}")
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"  ⚠ 聊天轮询异常: {exc}")
            logger.update_status("WATCH_ERROR", round=current_round, error=str(exc), interval=interval, rounds=rounds)
        if rounds and current_round >= rounds:
            break
        print(f"  等待 {interval} 秒后继续轮询...")
        time.sleep(interval)

def cmd_interviews():
    """查看面试安排"""
    from interview_mgr import InterviewManager
    mgr = InterviewManager(DATA_DIR)
    print(mgr.summary())

def cmd_full():
    """完整流程：投递 → 回复聊天"""
    print("\n🚀 === 第1步: 自动投递 ===")
    cmd_run()
    print("\n💬 === 第2步: 自动回复聊天 ===")
    cmd_chat(dry_run=False)
    print("\n📅 === 面试安排 ===")
    cmd_interviews()

def cmd_monitor(interval: int = 300, rounds: int = 5, sleep_minutes: int = 15, batch: int = 40):
    """持续监控模式：扫全量聊天 → 投递 → 处理未读 → 等待 → 循环"""
    from auth import BossAuth
    import signal

    config = load_config()
    auth = BossAuth(DATA_DIR)
    if not auth.check_login():
        print("❌ 未登录，请先运行: python main.py --login")
        sys.exit(1)

    running = True
    def _stop(sig, frame):
        nonlocal running
        print("\n⏹ 收到停止信号，完成当前轮次后退出...")
        running = False
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    round_num = 0
    applied_total = 0
    total_replies = 0
    total_interviews = 0
    max_rounds = rounds if isinstance(rounds, int) and rounds > 0 else 0

    print(f"\n🔄 === 全自动模式 === 每 {interval}秒 一轮（全量聊天 → 投递 → 未读聊天）")
    print(f"   最大轮次: {max_rounds or '无限'} | 单轮投递上限: {batch} | 按 Ctrl+C 优雅退出\n")
    _write_monitor_state(
        "monitor_start",
        session_key=os.getenv("HERMES_TEAM_SESSION_KEY", "").strip(),
        worker_name=os.getenv("HERMES_TEAM_WORKER_NAME", "").strip(),
        worker_session_id=os.getenv("HERMES_TEAM_WORKER_SESSION_ID", "").strip(),
        interval=interval,
        rounds=max_rounds,
        sleep_minutes=sleep_minutes,
        batch=batch,
        pid=os.getpid(),
    )

    # 连续轮次全挂的熔断计数
    consecutive_chrome_fail = 0
    FATAL_ERR_MARKERS = ("_dl_mgr", "连接已断开", "与页面的连接", "Connection closed", "no attribute")

    def _is_fatal_browser_err(err: Exception) -> bool:
        s = str(err)
        return any(m in s for m in FATAL_ERR_MARKERS)

    while running:
        if max_rounds and round_num >= max_rounds:
            break
        round_num += 1
        print(f"\n{'='*60}")
        print(f"🔄 第 {round_num} 轮 ({time.strftime('%H:%M:%S')})")
        print(f"{'='*60}")

        round_fatal = False
        print(f"\n💬 --- 全量聊天巡检阶段 ---")
        _write_monitor_state(
            f"round_{round_num}_chat_all",
            round=round_num,
            applied_total=applied_total,
            replied_total=total_replies,
            interview_total=total_interviews,
        )
        try:
            stats = cmd_chat(dry_run=False, mode="all") or {}
            total_replies += int(stats.get("replied", 0) or 0)
            total_interviews += int(stats.get("interviews", 0) or 0)
        except Exception as e:
            print(f"\n  ❌ 全量聊天巡检出错: {e}")
            if _is_fatal_browser_err(e):
                round_fatal = True
                print(f"  ⚠ 检测到浏览器致命错误，本轮剩余阶段跳过，等待下轮重建连接")

        if not running:
            break

        if not round_fatal:
            print(f"\n📋 --- 投递阶段 ---")
            _write_monitor_state(
                f"round_{round_num}_apply",
                round=round_num,
                applied_total=applied_total,
                replied_total=total_replies,
                interview_total=total_interviews,
            )
            try:
                run_stats = cmd_run(limit=batch) or {}
                applied_total += int(run_stats.get("applied", 0) or 0)
            except Exception as e:
                print(f"\n  ❌ 投递出错: {e}")
                if _is_fatal_browser_err(e):
                    round_fatal = True
                    print(f"  ⚠ 检测到浏览器致命错误，本轮剩余阶段跳过")

        if not running:
            break

        if not round_fatal:
            print(f"\n💬 --- 未读聊天处理阶段 ---")
            _write_monitor_state(
                f"round_{round_num}_chat_unread",
                round=round_num,
                applied_total=applied_total,
                replied_total=total_replies,
                interview_total=total_interviews,
            )
            try:
                stats = cmd_chat(dry_run=False, mode="unread") or {}
                total_replies += int(stats.get("replied", 0) or 0)
                total_interviews += int(stats.get("interviews", 0) or 0)
            except Exception as e:
                print(f"\n  ❌ 未读聊天处理出错: {e}")
                if _is_fatal_browser_err(e):
                    round_fatal = True

        if round_fatal:
            consecutive_chrome_fail += 1
            print(f"\n  🔥 浏览器故障轮次计数: {consecutive_chrome_fail}")
            if consecutive_chrome_fail >= 2:
                print(f"  💀 连续{consecutive_chrome_fail}轮浏览器致命错误，尝试 execv 自重启...")
                # 写一个哨兵文件，外层 runner 可以据此判断
                try:
                    _write_monitor_state(
                        "self_restart",
                        round=round_num,
                        reason="consecutive_browser_fatal",
                        applied_total=applied_total,
                        replied_total=total_replies,
                        interview_total=total_interviews,
                    )
                except Exception:
                    pass
                # 等 10 秒，让 Chrome 进程彻底释放
                time.sleep(10)
                try:
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                except Exception as e:
                    print(f"  ❌ execv 失败: {e}，退出由外层拉起")
                    break
        else:
            consecutive_chrome_fail = 0

        # --- 跟进引擎扫描（漏接告警每轮都扫，alerts 直推飞书） ---
        try:
            from followup_engine import sweep as _fu_sweep, format_report as _fu_report, write_alerts_to_log as _fu_alerts
            res = _fu_sweep(dry_run=False)
            if res.get("alerts") or res.get("nudges") or res.get("dead"):
                print(f"\n🔔 --- 跟进引擎 ---")
                print(_fu_report(res))
                _fu_alerts(res.get("alerts") or [])
                # 把漏接告警同步推飞书（不只写日志）
                try:
                    from notify_feishu import notify_alerts as _fs_alerts
                    _fs_alerts(res.get("alerts") or [])
                except Exception as _ne:
                    print(f"  ⚠ 飞书告警推送失败: {_ne}")
        except Exception as e:
            print(f"\n  ⚠ followup sweep 异常: {e}")

        # --- 每轮汇报飞书（不刷屏：只在有变化时推） ---
        try:
            from notify_feishu import notify_summary as _fs_sum
            _fs_sum({
                "round": round_num,
                "applied_total": applied_total,
                "replied_total": total_replies,
                "interview_total": total_interviews,
            })
        except Exception:
            pass

        print(f"\n📈 === 累计统计 ===")
        print(f"  投递: {applied_total} | 回复: {total_replies} | 面试: {total_interviews}")

        if running and (not max_rounds or round_num < max_rounds):
            _write_monitor_state(
                f"round_{round_num}_sleeping",
                round=round_num,
                applied_total=applied_total,
                replied_total=total_replies,
                interview_total=total_interviews,
            )
            print(f"\n⏳ 等待 {interval}秒 后下一轮...")
            for _ in range(interval):
                if not running:
                    break
                time.sleep(1)

    final_stage = "stopped" if not running else "completed"
    _write_monitor_state(
        final_stage,
        round=round_num,
        applied_total=applied_total,
        replied_total=total_replies,
        interview_total=total_interviews,
    )
    print(f"\n✅ 全自动模式结束。总计: 投递 {applied_total} | 回复 {total_replies} | 面试 {total_interviews}")

def main():
    parser = argparse.ArgumentParser(description="BOSS直聘自动求职助手")
    parser.add_argument("--login", action="store_true", help="登录（扫码）")
    parser.add_argument("--run", action="store_true", help="自动投递简历")
    parser.add_argument("--dry-run", action="store_true", help="投递预演：打开JD并生成招呼语，但不点击发送")
    parser.add_argument("--report", action="store_true", help="查看投递报告")
    parser.add_argument("--doctor", action="store_true", help="运行本地环境/AI/状态自检")
    parser.add_argument("--chat", action="store_true", help="扫描聊天并自动回复")
    parser.add_argument("--chat-dry", action="store_true", help="聊天预览模式（不实际发送）")
    parser.add_argument("--chat-all", action="store_true", help="处理全部聊天（含已读未回）")
    parser.add_argument("--chat-all-dry", action="store_true", help="全部聊天预览模式")
    parser.add_argument("--resume-sweep", action="store_true", help="扫描历史聊天，给有HR消息但未发简历的会话补发在线简历")
    parser.add_argument("--resume-sweep-dry", action="store_true", help="简历补漏预览模式，不实际发送")
    parser.add_argument("--interviews", action="store_true", help="查看面试安排")
    parser.add_argument("--full", action="store_true", help="完整流程（投递+回复+面试）")
    parser.add_argument("--monitor", action="store_true", help="持续监控聊天（每5分钟扫描）")
    parser.add_argument("--chat-watch", action="store_true", help="只轮询未读聊天；HR有新消息则发简历，不新增投递")
    parser.add_argument("--apply-watch", action="store_true", help="循环执行：每轮投递一批，然后轮询未读聊天；HR有消息则发简历")
    parser.add_argument("--with-resume-sweep", action="store_true", help="apply-watch 模式先扫描历史聊天补发简历（默认开启，保留兼容）")
    parser.add_argument("--no-resume-sweep", action="store_true", help="apply-watch 模式跳过历史补漏，只轮询未读聊天")
    parser.add_argument("--interval", type=int, default=300, help="监控间隔秒数（默认300）")
    parser.add_argument("--limit", type=int, default=None, help="本次最多投递数量（可选）")
    parser.add_argument("--rounds", type=int, default=5, help="monitor 模式最大轮次（默认5）")
    parser.add_argument("--sleep", type=int, default=15, help="monitor 模式轮次间隔分钟（兼容参数）")
    parser.add_argument("--batch", type=int, default=40, help="monitor 模式单轮投递上限（默认40）")
    args = parser.parse_args()

    if args.login:
        cmd_login()
    elif args.run:
        cmd_run(limit=args.limit, dry_run=args.dry_run)
    elif args.report:
        cmd_report()
    elif args.doctor:
        cmd_doctor()
    elif args.chat:
        cmd_chat(dry_run=False)
    elif args.chat_dry:
        cmd_chat(dry_run=True)
    elif args.chat_all:
        cmd_chat(dry_run=False, mode="all")
    elif args.chat_all_dry:
        cmd_chat(dry_run=True, mode="all")
    elif args.resume_sweep:
        cmd_resume_sweep(dry_run=False, max_process=args.limit or 200)
    elif args.resume_sweep_dry:
        cmd_resume_sweep(dry_run=True, max_process=args.limit or 200)
    elif args.interviews:
        cmd_interviews()
    elif args.full:
        cmd_full()
    elif args.monitor:
        cmd_monitor(interval=args.interval, rounds=args.rounds, sleep_minutes=args.sleep, batch=args.batch)
    elif args.chat_watch:
        cmd_chat_watch(interval=args.interval, rounds=args.rounds)
    elif args.apply_watch:
        resume_sweep = args.with_resume_sweep or not args.no_resume_sweep
        cmd_apply_then_watch(limit=args.limit, interval=args.interval, rounds=args.rounds, resume_sweep=resume_sweep)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
