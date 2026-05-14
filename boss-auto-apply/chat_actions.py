"""
BOSS直聘 聊天高级动作模块
- 发送简历（在线简历 / 附件简历）
- 交换电话
- 交换微信
- 发送图片

DOM结构（2026-04实测 via explore_buttons2.py）:
  工具栏: .chat-controls > .toolbar-btn-content
    表情:   .btn-emotion (d-c="62005")
    常用语: .btn-dict (d-c="62003")
    发图片: .btn-sendimg (input[type=file])
    发简历: .toolbar-btn (d-c="62009") -> 弹窗 .select-one x2 (.main-title="发送在线简历")
    换电话: .toolbar-btn-content.btn-contact (d-c="62007") -> 弹窗 .sentence-popover.panel-contact -> 确定
    换微信: .btn-weixin (d-c="62011") -> 弹窗确认
"""
import time
import os
from pathlib import Path
from anti_detect import random_delay


class ChatActions:
    """聊天页面高级操作"""

    def __init__(self, page):
        self.page = page

    # ========== 检查简历是否已发过 ==========
    def _has_resume_in_chat(self) -> bool:
        """检查当前聊天是否已存在简历卡片（避免重复发送）"""
        try:
            im_list = self.page.ele('.im-list', timeout=2)
            if not im_list:
                return False
            # 简历发送后会有卡片消息，包含"简历"关键词
            cards = im_list.eles('css:.message-card-wrap')
            for card in cards:
                text = (card.text or "").strip()
                if '简历' in text or '在线简历' in text:
                    return True
            # 也检查是否有"我发的"简历文本消息
            items = im_list.eles('css:li.item-myself')
            for item in items:
                text = (item.text or "").strip()
                if '在线简历' in text:
                    return True
        except:
            pass
        return False

    # ========== 发送在线简历 ==========
    def send_online_resume(self) -> bool:
        """
        点击'发简历'按钮 -> 选择'发送在线简历'
        Returns: True if sent successfully
        """
        # 先检查是否已发过
        if self._has_resume_in_chat():
            print("  [ACTION] 简历已发过，跳过")
            return True  # 返回True不算失败
        print("  [ACTION] 发送在线简历...")
        try:
            chat_url = self.page.url
            # 1. 点击发简历按钮 (BOSS DOM 经常改，按 d-c/文字/class 多策略找)
            resume_btn = self._find_resume_button()
            if not resume_btn:
                print("    -> 找不到发简历按钮")
                return False

            resume_btn.click(by_js=True)
            random_delay(1, 2)
            if self._is_resume_edit_page():
                print("    -> 误跳到简历编辑页，已停止发简历动作")
                self._return_to_chat(chat_url)
                return False

            # 新版 BOSS 有时点击聊天框「发简历」后直接弹「确定/取消」，
            # 不再先展示「上传简历 / 发送在线简历」二选一。
            direct_confirm = self._find_resume_confirm_button(timeout=2)
            if direct_confirm:
                direct_confirm.click(by_js=True)
                random_delay(1, 2)
                if self._is_resume_edit_page():
                    print("    -> 直达确认后跳到简历编辑页，未确认简历已发，已回退")
                    self._return_to_chat(chat_url)
                    return False
                if self._wait_resume_confirmation(timeout=8):
                    print("    -> 已通过直达确认发送简历")
                    return True
                print("    -> 已点击直达确认，但聊天记录未确认出现简历卡片")
                self._dump_resume_dom("resume_direct_confirm_not_confirmed")
                return False

            # 2. 弹窗出现：两个选项 .select-one
            #    第一个: 上传简历
            #    第二个: 发送在线简历
            target = self._find_resume_option("发送在线简历", timeout=3)
            if not target:
                print("    -> 简历选项弹窗未出现")
                self._dump_resume_dom("resume_options_missing")
                return False

            target.click(by_js=True)
            random_delay(1, 2)
            if self._is_resume_edit_page():
                print("    -> 发送在线简历触发了简历编辑页，说明在线简历未就绪/按钮选错；已回退")
                self._return_to_chat(chat_url)
                self._dump_resume_dom("resume_edit_after_online_option")
                return False

            # 3. 二次确认弹窗："确定向 Boss 发送简历吗？" -> 点"确认"
            #    关键：不点确认简历不会真的发出去！
            confirm_clicked = False
            try:
                confirm_btn = self._find_resume_confirm_button(timeout=4)
                if confirm_btn:
                    confirm_btn.click(by_js=True)
                    confirm_clicked = True
                    random_delay(1, 2)
                    if self._is_resume_edit_page():
                        print("    -> 确认后跳到简历编辑页，未确认简历已发，已回退")
                        self._return_to_chat(chat_url)
                        return False
                    print("    -> 已点击确认，在线简历发送中")
                else:
                    # 没找到确认按钮 — 有些情况是直接发送无需二次确认
                    print("    -> 无二次确认弹窗，按直接发送处理")
            except Exception as ce:
                print(f"    -> 确认弹窗处理异常: {ce}")

            # 4. 关闭残留弹窗（兜底）
            if not confirm_clicked:
                self._close_popup()

            if self._wait_resume_confirmation(timeout=8):
                print("    -> 在线简历已发送并在聊天记录中确认")
                return True
            print("    -> 已执行发送动作，但聊天记录未确认出现简历卡片")
            self._dump_resume_dom("resume_card_not_confirmed")
            return False

        except Exception as e:
            print(f"    -> 发送在线简历失败: {e}")
            return False

    def _is_resume_edit_page(self) -> bool:
        try:
            url = self.page.url or ""
            return "cv.zhipin.com/edit-resume" in url or "/edit-resume" in url
        except Exception:
            return False

    def _return_to_chat(self, chat_url: str):
        try:
            if chat_url and "zhipin.com" in chat_url:
                self.page.get(chat_url)
                random_delay(0.5, 1)
        except Exception:
            try:
                self.page.back()
                random_delay(0.5, 1)
            except Exception:
                pass

    def _find_resume_button(self):
        selectors = [
            'css:.toolbar-btn[d-c="62009"]',
            'css:[d-c="62009"]',
            'css:.toolbar-btn:has-text("简历")',
            'css:.chat-controls .toolbar-btn:has-text("简历")',
            'css:.chat-controls [class*="toolbar"]:has-text("简历")',
        ]
        for selector in selectors:
            try:
                btn = self.page.ele(selector, timeout=1.5)
                if btn:
                    return btn
            except Exception:
                continue
        try:
            buttons = self.page.eles('css:.toolbar-btn,.toolbar-btn-content,[class*="toolbar"]', timeout=2)
            for btn in buttons:
                text = (btn.text or '').strip()
                title = (btn.attr('title') or '').strip()
                aria = (btn.attr('aria-label') or '').strip()
                class_name = (btn.attr('class') or '').strip()
                blob = f'{text} {title} {aria} {class_name}'
                if '简历' in blob or 'resume' in blob.lower() or '62009' in blob:
                    return btn
        except Exception:
            pass
        return None

    def _find_resume_option(self, expected_title: str, timeout: int = 3):
        """只从简历弹窗选项里找目标，避免全局 text 命中简历编辑入口。"""
        try:
            options = self.page.eles('css:.select-one', timeout=timeout)
        except Exception:
            options = []
        for opt in options or []:
            try:
                title = opt.ele('.main-title', timeout=0)
                title_text = (title.text or "").strip() if title else ""
                opt_text = (opt.text or "").strip()
                if expected_title in title_text or expected_title in opt_text:
                    return opt
            except Exception:
                continue
        return None

    def _find_resume_confirm_button(self, timeout: int = 4):
        """确认按钮必须来自简历相关弹窗，避免误点页面其他确认。"""
        dialog_selectors = [
            'css:.dialog-container',
            'css:.resume-pop',
            'css:.upload-resume__old',
            'css:[class*="resume"]',
            'css:[class*="dialog"]',
        ]
        deadline = time.time() + timeout
        while time.time() < deadline:
            for selector in dialog_selectors:
                try:
                    dialogs = self.page.eles(selector, timeout=0.5)
                except Exception:
                    dialogs = []
                for dialog in dialogs or []:
                    try:
                        text = (dialog.text or "").strip()
                        if "简历" not in text:
                            continue
                        for btn_sel in ['css:.btn-sure-v2', 'css:.btn-sure', 'text:确认', 'text:确定']:
                            try:
                                btn = dialog.ele(btn_sel, timeout=0.2)
                                if btn:
                                    return btn
                            except Exception:
                                continue
                    except Exception:
                        continue
            time.sleep(0.3)
        return None

    def _wait_resume_confirmation(self, timeout: int = 8) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._is_resume_edit_page():
                return False
            if self._has_resume_in_chat():
                return True
            time.sleep(0.8)
        return False

    def _dump_resume_dom(self, reason: str) -> None:
        """保存当前页面 DOM，便于下次按真实 BOSS 页面修选择器。"""
        try:
            dump_dir = Path(__file__).parent / "data" / "dom_dumps"
            dump_dir.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            html = getattr(self.page, "html", "") or ""
            if not html:
                try:
                    html = self.page.ele("tag:body", timeout=1).html
                except Exception:
                    html = ""
            if html:
                path = dump_dir / f"{reason}_{ts}.html"
                path.write_text(html, encoding="utf-8")
                print(f"    💾 DOM dump -> data/dom_dumps/{path.name}")
        except Exception as exc:
            print(f"    ! DOM dump 失败: {exc}")

    # ========== 上传附件简历 ==========
    def upload_resume(self, file_path: str) -> bool:
        """
        点击'发简历'按钮 -> 选择'上传简历' -> 选择文件
        file_path: PDF/DOC/DOCX 文件路径
        """
        print(f"  [ACTION] 上传附件简历: {os.path.basename(file_path)}")
        if not os.path.exists(file_path):
            print(f"    -> 文件不存在: {file_path}")
            return False

        try:
            # 1. 点击发简历按钮
            resume_btn = self._find_resume_button()
            if not resume_btn:
                print("    -> 找不到发简历按钮")
                return False

            resume_btn.click(by_js=True)
            random_delay(1, 2)

            # 2. 选择"上传简历"选项
            options = self.page.eles('css:.select-one', timeout=3)
            target = None
            for opt in options:
                try:
                    title = opt.ele('.main-title', timeout=0)
                    if title and '上传简历' in title.text:
                        target = opt
                        break
                except:
                    pass

            if not target:
                target = self.page.ele('text:上传简历', timeout=2)

            if not target:
                print("    -> 找不到'上传简历'选项")
                self._close_popup()
                return False

            target.click(by_js=True)
            random_delay(1, 2)

            # 3. 上传弹窗出现 (.upload-resume__old)
            #    找到文件input或"上传附件简历"按钮
            #    DOM: a.btn.btn-primary.btn-file 下有隐藏的 input[type=file]
            file_input = self.page.ele('css:.upload-resume__old input[type="file"]', timeout=3)
            if not file_input:
                # fallback: 找所有file input
                file_input = self.page.ele('css:input[type="file"][accept*="pdf"]', timeout=3)
            if not file_input:
                # 再fallback: 找 .btn-file 下的 input
                btn_file = self.page.ele('.btn-file', timeout=3)
                if btn_file:
                    file_input = btn_file.ele('tag:input', timeout=1)

            if not file_input:
                print("    -> 找不到文件上传input")
                self._close_popup()
                return False

            # 4. 设置文件路径（DrissionPage方式）
            # 需要用Windows路径格式
            win_path = file_path
            if file_path.startswith('/mnt/'):
                # 转换 /mnt/c/xxx -> C:\xxx
                parts = file_path.split('/')
                drive = parts[2].upper()
                rest = '\\'.join(parts[3:])
                win_path = f"{drive}:\\{rest}"

            file_input.input(win_path)
            random_delay(3, 5)

            # 5. 等待上传完成
            print(f"    -> 附件简历上传中...")
            time.sleep(3)

            # 检查是否有确认按钮
            confirm_btn = self.page.ele('css:.upload-resume__old .btn-sure-v2', timeout=3)
            if confirm_btn:
                confirm_btn.click(by_js=True)
                random_delay(2, 3)

            print("    -> 附件简历已上传")
            return True

        except Exception as e:
            print(f"    -> 上传附件简历失败: {e}")
            return False

    # ========== 交换电话 ==========
    def exchange_phone(self) -> bool:
        """
        点击'换电话'按钮 -> 确认弹窗
        DOM: .btn-contact (d-c="62007") -> .panel-contact -> 确定
        """
        # 先检查是否已交换/请求中
        phone_btn = self.page.ele('css:.btn-contact', timeout=2)
        if phone_btn:
            cls = phone_btn.attr('class') or ''
            aria = phone_btn.attr('aria-label') or ''
            if 'unable' in cls or '请求中' in aria or '等待' in aria:
                print("  [ACTION] 电话已交换/请求中，跳过")
                return True
        print("  [ACTION] 交换电话...")
        try:
            # 1. 点击换电话按钮
            # 多种选择器兜底
            phone_btn = None
            selectors = [
                'css:.btn-contact',
                'css:.toolbar-btn-content.btn-contact',
                'css:[d-c="62007"]',
                'text:换电话',
            ]
            for sel in selectors:
                try:
                    phone_btn = self.page.ele(sel, timeout=2)
                    if phone_btn:
                        break
                except:
                    pass

            if not phone_btn:
                print("    -> 找不到换电话按钮")
                return False

            phone_btn.click(by_js=True)
            random_delay(1, 2)

            # 2. 确认弹窗 — 找"确定"按钮
            # DOM: .sentence-popover.panel-contact 在按钮内部
            confirm = None
            # 先在按钮内部找 panel-contact
            try:
                panel = phone_btn.ele('css:.panel-contact', timeout=3)
                if not panel:
                    panel = phone_btn.ele('css:.sentence-popover', timeout=2)
                if not panel:
                    panel = self.page.ele('css:.sentence-popover.panel-contact', timeout=3)
                if panel:
                    confirm = panel.ele('css:.btn-sure-v2', timeout=2)
                    if not confirm:
                        confirm = panel.ele('text:确定', timeout=2)
            except:
                pass

            if not confirm:
                # fallback: 找页面上所有"确定"按钮
                try:
                    confirms = self.page.eles('text:确定', timeout=3)
                    for c in confirms:
                        try:
                            if c.text.strip() == '确定':
                                confirm = c
                                break
                        except:
                            pass
                except:
                    pass

            if not confirm:
                # 可能弹窗就是直接确认了（没有二次确认）
                print("    -> 未找到确认按钮，可能已自动交换")
                return True

            confirm.click(by_js=True)
            random_delay(2, 3)

            # 4. 检查是否有隐私保护弹窗 (dialog-virtual-container)
            try:
                virtual_dialog = self.page.ele('css:.dialog-virtual-container', timeout=2)
                if virtual_dialog:
                    style = virtual_dialog.attr('style') or ''
                    if 'display: none' not in style:
                        # 有隐私保护弹窗，找确定按钮
                        v_confirm = virtual_dialog.ele('.btn-sure-v2', timeout=2)
                        if v_confirm:
                            v_confirm.click(by_js=True)
                            random_delay(1, 2)
            except:
                pass

            print("    -> 电话交换已发起")
            return True

        except Exception as e:
            print(f"    -> 交换电话失败: {e}")
            return False

    # ========== 交换微信 ==========
    def exchange_wechat(self) -> bool:
        """
        点击'换微信'按钮 -> 确认弹窗
        DOM: .btn-weixin
        """
        # 先检查是否已交换/请求中
        wx_check = self.page.ele('css:.btn-weixin', timeout=2)
        if wx_check:
            cls = wx_check.attr('class') or ''
            aria = wx_check.attr('aria-label') or ''
            if 'unable' in cls or '请求中' in aria or '等待' in aria:
                print("  [ACTION] 微信已交换/请求中，跳过")
                return True
        print("  [ACTION] 交换微信...")
        try:
            # 1. 点击换微信按钮
            wx_btn = self.page.ele('css:.btn-weixin[d-c="62011"]', timeout=3)
            if not wx_btn:
                wx_btn = self.page.ele('css:.btn-weixin', timeout=3)
            if not wx_btn:
                wx_btn = self.page.ele('css:[d-c="62011"]', timeout=2)
            if not wx_btn:
                wx_btn = self.page.ele('text:换微信', timeout=2)
            if not wx_btn:
                print("    -> 找不到换微信按钮")
                return False

            wx_btn.click(by_js=True)
            random_delay(1, 2)

            # 2. 确认弹窗 — 结构与换电话类似
            # 找到确认按钮
            # 2. 确认弹窗 — 和换电话类似，查找确认按钮
            confirm = None
            # 先在按钮内部找 sentence-popover
            try:
                panel = wx_btn.ele('css:.sentence-popover', timeout=3)
                if panel:
                    confirm = panel.ele('css:.btn-sure-v2', timeout=2)
                    if not confirm:
                        confirm = panel.ele('text:确定', timeout=2)
            except:
                pass

            if not confirm:
                # fallback: 找页面上所有确定按钮
                try:
                    confirms = self.page.eles('text:确定', timeout=3)
                    for c in confirms:
                        try:
                            if c.text.strip() == '确定':
                                confirm = c
                                break
                        except:
                            pass
                except:
                    pass

            if not confirm:
                print("    -> 未找到确认按钮，可能已自动交换")
                return True

            confirm.click(by_js=True)
            random_delay(2, 3)
            print("    -> 微信交换已发起")
            return True

        except Exception as e:
            print(f"    -> 交换微信失败: {e}")
            return False

    # ========== 检查是否已交换过 ==========
    def check_already_exchanged(self) -> dict:
        """
        检查当前聊天是否已交换过电话/微信
        Returns: {"phone_exchanged": bool, "wechat_exchanged": bool, "resume_requested": bool}
        """
        result = {"phone_exchanged": False, "wechat_exchanged": False, "resume_requested": False}
        try:
            # 检查换电话按钮状态
            # 交换后: class加"unable", aria-label含"请求中"或"等待"
            phone_btn = self.page.ele('css:.btn-contact', timeout=2)
            if phone_btn:
                cls = phone_btn.attr('class') or ''
                aria = phone_btn.attr('aria-label') or ''
                text = phone_btn.text.strip()
                if any(k in cls for k in ('unable', 'exchanged', 'disabled')):
                    result["phone_exchanged"] = True
                if any(k in aria for k in ('请求中', '等待', '已交换')):
                    result["phone_exchanged"] = True

            # 检查换微信按钮状态
            wx_btn = self.page.ele('css:.btn-weixin', timeout=2)
            if wx_btn:
                cls = wx_btn.attr('class') or ''
                aria = wx_btn.attr('aria-label') or ''
                if any(k in cls for k in ('unable', 'exchanged', 'disabled')):
                    result["wechat_exchanged"] = True
                if any(k in aria for k in ('请求中', '等待', '已交换')):
                    result["wechat_exchanged"] = True

            # 扫描系统消息
            try:
                im_list = self.page.ele('.im-list', timeout=2)
                if im_list:
                    sys_msgs = im_list.eles('css:.item-system')
                    for sm in sys_msgs:
                        text = (sm.text or '').strip()
                        if '交换电话' in text:
                            result["phone_exchanged"] = True
                        if '交换微信' in text:
                            result["wechat_exchanged"] = True

                    # 检查HR发的简历请求卡片（"我想要一份您的附件简历"）
                    items = im_list.eles('css:.item-friend')
                    for item in items:
                        text = (item.text or '').strip()
                        if '附件简历' in text and '同意' in text:
                            result["resume_requested"] = True
            except:
                pass

        except Exception as e:
            print(f"    -> 检查交换状态失败: {e}")

        return result

    # ========== 同意HR的简历请求 ==========
    def accept_resume_request(self) -> bool:
        """
        HR发的"我想要一份您的附件简历，您是否同意"卡片 -> 点击同意
        Returns: True if accepted
        """
        print("  [ACTION] 检查并同意HR简历请求...")
        try:
            im_list = self.page.ele('.im-list', timeout=3)
            if not im_list:
                return False

            # 找HR发的简历请求卡片
            items = im_list.eles('css:.item-friend')
            for item in items:
                text = (item.text or '').strip()
                if '附件简历' in text and '同意' in text:
                    # 找"同意"按钮
                    agree_btn = item.ele('text:同意', timeout=2)
                    if agree_btn:
                        agree_btn.click(by_js=True)
                        random_delay(2, 3)
                        print("    -> 已同意HR简历请求")
                        return True
            print("    -> 没找到HR简历请求卡片")
            return False
        except Exception as e:
            print(f"    -> 同意简历请求失败: {e}")
            return False

    # ========== 同意HR的电话/微信交换请求 ==========
    def accept_contact_request(self) -> bool:
        """
        HR发的联系方式交换卡片 -> 点击"电话号码"或"微信号码"
        Returns: True if any accepted
        """
        print("  [ACTION] 检查HR联系方式交换请求...")
        try:
            im_list = self.page.ele('.im-list', timeout=3)
            if not im_list:
                return False
            accepted = False
            items = im_list.eles('css:.item-friend')
            for item in items:
                text = (item.text or '').strip()
                if '电话号码' in text or '微信号码' in text:
                    # 优先点"电话号码"
                    phone_link = item.ele('text:电话号码', timeout=1)
                    if phone_link:
                        phone_link.click(by_js=True)
                        random_delay(2, 3)
                        print("    -> 已发送电话号码")
                        accepted = True
                    wx_link = item.ele('text:微信号码', timeout=1)
                    if wx_link:
                        wx_link.click(by_js=True)
                        random_delay(2, 3)
                        print("    -> 已发送微信号码")
                        accepted = True
            if not accepted:
                print("    -> 没找到联系方式交换请求")
            return accepted
        except Exception as e:
            print(f"    -> 处理联系方式请求失败: {e}")
            return False

    # ========== 辅助方法 ==========
    def _close_popup(self):
        """关闭可能的弹窗"""
        try:
            # 按ESC
            from DrissionPage.common import Keys
            self.page.actions.key_down(Keys.ESCAPE)
            time.sleep(0.5)
        except:
            pass
        try:
            # 点击遮罩层
            mask = self.page.ele('css:.dialog-mask', timeout=1)
            if mask:
                mask.click()
        except:
            pass
        try:
            # 点击取消按钮
            cancel = self.page.ele('text:取消', timeout=1)
            if cancel:
                cancel.click(by_js=True)
        except:
            pass

    def is_resume_btn_available(self) -> bool:
        """检查发简历按钮是否存在"""
        try:
            btn = self.page.ele('css:.toolbar-btn[d-c="62009"]', timeout=1)
            return btn is not None
        except:
            return False

    def is_phone_btn_available(self) -> bool:
        """检查换电话按钮是否存在"""
        try:
            btn = self.page.ele('css:.btn-contact', timeout=2)
            return btn is not None
        except:
            return False

    def is_wechat_btn_available(self) -> bool:
        """检查换微信按钮是否存在"""
        try:
            btn = self.page.ele('css:.btn-weixin', timeout=2)
            return btn is not None
        except:
            return False
