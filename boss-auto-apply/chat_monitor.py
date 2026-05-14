"""
BOSS直聘 聊天监控模块
- 扫描聊天列表，找到未读/新消息
- 读取HR消息内容
- 发送回复

DOM结构（2025-04实测）:
  聊天列表: .friend-content-warp > .friend-content
  聊天名: .name-text
  未读: .notice-badge
  最后消息: .last-msg-text
  
  消息区域: .chat-message > ul.im-list > li.message-item
  自己: .item-myself
  对方: .item-friend
  文本: .text p span
  时间: .item-time .time
"""
import time
import json
import re
import os
from pathlib import Path
from datetime import datetime
from anti_detect import random_delay
try:
    from candidate_profile import load_resume
except Exception:
    def load_resume():
        return {"name": ""}


class ChatMonitor:
    CHAT_URL = os.environ.get("BOSS_CHAT_URL", "https://www.zhipin.com/web/geek/chat")
    CHAT_STATE_FILE = "chat_state.json"

    def __init__(self, page, data_dir: Path):
        self.page = page
        self.data_dir = data_dir
        self.state_path = data_dir / self.CHAT_STATE_FILE
        self.state = self._load_state()

    def _load_state(self) -> dict:
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {"replied": {}, "last_scan": None}

    def _save_state(self):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def mark_replied(self, chat_id: str, last_msg: str):
        self.state["replied"][chat_id] = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_msg": last_msg[:100]
        }
        self._save_state()

    def dismiss_pending_alert(self) -> bool:
        """Close a browser alert left by BOSS so navigation/scrolling can continue."""
        dismissed = False
        try:
            for _ in range(3):
                text = self.page.handle_alert(accept=True, timeout=0.5)
                if text is False or text is None:
                    break
                print(f"  已关闭页面提示框: {str(text)[:80]}")
                dismissed = True
        except Exception:
            pass
        return dismissed

    def _safe_get(self, url: str) -> None:
        try:
            self.page.get(url)
            return
        except Exception:
            if self.dismiss_pending_alert():
                self.page.get(url)
                return
            raise

    def go_to_chat_page(self):
        """确保在聊天页面"""
        self.dismiss_pending_alert()
        if "/web/chat/" not in (self.page.url or ""):
            self._safe_get(self.CHAT_URL)
            random_delay(4, 6)
        else:
            random_delay(1, 2)
        self.dismiss_pending_alert()

    def scan_chats(self, max_chats: int = 200) -> list:
        """
        扫描聊天列表，通过滚动加载更多聊天（虚拟列表）。
        Returns: [{"chat_id", "name", "company", "title", "last_msg", "unread", "unread_count", "element"}]
        
        重要：切到「未读」tab后，虚拟列表元素引用会在open_chat时失效，
        所以返回的chat里element不可靠。open_chat应使用click_first_unread()替代。
        """
        print("\n📋 扫描聊天列表...")
        self.go_to_chat_page()

        # 等待列表加载
        try:
            self.page.ele('.friend-content', timeout=10)
        except Exception:
            page_url = ""
            page_title = ""
            body_preview = ""
            try:
                page_url = self.page.url or ""
            except Exception:
                pass
            try:
                page_title = self.page.title or ""
            except Exception:
                pass
            try:
                body = self.page.ele("tag:body", timeout=1)
                body_preview = " ".join((body.text or "").split())[:180] if body else ""
            except Exception:
                pass
            print(f"  ❌ 聊天列表加载失败 url={page_url} title={page_title} body={body_preview}")
            return []

        # 点击"未读"tab筛选，优先处理未读消息
        self._switch_to_unread = False
        try:
            unread_tab = self.page.ele('text:未读', timeout=3)
            if unread_tab:
                unread_tab.click()
                random_delay(2, 3)
                print("  📌 已切换到「未读」筛选")
                self._switch_to_unread = True
        except:
            print("  ⚠ 未读tab点击失败，使用默认列表")

        # 滚动加载虚拟列表，收集所有chat_id
        seen_ids = set()
        chats = []
        no_new_rounds = 0
        max_scroll_rounds = 20  # 最多滚动20次

        for scroll_round in range(max_scroll_rounds):
            chat_items = self.page.eles('.friend-content-warp')
            new_count = 0
            for item in chat_items:
                try:
                    chat = self._parse_chat_item(item)
                    if chat and chat["chat_id"] not in seen_ids:
                        seen_ids.add(chat["chat_id"])
                        chats.append(chat)
                        new_count += 1
                        if len(chats) >= max_chats:
                            break
                except:
                    continue

            if len(chats) >= max_chats:
                break

            if new_count == 0:
                no_new_rounds += 1
                if no_new_rounds >= 3:
                    break  # 连续3轮没有新聊天，说明到底了
            else:
                no_new_rounds = 0

            # 滚动加载更多
            self._scroll_chat_list("down", 400)
            random_delay(0.5, 1)

        print(f"  找到 {len(chats)} 个聊天（滚动{scroll_round + 1}轮）")
        if not chats:
            page_url = ""
            page_title = ""
            body_preview = ""
            try:
                page_url = self.page.url or ""
            except Exception:
                pass
            try:
                page_title = self.page.title or ""
            except Exception:
                pass
            try:
                body = self.page.ele("tag:body", timeout=1)
                body_preview = " ".join((body.text or "").split())[:220] if body else ""
            except Exception:
                pass
            print(f"  ⚠ 聊天列表为空诊断 url={page_url} title={page_title} body={body_preview}")

        # 系统噪声模式：这些在列表预览里就能识别，不用点进去浪费20s
        SYSTEM_NOISE_PATTERNS = [
            "共人投递", "你超过竞争者", "超过.*竞争者",
            "您的附件简历", "已发送给Boss",
            "[投递提醒]", "[系统通知]",
        ]
        # 我自己发的招呼语开头：HR还没回，无新内容可处理
        candidate_name = load_resume().get("name", "")
        MY_GREETING_PREFIXES = [
            f"您好，我叫{candidate_name}" if candidate_name else "",
            "您好，关注到贵公司",
            "您好！我5年测试",
        ]
        MY_GREETING_PREFIXES = [prefix for prefix in MY_GREETING_PREFIXES if prefix]
        import re as _re
        noise_re = _re.compile("|".join(SYSTEM_NOISE_PATTERNS))

        # 过滤：未读 或 从未回复过的；同时预过滤系统噪声
        actionable = []
        prefiltered_noise = 0
        for chat in chats:
            cid = chat.get("chat_id", "")
            last_msg = chat.get("last_msg", "") or ""
            # 列表预览命中噪声 && 非未读：直接标记已读，不进流程
            if noise_re.search(last_msg) and not chat.get("unread"):
                if cid and cid not in self.state.get("replied", {}):
                    self.state.setdefault("replied", {})[cid] = {
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "last_msg": last_msg[:100],
                        "prefiltered": "system_noise",
                    }
                prefiltered_noise += 1
                continue
            # 列表预览是我自己发的招呼语 && 非未读 → HR还没回，跳过不打开
            if any(last_msg.startswith(p) for p in MY_GREETING_PREFIXES) and not chat.get("unread"):
                prefiltered_noise += 1
                continue
            if chat.get("unread"):
                actionable.append(chat)
            elif not self._switch_to_unread and cid not in self.state.get("replied", {}):
                actionable.append(chat)

        if prefiltered_noise:
            print(f"  🧹 预过滤系统噪声: {prefiltered_noise} 条")
        if self._switch_to_unread and not any(c.get("unread") for c in actionable):
            print("  ✅ 未读筛选下没有明确未读聊天，跳过本轮")
            actionable = []
        print(f"  需处理: {len(actionable)} 个（未读: {sum(1 for c in actionable if c.get('unread'))}）")
        self.state["last_scan"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save_state()
        return actionable

    def click_first_chat(self) -> dict:
        """
        直接点击聊天列表中第一个聊天项并打开它。
        虚拟列表友好——每次重新获取DOM元素，不依赖缓存引用。
        Returns: 解析后的chat info dict，打开失败返回None
        """
        try:
            items = self.page.eles('.friend-content-warp')
            if not items:
                return None
            item = items[0]
            chat = self._parse_chat_item(item)
            if not chat:
                return None
            # 直接点击这个新鲜的元素 —— by_js=True 避开 DOM.getNodeForLocation
            # (坐标点击在 BOSS 的虚拟列表 + 重绘场景下容易卡死 chrome devtools RPC)
            fc = item.ele(".friend-content", timeout=0) or item
            # 最多尝试 2 次点击：首次若落到 chat-no-data（BOSS 偶发空态），重试一次
            for attempt in range(2):
                try:
                    fc.click(by_js=True)
                except Exception:
                    fc.click()
                random_delay(2, 3)
                # 如果是空态，等一会儿再重试
                # 坑：.chat-no-data 是常驻模板节点，必须验 visible + im-list 双信号
                nd = self.page.ele('.chat-no-data', timeout=1)
                nd_visible = False
                if nd:
                    try:
                        nd_visible = bool(nd.states.is_displayed)
                    except Exception:
                        try:
                            nd_visible = nd.style('display') != 'none'
                        except Exception:
                            nd_visible = True
                im_present = bool(self.page.ele('.im-list', timeout=1) or self.page.ele('css:li.message-item', timeout=1))
                if nd and nd_visible and not im_present:
                    if attempt == 0:
                        print("  ⚠ 首次点击落到 chat-no-data（im-list缺失），重试一次")
                        import time as _t
                        _t.sleep(1.5)
                        continue
                    else:
                        print("  ⚠ 重试后仍是 chat-no-data 且无 im-list，放弃该会话")
                        return None
                # 验证聊天窗口真的有消息容器
                if self.page.ele('.im-list', timeout=3) or self.page.ele('css:li.message-item', timeout=1):
                    return chat
                # 有 chat-message 但无消息容器也算降级成功
                if self.page.ele('.chat-message', timeout=2):
                    return chat
                break
            return None
        except Exception as e:
            print(f"  click_first_chat 异常: {e}")
            return None

    def _parse_chat_item(self, item) -> dict:
        """解析单个聊天项"""
        result = {}

        # 名称
        name_el = item.ele(".name-text", timeout=0)
        result["name"] = name_el.text.strip() if name_el else ""

        # 公司 + 职位 — .name-box 内的 span
        try:
            name_box = item.ele(".name-box", timeout=0)
            if name_box:
                spans = name_box.eles("tag:span")
                # spans: [0]=name-text, [1]=公司, [2?]=职位
                result["company"] = spans[1].text.strip() if len(spans) > 1 else ""
                result["title"] = spans[2].text.strip() if len(spans) > 2 else ""
            else:
                result["company"] = ""
                result["title"] = ""
        except:
            result["company"] = ""
            result["title"] = ""

        # 最后一条消息
        msg_el = item.ele(".last-msg-text", timeout=0)
        if not msg_el:
            msg_el = item.ele(".last-msg", timeout=0)
        result["last_msg"] = msg_el.text.strip() if msg_el else ""

        # 未读标记
        badge = item.ele(".notice-badge", timeout=0)
        if badge:
            badge_text = badge.text.strip()
            result["unread"] = badge_text != ""
            try:
                result["unread_count"] = int(badge_text.replace("+", ""))
            except:
                result["unread_count"] = 1 if badge_text else 0
        else:
            result["unread"] = False
            result["unread_count"] = 0

        # 获取 d-c 属性（BOSS内部聊天ID）— 优先作为唯一标识
        fc = item.ele(".friend-content", timeout=0)
        boss_chat_id = ""
        if fc:
            dc = fc.attr("d-c")
            # d-c="62001" 是通用值，所有聊天项都一样，不能用作唯一ID
            if dc and dc != "62001":
                boss_chat_id = dc
                result["boss_chat_id"] = dc

        # ID: 优先用boss_chat_id，降级用 name@company
        result["chat_id"] = boss_chat_id if boss_chat_id else f"{result['name']}@{result['company']}"

        result["element"] = item

        return result if result["name"] else None

    def _scroll_into_view(self, element):
        """滚动元素到可视区域"""
        try:
            element.scroll.to_see()
            time.sleep(0.3)
        except Exception:
            try:
                element.run_js("this.scrollIntoView({block:'center'})")
                time.sleep(0.3)
            except Exception:
                pass

    def _scroll_chat_list(self, direction="down", pixels=300):
        """滚动聊天列表侧边栏"""
        try:
            # 找到聊天列表的滚动容器
            container = self.page.ele('.user-list-content', timeout=3)
            if not container:
                container = self.page.ele('.user-list', timeout=3)
            if not container:
                container = self.page.ele('css:.chat-user', timeout=3)
            if container:
                if direction == "down":
                    container.scroll.down(pixels)
                else:
                    container.scroll.up(pixels)
                time.sleep(0.5)
        except Exception:
            pass

    def open_chat(self, chat_item: dict) -> bool:
        """点击进入某个聊天 — 优先用存储的元素点击，降级按名字+公司"""
        name = chat_item.get("name", "")
        company = chat_item.get("company", "")
        boss_id = chat_item.get("boss_chat_id", "")
        try:
            # 策略1: 用存储的元素直接点击
            element = chat_item.get("element")
            if element:
                try:
                    fc = element.ele(".friend-content", timeout=0) or element
                    self._scroll_into_view(fc)
                    fc.click()
                    random_delay(2, 3)
                    if self.page.ele('.chat-message', timeout=5):
                        return True
                except Exception:
                    pass  # 元素引用失效，降级

            # 策略2: 按名字+公司精确查找（d-c="62001"是通用值，不能区分聊天）
            print(f"  🔄 按名字+公司查找: {name}@{company}")
            if self._find_and_click_by_name(name, company):
                # 验证：打开后检查聊天标题是否匹配
                if self._verify_opened_chat(name):
                    return True
                print(f"  ⚠️ 打开了错误的聊天，跳过")
                return False

            print(f"  ⚠️ 查找 {name} 全部失败")
        except Exception as e:
            print(f"  打开聊天失败: {e}")
        return False

    def _verify_opened_chat(self, expected_name: str) -> bool:
        """验证打开的聊天是否是期望的对话（防止错位）"""
        try:
            # 聊天窗口顶部有 HR 名字
            header = self.page.ele('.chat-greet', timeout=3) or self.page.ele('.start-head', timeout=2)
            if header:
                header_text = header.text or ""
                if expected_name in header_text:
                    return True
                print(f"    验证: 期望 {expected_name}, 实际 {header_text[:30]}")
                return False
            # 找不到header也算通过（避免误判）
            return True
        except Exception:
            return True

    def _find_and_click_by_boss_id(self, boss_id: str) -> bool:
        """通过 d-c 属性精确定位并点击聊天"""
        # 先滚动到顶部
        for _ in range(3):
            self._scroll_chat_list("up", 500)

        for attempt in range(15):
            # 直接用CSS属性选择器找 d-c="xxx" 的元素
            try:
                fc = self.page.ele(f'css:.friend-content[d-c="{boss_id}"]', timeout=1)
                if fc:
                    self._scroll_into_view(fc)
                    fc.click()
                    random_delay(2, 3)
                    if self.page.ele('.chat-message', timeout=5):
                        return True
            except Exception:
                pass

            # 也尝试遍历当前可见列表
            try:
                items = self.page.eles('.friend-content-warp')
                for item in items:
                    fc = item.ele(".friend-content", timeout=0)
                    if fc and fc.attr("d-c") == boss_id:
                        self._scroll_into_view(fc)
                        fc.click()
                        random_delay(2, 3)
                        if self.page.ele('.chat-message', timeout=5):
                            return True
            except Exception:
                pass

            self._scroll_chat_list("down", 200)
        return False

    def _find_and_click_by_name(self, name: str, company: str = "") -> bool:
        """按名字+公司滚动查找并点击"""
        for _ in range(3):
            self._scroll_chat_list("up", 500)

        for attempt in range(15):
            items = self.page.eles('.friend-content-warp')
            for item in items:
                try:
                    name_el = item.ele(".name-text", timeout=0)
                    if not name_el or name_el.text.strip() != name:
                        continue
                    # 如果有公司信息，再匹配公司
                    if company:
                        name_box = item.ele(".name-box", timeout=0)
                        if name_box:
                            box_text = name_box.text or ""
                            if company not in box_text:
                                continue
                    fc = item.ele(".friend-content", timeout=0) or item
                    self._scroll_into_view(fc)
                    fc.click()
                    random_delay(2, 3)
                    if self.page.ele('.chat-message', timeout=5):
                        return True
                except Exception:
                    continue
            self._scroll_chat_list("down", 200)
        return False

    def read_messages(self, limit: int = 20) -> list:
        """
        读取当前聊天窗口的消息
        Returns: [{"role": "hr"|"me", "text": str, "time": str, "mid": str}]
        """
        # 先滚动聊天区到底部，确保最新消息已加载（防止HR追问在滚动范围外未渲染）
        try:
            import time as _t
            chat_area = self.page.ele('.chat-message', timeout=3)
            if not chat_area:
                chat_area = self.page.ele('.im-list', timeout=2)
            if chat_area:
                chat_area.scroll.to_bottom()
                _t.sleep(0.8)
        except Exception:
            pass

        messages = []
        try:
            # 先检测 chat-no-data (BOSS"该Boss更换了岗位"后聊天被清空的典型DOM)
            # 坑：.chat-no-data 节点常驻 DOM（template预渲染），仅靠 ele 存在性判断会全量误杀。
            # 必须同时验证：(a) 节点 displayed (b) 不存在消息容器/消息项
            no_data = self.page.ele('.chat-no-data', timeout=1)
            if no_data:
                visible = True
                try:
                    visible = bool(no_data.states.is_displayed)
                except Exception:
                    try:
                        visible = no_data.style('display') != 'none'
                    except Exception:
                        visible = True
                # 双保险：即使 visible，也再确认 im-list/message-item 真的没东西
                has_msgs = False
                try:
                    probe_list = self.page.ele('.im-list', timeout=1) or self.page.ele('.chat-record-box', timeout=1)
                    if probe_list:
                        probe_items = probe_list.eles('css:li.message-item')
                        if probe_items:
                            has_msgs = True
                    if not has_msgs:
                        any_items = self.page.eles('css:li.message-item')
                        if any_items:
                            has_msgs = True
                except Exception:
                    pass

                if visible and not has_msgs:
                    # 给BOSS足够渲染时间再确认（切换会话时chat-no-data是过渡态）
                    # 坑：有些慢会话要3-4s才把im-list挂上；过去1.5s太短导致批量误判。
                    # 改成 8 轮 x 1.5s 轮询(共12s)，命中即退出，避开固定长sleep的浪费。
                    # 同时检测输入框——有输入框说明聊天窗口已开，只是消息为空（新会话或历史清空）
                    import time as _t2
                    for _retry_round in range(8):
                        _t2.sleep(1.5)
                        try:
                            retry_list = self.page.ele('.im-list', timeout=1) or self.page.ele('.chat-record-box', timeout=1) or self.page.ele('.im-message-list', timeout=1)
                            if retry_list and retry_list.eles('css:li.message-item'):
                                has_msgs = True
                                break
                            # 兜底：全局 li.message-item
                            if self.page.eles('css:li.message-item'):
                                has_msgs = True
                                break
                            # 有输入框说明聊天窗口存在，即使消息为空（新会话）也不再等待
                            _has_input = (
                                self.page.ele('tag:textarea', timeout=0) or
                                self.page.ele('[contenteditable="true"]', timeout=0)
                            )
                            if _has_input:
                                # 聊天窗口已开但无历史消息——视为"有窗口但消息为空"，继续解析
                                has_msgs = False  # 让下面判断正常走
                                break
                        except Exception:
                            pass
                    if not has_msgs:
                        print(f"  · 系统通知条目或空会话（im-list 12s未挂载），跳过")
                        # DEBUG: dump 一次失败时的 DOM 用于排查（只 dump 一次，文件存在就跳过）
                        try:
                            import os as _os
                            dump_path = 'data/chat_no_data_dump.html'
                            if not _os.path.exists(dump_path):
                                body_html = self.page.ele('css:body', timeout=1)
                                if body_html:
                                    with open(dump_path, 'w', encoding='utf-8') as _f:
                                        _f.write(body_html.html)
                                    print(f"  [DEBUG] 已 dump body HTML 到 {dump_path}")
                        except Exception as _e:
                            print(f"  [DEBUG] dump 失败: {_e}")
                        return []
                # 否则继续走下面的正常解析路径（chat-no-data 是模板残留/过渡态）

            # 页面级 .message-item 搜索不到，必须先定位父元素
            # 多候选选择器：.im-list 是主选择器，新DOM里可能是 .chat-record-box 或 .im-message-list
            im_list = None
            for sel in ['.im-list', '.chat-record-box', '.im-message-list', 'ul.im-list']:
                im_list = self.page.ele(sel, timeout=2)
                if im_list:
                    break
            if not im_list:
                # 最后兜底：直接全局搜 li.message-item
                msg_items = self.page.eles('css:li.message-item')
                if msg_items:
                    print(f"  ⚠️ 无 im-list，但找到 {len(msg_items)} 条 message-item 兜底")
                else:
                    print("  ⚠️ 找不到 .im-list 及所有 fallback 选择器")
                    return []
            else:
                msg_items = im_list.eles('css:li.message-item')

            if not msg_items:
                print("  ⚠️ 找到容器但内无消息")
                return []

            # 系统卡片/通知文本 pattern（即使 role 标为 item-friend 也要降级为 system）
            # BOSS 的"共X人投递,你超过竞争者"这类通知 DOM 布局和 HR 消息同构，但不是HR真实消息
            SYSTEM_TEXT_PATTERNS = [
                "共人投递", "共.*人投递", "超过竞争者", "超过.*竞争者",
                "投递提醒", "[系统通知]", "系统通知",
                "正在查看你的简历", "已读你的简历", "查看过你的简历",
                "Boss已读", "Boss查看",
            ]
            import re as _re
            def _is_system_text(t: str) -> bool:
                if not t:
                    return False
                for p in SYSTEM_TEXT_PATTERNS:
                    if _re.search(p, t):
                        return True
                return False

            for item in msg_items[-limit:]:
                msg = {}
                cls = item.attr("class") or ""

                # 角色判断 —— system 类直接忽略 DOM role 提示
                if "item-system" in cls or "item-notice" in cls:
                    role_hint = "system"
                elif "item-myself" in cls:
                    role_hint = "me"
                elif "item-friend" in cls:
                    role_hint = "hr"
                else:
                    continue

                # 消息ID
                mid = item.attr("data-mid")
                msg["mid"] = mid or ""

                # 消息文本 — .text p span 或直接 .text
                text_el = item.ele("tag:p", timeout=0)
                if text_el:
                    msg["text"] = text_el.text.strip()
                else:
                    text_div = item.ele(".text", timeout=0)
                    msg["text"] = text_div.text.strip() if text_div else ""

                # 卡片类消息统一降级为 system（竞争者PK/已读通知/BOSS系统卡片等）
                has_card = bool(item.ele(".message-card-wrap", timeout=0))
                if has_card:
                    if not msg["text"]:
                        msg["text"] = "[系统卡片消息]"
                    role_hint = "system"
                # 文本匹配系统通知模式也降级 —— 即使 item-friend class 也不信
                elif role_hint == "hr" and _is_system_text(msg["text"]):
                    role_hint = "system"

                msg["role"] = role_hint

                # 时间
                time_el = item.ele(".time", timeout=0)
                msg["time"] = time_el.text.strip() if time_el else ""

                if msg.get("text"):
                    messages.append(msg)

        except Exception as e:
            print(f"  读取消息失败: {e}")

        return messages

    def get_last_hr_message(self) -> str:
        """获取对方（HR）最后一条消息文本"""
        msgs = self.read_messages()
        for m in reversed(msgs):
            if m["role"] == "hr":
                return m["text"]
        return ""

    def is_my_last_message(self) -> bool:
        """判断最后一条消息是否是自己发的（已回复过）"""
        msgs = self.read_messages()
        for m in reversed(msgs):
            if m["role"] in ("me", "hr"):
                return m["role"] == "me"
        return False

    def send_message(self, text: str) -> bool:
        """在当前聊天窗口发送消息 — 多策略确保输入框可见"""
        # 空串/纯空白守卫：防止给HR发空Enter消息
        if not text or not text.strip():
            print(f"  ⏭️  跳过发送（空回复，可能是 system_noise / silent intent）")
            return False
        try:
            # 先确保聊天区域滚到底部
            chat_area = self.page.ele('.chat-message', timeout=3)
            if chat_area:
                try:
                    chat_area.scroll.to_bottom()
                    time.sleep(0.3)
                except:
                    pass

            # 找输入框
            input_el = self.page.ele("tag:textarea", timeout=5)
            if not input_el:
                input_el = self.page.ele("css:[contenteditable='true']", timeout=3)
            if not input_el:
                print("  ❌ 找不到输入框")
                return False

            # 策略1: JS强制让输入框可见并聚焦
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

            # 策略2: 尝试原生点击+输入
            sent = False
            try:
                input_el.click(by_js=True)
                random_delay(0.3, 0.5)
                input_el.clear()
                input_el.input(text)
                random_delay(0.5, 1)
                sent = True
            except Exception as e1:
                # 策略3: 纯JS设值
                try:
                    escaped = text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
                    input_el.run_js(f"""
                        this.focus();
                        this.value = `{escaped}`;
                        this.dispatchEvent(new Event('input', {{bubbles: true}}));
                        this.dispatchEvent(new Event('change', {{bubbles: true}}));
                    """)
                    random_delay(0.5, 1)
                    sent = True
                except Exception as e2:
                    print(f"  ❌ 输入失败: {e1} / {e2}")
                    return False

            if not sent:
                return False

            # 等一下让按钮激活
            time.sleep(0.5)

            # 点发送按钮
            send_btn = self.page.ele('.btn-sure-v2', timeout=3)
            if send_btn and "disabled" not in (send_btn.attr("class") or ""):
                try:
                    send_btn.click(by_js=True)
                    random_delay(1, 2)
                    print(f"  ✅ 已发送: {text[:50]}...")
                    return True
                except:
                    pass

            # fallback: 用Enter键发送
            try:
                from DrissionPage.common import Keys
                input_el.input(Keys.ENTER)
                random_delay(1, 2)
                print(f"  ✅ 已发送(Enter): {text[:50]}...")
                return True
            except:
                pass

            # 最终fallback: JS模拟Enter
            try:
                input_el.run_js("""
                    this.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
                """)
                random_delay(1, 2)
                print(f"  ✅ 已发送(JS-Enter): {text[:50]}...")
                return True
            except Exception as e:
                print(f"  ❌ 发送失败: {e}")
                return False

        except Exception as e:
            print(f"  ❌ 发送失败: {e}")
            return False

    def get_job_info(self) -> dict:
        """从当前聊天顶部获取职位信息 + JD正文 + 解析后的结构化字段
        返回字段:
          raw: 顶部摘要
          salary: "15-25K" 原始字符串
          salary_min, salary_max: int (K为单位)
          title, company, location
          jd: 职位描述正文 (最多1500字)
          tags: list[str] 技能/福利标签
        """
        info = {"raw": "", "jd": "", "tags": []}
        # --- 顶部摘要 ---
        try:
            top = self.page.ele('.top-info-content', timeout=3)
            if top:
                text = top.text
                info["raw"] = text[:300]
                # 薪资 XX-XXK 或 XX-XXK·13薪
                m = re.search(r'(\d+)[-~](\d+)\s*K', text)
                if m:
                    info["salary"] = f"{m.group(1)}-{m.group(2)}K"
                    try:
                        info["salary_min"] = int(m.group(1))
                        info["salary_max"] = int(m.group(2))
                    except:
                        pass
                # 职位名 (top的第一行通常是职位)
                first_line = text.split("\n")[0].strip() if text else ""
                if first_line and len(first_line) < 40:
                    info["title"] = first_line
        except Exception:
            pass

        # --- JD 正文 (右侧面板/弹窗/iframe, 多选择器兜底) ---
        selectors = [
            '.job-detail-content',
            '.job-detail',
            '.job-sec-text',
            '.detail-content',
            '.job-description',
            '[class*="job-detail"]',
        ]
        for sel in selectors:
            try:
                el = self.page.ele(sel, timeout=1)
                if el and el.text and len(el.text.strip()) > 30:
                    info["jd"] = el.text.strip()[:1500]
                    break
            except Exception:
                continue

        # --- 公司 / 地点 / 标签 ---
        try:
            company_el = self.page.ele('.boss-name', timeout=1) or self.page.ele('.company-name', timeout=1)
            if company_el and company_el.text:
                info["company"] = company_el.text.strip()
        except Exception:
            pass
        try:
            loc_el = self.page.ele('.company-location', timeout=1) or self.page.ele('.job-location', timeout=1)
            if loc_el and loc_el.text:
                info["location"] = loc_el.text.strip()
        except Exception:
            pass
        try:
            tag_els = self.page.eles('.tag-list li')[:10]
            info["tags"] = [t.text.strip() for t in tag_els if t.text]
        except Exception:
            pass

        # JD 回查：聊天页拉不到 JD 时，按 company+title 从投递阶段缓存里回查
        if not info.get("jd"):
            try:
                cached = self._lookup_jd_cache(info.get("company", ""), info.get("title", ""))
                if cached:
                    info["jd"] = cached.get("jd", "")[:1500]
                    if not info.get("tags") and cached.get("tags"):
                        info["tags"] = cached["tags"]
                    if not info.get("salary") and cached.get("salary"):
                        info["salary"] = cached["salary"]
            except Exception:
                pass

        return info

    def _lookup_jd_cache(self, company: str, title: str) -> dict:
        """从 data/jd_cache.json 按 company+title 模糊匹配，找投递时存的 JD"""
        import json as _json
        from pathlib import Path as _P
        if not company:
            return {}
        cache_path = _P(__file__).parent / "data" / "jd_cache.json"
        if not cache_path.exists():
            return {}
        try:
            data = _json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        company_s = company.strip()
        title_s = (title or "").strip()
        # 1) 精确匹配
        exact = data.get(f"{company_s}||{title_s}")
        if exact:
            return exact
        # 2) 公司模糊（包含），标题部分匹配
        best = None
        best_score = 0
        for k, v in data.items():
            c = v.get("company", "")
            t = v.get("title", "")
            if not c:
                continue
            if company_s in c or c in company_s:
                score = 1
                if title_s and (title_s in t or t in title_s):
                    score += 2
                if score > best_score:
                    best_score = score
                    best = v
        return best or {}
