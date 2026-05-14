"""
登录 & Cookie管理
- 首次: 打开BOSS直聘登录页，用户手动扫码，保存Cookie
- 后续: 自动加载Cookie，检测有效性
"""
import json
import os
import time
from pathlib import Path
from DrissionPage import ChromiumPage, ChromiumOptions


class BossAuth:
    COOKIE_FILE = "cookies.json"
    BASE_URL = "https://www.zhipin.com"
    LOGIN_URL = "https://www.zhipin.com/web/user/?ka=header-login"
    CHAT_URL = os.environ.get("BOSS_CHAT_URL", "https://www.zhipin.com/web/geek/chat")
    LOGGED_IN_SELECTORS = (
        ".user-nav",
        ".nav-figure",
        ".chat-conversation",
        ".chat-content-wrap",
        ".chat-message",
        ".chat-record",
        ".message-controls",
        ".friend-list",
        ".friend-content",
        ".friend-content-warp",
        ".chat-no-data",
        ".rec-job-list",
    )
    NEGATIVE_LOGIN_MARKERS = (
        "扫码登录",
        "密码登录",
        "验证码",
        "安全验证",
        "请完成验证",
        "登录后",
        "登录/注册",
        "登录注册后",
        "我要找工作 我要招聘",
    )

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.profile_name = os.environ.get("BOSS_PROFILE_NAME", "chrome_profile_fengshen").strip() or "chrome_profile_fengshen"
        self.profile_path = data_dir / self.profile_name
        cookie_name = self.COOKIE_FILE if self.profile_name == "chrome_profile" else f"cookies.{self.profile_name}.json"
        self.cookie_path = data_dir / cookie_name
        self.page = None
        self._last_alert_text = ""
        self._init_browser_with_recovery()

    def _is_browser_alive(self) -> bool:
        """轻量健康检测：能拿到 url 就算活。"""
        try:
            _ = self.page.url
            return True
        except Exception:
            return False

    def _kill_stale_chrome(self):
        """清理残留 Chrome 进程（Windows 侧）。仅在 attach 失败时调用。"""
        import subprocess
        try:
            # 只杀我们启动的那个 user-data-dir 对应的进程不可靠，
            # 保守做法：只 kill 不影响用户主 Chrome 的边缘进程——跳过这步，
            # 改为换一个新的 user-data-dir。
            pass
        except Exception:
            pass

    def _init_browser_with_recovery(self, max_retry: int = 2):
        last_err = None
        for attempt in range(max_retry + 1):
            try:
                self._init_browser()
                # 立刻做一次健康检测
                if self._is_browser_alive():
                    return
                raise RuntimeError("browser init returned half-dead page")
            except Exception as e:
                last_err = e
                print(f"  ⚠ 浏览器初始化失败 (attempt {attempt+1}/{max_retry+1}): {e}")
                self.page = None
                time.sleep(2)
        raise RuntimeError(f"无法初始化浏览器: {last_err}")

    def _init_browser(self):
        """初始化浏览器（使用Windows Chrome）"""
        co = ChromiumOptions()
        chrome_path = self._resolve_chrome_path()
        co.set_browser_path(chrome_path)
        # 反检测设置
        co.set_argument("--disable-blink-features=AutomationControlled")
        co.set_argument("--no-first-run")
        co.set_argument("--no-default-browser-check")
        # 用户数据目录（持久化登录态）。BOSS 对浏览器身份比较敏感，允许按任务隔离 profile。
        user_data = str(self.profile_path)
        co.set_argument(f"--user-data-dir={user_data}")
        port = int(os.environ.get("BOSS_CHROME_PORT") or ("9223" if self.profile_name == "chrome_profile_java_agent" else "9222"))
        co.set_local_port(port)
        co.set_argument("--remote-debugging-address=127.0.0.1")
        co.set_argument(f"--remote-debugging-port={port}")
        print(f" Chrome debug port: {port}")
        print(f" Chrome profile: {user_data}")
        
        self.page = ChromiumPage(co)

    def _resolve_chrome_path(self) -> str:
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
            r"/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe",
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        return candidates[0]

    def login(self):
        """打开登录页，等待用户扫码"""
        print(" 正在打开BOSS直聘登录页...")
        self.page.get(self.LOGIN_URL)
        
        print(" 请用BOSS直聘APP扫码登录...")
        print("   （等待登录完成，最长120秒）")
        
        # 等待登录成功（检测URL变化或特定元素出现）
        for i in range(120):
            time.sleep(1)
            if self._is_logged_in_page():
                print(" 登录成功，正在进入聊天页验证会话...")
                if self.recover_chat_page():
                    print(" 登录成功!")
                    self._save_cookies()
                    return True
                print(" 登录后聊天页验证失败，请在当前浏览器里重新完成登录/验证")
                self._safe_get(self.LOGIN_URL)
        
        print(" 登录超时，请重试")
        return False

    def check_login(self) -> bool:
        """检查登录状态"""
        # 优先信任持久化 Chrome profile。旧 cookies.json 可能过期，启动时先注入会干扰当前会话。
        self._dismiss_pending_alert()
        self._safe_get(self.CHAT_URL)
        time.sleep(3)
        self._dismiss_pending_alert()

        if self._is_logged_in_page():
            print(" Chrome profile valid, logged in")
            self._save_cookies()
            return True

        # 旧 cookies 回灌可能把刚扫码的新登录态污染回失效态；默认关闭，仅排障时手动开启。
        if os.environ.get("BOSS_COOKIE_FALLBACK", "0") == "1" and self._load_cookies():
            self._dismiss_pending_alert()
            self._safe_get(self.CHAT_URL)
            time.sleep(3)
            self._dismiss_pending_alert()
            if self._is_logged_in_page():
                print(" Cookie valid, logged in")
                self._save_cookies()
                return True
        elif self.cookie_path.exists():
            print(" Skip cookies fallback (set BOSS_COOKIE_FALLBACK=1 to enable)")

        # Check if redirected to login page
        if "login" in self.page.url.lower() or "web/user" in self.page.url:
            print(" Cookie expired")
            return False

        return False

    def recover_chat_page(self) -> bool:
        """清掉残留提示框并回到新版聊天页，供 apply -> sweep -> watch 阶段切换使用。"""
        self._dismiss_pending_alert()
        self._safe_get(self.CHAT_URL)
        time.sleep(2)
        self._dismiss_pending_alert()
        return self._is_logged_in_page()

    def _safe_get(self, url: str) -> None:
        """Navigate with alert cleanup; BOSS may leave an unsent-draft prompt after chat input."""
        self._last_alert_text = ""
        try:
            self.page.get(url)
            return
        except Exception:
            if self._dismiss_pending_alert():
                self.page.get(url)
                return
            raise

    def _dismiss_pending_alert(self) -> bool:
        """Close a browser alert left by BOSS before navigation or DOM operations."""
        dismissed = False
        self._last_alert_text = ""
        try:
            for _ in range(3):
                text = self.page.handle_alert(accept=True, timeout=0.5)
                if text is False or text is None:
                    break
                self._last_alert_text = str(text)
                print(f" 已关闭页面提示框: {self._last_alert_text[:80]}")
                dismissed = True
        except Exception:
            pass
        return dismissed

    def _is_logged_in_page(self) -> bool:
        """根据页面元素判断当前是否已登录。"""
        url = (self.page.url or "").lower()
        if "登录信息失效" in self._last_alert_text:
            print(f" 登录态检查: 页面提示登录信息失效 url={self.page.url}")
            return False
        if "login" in url or "web/user" in url:
            print(f" 登录态检查: 当前在登录页 url={self.page.url}")
            return False

        # 明确的未登录/风控页面信号。不要用“找不到登录按钮”反推已登录。
        body_text = ""
        try:
            body = self.page.ele("tag:body", timeout=2)
            body_text = (body.text or "")[:1200] if body else ""
            if any(marker in body_text for marker in self.NEGATIVE_LOGIN_MARKERS):
                print(f" 登录态检查: 命中未登录/验证页面 marker，url={self.page.url}")
                return False
        except Exception:
            pass

        # 明确的登录态：用户导航、聊天壳、聊天列表、消息空态都说明已进入求职者工作区。
        try:
            for selector in self.LOGGED_IN_SELECTORS:
                if self.page.ele(selector, timeout=1):
                    return True
        except Exception:
            pass

        # BOSS 2026 新聊天页偶尔会改 class，导致 selector 全失效。
        # 只在已位于 chat URL 且没有未登录/验证文案时，用聊天页文案兜底，避免刚扫码成功后被误判为失效。
        if "/web/chat/" in url or "/web/chat/index" in url:
            chat_markers = ("全部", "未读", "沟通", "消息", "联系人")
            if body_text and any(marker in body_text for marker in chat_markers):
                print(f" 登录态检查: 聊天页文案兜底通过 url={self.page.url}")
                return True

        print(f" 登录态检查: 未找到明确登录信号，url={self.page.url}")
        return False

    def _save_cookies(self):
        """保存Cookie到文件"""
        cookies = self.page.cookies(all_domains=True, all_info=True)
        with open(self.cookie_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f"   Cookie已保存到 {self.cookie_path}")

    def _load_cookies(self):
        """从文件加载Cookie"""
        if not self.cookie_path.exists():
            return False
        try:
            with open(self.cookie_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            self.page.get(self.BASE_URL)
            time.sleep(1)
            for cookie in cookies:
                try:
                    self.page.set.cookies(cookie)
                except:
                    pass
            return True
        except Exception as e:
            print(f"   加载Cookie失败: {e}")
            return False
