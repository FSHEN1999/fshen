"""
Auto apply - send greeting message on BOSS zhipin
2025 behavior: clicking 立即沟通 auto-sends greeting and navigates to chat page.
No need to manually type/send a message.
"""
import time
import random
from anti_detect import random_delay, random_scroll
from candidate_profile import load_resume

# AI 生成招呼语（可选），失败 fallback 规则模板
try:
    from ai_reply import ai_generate, should_use_ai, ai_review_match
except Exception:
    def ai_generate(*a, **kw): return None
    def should_use_ai(*a, **kw): return False
    def ai_review_match(*a, **kw): return None

# JD-简历匹配打分，低分skip避免无脑海投
try:
    from jd_matcher import should_apply as jd_should_apply
except Exception:
    def jd_should_apply(*a, **kw): return (True, 100, "matcher unavailable")


class DailyCommunicationLimitReached(RuntimeError):
    """BOSS daily communication quota has been reached."""


def maybe_ai_override_match(job: dict, score: int, reason: str, min_score: int = 55, boundary_min: int = 45):
    """
    规则分略低时让 AI 二次判断是否值得投递。
    硬过滤永远不放行，避免前端/运维/产品等明显不匹配岗位被捞回来。
    """
    if score >= min_score or score < boundary_min:
        return None
    if "HARD_SKIP" in (reason or ""):
        return None
    if not should_use_ai("match_review"):
        return None
    review = ai_review_match(job, score=score, reason=reason, min_score=min_score)
    if not review:
        return None
    ai_reason = review.get("reason") or "AI二次判断"
    if review.get("apply"):
        return True, f"AI_REVIEW_PASS: {ai_reason}"
    return False, f"AI_REVIEW_SKIP: {ai_reason}"


