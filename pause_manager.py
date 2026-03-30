# -*- coding: utf-8 -*-
"""
暂停管理器 - 支持通过空格键暂停/继续自动化脚本

使用方法:
    from pause_manager import PauseManager

    pause_mgr = PauseManager()

    # 在脚本的检查点调用
    pause_mgr.check_pause()

    # 或在循环中使用
    while running:
        # ... 你的代码 ...
        pause_mgr.check_pause()
"""

import sys
import time
import threading
from typing import Optional

# Windows平台使用msvcrt检测按键
if sys.platform == "win32":
    import msvcrt
else:
    # 非Windows平台使用termios/tty（需要终端支持）
    import termios
    import tty


class StopScriptException(Exception):
    """用户请求停止脚本执行的异常"""
    pass


class PauseManager:
    """暂停管理器：通过空格键控制脚本暂停/继续"""

    def __init__(self, pause_key: str = " ", stop_key: str = "s", stop_combo: str = "ctrl+f12"):
        """
        初始化暂停管理器

        Args:
            pause_key: 触发暂停的按键，默认为空格键
            stop_key: 触发停止的按键，默认为's'键
            stop_combo: 触发停止的组合键，默认为'ctrl+f12'
        """
        self._paused = False
        self._pause_key = pause_key
        self._stop_key = stop_key.lower()
        self._stop_combo = stop_combo.lower()
        self._lock = threading.Lock()
        # 是否启用暂停功能（可通过环境变量PAUSE_ENABLED控制）
        self._enabled = True
        # 实时监听线程
        self._listener_thread: Optional[threading.Thread] = None
        self._stop_listener = False
        # 停止标志
        self._stopped = False

    def __del__(self):
        """析构函数，确保停止监听线程"""
        self._stop_listener = True
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=1.0)

    @property
    def is_paused(self) -> bool:
        """当前是否处于暂停状态"""
        return self._paused

    @property
    def is_enabled(self) -> bool:
        """暂停功能是否已启用"""
        return self._enabled

    @property
    def is_stopped(self) -> bool:
        """当前是否已停止"""
        return self._stopped

    def enable(self) -> None:
        """启用暂停功能"""
        self._enabled = True
        self._start_listener()

    def disable(self) -> None:
        """禁用暂停功能"""
        self._enabled = False
        self._stop_listener = True
        # 如果当前暂停，自动恢复
        if self._paused:
            self._paused = False
            print("\n[暂停管理] 暂停功能已禁用，自动继续执行\n")

    def toggle(self) -> bool:
        """
        切换暂停状态

        Returns:
            切换后的暂停状态
        """
        with self._lock:
            self._paused = not self._paused
            return self._paused

    def stop(self) -> None:
        """停止脚本执行（但不关闭浏览器）"""
        with self._lock:
            if not self._stopped:
                self._stopped = True
                print("\n" + "=" * 50)
                print("🛑 脚本已停止")
                print("=" * 50)
                print("💡 提示: 浏览器将保持打开状态供您手动检查")
                print("=" * 50)

    def _check_key(self) -> Optional[str]:
        """检测键盘输入（非阻塞方式）"""
        try:
            if sys.platform == "win32":
                # Windows平台使用msvcrt
                if msvcrt.kbhit():
                    key_bytes = msvcrt.getch()
                    
                    # 处理特殊键和组合键
                    if key_bytes == b'\x00' or key_bytes == b'\xe0':
                        # 这是功能键的前缀，读取下一个字节
                        key_bytes = msvcrt.getch()
                        
                        # F12键的扫描码是0x8c (140 in decimal)
                        if key_bytes == b'\x8c':
                            return 'f12'
                        # 其他功能键也可以在这里处理
                        elif key_bytes == b';':  # F1
                            return 'f1'
                        elif key_bytes == b'<':  # F2
                            return 'f2'
                        # ... 其他功能键
                        else:
                            # 返回功能键的十六进制表示
                            return f'fkey_{key_bytes.hex()}'
                    
                    try:
                        # 尝试解码为字符串
                        key = key_bytes.decode('utf-8')
                        return key
                    except UnicodeDecodeError:
                        # 处理特殊情况
                        if key_bytes == b' ':  # 空格键
                            return ' '
                        elif key_bytes == b'\r':  # 回车键
                            return '\r'
                        elif key_bytes == b'\n':  # 换行键
                            return '\n'
                        elif key_bytes == b'\t':  # Tab键
                            return '\t'
                        elif key_bytes == b'\x1b':  # ESC键
                            return '\x1b'
                        elif key_bytes == b'\x8c':  # F12键（如果没有前缀）
                            return 'f12'
                        else:
                            # 对于其他无法解码的字节，返回其十六进制表示用于调试
                            return f'unknown_{key_bytes.hex()}'
            else:
                # 非Windows平台（需要终端支持）
                import select
                import termios
                import tty
                
                # 保存当前终端设置
                old_settings = termios.tcgetattr(sys.stdin)
                try:
                    tty.setcbreak(sys.stdin.fileno())
                    if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                        key = sys.stdin.read(1)
                        return key
                finally:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        except Exception:
            # 如果检测失败，返回None
            pass
        return None

    def _start_listener(self) -> None:
        """启动实时键盘监听线程"""
        if not self._enabled or (self._listener_thread and self._listener_thread.is_alive()):
            return

        self._stop_listener = False
        self._listener_thread = threading.Thread(target=self._keyboard_listener, daemon=True)
        self._listener_thread.start()

    def _keyboard_listener(self) -> None:
        """后台键盘监听线程"""
        while not self._stop_listener:
            try:
                key = self._check_key()
                if key is not None:
                    if key == self._pause_key:
                        with self._lock:
                            if not self._paused:
                                self._paused = True
                                # 在主线程中显示暂停信息
                                print("\n" + "=" * 50)
                                print("⏸️  脚本已暂停")
                                print("=" * 50)
                                print("💡 提示: 按 [空格键] 继续执行，按 [F12键] 停止脚本")
                                print("=" * 50)
                            else:
                                self._paused = False
                                print("\n▶️  继续执行...\n")
                    elif key.lower() == self._stop_key or key.lower() == 'f12':
                        with self._lock:
                            if not self._stopped:
                                self._stopped = True
                                print("\n" + "=" * 50)
                                print("🛑 脚本已停止")
                                print("=" * 50)
                                print("💡 提示: 浏览器将保持打开状态供您手动检查")
                                print("=" * 50)
                time.sleep(0.05)  # 短暂休眠避免CPU占用过高
            except Exception as e:
                # 忽略监听过程中的异常，但可以记录调试信息
                # print(f"[DEBUG] 键盘监听异常: {e}")
                time.sleep(0.1)

    def _wait_for_resume(self) -> None:
        """等待用户按空格键继续（简化版，因为暂停检测已由后台线程处理）"""
        while self._paused and not self._stop_listener:
            time.sleep(0.1)  # 等待后台线程检测到继续信号

    def check_pause(self, show_hint: bool = True) -> None:
        """
        检查是否需要暂停（在关键检查点调用）

        Args:
            show_hint: 是否在首次使用时显示提示信息
        """
        if not self._enabled:
            return

        # 首次调用时启动监听线程
        if self._listener_thread is None or not self._listener_thread.is_alive():
            self._start_listener()

        # 如果处于暂停状态，等待恢复
        if self._paused:
            self._wait_for_resume()
        # 如果已停止，抛出异常让调用方处理
        if self._stopped:
            raise StopScriptException("用户请求停止脚本执行")
    def pause(self) -> None:
        """手动触发暂停（代码方式）"""
        if not self._enabled:
            return

        with self._lock:
            if not self._paused:
                self._paused = True
                print("\n" + "=" * 50)
                print("⏸️  脚本已暂停")
                print("=" * 50)
                print("💡 提示: 按 [空格键] 继续执行")
                print("=" * 50)

        self._wait_for_resume()

    def resume(self) -> None:
        """手动恢复（代码方式）"""
        with self._lock:
            if self._paused:
                self._paused = False
                print("\n▶️  已恢复执行\n")


# 全局单例实例
_global_pause_manager: Optional[PauseManager] = None


def get_pause_manager() -> PauseManager:
    """获取全局暂停管理器实例"""
    global _global_pause_manager
    if _global_pause_manager is None:
        _global_pause_manager = PauseManager()
        # 自动启用实时监听
        _global_pause_manager.enable()
    return _global_pause_manager


def check_pause(show_hint: bool = True) -> None:
    """
    快捷方式：检查暂停状态

    Args:
        show_hint: 是否在首次使用时显示提示信息
    """
    get_pause_manager().check_pause(show_hint)
