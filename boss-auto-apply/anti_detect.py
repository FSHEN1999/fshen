"""
反检测策略
"""
import time
import random
import os


def random_delay(min_sec=None, max_sec=None):
    """随机延迟，模拟人类操作"""
    if min_sec is None:
        min_sec = 3
    if max_sec is None:
        max_sec = 8
    if os.environ.get("BOSS_FAST_MODE") == "1":
        min_sec = min(min_sec, 0.8)
        max_sec = min(max_sec, 1.8)
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


def random_scroll(page, times=None):
    """随机滚动页面"""
    if times is None:
        times = 1 if os.environ.get("BOSS_FAST_MODE") == "1" else random.randint(1, 3)
    for _ in range(times):
        # 随机滚动距离
        scroll_y = random.randint(200, 600)
        try:
            page.scroll.down(scroll_y)
        except:
            try:
                page.run_js(f"window.scrollBy(0, {scroll_y})")
            except:
                pass
        if os.environ.get("BOSS_FAST_MODE") == "1":
            time.sleep(random.uniform(0.1, 0.3))
        else:
            time.sleep(random.uniform(0.5, 1.5))


def random_mouse_move(page):
    """随机移动鼠标（增加真实性）"""
    try:
        x = random.randint(100, 800)
        y = random.randint(100, 600)
        page.actions.move_to(x, y)
        time.sleep(random.uniform(0.2, 0.5))
    except:
        pass