class JobApplier:
    def __init__(self, page, config: dict, logger, dry_run: bool = False):
        self.page = page
        self.config = config
        self.logger = logger
        self.dry_run = dry_run

    def apply(self, job: dict) -> bool:
        title = job.get("title", "?")
        company = job.get("company", "?")
        url = job.get("url", "")

        print(f"  -> {company} - {title} ({job.get('salary', '')})")
        self.logger.update_status("OPEN_DETAIL", job=job, dry_run=self.dry_run)

        try:
            # Open job detail page
            self.page.get(url)
            random_delay(2, 4)

            # Check if redirected to login
            cur_url = self.page.url
            if "login" in cur_url.lower() or "web/user" in cur_url:
                print("    X need login")
                self.logger.log(job, "failed", "need login")
                return False

            # Check for security verification
            if self._check_verify():
                print("    ! security verify triggered, wait 30s...")
                time.sleep(30)
                self.page.get(url)
                random_delay(2, 4)

            # Simulate reading JD
            random_scroll(self.page)
            random_delay(1, 2)

            # 抓 JD 正文（用于 AI 生成招呼语/意图回复；失败不影响主流程）
            try:
                jd_text = ""
                for sel in [
                    "css:.job-sec-text",
                    "css:.job-detail-section .text",
                    "css:.job-detail .job-sec .text",
                    "css:div[class*='job-detail-section']",
                ]:
                    try:
                        el = self.page.ele(sel, timeout=1)
                        if el:
                            t = (el.text or "").strip()
                            if t and len(t) > len(jd_text):
                                jd_text = t
                    except Exception:
                        continue
                if jd_text:
                    job["jd"] = jd_text[:1500]
            except Exception:
                pass

            # 持久化 JD 到 data/jd_cache.json，聊天阶段可回查（即便对话页JD折叠）
            try:
                if job.get("jd"):
                    self._save_jd_cache(job)
            except Exception as _e:
                pass

            # === JD匹配分闸门 === 低分直接skip，避免海投+留坏印象
            try:
                min_score = int(self.config.get("match", {}).get("min_score", 55))
                go, score, reason = jd_should_apply(job, min_score=min_score)
                job["match_score"] = score
                job["match_reason"] = reason
                if not go:
                    ai_decision = maybe_ai_override_match(job, score, reason, min_score=min_score)
                    if ai_decision and ai_decision[0]:
                        go = True
                        reason = f"{reason} | {ai_decision[1]}"
                        job["match_reason"] = reason
                    elif ai_decision and not ai_decision[0]:
                        reason = f"{reason} | {ai_decision[1]}"
                        job["match_reason"] = reason
                    if go:
                        pass
                    else:
                        print(f"    skip (match_score={score}) {reason}")
                        self.logger.update_status("SKIPPED_LOW_MATCH", job=job, score=score, reason=reason, dry_run=self.dry_run)
                        self.logger.log(job, "skipped", f"low_match:{score}|{reason[:80]}")
                        return False
                if go:
                    print(f"    ✓ match_score={score} {reason[:100]}")
                    status = "MATCHED_AI_REVIEW" if "AI_REVIEW_PASS" in reason else "MATCHED"
                    self.logger.update_status(status, job=job, score=score, reason=reason, dry_run=self.dry_run)
            except Exception as _e:
                print(f"    ⚠ matcher error: {_e}, 继续投递")

            greeting = self._build_greeting(job)
            job["greeting_preview"] = greeting
            if self.dry_run:
                print("    [DRY-RUN] 不点击立即沟通，不发送消息/简历")
                print(f"    [DRY-RUN] 招呼语: {greeting}")
                self.logger.update_status("DRY_RUN_READY", job=job, greeting=greeting, dry_run=True)
                self.logger.log(job, "skipped", f"dry_run score={job.get('match_score', '')} greeting={greeting[:80]}")
                return True

            # Find chat button
            chat_btn = self._find_chat_button()
            if chat_btn is None:
                print("    skip (no chat btn / already chatted)")
                self.logger.log(job, "skipped", "no chat button")
                return False

            if chat_btn == "already_chatted":
                print("    skip (already chatted)")
                self.logger.log(job, "skipped", "already chatted")
                return False

            # Click 立即沟通 - BOSS auto-sends default greeting
            print("    clicking chat button...")
            chat_btn.click()
            random_delay(3, 5)

            limit_text = self._detect_daily_chat_limit()
            if limit_text:
                msg = f"daily communication limit reached: {limit_text[:80]}"
                print(f"    ⛔ 今日沟通上限已达，停止继续投递: {limit_text[:80]}")
                self.logger.update_status("DAILY_CHAT_LIMIT_REACHED", job=job, reason=limit_text, dry_run=self.dry_run)
                self.logger.log(job, "skipped", msg)
                self._confirm_limit_dialog()
                raise DailyCommunicationLimitReached(msg)

            cur_url = self.page.url
            entered_chat = ("chat" in cur_url or "message" in cur_url)

            if not entered_chat:
                try:
                    dialog = self.page.ele(".dialog-container", timeout=1)
                    if dialog:
                        entered_chat = True
                except:
                    pass

            if not entered_chat:
                print("    ⚠ 点击后未进入聊天页/确认弹窗，不能确认已发送简历")
                self.logger.log(job, "failed", "chat page not entered after click")
                return False

            # 进入了聊天页，发送自定义招呼语
            self._last_greeting_mode = None
            self.logger.update_status("CHAT_ENTERED", job=job, dry_run=self.dry_run)
            sent_ok = greeting and self._send_greeting(greeting)
            if sent_ok:
                self.logger.update_status("GREETING_SENT", job=job, greeting=greeting, dry_run=self.dry_run)
                mode = getattr(self, "_last_greeting_mode", None)
                if mode == "preset_plus_followup":
                    print(f"    OK! BOSS预设招呼+个性化追发 双发成功")
                elif mode == "preset_only":
                    print(f"    OK! BOSS预设招呼已发送（v3协议）")
                elif mode == "preset_confirmed":
                    print(f"    OK! BOSS 预设招呼语已确认发送")
                else:
                    print(f"    OK! custom greeting sent")

                final_note = f"{mode or 'custom greeting'}; resume=pending_hr_reply"
                self.logger.log(job, "success", final_note)
                self.logger.update_status("GREETING_SENT_WAIT_HR", job=job, note=final_note, dry_run=self.dry_run)
                print(f"    📎 简历暂不主动发送，等待HR回复后由聊天监听补发")
            else:
                # custom greeting 失败 — 依赖 BOSS 点击立即沟通时自带的默认招呼语
                # 注意：BOSS 是否真的自动发了默认招呼语取决于版本，可能是无声失败
                print(f"    ⚠ custom greeting FAILED, fallback to BOSS auto-greeting (may be silent fail)")
                self.logger.log(job, "failed", "custom greeting failed")
                return False
            return True

        except DailyCommunicationLimitReached:
            raise
        except Exception as e:
            print(f"    X error: {e}")
            self.logger.log(job, "failed", str(e)[:100])
            return False

    def _detect_daily_chat_limit(self) -> str:
        """Return limit dialog text when BOSS blocks new communication today."""
        limit_markers = ("无法进行沟通", "150位BOSS", "明天再来", "休息一下")
        selectors = ("css:.dialog-container", "css:.boss-dialog", "css:.dialog-wrap")
        for sel in selectors:
            try:
                dialog = self.page.ele(sel, timeout=0.5)
                if not dialog:
                    continue
                text = (dialog.text or "").strip()
                if text and any(marker in text for marker in limit_markers):
                    return " ".join(text.split())
            except Exception:
                continue
        try:
            body_text = (self.page.ele("tag:body", timeout=0.5).text or "").strip()
            if body_text and any(marker in body_text for marker in limit_markers):
                return " ".join(body_text.split())[:200]
        except Exception:
            pass
        return ""

    def _confirm_limit_dialog(self) -> None:
        """Close the quota dialog so the page is ready for chat polling."""
        for sel in ("text:确定", "css:.btn-sure", "css:.dialog-footer .btn"):
            try:
                btn = self.page.ele(sel, timeout=0.5)
                if btn:
                    try:
                        btn.click(by_js=True)
                    except Exception:
                        btn.click()
                    return
            except Exception:
                continue

    def _send_resume_if_possible(self) -> bool:
        """投递成功后尽量发送在线简历；返回是否确认已发/已存在。"""
        try:
            cur_url = self.page.url
            if "chat" not in cur_url and "message" not in cur_url:
                print("    ⚠ 当前不在聊天页，跳过自动发简历")
                return False
            from chat_actions import ChatActions
            actions = ChatActions(self.page)
            return bool(actions.send_online_resume())
        except Exception as _re:
            print(f"    ⚠ 简历推送异常: {_re}")
            return False

    def _find_chat_button(self):
        """Find the chat button. Returns element, 'already_chatted', or None."""
        # Primary: 立即沟通 (new contact)
        try:
            btn = self.page.ele("text:立即沟通", timeout=3)
            if btn:
                print("    found: 立即沟通")
                return btn
        except:
            pass

        # 继续沟通 = already contacted, skip
        try:
            btn = self.page.ele("text:继续沟通", timeout=1)
            if btn:
                print("    found: 继续沟通 (already contacted)")
                return "already_chatted"
        except:
            pass

        # 已沟通 = already contacted, skip
        try:
            btn = self.page.ele("text:已沟通", timeout=1)
            if btn:
                print("    found: 已沟通 (already contacted)")
                return "already_chatted"
        except:
            pass

        # CSS selectors fallback
        selectors = [
            ".btn-startchat",
            ".op-btn-chat",
        ]
        for sel in selectors:
            try:
                btn = self.page.ele(sel, timeout=1)
                if btn:
                    text = btn.text.strip()
                    print(f"    found btn: [{sel}] text='{text}'")
                    if "已" in text:
                        return "already_chatted"
                    return btn
            except:
                continue

        return None

    def _extract_jd_highlights(self, jd: str, tags) -> dict:
        """从 JD 文本+tags 提取关键技术栈+业务方向，用于生成个性化招呼语。"""
        jd_lower = (jd or "").lower()
        tags_str = " ".join(tags or []).lower() if tags else ""
        blob = f"{jd_lower} {tags_str}"

        # 技术栈关键词（按优先级匹配）
        tech_map = [
            ("测试开发", ["测试开发", "测开"]),
            ("测试负责人", ["测试负责人", "测试组长", "qa lead", "质量负责人"]),
            ("自动化测试", ["自动化测试", "自动化回归", "接口自动化"]),
            ("接口测试", ["接口测试", "api", "postman", "requests"]),
            ("Python", ["python", "pytest"]),
            ("Selenium", ["selenium", "web自动化"]),
            ("JMeter", ["jmeter", "性能测试", "压测"]),
            ("MySQL/SQL", ["mysql", "sql", "数据库校验", "数据一致性"]),
            ("Fiddler/抓包", ["fiddler", "抓包"]),
            ("Jenkins/CI", ["jenkins", "持续集成", "ci"]),
            ("金融/银行", ["金融", "银行", "支付", "贷款", "信贷", "跨境"]),
            ("数据迁移", ["数据迁移", "迁移测试", "客户迁移"]),
            ("AI Agent测试", ["ai agent", "agent", "智能体", "ai测试", "大模型测试"]),
        ]
        hits = []
        for name, kws in tech_map:
            for kw in kws:
                if kw in blob:
                    hits.append(name)
                    break
            if len(hits) >= 4:
                break

        # 业务方向
        domain = ""
        for d in ["金融", "银行", "贷款", "跨境", "数据迁移", "AI", "Agent", "质量"]:
            if d.lower() in blob:
                domain = d
                break

        return {"tech": hits, "domain": domain}

    def _build_greeting(self, job: dict) -> str:
        """根据职位信息构建个性化招呼语。
        优先 AI（基于 JD + 简历高亮），失败 fallback JD 驱动动态模板，再失败多模板，最后硬编码。
        """
        profile = load_resume()
        title = job.get("title", "测试开发")
        company = job.get("company", "")
        jd = job.get("jd", "") or ""
        tags = job.get("tags", []) or []

        # === AI 路径（greeting 意图）===
        if should_use_ai("greeting"):
            try:
                ai_text = ai_generate(
                    "greeting",
                    messages=[],
                    job_info={
                        "title": title,
                        "company": company,
                        "salary": job.get("salary", ""),
                        "jd": jd,
                        "tags": tags,
                    },
                )
                if ai_text and 10 <= len(ai_text) <= 200:
                    print(f"    🤖 AI 招呼语: {ai_text}")
                    return ai_text
            except Exception as e:
                print(f"    ! AI 招呼语失败 fallback 模板: {e}")

        # === JD 驱动的动态模板（AI 不可用/超时时）===
        try:
            hl = self._extract_jd_highlights(jd, tags)
            tech_hits = hl["tech"]
            domain = hl["domain"]

            if tech_hits:
                # 挑 1-2 个最相关技术词
                my_stack = []
                # 用户真实技能优先序
                my_skills_priority = [
                    "测试负责人", "测试开发", "自动化测试", "接口测试", "Python",
                    "Selenium", "JMeter", "MySQL/SQL", "金融/银行", "数据迁移", "AI Agent测试",
                    "Fiddler/抓包", "Jenkins/CI",
                ]
                for s in my_skills_priority:
                    if s in tech_hits and s not in my_stack:
                        my_stack.append(s)
                    if len(my_stack) >= 2:
                        break
                if not my_stack:
                    my_stack = tech_hits[:2]

                stack_str = "、".join(my_stack)
                # 用 job hash 选模板，保证同一职位稳定但不同职位多样
                import hashlib
                seed = int(hashlib.md5(f"{company}{title}".encode()).hexdigest()[:8], 16)
                templates = [
                    f"您好，看到{title}提到{stack_str}，我{profile['experience']}测试/质量工程经验，做过测试负责人，方便了解下岗位测试范围和团队分工吗？",
                    f"您好，{title}这个方向和我比较匹配。我有金融项目测试交付、接口自动化和数据一致性校验经验，{stack_str}这块也做过，方便进一步沟通吗？",
                    f"您好！看到JD里有{stack_str}，我做过测试计划、用例设计、缺陷闭环和上线验证，也维护过Python自动化回归脚本，想了解下当前质量建设重点。",
                    f"您好，我关注到贵司{title}岗位。我有测试负责人/测开经验，熟悉{stack_str}相关工作，最近也在结合AI/Agent做测试提效，方便聊聊吗？",
                ]
                chosen = templates[seed % len(templates)]
                print(f"    📝 JD驱动招呼: [{stack_str}] {chosen[:50]}...")
                return chosen
        except Exception as e:
            print(f"    ! JD驱动模板失败: {e}")

        # === 原多模板 fallback ===
        templates = self.config.get("greetings", [])
        if not templates:
            single = self.config.get("greeting", "")
            if single:
                templates = [single]

        if templates:
            template = random.choice(templates)
            return template.replace("{job_title}", title).replace("{company}", company)

        # 兜底
        return f"您好，关注到贵公司的{title}岗位，和我的测试开发/测试负责人方向比较匹配。我{profile['experience']}测试与质量工程经验，做过接口自动化、数据库一致性校验和上线质量把关，方便聊聊岗位细节吗？"

    def _send_chat_followup(self, text: str) -> bool:
        """在 chat 页追发一条个性化消息。调用前必须已进入 chat 页面。
        复用 chat_monitor.send_message 的多策略输入逻辑。
        """
        try:
            # 等 chat 页 DOM 稳定
            time.sleep(1.5)

            # 先等聊天消息区出现
            chat_area = None
            for _ in range(6):
                try:
                    chat_area = self.page.ele('.chat-message', timeout=1)
                    if chat_area:
                        break
                except Exception:
                    pass
                time.sleep(0.5)

            if chat_area:
                try:
                    chat_area.scroll.to_bottom()
                    time.sleep(0.3)
                except Exception:
                    pass

            # 找输入框 — chat 页 textarea 主力
            input_el = None
            for _ in range(6):
                try:
                    input_el = self.page.ele("tag:textarea", timeout=1)
                    if input_el:
                        break
                except Exception:
                    pass
                try:
                    input_el = self.page.ele("css:[contenteditable='true']", timeout=1)
                    if input_el:
                        break
                except Exception:
                    pass
                time.sleep(0.5)

            if not input_el:
                print(f"    ! 追发：未找到 chat 输入框")
                return False

            # JS 强制可见+聚焦
            try:
                input_el.run_js("""
                    this.style.display='block';this.style.visibility='visible';this.style.opacity='1';
                    this.scrollIntoView({block:'center'});this.focus();
                """)
                time.sleep(0.3)
            except Exception:
                pass

            # 输入
            try:
                input_el.click(by_js=True)
                time.sleep(0.3)
                try: input_el.clear()
                except Exception: pass
                input_el.input(text)
                time.sleep(0.6)
            except Exception as e1:
                # JS 兜底
                try:
                    escaped = text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
                    input_el.run_js(f"""
                        this.focus();this.value=`{escaped}`;
                        this.dispatchEvent(new Event('input',{{bubbles:true}}));
                        this.dispatchEvent(new Event('change',{{bubbles:true}}));
                    """)
                    time.sleep(0.6)
                except Exception as e2:
                    print(f"    ! 追发输入失败: {e1} / {e2}")
                    return False

            # 发送
            # 1) .btn-sure-v2
            try:
                send_btn = self.page.ele('.btn-sure-v2', timeout=2)
                if send_btn and "disabled" not in (send_btn.attr("class") or ""):
                    send_btn.click(by_js=True)
                    time.sleep(1)
                    return True
            except Exception:
                pass
            # 2) Enter
            try:
                from DrissionPage.common import Keys
                input_el.input(Keys.ENTER)
                time.sleep(1)
                return True
            except Exception:
                pass
            # 3) JS Enter
            try:
                input_el.run_js("""
                    this.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,bubbles:true}));
                """)
                time.sleep(1)
                return True
            except Exception as e:
                print(f"    ! 追发发送失败: {e}")
                return False
        except Exception as e:
            print(f"    ! 追发异常: {e}")
            return False

    def _send_greeting(self, text: str) -> bool:
        """在聊天页发送招呼语 — 对齐 chat_monitor.send_message 的成功策略"""
        try:
            preset_already_sent = False
            # 等聊天页/弹窗渲染完成（BOSS 点击立即沟通后有时是弹窗，有时是跳转）
            time.sleep(3)

            # ---- BOSS 2026-04 新流程：点"立即沟通"后出现"已向BOSS发送消息"确认弹窗 ----
            # DOM: <div class="dialog-container">
            #        <div class="dialog-title"><h3>已向BOSS发送消息</h3></div>
            #        <div class="dialog-con"><div class="greet-con">[账号预设招呼语]</div></div>
            #        <span class="btn btn-sure" ka="dialog_confirm">继续沟通</span>
            # 这里 BOSS 已经自动发了预设招呼语，但给了"继续沟通"按钮 → 点它进聊天页，追发个性化消息。
            post_send_dialog = None
            try:
                # 多选择器找这个 confirm dialog
                for dsel in ["css:.dialog-container", "css:.greet-pop", "css:.greet-boss-pop"]:
                    try:
                        d = self.page.ele(dsel, timeout=1.2)
                        if d:
                            # 必须含 greet-con（确认弹窗特征），否则是其他 dialog
                            gc = None
                            try:
                                gc = d.ele("css:.greet-con", timeout=0.5)
                            except Exception:
                                gc = None
                            if gc:
                                post_send_dialog = d
                                try:
                                    preset_txt = (gc.text or "").strip()[:80]
                                    if preset_txt:
                                        print(f"    → BOSS 已自动发送预设招呼语: {preset_txt}")
                                        preset_already_sent = True
                                except Exception:
                                    preset_already_sent = True
                                    pass
                                break
                    except Exception:
                        continue

                if post_send_dialog:
                    # 点"继续沟通" → 跳转 chat 页
                    confirm_btn = None
                    for sel in ["css:.btn-sure[ka='dialog_confirm']", "css:.btn-sure", "text:继续沟通"]:
                        try:
                            b = post_send_dialog.ele(sel, timeout=1)
                            if b:
                                confirm_btn = b
                                break
                        except Exception:
                            continue
                    if not confirm_btn:
                        # 兜底全局找
                        try:
                            confirm_btn = self.page.ele("text:继续沟通", timeout=1)
                        except Exception:
                            pass
                    if confirm_btn:
                        try:
                            confirm_btn.click(by_js=True)
                        except Exception:
                            try:
                                confirm_btn.click()
                            except Exception:
                                pass
                        time.sleep(3)  # 等 chat 页加载

                        # [2026-04-19 晚 v4] BOSS 预设发完后，继续追发一条 AI 个性化招呼
                        # 旧 v3 在进入 chat 页直接 return，浪费了生成的 greeting
                        # 现在 fall through 到下方输入框定位+发送逻辑，追发 greeting
                        cur_url = self.page.url
                        if "chat" in cur_url or "message" in cur_url:
                            print(f"    → 已进入聊天页 {cur_url[:80]}，准备追发个性化招呼")
                            # 不 return，继续走下面的输入框查找+发送逻辑
                        else:
                            # 没进聊天页，仅确认预设
                            self._last_greeting_mode = "preset_confirmed"
                            print(f"    OK! 预设招呼语已确认（未进 chat 页）")
                            return True
                    else:
                        print(f"    ! 确认弹窗内未找到「继续沟通」按钮")
            except Exception as ge:
                print(f"    ! 弹窗处理异常: {ge}")
                pass

            # 找输入框 — 选择器从宽到窄，对齐 chat_monitor 里已验证可用的路径
            input_sel = [
                "tag:textarea",                                  # chat_monitor 主力 selector
                "css:[contenteditable='true']",                  # chat_monitor 兜底 selector
                "css:div.chat-input div[contenteditable='true']",
                "css:div[contenteditable='true'].ql-editor",
                "css:div.input-area div[contenteditable='true']",
                "css:textarea.chat-input",
                "css:textarea[placeholder]",                      # 通用 textarea
            ]
            input_el = None
            matched_sel = None
            for sel in input_sel:
                try:
                    el = self.page.ele(sel, timeout=1.5)
                    if el:
                        input_el = el
                        matched_sel = sel
                        break
                except:
                    continue

            # ---- 弹窗路径：dialog 内部找输入框 ----
            if not input_el:
                dialog_selectors = [
                    ".dialog-container",
                    ".boss-dialog",
                    ".chat-dialog",
                    "[class*='dialog'][class*='chat']",
                    "[class*='start-chat']",
                    "[class*='dialog']",
                ]
                for dlg_sel in dialog_selectors:
                    try:
                        dlg = self.page.ele(dlg_sel, timeout=1)
                        if not dlg:
                            continue
                        print(f"    → 进入弹窗容器 [{dlg_sel}] 找输入框")
                        # 先等弹窗内部渲染
                        time.sleep(1)
                        for sel in input_sel:
                            try:
                                el = dlg.ele(sel, timeout=1.5)
                                if el:
                                    input_el = el
                                    matched_sel = f"{dlg_sel} > {sel}"
                                    break
                            except:
                                continue
                        if input_el:
                            break
                    except:
                        continue

            # ---- JS 兜底：直接查 DOM 最顶层可见 contentEditable ----
            if not input_el:
                try:
                    js_found = self.page.run_js("""
                        var els = document.querySelectorAll('[contenteditable="true"]');
                        for (var i = 0; i < els.length; i++) {
                            var r = els[i].getBoundingClientRect();
                            if (r.width > 0 && r.height > 0) return i;
                        }
                        return -1;
                    """)
                    if js_found is not None and js_found >= 0:
                        all_ce = self.page.eles("css:[contenteditable='true']")
                        if all_ce and int(js_found) < len(all_ce):
                            input_el = all_ce[int(js_found)]
                            matched_sel = f"js-visible-contenteditable[{js_found}]"
                            print(f"    → JS 兜底找到可见 contentEditable[{js_found}]")
                except Exception as je:
                    print(f"    ! JS 兜底失败: {je}")

            # ---- iframe 兜底：BOSS 弹窗聊天框可能嵌在 iframe 里 ----
            frame_input_el = None
            if not input_el:
                try:
                    iframes = self.page.eles("tag:iframe")
                    print(f"    → 主文档无输入框，尝试 iframe 遍历 (共 {len(iframes)} 个 iframe)")
                    for fi, ifr in enumerate(iframes):
                        try:
                            # 切到 iframe 上下文
                            frame = self.page.get_frame(ifr)
                            if not frame:
                                continue
                            for sel in input_sel:
                                try:
                                    el = frame.ele(sel, timeout=1)
                                    if el:
                                        # 可见性检查
                                        try:
                                            r = el.run_js("var r=this.getBoundingClientRect();return r.width>0&&r.height>0;")
                                        except Exception:
                                            r = True
                                        if r:
                                            input_el = el
                                            frame_input_el = frame  # 记下 frame，发送按钮也得在里面找
                                            matched_sel = f"iframe[{fi}] > {sel}"
                                            print(f"    → iframe[{fi}] 命中: {sel}")
                                            break
                                except Exception:
                                    continue
                            if input_el:
                                break
                        except Exception as fe:
                            print(f"    ! iframe[{fi}] 访问失败: {fe}")
                            continue
                except Exception as ife:
                    print(f"    ! iframe 兜底失败: {ife}")

            if not input_el:
                if preset_already_sent:
                    self._last_greeting_mode = "preset_only"
                    print("    → 已有BOSS预设招呼语，未找到输入框，跳过追发")
                    return True
                # 诊断日志：当前 URL + 可见 textarea/contenteditable 数量 + iframe 数
                try:
                    diag = self.page.run_js("""
                        var ta = document.querySelectorAll('textarea').length;
                        var ce = document.querySelectorAll('[contenteditable=\"true\"]').length;
                        var dlg = document.querySelectorAll('.dialog-container, .boss-dialog, [class*=\"dialog\"]').length;
                        var ifr = document.querySelectorAll('iframe').length;
                        return 'url=' + location.pathname + ' textarea=' + ta + ' contentEditable=' + ce + ' dialog=' + dlg + ' iframe=' + ifr;
                    """)
                    print(f"    ! 未找到输入框 [diag: {diag}]")
                    # 首次失败 dump HTML — 留一份方便下次 DOM 变了能肉眼看
                    try:
                        import os as _os, time as _time
                        from pathlib import Path as _P
                        dump_dir = _P(__file__).parent / "data" / "dom_dumps"
                        dump_dir.mkdir(parents=True, exist_ok=True)
                        # 只在目录文件少于 5 个时 dump，避免磁盘爆
                        if len(list(dump_dir.glob("*.html"))) < 5:
                            ts = _time.strftime("%Y%m%d_%H%M%S")
                            html = self.page.html
                            (dump_dir / f"greeting_fail_{ts}.html").write_text(html, encoding="utf-8")
                            print(f"    💾 DOM dump -> data/dom_dumps/greeting_fail_{ts}.html")
                    except Exception as de:
                        print(f"    ! DOM dump 失败: {de}")
                except Exception:
                    print(f"    ! 未找到输入框")
                return False

            # 记录是否在 iframe 上下文，后面发送按钮也得在 frame 里找
            self._greeting_frame = frame_input_el  # None = 主文档

            print(f"    ✓ 输入框命中: {matched_sel}")

            # 策略1: JS 强制可见 + 聚焦（对齐 chat_monitor 策略1）
            try:
                input_el.run_js("""
                    this.style.display = 'block';
                    this.style.visibility = 'visible';
                    this.style.opacity = '1';
                    this.scrollIntoView({block: 'center'});
                    this.focus();
                """)
                time.sleep(0.3)
            except:
                pass

            # 点击聚焦 + 输入
            try:
                input_el.click(by_js=True)
            except Exception:
                pass
            time.sleep(0.4)
            try:
                input_el.clear()
            except Exception:
                pass
            input_el.input(text)
            time.sleep(0.5)

            # 发送：优先点击发送按钮。BOSS 的 textarea/contenteditable 在部分页面里
            # Enter 会变成换行/草稿，随后切聊天页会触发“未处理提示框”。
            sent = False
            btn_ctx = getattr(self, "_greeting_frame", None) or self.page
            send_btn = self._find_greeting_send_button(btn_ctx)
            if send_btn:
                try:
                    send_btn.click(by_js=True)
                    sent = self._wait_greeting_sent(input_el, text)
                except Exception as e:
                    print(f"    ! 点击发送按钮失败: {e}")

            if not sent:
                try:
                    from DrissionPage.common import Keys
                    input_el.input(Keys.ENTER)
                    sent = self._wait_greeting_sent(input_el, text)
                    if not sent:
                        print("    ! Enter 后未确认发送成功，可能仍是草稿")
                except Exception as e:
                    print(f"    ! Enter 发送失败: {e}")

            if not sent:
                self._clear_greeting_draft(input_el)

            if sent:
                print(f"    ✅ 招呼语已发送")
                return True
            if preset_already_sent:
                self._last_greeting_mode = "preset_only"
                print("    → 已有BOSS预设招呼语，追发失败但不阻断投递")
                return True
            return False
        except Exception as e:
            print(f"    ! 发送招呼语失败: {e}")
            if getattr(self, "_last_greeting_mode", None) in ("preset_confirmed", "preset_only"):
                return True
            return False

    def _find_greeting_send_button(self, ctx):
        selectors = [
            "css:.btn-sure-v2",
            "css:.btn-sure",
            "css:button.send-btn",
            "css:.btn-send",
            "css:button[class*='send']",
            "css:button[class*='sure']",
            "text:发送",
        ]
        for selector in selectors:
            try:
                btn = ctx.ele(selector, timeout=1)
                if btn and "disabled" not in (btn.attr("class") or ""):
                    return btn
            except Exception:
                continue
        return None

    def _read_greeting_input(self, input_el) -> str:
        try:
            value = input_el.run_js(
                "return (this.value !== undefined ? this.value : (this.innerText || this.textContent || ''));"
            )
            return (value or "").strip()
        except Exception:
            try:
                return (input_el.text or "").strip()
            except Exception:
                return ""

    def _wait_greeting_sent(self, input_el, text: str, timeout: float = 4.0) -> bool:
        deadline = time.time() + timeout
        probe = (text or "").strip()[:24]
        while time.time() < deadline:
            time.sleep(0.4)
            if not self._read_greeting_input(input_el):
                return True
            if probe:
                try:
                    my_items = self.page.eles("css:li.item-myself", timeout=0.5)
                    for item in my_items[-5:]:
                        if probe in ((item.text or "").strip()):
                            return True
                except Exception:
                    pass
        return False

    def _clear_greeting_draft(self, input_el) -> None:
        try:
            input_el.clear()
            return
        except Exception:
            pass
        try:
            input_el.run_js(
                """
                if (this.value !== undefined) this.value = '';
                this.innerText = '';
                this.textContent = '';
                this.dispatchEvent(new Event('input', {bubbles: true}));
                this.dispatchEvent(new Event('change', {bubbles: true}));
                """
            )
        except Exception:
            pass

    def _check_verify(self) -> bool:
        try:
            verify_selectors = [
                ".verify-wrap",
                "#captcha",
                ".slide-verify",
                "iframe[src*='verify']",
                ".geetest_panel",
                ".nc-container",
            ]
            for sel in verify_selectors:
                if self.page.ele(sel, timeout=0.5):
                    return True
        except:
            pass
        return False

    def _save_jd_cache(self, job: dict):
        """把投递时抓到的 JD 持久化，聊天阶段可回查（company+title 索引）"""
        import json as _json
        from pathlib import Path as _P
        cache_path = _P(__file__).parent / "data" / "jd_cache.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if cache_path.exists():
            try:
                data = _json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        company = (job.get("company") or "").strip()
        title = (job.get("title") or "").strip()
        if not company or not title:
            return
        key = f"{company}||{title}"
        data[key] = {
            "company": company,
            "title": title,
            "salary": job.get("salary", ""),
            "location": job.get("location", ""),
            "tags": job.get("tags", []),
            "jd": (job.get("jd") or "")[:1500],
            "url": job.get("url", ""),
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        # 控制缓存上限：保留最近 500 条
        if len(data) > 500:
            items = sorted(data.items(), key=lambda kv: kv[1].get("ts", ""), reverse=True)[:500]
            data = dict(items)
        try:
            cache_path.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
