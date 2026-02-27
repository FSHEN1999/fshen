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


class PauseManager:
    """暂停管理器：通过空格键控制脚本暂停/继续"""

    def __init__(self, pause_key: str = " "):
        """
        初始化暂停管理器

        Args:
            pause_key: 触发暂停的按键，默认为空格键
        """
        self._paused = False
        self._pause_key = pause_key
        self._lock = threading.Lock()
        # 是否启用暂停功能（可通过环境变量PAUSE_ENABLED控制）
        self._enabled = True

    @property
    def is_paused(self) -> bool:
        """当前是否处于暂停状态"""
        return self._paused

    @property
    def is_enabled(self) -> bool:
        """暂停功能是否已启用"""
        return self._enabled

    def enable(self) -> None:
        """启用暂停功能"""
        self._enabled = True

    def disable(self) -> None:
        """禁用暂停功能"""
        self._enabled = False
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

    def _check_key(self) -> Optional[str]:
        """
        非阻塞检测是否有按键按下

        Returns:
            按下的字符，如果没有按键则返回None
        """
        if sys.platform == "win32":
            if msvcrt.kbhit():
                return msvcrt.getch().decode('utf-8', errors='ignore')
        else:
            # 非Windows平台的实现需要更复杂的处理
            # 这里简化处理，返回None表示不支持
            pass
        return None

    def _wait_for_resume(self) -> None:
        """等待用户按空格键继续"""
        print("\n" + "=" * 50)
        print("⏸️  脚本已暂停")
        print("=" * 50)
        print("💡 提示: 按 [空格键] 继续执行")
        print("=" * 50)

        while True:
            key = self._check_key()
            if key == self._pause_key:
                print("\n▶️  继续执行...\n")
                with self._lock:
                    self._paused = False
                break
            time.sleep(0.1)  # 避免CPU占用过高

    def check_pause(self, show_hint: bool = True) -> None:
        """
        检查是否需要暂停（在关键检查点调用）

        Args:
            show_hint: 是否在首次使用时显示提示信息
        """
        if not self._enabled:
            return

        # 检测是否有空格键按下
        key = self._check_key()
        if key == self._pause_key:
            self._paused = True

        # 如果处于暂停状态，等待恢复
        if self._paused:
            self._wait_for_resume()

    def pause(self) -> None:
        """手动触发暂停（代码方式）"""
        with self._lock:
            self._paused = True
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
    return _global_pause_manager


def check_pause(show_hint: bool = True) -> None:
    """
    快捷方式：检查暂停状态

    Args:
        show_hint: 是否在首次使用时显示提示信息
    """
    get_pause_manager().check_pause(show_hint)
