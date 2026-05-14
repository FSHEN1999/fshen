"""
BOSS直聘 自动聊天处理
整合：聊天监控 + 智能回复 + 面试管理

用法:
  python main.py --chat          # 扫描聊天并自动回复
  python main.py --chat-dry      # 只扫描不发送（预览模式）
  python main.py --interviews    # 查看面试安排
"""
import time
import os
from datetime import datetime
from pathlib import Path
from chat_monitor import ChatMonitor
from reply_engine import classify_and_reply, RESUME
from reply_guard import sanitize_reply
from manual_review import assess_manual_review

# 附件简历PDF路径（环境变量覆盖 > 默认 D:/code/ai-hub/job-hunt/resume/）
# 说明：Windows Python 运行时用 Windows 路径；在 Linux/WSL 测试时用 /mnt/ 路径。
RESUME_FILE = os.environ.get(
    "BOSS_RESUME_FILE",
    str(Path(__file__).parent / "data" / "resume.pdf")
)
try:
    from conversation_state import get_state as _cs_get, update_state as _cs_update, chat_key as _cs_key
except Exception:
    def _cs_update(*a, **kw): return None
    def _cs_get(*a, **kw): return None
    def _cs_key(*a, **kw): return ""
from interview_mgr import InterviewManager, extract_interview_info
from chat_actions import ChatActions
from anti_detect import random_delay


class ChatProcessor:
    def __init__(self, page, data_dir: Path, dry_run: bool = False, auto_resume_on_hr_message: bool = False):
        self.page = page
        self.data_dir = data_dir
        self.dry_run = dry_run
        self.auto_resume_on_hr_message = auto_resume_on_hr_message
        self.monitor = ChatMonitor(page, data_dir)
        self.interview_mgr = InterviewManager(data_dir)
        self.actions = ChatActions(page)
        self.stats = {"scanned": 0, "replied": 0, "interviews": 0, "skipped": 0, "actions": 0}

    def _mark_resume_status(self, company: str, hr_name: str, job_title: str, status: str, note: str = ""):
        """Persist resume-send state so sweeps do not rely only on current DOM."""
        try:
            key = _cs_key(company, hr_name, job_title)
            extra = {
                "resume_status": status,
                "resume_status_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            if note:
                extra["resume_note"] = note[:160]
            _cs_update(
                key,
                company=company,
                hr_name=hr_name,
                job_title=job_title,
                extra=extra,
            )
        except Exception as exc:
            print(f"  ⚠ resume state update failed: {exc}")

    def _get_resume_status(self, company: str, hr_name: str, job_title: str) -> str:
        """Read persisted resume-send state for duplicate-action protection."""
        try:
            key = _cs_key(company, hr_name, job_title)
            state = _cs_get(key) or {}
            return str((state.get("extra") or {}).get("resume_status", "") or "")
        except Exception:
            return ""

    def _record_interview_invite(self, company: str, title: str, hr_name: str, raw_msg: str) -> None:
        """记录面试邀约；实战模式下同步飞书急推，重复邀约不重复推。"""
        iv_info = extract_interview_info(raw_msg)
        entry = self.interview_mgr.add(
            company=company,
            job=title,
            hr_name=hr_name,
            interview_type=iv_info.get("type", ""),
            time_str=iv_info.get("time", ""),
            location=iv_info.get("location", ""),
            raw_msg=raw_msg,
        )
        if entry.get("_duplicate"):
            return
        self.stats["interviews"] += 1
        if self.dry_run:
            return
        try:
            from notify_feishu import notify_interview as _fs_iv
            ok = _fs_iv(company, title, hr_name, iv_info.get("time", ""), iv_info.get("location", ""))
            if ok is False:
                print("  ⚠ 面试飞书提醒未发送成功")
        except Exception as exc:
            print(f"  ⚠ 面试飞书提醒失败: {exc}")

    def _recover_hidden_hr_preview(self, real_msgs: list, messages: list, preview: str) -> tuple[list, list, bool]:
        """If the rendered message list ends with me but list preview is HR text, retry then use preview as fallback."""
        if not real_msgs or real_msgs[-1].get("role") != "me":
            return real_msgs, messages, False
        my_last_txt = (real_msgs[-1].get("text") or "").strip()
        lp = (preview or "").strip()
        if not lp:
            return real_msgs, messages, False
        lp_core = lp.split("：", 1)[-1] if lp.startswith("我：") else lp
        preview_matches_mine = (
            lp_core and my_last_txt and (
                lp_core[:20] in my_last_txt or my_last_txt[:20] in lp_core
            )
        )
        if preview_matches_mine:
            return real_msgs, messages, False

        print(f"  🔄 preview({lp[:30]}) vs mine({my_last_txt[:30]}) 不一致，重读HR新消息")
        import time as _rt
        for retry in range(3):
            _rt.sleep(2.0)
            try:
                list_el = (
                    self.page.ele('.im-list', timeout=1) or
                    self.page.ele('.chat-record-box', timeout=1) or
                    self.page.ele('.im-message-list', timeout=1)
                )
                if list_el:
                    self.page.run_js('arguments[0].scrollTop = arguments[0].scrollHeight;', list_el)
            except Exception:
                pass
            messages2 = self.monitor.read_messages(limit=30)
            real_msgs2 = [m for m in (messages2 or []) if m.get("role") in ("me", "hr")]
            if real_msgs2 and real_msgs2[-1].get("role") == "hr":
                print(f"  ✅ 第{retry + 1}次重试读到 HR 新消息: {real_msgs2[-1].get('text','')[:40]}")
                return real_msgs2, messages2, True

        print(f"  ⚠ 重读3次仍未读到HR新消息，使用列表preview兜底: {lp[:40]}")
        fake_hr_msg = {"role": "hr", "text": lp_core or lp}
        return [*real_msgs, fake_hr_msg], [*(messages or []), fake_hr_msg], True

    def run(self, mode="unread"):
        """主流程：扫描 → 分析 → 回复
        mode: "unread" = 只处理未读(默认), "all" = 处理全部(包括已读未回)
        """
        print("\n" + "="*50)
        mode_label = "全部聊天" if mode == "all" else ("预览模式" if self.dry_run else "实战模式")
        print(f"🤖 BOSS直聘自动聊天 [{mode_label}]")
        print("="*50)

        if mode == "all":
            return self._run_all_chats()

        drain_round = 0
        max_drain_rounds = int(os.environ.get("BOSS_UNREAD_DRAIN_ROUNDS", "8") or "8")

        while True:
            # 1. 扫描聊天列表（获取数量信息）
            chats = self.monitor.scan_chats(max_chats=200)
            if not chats:
                if drain_round == 0:
                    print("\n没有需要处理的聊天")
                break

            drain_round += 1
            total = len(chats)
            use_click_first = getattr(self.monitor, '_switch_to_unread', False)
            processed_ids = set()  # 跟踪已处理的聊天ID，防止循环重复
            consecutive_skips = 0  # 连续跳过计数，防止死循环
            max_consecutive_skips = 3  # 连续3次重复就停止

            # 2. 逐个处理（未读tab模式 vs 传统模式）
            for i in range(total):
                if use_click_first:
                    # 未读tab模式：每次直接点击列表第一条（虚拟列表友好）
                    chat = self.monitor.click_first_chat()
                    if not chat:
                        print(f"\n--- [{i+1}/{total}] 无法打开第一条聊天，结束处理 ---")
                        break
                    # 防循环：检查是否已处理过
                    cid = chat.get("chat_id", "")
                    if cid in processed_ids:
                        consecutive_skips += 1
                        print(f"\n--- [{i+1}/{total}] {chat.get('name','?')}@{chat.get('company','?')} 已处理过，跳过 (连续重复{consecutive_skips}) ---")
                        if consecutive_skips >= max_consecutive_skips:
                            print(f"  ⚠ 连续{max_consecutive_skips}次重复，停止处理（可能已无新未读）")
                            break
                        # 回到聊天列表重新点未读tab
                        self.monitor.go_to_chat_page()
                        try:
                            unread_tab = self.monitor.page.ele('text:未读', timeout=3)
                            if unread_tab:
                                unread_tab.click()
                                random_delay(1, 2)
                        except:
                            pass
                        continue
                    consecutive_skips = 0  # 遇到新聊天，重置计数
                    processed_ids.add(cid)
                else:
                    chat = chats[i]

                self.stats["scanned"] += 1
                name = chat.get("name", "?")
                company = chat.get("company", "?")
                title = chat.get("title", "")

            print(f"\n--- [{i+1}/{total}] {name} @ {company} ({title}) ---")
            print(f"  最后消息: {chat.get('last_msg', '?')[:60]}")
            if chat.get("unread"):
                print(f"  🔴 未读: {chat.get('unread_count', '?')}条")

            if not use_click_first:
                # 传统模式：需要手动打开
                if not self.monitor.open_chat(chat):
                    print("  ⚠ 打开聊天失败，跳过")
                    self.stats["skipped"] += 1
                    self.monitor.go_to_chat_page()
                    continue

            # 读取消息
            messages = self.monitor.read_messages(limit=15)
            if not messages:
                print("  ⚠ 无法读取消息，跳过")
                self.stats["skipped"] += 1
                if use_click_first:
                    self._return_to_unread_list()
                continue

            # 打印消息历史
            print("  📨 消息记录:")
            for msg in messages[-5:]:
                if msg["role"] == "me":
                    role = "👤我"
                elif msg["role"] == "hr":
                    role = "👔HR"
                else:
                    role = "📌系统"
                print(f"    {role}: {msg['text'][:80]}")

            # 过滤掉系统消息后判断
            real_msgs = [m for m in messages if m["role"] in ("me", "hr")]
            if not real_msgs:
                print("  → 没有实际对话消息，跳过")
                self.stats["skipped"] += 1
                # 标记避免循环
                cid = chat.get("chat_id", "")
                if cid:
                    self.monitor.mark_replied(cid, "[无实际消息]")
                if use_click_first:
                    self._return_to_unread_list()
                continue

            # 检查最后一条是否是自己发的（已回复 or 需要 nudge 跟进）
            if real_msgs[-1]["role"] == "me":
                recovered_real, recovered_messages, recovered = self._recover_hidden_hr_preview(
                    real_msgs, messages, chat.get("last_msg", "")
                )
                if recovered:
                    real_msgs = recovered_real
                    messages = recovered_messages
                else:
                    # 判断是否该发 nudge 轻推
                    nudge_sent = False
                    try:
                        from followup_engine import NUDGE_TEMPLATES, mark_nudge_sent
                        from conversation_state import _load as _cs_load
                        _ck2 = _cs_key(company, name, title)
                        _st = _cs_load().get(_ck2, {})
                        _my_ts = _st.get("my_last_ts", "")
                        _nudge_cnt = int((_st.get("extra") or {}).get("nudge_count", 0))
                        if _my_ts and _nudge_cnt < 2:
                            from datetime import datetime
                            _dt = datetime.strptime(_my_ts, "%Y-%m-%d %H:%M:%S")
                            _idle_h = (time.time() - _dt.timestamp()) / 3600
                            _round = 0
                            if _nudge_cnt == 0 and _idle_h >= 24:
                                _round = 1
                            elif _nudge_cnt == 1 and _idle_h >= 72:
                                _round = 2
                            if _round and not self.dry_run:
                                nudge_text = NUDGE_TEMPLATES[_round]
                                print(f"  🔔 发 nudge R{_round} ({_idle_h:.1f}h): {nudge_text}")
                                if self.monitor.send_message(nudge_text):
                                    mark_nudge_sent(_ck2, _round)
                                    self.stats["replied"] = self.stats.get("replied", 0) + 1
                                    nudge_sent = True
                                    try:
                                        from notify_feishu import notify as _fs_n
                                        _fs_n(f"🔔 BOSS nudge R{_round} → {company}/{name}（静默{_idle_h:.1f}h）")
                                    except Exception:
                                        pass
                                    random_delay(3, 6)
                    except Exception as _ne:
                        print(f"  ⚠ nudge 判断失败: {_ne}")

                    if not nudge_sent:
                        print("  → 最后一条是自己发的，跳过")
                    self.stats["skipped"] += 1 if not nudge_sent else 0
                    # 标记已处理防止重复
                    cid = chat.get("chat_id", "")
                    if cid:
                        self.monitor.mark_replied(cid, real_msgs[-1]["text"])
                    # 未读tab模式：跳过也必须回列表+刷新，否则死循环同一个人
                    if use_click_first:
                        self._return_to_unread_list()
                    continue

            # 获取职位信息
            job_info = self.monitor.get_job_info()
            job_info["company"] = company
            job_info["title"] = title

            # 分类 + 生成回复
            result = classify_and_reply(real_msgs, job_info)
            intent = result["intent"]
            reply = result["reply"]
            actions = result.get("actions", [])
            reply, guard_notes = sanitize_reply(reply, intent=intent)
            if guard_notes:
                print(f"  🛡 回复校验: {', '.join(guard_notes)}")
            _hr_last = next((m["text"] for m in reversed(real_msgs) if m["role"] == "hr"), "")
            manual_review = assess_manual_review(intent, _hr_last, result.get("confidence", ""))
            if "manual_contact_info" in guard_notes:
                print("  → 回复包含联系方式/微信内容，改为人工接管")
                cid = chat.get("chat_id", "")
                if cid:
                    self.monitor.mark_replied(cid, real_msgs[-1]["text"])
                _ck = _cs_key(company, name, title)
                try:
                    extra = manual_review.as_extra()
                    extra.update({
                        "manual_review_required": True,
                        "manual_review_tag": "contact_reply_guard",
                        "manual_review_label": "联系方式回复",
                        "manual_review_risk": "medium",
                        "manual_review_action": "人工回复",
                        "manual_review_note": "待发送回复包含微信、电话或联系方式内容，已阻止自动发送。",
                    })
                    _cs_update(
                        _ck,
                        company=company,
                        hr_name=name,
                        job_title=title,
                        intent=intent,
                        last_hr_text=real_msgs[-1]["text"],
                        my_last_reply="",
                        extra=extra,
                    )
                except Exception as _e:
                    print(f"  ⚠ contact guard state update failed: {_e}")
                self.stats["skipped"] += 1
                if use_click_first:
                    self._return_to_unread_list()
                continue
            if manual_review.tag:
                print(f"  🏷 标签: {manual_review.label} / {manual_review.risk} / {manual_review.action}")
            if self.auto_resume_on_hr_message and real_msgs[-1]["role"] == "hr" and not manual_review.block_auto_actions:
                resume_actions = ["send_online_resume"]
                if os.environ.get("BOSS_ALLOW_UPLOAD_RESUME", "0") == "1":
                    resume_actions.append("upload_resume")
                resume_status = self._get_resume_status(company, name, title)
                resume_done = resume_status in {"confirmed_in_chat", "sent_by_sweep", "sent_by_chat_action"}
                extra_actions = [] if resume_done else [a for a in resume_actions if a not in actions]
                if extra_actions:
                    actions = [*actions, *extra_actions]
                    print("  📎 自动策略: HR有新消息，本轮追加发送简历动作")
                elif resume_done:
                    print(f"  📎 自动策略: 已记录简历状态={resume_status}，不重复发送")

            print(f"  🧠 意图: {intent} (置信度: {result['confidence']})")
            print(f"  💬 回复: {reply[:100]}")
            if actions:
                print(f"  ⚡ 动作: {', '.join(actions)}")

            # 写入对话状态机（HR最新消息+我的回复+意图推断阶段）
            _ck = _cs_key(company, name, title)
            try:
                _cs_update(
                    _ck, company=company, hr_name=name, job_title=title,
                    intent=intent, last_hr_text=_hr_last, my_last_reply=reply,
                    extra=manual_review.as_extra(),
                )
            except Exception as _e:
                print(f"  ⚠ state update failed: {_e}")

            # 面试邀约特殊处理
            if intent == "interview_invite":
                self._record_interview_invite(company, title, name, real_msgs[-1]["text"])

            # 高风险/低置信度场景：不自动回复，不执行动作，交给人工处理
            if manual_review.required:
                print(f"  → 命中人工接管: {manual_review.label}，静默跳过并标记人工处理")
                cid = chat.get("chat_id", "")
                if cid:
                    self.monitor.mark_replied(cid, real_msgs[-1]["text"])
                try:
                    _cs_update(
                        _ck,
                        company=company,
                        hr_name=name,
                        job_title=title,
                        intent=intent,
                        last_hr_text=real_msgs[-1]["text"],
                        my_last_reply="",
                        extra=manual_review.as_extra(),
                    )
                except Exception as _e:
                    print(f"  ⚠ manual review state update failed: {_e}")
                self.stats["skipped"] += 1
                continue

            # unknown意图且置信度低 + 消息太短 → 跳过
            if intent == "unknown" and result["confidence"] == "low":
                hr_msgs = [m for m in real_msgs if m["role"] == "hr"]
                if hr_msgs and len(hr_msgs[-1]["text"]) < 5:
                    print("  → 消息太短且意图不明，跳过")
                    self.stats["skipped"] += 1
                    cid = chat.get("chat_id", "")
                    if cid:
                        self.monitor.mark_replied(cid, hr_msgs[-1]["text"])
                    continue

            # 空回复 → 不发（hr_confirm等静默场景）
            if not reply or not reply.strip():
                print("  → 回复为空，静默跳过（如HR只回'好的'）")
                cid = chat.get("chat_id", "")
                hr_msgs_real = [m for m in real_msgs if m["role"] == "hr"]
                if cid and hr_msgs_real:
                    self.monitor.mark_replied(cid, hr_msgs_real[-1]["text"])
                self.stats["skipped"] += 1
                continue

            # 不回复拒绝消息（避免尴尬）
            if intent == "rejection":
                print("  → 对方拒绝，不回复")
                self.monitor.mark_replied(chat.get("chat_id", ""), real_msgs[-1]["text"])
                self.stats["skipped"] += 1
                continue

            # 不重复回复同一条HR消息
            cid = chat.get("chat_id", "")
            replied_info = self.monitor.state.get("replied", {}).get(cid, {})
            if replied_info and replied_info.get("last_msg", "") == real_msgs[-1]["text"][:100]:
                print("  → 已回复过相同消息，跳过")
                self.stats["skipped"] += 1
                continue

            # 空回复早退（system_noise / silent intent）：标记已处理，避免每轮重扫耗20s
            if not reply or not reply.strip():
                print(f"  ⏭️  静默意图 ({intent})，标记已读跳过")
                self.monitor.mark_replied(chat.get("chat_id", ""), real_msgs[-1]["text"])
                self.stats["skipped"] += 1
                continue

            # 发送回复
            if self.dry_run:
                print("  📝 [预览] 不实际发送")
                self.stats["replied"] += 1
            else:
                if self.monitor.send_message(reply):
                    self.monitor.mark_replied(
                        chat.get("chat_id", ""),
                        real_msgs[-1]["text"]
                    )
                    self.stats["replied"] += 1

                    # 执行附加动作（发简历、交换电话等）
                    if actions:
                        random_delay(2, 4)  # 发完消息等一下再执行动作
                        self._execute_actions(actions, name, company, title)
                else:
                    self.stats["skipped"] += 1

            # 反检测延迟
            random_delay(3, 6)

            # 未读tab模式：处理完后需要回到聊天列表，让未读列表刷新
            if use_click_first:
                self.monitor.go_to_chat_page()
                # 重新点击未读tab
                try:
                    unread_tab = self.monitor.page.ele('text:未读', timeout=3)
                    if unread_tab:
                        unread_tab.click()
                        random_delay(1, 2)
                except:
                    pass

            if not use_click_first:
                break
            if drain_round >= max_drain_rounds:
                print(f"  ⚠ 未读清空轮询达到上限 {max_drain_rounds} 轮，先结束本次处理")
                break

        # 打印汇总
        self._print_summary()
        return self.stats

    def sweep_missing_resumes(self, max_process: int = 200):
        """扫全部聊天：有HR真实消息但没确认发过简历的会话，补发在线简历。"""
        self.monitor.go_to_chat_page()
        try:
            all_tab = self.page.ele('text:全部', timeout=3)
            if all_tab:
                all_tab.click()
                random_delay(2, 3)
                print("  📌 已切换到「全部」列表")
        except Exception:
            print("  ⚠ 未找到「全部」tab，使用当前列表")

        processed_keys = set()
        consecutive_dup = 0
        scroll_rounds = 0
        max_scroll = 30

        print(f"\n📎 简历补漏扫描：最多处理 {max_process} 条聊天")
        while len(processed_keys) < max_process and scroll_rounds < max_scroll:
            items = self.page.eles('css:.friend-content-warp', timeout=5)
            new_this_round = 0

            for item in items:
                if len(processed_keys) >= max_process:
                    break
                name, company, title, last_msg = self._parse_chat_item(item)
                cid = f"{name}@{company}"
                if cid in processed_keys:
                    continue

                state_key = _cs_key(company, name, title)
                state = _cs_get(state_key) or {}
                resume_status = (state.get("extra") or {}).get("resume_status", "")
                if resume_status in {"confirmed_in_chat", "sent_by_sweep", "sent_by_chat_action"}:
                    processed_keys.add(cid)
                    self.stats["skipped"] += 1
                    print(f"\n--- [resume {len(processed_keys)}] {name} @ {company} ({title}) ---")
                    print(f"  → 状态机已记录简历状态={resume_status}，跳过")
                    continue

                new_this_round += 1
                processed_keys.add(cid)
                self.stats["scanned"] += 1
                print(f"\n--- [resume {len(processed_keys)}] {name} @ {company} ({title}) ---")
                print(f"  最后消息: {last_msg[:60]}")

                if not self._open_chat_item(item, name, company):
                    print("  ⚠ 打开聊天失败，跳过")
                    self.stats["skipped"] += 1
                    self._return_to_all_list()
                    continue

                messages = self.monitor.read_messages(limit=30)
                real_msgs = [m for m in (messages or []) if m.get("role") in ("me", "hr")]
                if not any(m.get("role") == "hr" for m in real_msgs):
                    print("  → 没有HR真实消息，跳过")
                    self.stats["skipped"] += 1
                    self._return_to_all_list()
                    continue

                try:
                    if self.actions._has_resume_in_chat():
                        print("  → 已有简历卡片，跳过")
                        self._mark_resume_status(company, name, title, "confirmed_in_chat", "resume card already exists")
                        self.stats["skipped"] += 1
                    elif self.dry_run:
                        print("  📝 [预览] 有HR消息但未发现简历卡片，会补发在线简历")
                        self._mark_resume_status(company, name, title, "pending_dry_run", "dry-run would send online resume")
                        self.stats["actions"] += 1
                    else:
                        ok = self.actions.send_online_resume()
                        if ok:
                            print(f"  ✅ 已补发在线简历给 {name}@{company}")
                            self._mark_resume_status(company, name, title, "sent_by_sweep", "online resume sent by resume sweep")
                            self.stats["actions"] += 1
                        else:
                            print("  ❌ 补发在线简历失败")
                            self._mark_resume_status(company, name, title, "send_failed", "online resume send failed during sweep")
                            self.stats["skipped"] += 1
                except Exception as e:
                    print(f"  ⚠ 简历补漏异常: {e}")
                    self._mark_resume_status(company, name, title, "error", str(e))
                    self.stats["skipped"] += 1

                self.actions._close_popup()
                random_delay(2, 4)
                self._return_to_all_list()

            if new_this_round == 0:
                consecutive_dup += 1
                if consecutive_dup >= 2:
                    print(f"  ✅ 连续{consecutive_dup}轮无新对话，列表到底，结束")
                    break
            else:
                consecutive_dup = 0

            scroll_rounds += 1
            try:
                self.monitor.dismiss_pending_alert()
                list_el = self.page.ele('css:.friend-list', timeout=2)
                if not list_el:
                    list_el = self.page.ele('css:[class*="chat-list"]', timeout=1)
                if list_el:
                    self.page.run_js('arguments[0].scrollTop += 3000', list_el)
                else:
                    self.page.run_js('window.scrollBy(0, 3000)')
                random_delay(1, 2)
            except Exception as e:
                if self.monitor.dismiss_pending_alert():
                    continue
                print(f"  (滚动失败: {e}，结束)")
                break

        self._print_summary()
        return self.stats

    def _parse_chat_item(self, item):
        try:
            name_el = item.ele('.name-text', timeout=0)
            name = name_el.text.strip() if name_el else "未知"
            name_box = item.ele('.name-box', timeout=0)
            company = ""
            title = ""
            if name_box:
                spans = name_box.eles('tag:span')
                company = spans[1].text.strip() if len(spans) > 1 else ""
                title = spans[2].text.strip() if len(spans) > 2 else ""
            msg_el = item.ele('.last-msg-text', timeout=0)
            last_msg = msg_el.text.strip() if msg_el else ""
            return name, company, title, last_msg
        except Exception:
            return "未知", "", "", ""

    def _open_chat_item(self, item, name: str, company: str) -> bool:
        import time as _click_time

        for attempt in range(3):
            try:
                if attempt > 0:
                    for candidate in self.page.eles('css:.friend-content-warp', timeout=3):
                        c_name, c_company, _, _ = self._parse_chat_item(candidate)
                        if c_name == name and c_company == company:
                            item = candidate
                            break
                fc = item.ele('.friend-content', timeout=0) or item
                try:
                    fc.click(by_js=True)
                except Exception:
                    fc.click()
                _click_time.sleep(2.5)
            except Exception as e:
                print(f"  ⚠ 点击失败(attempt {attempt + 1}): {e}")
                _click_time.sleep(1)
                continue

            url_now = self.page.url or ""
            has_input = False
            try:
                has_input = bool(
                    self.page.ele('tag:textarea', timeout=1) or
                    self.page.ele('[contenteditable="true"]', timeout=1)
                )
            except Exception:
                pass
            has_chat_area = False
            for sel in ['.im-list', '.chat-message', '.chat-conversation', '.chat-content-wrap']:
                try:
                    if self.page.ele(sel, timeout=0.5):
                        has_chat_area = True
                        break
                except Exception:
                    pass
            if has_input or has_chat_area or "boss_id" in url_now or "chat?encrypt" in url_now:
                return True
            print(f"  ⚠ 点击后未检测到聊天窗口(attempt {attempt + 1})，等待重试...")
            _click_time.sleep(2)
        return False

    def _run_all_chats(self):
        """处理全部聊天列表（包括已读未回），逐个点开"""
        self.monitor.go_to_chat_page()

        # 切到「全部」tab
        try:
            all_tab = self.page.ele('text:全部', timeout=3)
            if all_tab:
                all_tab.click()
                random_delay(2, 3)
                print("  📌 已切换到「全部」列表")
        except:
            print("  ⚠ 未找到「全部」tab，使用当前列表")

        # 收集可见聊天（虚拟列表：滚动翻页，最多处理200条）
        max_process = int(os.environ.get("BOSS_CHAT_MAX_PROCESS", "200") or "200")
        processed_keys = set()  # 已处理的 name@company，防重复
        consecutive_dup = 0     # 连续全重复轮数，判断列表到底了

        # 先获取一次，计算初始可见数
        chat_items = self.page.eles('css:.friend-content-warp', timeout=5)
        total_visible = len(chat_items)
        print(f"  初始可见聊天数: {total_visible}，最多处理 {max_process} 条")

        scroll_rounds = 0
        max_scroll = 30  # 最多滚动30次

        while len(processed_keys) < max_process and scroll_rounds < max_scroll:
            items = self.page.eles('css:.friend-content-warp', timeout=5)
            new_this_round = 0

            for item in items:
                if len(processed_keys) >= max_process:
                    break
                # 解析聊天项
                try:
                    name_el = item.ele('.name-text', timeout=0)
                    name = name_el.text.strip() if name_el else f"未知"
                    name_box = item.ele('.name-box', timeout=0)
                    company = ""
                    title = ""
                    if name_box:
                        spans = name_box.eles('tag:span')
                        company = spans[1].text.strip() if len(spans) > 1 else ""
                        title = spans[2].text.strip() if len(spans) > 2 else ""
                    msg_el = item.ele('.last-msg-text', timeout=0)
                    last_msg = msg_el.text.strip() if msg_el else ""
                except:
                    name = "未知"
                    company = ""
                    title = ""
                    last_msg = ""

                cid = f"{name}@{company}"

                # 已处理过本轮跳过（防虚拟列表重复出现同一条）
                if cid in processed_keys:
                    continue

                new_this_round += 1
                self.stats["scanned"] += 1
                total_processed = len(processed_keys)
                print(f"\n--- [{total_processed+1}] {name} @ {company} ({title}) ---")
                print(f"  最后消息: {last_msg[:60]}")

                # 列表预览已是我刚回复的内容 → 跳过（漏消息防御：只有确认匹配才跳）
                replied_info = self.monitor.state.get("replied", {}).get(cid, {})
                replied_last = replied_info.get("last_msg", "") if replied_info else ""
                if replied_last and last_msg and last_msg[:30] and last_msg[:30] in replied_last:
                    print(f"  → 列表预览已回复内容，跳过 ({last_msg[:30]})")
                    self.stats["skipped"] += 1
                    processed_keys.add(cid)
                    continue

                # 点击打开聊天 —— 带重试机制：最多3次，每次验证聊天窗口真的打开
                import time as _click_time
                click_ok = False
                for _click_attempt in range(3):
                    try:
                        # 重新获取item避免DOM刷新后引用失效
                        if _click_attempt > 0:
                            _all_items = self.page.eles('css:.friend-content-warp', timeout=3)
                            # 通过name+company重新匹配item
                            for _it in _all_items:
                                try:
                                    _n = (_it.ele('.name-text', timeout=0) or type('', (), {'text': ''})()).text.strip()
                                    _nb = _it.ele('.name-box', timeout=0)
                                    _spans = _nb.eles('tag:span') if _nb else []
                                    _c = _spans[1].text.strip() if len(_spans) > 1 else ''
                                    if _n == name and _c == company:
                                        item = _it
                                        break
                                except Exception:
                                    continue
                        fc = item.ele('.friend-content', timeout=0) or item
                        try:
                            fc.click(by_js=True)
                        except Exception:
                            fc.click()
                        _click_time.sleep(2.5)
                    except Exception as e:
                        print(f"  ⚠ 点击失败(attempt {_click_attempt+1}): {e}")
                        _click_time.sleep(1)
                        continue

                    # 验证聊天窗口真的打开：URL含boss_id 或 找到输入框
                    _url_now = self.page.url or ""
                    _has_input = False
                    try:
                        _has_input = bool(
                            self.page.ele('tag:textarea', timeout=1) or
                            self.page.ele('[contenteditable="true"]', timeout=1)
                        )
                    except Exception:
                        pass
                    _has_chat_area = False
                    for _sel in ['.im-list', '.chat-message', '.chat-conversation', '.chat-content-wrap']:
                        try:
                            if self.page.ele(_sel, timeout=0.5):
                                _has_chat_area = True
                                break
                        except Exception:
                            pass
                    if _has_input or _has_chat_area or "boss_id" in _url_now or "chat?encrypt" in _url_now:
                        click_ok = True
                        break
                    print(f"  ⚠ 点击后未检测到聊天窗口(attempt {_click_attempt+1})，等待重试...")
                    _click_time.sleep(2)

                if not click_ok:
                    print(f"  ⚠ 3次点击均未打开聊天窗口，跳过")
                    self.stats["skipped"] += 1
                    self._return_to_all_list()
                    processed_keys.add(cid)
                    continue

                # 等待聊天窗口加载（多候选选择器 + 更长超时，适配 BOSS 页面改版）
                chat_sel_candidates = [
                    '.chat-message', '.im-list', '.chat-content-wrap',
                    '.chat-conversation', '.message-controls',
                    '[class*="chat-content"]', '[class*="im-list"]',
                    '.chat-record', '.conversation-message',
                ]
                loaded_sel = None
                for sel in chat_sel_candidates:
                    try:
                        if self.page.ele(sel, timeout=1.2):
                            loaded_sel = sel
                            break
                    except Exception:
                        continue
                if not loaded_sel:
                    # 最后兜底：有 textarea 或 contenteditable 输入框也算窗口开了
                    try:
                        if self.page.ele('tag:textarea', timeout=1) or self.page.ele('[contenteditable="true"]', timeout=1):
                            loaded_sel = "(input-area fallback)"
                    except Exception:
                        pass
                if not loaded_sel:
                    print("  ⚠ 聊天窗口未加载，跳过")
                    # 一次性 dump 当前页面关键 class 用于诊断（只在首次跳过时 dump）
                    if not getattr(self, "_dumped_chat_dom", False):
                        try:
                            import json as _json
                            from pathlib import Path as _P
                            js = """
                            (() => {
                              const s = new Set();
                              for (const d of document.querySelectorAll('div[class]')) {
                                for (const c of d.className.split(/\\s+/)) {
                                  if (c && (c.includes('chat') || c.includes('im-') || c.includes('message') || c.includes('conversation'))) s.add(c);
                                }
                              }
                              return [...s].slice(0,80);
                            })()
                            """
                            val = self.page.run_js(js)
                            _P("data/chat_dom_dump.json").write_text(_json.dumps(val, ensure_ascii=False, indent=2), encoding="utf-8")
                            print(f"  📝 DOM class dump: data/chat_dom_dump.json")
                            self._dumped_chat_dom = True
                        except Exception as _e:
                            print(f"  (dom dump 失败: {_e})")
                    self.stats["skipped"] += 1
                    self._return_to_all_list()
                    continue
                if loaded_sel not in ('.chat-message', '.im-list'):
                    print(f"  ✓ 通过选择器识别聊天窗口: {loaded_sel}")
                    # 第一次成功打开新版 chat 窗口时，dump 一次 HTML 用于离线适配
                    if not getattr(self, "_dumped_chat_html", False):
                        try:
                            from pathlib import Path as _P
                            # 抓 .chat-conversation 的 outerHTML（限制大小）
                            html = self.page.run_js(
                                "return (document.querySelector('.chat-conversation')||document.body).outerHTML.slice(0,80000)"
                            )
                            _P("data/chat_html_dump.html").write_text(html or "", encoding="utf-8")
                            print(f"  📝 chat HTML dump (80KB cap): data/chat_html_dump.html")
                            self._dumped_chat_html = True
                        except Exception as _e:
                            print(f"  (html dump 失败: {_e})")
    
                # 读取消息
                messages = self.monitor.read_messages(limit=15)
                if not messages:
                    print("  ⚠ 无法读取消息，跳过")
                    self.stats["skipped"] += 1
                    self._return_to_all_list()
                    continue
    
                # 打印消息历史
                print("  📨 消息记录:")
                for msg in messages[-5:]:
                    if msg["role"] == "me":
                        role = "👤我"
                    elif msg["role"] == "hr":
                        role = "👔HR"
                    else:
                        role = "📌系统"
                    print(f"    {role}: {msg['text'][:80]}")
    
                # 过滤掉系统消息后判断
                real_msgs = [m for m in messages if m["role"] in ("me", "hr")]
                if not real_msgs:
                    print("  → 没有实际对话消息，跳过")
                    self.stats["skipped"] += 1
                    self.monitor.mark_replied(cid, "[无实际消息]")
                    self._return_to_all_list()
                    continue
    
                # 最后一条是自己发的→要和列表preview对齐才算真的"我回过了"
                # 若 preview 与我最后一条不一致，说明 HR 有新追问，read_messages漏读了 → 重试读一次
                if real_msgs[-1]["role"] == "me":
                    my_last_txt = (real_msgs[-1]["text"] or "").strip()
                    lp = (last_msg or "").strip()
                    # 剥掉preview里可能的"我："前缀，只比对正文
                    lp_core = lp.split("：", 1)[-1] if lp.startswith("我：") else lp
                    preview_matches_mine = (
                        lp_core and my_last_txt and (
                            lp_core[:20] in my_last_txt or my_last_txt[:20] in lp_core
                        )
                    )
                    if not preview_matches_mine and lp:
                        # preview 与我最后一条对不上 → HR 有新追问未渲染到
                        # 坑：message-item 虚拟滚动，新消息在底部可能没被渲染。
                        # 多轮重试：滚动到底部 + 重读，最多3次，每次2秒。
                        print(f"  🔄 preview({lp[:30]}) vs mine({my_last_txt[:30]}) 不一致，开始滚动重读")
                        import time as _rt
                        _got_hr = False
                        for _rtry in range(3):
                            _rt.sleep(2.0)
                            # 尝试把聊天窗口滚到底部,触发虚拟列表渲染
                            try:
                                _list_el = (self.page.ele('.im-list', timeout=1) or
                                            self.page.ele('.chat-record-box', timeout=1) or
                                            self.page.ele('.im-message-list', timeout=1))
                                if _list_el:
                                    self.page.run_js(
                                        'arguments[0].scrollTop = arguments[0].scrollHeight;',
                                        _list_el
                                    )
                            except Exception:
                                pass
                            messages2 = self.monitor.read_messages(limit=30)
                            real_msgs2 = [m for m in (messages2 or []) if m["role"] in ("me", "hr")]
                            if real_msgs2 and real_msgs2[-1]["role"] == "hr":
                                print(f"  ✅ 第{_rtry+1}次重试读到 HR 新消息: {real_msgs2[-1]['text'][:40]}")
                                real_msgs = real_msgs2
                                messages = messages2
                                _got_hr = True
                                break
                        if not _got_hr:
                            # 仍读不到 HR 消息，但 preview 明显不是我 → 用 preview 当作 HR 最后一条兜底
                            # 不再静默跳过，让AI基于preview内容生成回复，保证不漏消息
                            print(f"  ⚠ 滚动重读3次仍未读到HR新消息，使用preview兜底: {lp[:40]}")
                            fake_hr_msg = {"role": "hr", "text": lp_core or lp}
                            real_msgs = real_msgs + [fake_hr_msg]
                            messages = messages + [fake_hr_msg]
                    else:
                        print("  → 最后一条是自己发的（与preview一致），跳过")
                        self.stats["skipped"] += 1
                        self.monitor.mark_replied(cid, real_msgs[-1]["text"])
                        self._return_to_all_list()
                        continue
    
                # 获取职位信息
                job_info = self.monitor.get_job_info()
                job_info["company"] = company
                job_info["title"] = title
    
                # 分类 + 生成回复
                result = classify_and_reply(real_msgs, job_info)
                intent = result["intent"]
                reply = result["reply"]
                actions = result.get("actions", [])
                reply, guard_notes = sanitize_reply(reply, intent=intent)
                if guard_notes:
                    print(f"  🛡 回复校验: {', '.join(guard_notes)}")
                _hr_last = next((m["text"] for m in reversed(real_msgs) if m["role"] == "hr"), "")
                manual_review = assess_manual_review(intent, _hr_last, result.get("confidence", ""))
                if "manual_contact_info" in guard_notes:
                    print("  → 回复包含联系方式/微信内容，改为人工接管")
                    self.monitor.mark_replied(cid, real_msgs[-1]["text"])
                    _ck = _cs_key(company, name, title)
                    try:
                        extra = manual_review.as_extra()
                        extra.update({
                            "manual_review_required": True,
                            "manual_review_tag": "contact_reply_guard",
                            "manual_review_label": "联系方式回复",
                            "manual_review_risk": "medium",
                            "manual_review_action": "人工回复",
                            "manual_review_note": "待发送回复包含微信、电话或联系方式内容，已阻止自动发送。",
                        })
                        _cs_update(
                            _ck,
                            company=company,
                            hr_name=name,
                            job_title=title,
                            intent=intent,
                            last_hr_text=real_msgs[-1]["text"],
                            my_last_reply="",
                            extra=extra,
                        )
                    except Exception as _e:
                        print(f"  ⚠ contact guard state update failed: {_e}")
                    self.stats["skipped"] += 1
                    self._return_to_all_list()
                    continue
                if manual_review.tag:
                    print(f"  🏷 标签: {manual_review.label} / {manual_review.risk} / {manual_review.action}")
    
                print(f"  🧠 意图: {intent} (置信度: {result['confidence']})")
                print(f"  💬 回复: {reply[:100]}")
                if actions:
                    print(f"  ⚡ 动作: {', '.join(actions)}")
    
                # 写入对话状态机
                _ck = _cs_key(company, name, title)
                try:
                    _cs_update(
                        _ck, company=company, hr_name=name, job_title=title,
                        intent=intent, last_hr_text=_hr_last, my_last_reply=reply,
                        extra=manual_review.as_extra(),
                    )
                except Exception as _e:
                    print(f"  ⚠ state update failed: {_e}")
    
                # 面试邀约特殊处理
                if intent == "interview_invite":
                    self._record_interview_invite(company, title, name, real_msgs[-1]["text"])

                if manual_review.required:
                    print(f"  → 命中人工接管: {manual_review.label}，静默跳过并标记人工处理")
                    self.monitor.mark_replied(cid, real_msgs[-1]["text"])
                    try:
                        _cs_update(
                            _ck,
                            company=company,
                            hr_name=name,
                            job_title=title,
                            intent=intent,
                            last_hr_text=real_msgs[-1]["text"],
                            my_last_reply="",
                            extra=manual_review.as_extra(),
                        )
                    except Exception as _e:
                        print(f"  ⚠ manual review state update failed: {_e}")
                    self.stats["skipped"] += 1
                    self._return_to_all_list()
                    continue
    
                # 不回复拒绝消息
                if intent == "rejection":
                    print("  → 对方拒绝，不回复")
                    self.monitor.mark_replied(cid, real_msgs[-1]["text"])
                    self.stats["skipped"] += 1
                    self._return_to_all_list()
                    continue
    
                # unknown意图且置信度低 + 消息太短 → 跳过
                if intent == "unknown" and result["confidence"] == "low":
                    hr_msgs = [m for m in real_msgs if m["role"] == "hr"]
                    if hr_msgs and len(hr_msgs[-1]["text"]) < 5:
                        print("  → 消息太短且意图不明，跳过")
                        self.stats["skipped"] += 1
                        self.monitor.mark_replied(cid, hr_msgs[-1]["text"])
                        self._return_to_all_list()
                        continue
    
                # 空回复早退（system_noise / silent intent）
                if not reply or not reply.strip():
                    print(f"  ⏭️  静默意图 ({intent})，标记已读跳过")
                    self.monitor.mark_replied(cid, real_msgs[-1]["text"])
                    self.stats["skipped"] += 1
                    processed_keys.add(cid)
                    self._return_to_all_list()
                    continue
    
                # 发送回复
                if self.dry_run:
                    print("  📝 [预览] 不实际发送")
                    self.stats["replied"] += 1
                else:
                    if self.monitor.send_message(reply):
                        self.monitor.mark_replied(cid, real_msgs[-1]["text"])
                        self.stats["replied"] += 1
    
                        # 执行附加动作
                        if actions:
                            random_delay(2, 4)
                        self._execute_actions(actions, name, company, title)
                    else:
                        self.stats["skipped"] += 1
    
                processed_keys.add(cid)
                random_delay(3, 6)
    
                # 回到全部列表
                self._return_to_all_list()

            # --- 虚拟列表滚动翻页 ---
            if new_this_round == 0:
                consecutive_dup += 1
                if consecutive_dup >= 2:
                    print(f'  ✅ 连续{consecutive_dup}轮无新对话，列表到底，结束')
                    break
            else:
                consecutive_dup = 0

            scroll_rounds += 1
            try:
                list_el = self.page.ele('css:.friend-list', timeout=2)
                if not list_el:
                    list_el = self.page.ele('css:[class*="chat-list"]', timeout=1)
                if list_el:
                    self.page.run_js('arguments[0].scrollTop += 3000', list_el)
                else:
                    self.page.run_js('window.scrollBy(0, 3000)')
                random_delay(1, 2)
            except Exception as _se:
                print(f'  (滚动失败: {_se}，结束)')
                break


        # 打印汇总
        self._print_summary()
        return self.stats

    def _return_to_all_list(self):
        """回到全部聊天列表"""
        self.monitor.go_to_chat_page()
        try:
            all_tab = self.page.ele('text:全部', timeout=3)
            if all_tab:
                all_tab.click()
                random_delay(1, 2)
        except:
            pass

    def _return_to_unread_list(self):
        """处理完/跳过后回到未读聊天列表"""
        self.monitor.go_to_chat_page()
        try:
            unread_tab = self.monitor.page.ele('text:未读', timeout=3)
            if unread_tab:
                unread_tab.click()
                random_delay(1, 2)
        except:
            pass

    def _print_summary(self):
        s = self.stats
        print(f"\n{'='*50}")
        print(f"📊 聊天处理汇总:")
        print(f"  扫描: {s['scanned']} | 回复: {s['replied']} | 面试: {s['interviews']} | 动作: {s['actions']} | 跳过: {s['skipped']}")

        upcoming = self.interview_mgr.get_upcoming()
        if upcoming:
            print(f"\n📅 待处理面试 ({len(upcoming)}个):")
            for iv in upcoming:
                print(f"  ⏳ {iv['company']} - {iv['job']} {iv.get('type', '')} {iv.get('time', '')}")
        print("="*50)

    def _execute_actions(self, actions: list, hr_name: str, company: str, job_title: str = ""):
        """执行聊天动作（发简历、交换联系方式等）"""
        # 先检查并处理HR主动发的请求卡片（同意简历/发送联系方式）
        try:
            status = self.actions.check_already_exchanged()
            if status.get("resume_requested"):
                ok = self.actions.accept_resume_request()
                if ok:
                    print(f"    ✅ 已同意 {hr_name}@{company} 的简历请求")
                    self.stats["actions"] += 1
                self.actions._close_popup()
                random_delay(1, 2)
            # 检查HR发的联系方式交换卡片
            ok = self.actions.accept_contact_request()
            if ok:
                print(f"    ✅ 已响应 {hr_name}@{company} 的联系方式请求")
                self.stats["actions"] += 1
                self.actions._close_popup()
                random_delay(1, 2)
        except Exception as e:
            print(f"    ⚠ 处理HR请求卡片异常: {e}")

        for action in actions:
            print(f"  ⚡ 执行动作: {action}")
            try:
                if action == "send_online_resume":
                    resume_status = self._get_resume_status(company, hr_name, job_title)
                    if resume_status in {"confirmed_in_chat", "sent_by_sweep", "sent_by_chat_action"}:
                        print(f"    ℹ 已记录简历状态={resume_status}，跳过重复发送")
                        continue
                    # 先检查是否已交换过
                    ok = self.actions.send_online_resume()
                    if ok:
                        print(f"    ✅ 已向 {hr_name}@{company} 发送在线简历")
                        self._mark_resume_status(company, hr_name, job_title, "sent_by_chat_action", "online resume sent by chat action")
                        self.stats["actions"] += 1
                    else:
                        print(f"    ❌ 发送在线简历失败")
                        self._mark_resume_status(company, hr_name, job_title, "send_failed", "online resume send failed during chat action")

                elif action == "upload_resume":
                    # 附件PDF（走"上传简历"入口）
                    if os.environ.get("BOSS_ALLOW_UPLOAD_RESUME", "0") != "1":
                        print("    ⏭ 附件简历默认关闭，设置 BOSS_ALLOW_UPLOAD_RESUME=1 后才上传")
                    elif not os.path.exists(RESUME_FILE):
                        print(f"    ⚠ 附件简历文件不存在，跳过: {RESUME_FILE}")
                    else:
                        ok = self.actions.upload_resume(RESUME_FILE)
                        if ok:
                            print(f"    ✅ 已向 {hr_name}@{company} 发送附件简历")
                            self.stats["actions"] += 1
                        else:
                            print(f"    ❌ 发送附件简历失败")

                elif action == "exchange_phone":
                    exchanged = self.actions.check_already_exchanged()
                    if exchanged.get("phone_exchanged"):
                        print(f"    ℹ 已交换过电话，跳过")
                    else:
                        ok = self.actions.exchange_phone()
                        if ok:
                            print(f"    ✅ 已向 {hr_name}@{company} 发起电话交换")
                            self.stats["actions"] += 1
                        else:
                            print(f"    ❌ 交换电话失败")

                elif action == "exchange_wechat":
                    exchanged = self.actions.check_already_exchanged()
                    if exchanged.get("wechat_exchanged"):
                        print(f"    ℹ 已交换过微信，跳过")
                    else:
                        ok = self.actions.exchange_wechat()
                        if ok:
                            print(f"    ✅ 已向 {hr_name}@{company} 发起微信交换")
                            self.stats["actions"] += 1
                        else:
                            print(f"    ❌ 交换微信失败")

                else:
                    print(f"    ⚠ 未知动作: {action}")

            except Exception as e:
                print(f"    ❌ 动作执行异常: {e}")

            # 关闭可能残留的弹窗，防止影响下一个动作
            self.actions._close_popup()
            random_delay(1, 3)
