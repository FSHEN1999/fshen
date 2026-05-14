"""
检查BOSS直聘聊天界面的GUI功能状态
- 工具栏按钮（发简历、换电话、换微信）是否可见可用
- 当前聊天的完整信息
- 检测还有哪些可扩展的UI元素
"""
import sys, time
sys.path.insert(0, '.')
from auth import BossAuth
from anti_detect import random_delay

from pathlib import Path
auth = BossAuth(data_dir=Path('data'))
page = auth.page

# 确保在聊天页
if "web/geek/chat" not in (page.url or ""):
    page.get("https://www.zhipin.com/web/geek/chat")
    time.sleep(5)

print("="*60)
print("BOSS直聘 GUI状态检查")
print("="*60)

# 1. 点击第一个聊天
print("\n[1] 点击第一个聊天...")
items = page.eles('.friend-content-warp')
if items:
    item = items[0]
    name_el = item.ele(".name-text", timeout=0)
    name = name_el.text.strip() if name_el else "?"
    fc = item.ele(".friend-content", timeout=0) or item
    fc.click()
    time.sleep(3)
    print(f"  打开了: {name}")
else:
    print("  ❌ 没有聊天项")
    sys.exit(1)

# 2. 检查工具栏按钮
print("\n[2] 检查工具栏按钮...")
toolbar_selectors = {
    "表情": '.btn-emotion',
    "常用语": '.btn-dict',
    "发图片": '.btn-sendimg',
    "发简历(d-c=62009)": 'css:.toolbar-btn[d-c="62009"]',
    "换电话(btn-contact)": '.btn-contact',
    "换微信(btn-weixin)": '.btn-weixin',
}

for label, sel in toolbar_selectors.items():
    try:
        el = page.ele(sel, timeout=2)
        if el:
            cls = el.attr('class') or ''
            aria = el.attr('aria-label') or ''
            dc = el.attr('d-c') or ''
            text = (el.text or '').strip()[:30]
            disabled = 'unable' in cls or 'disabled' in cls
            status = "❌禁用" if disabled else "✅可用"
            print(f"  {label}: {status} | text='{text}' | aria='{aria}' | d-c='{dc}'")
            if '请求中' in aria or '等待' in aria:
                print(f"    → 已发起请求，等待对方回复")
        else:
            print(f"  {label}: ⚠️ 未找到")
    except Exception as e:
        print(f"  {label}: ❌ 异常: {e}")

# 3. 检查工具栏完整DOM
print("\n[3] 完整工具栏内容...")
try:
    toolbar = page.ele('.chat-controls', timeout=3)
    if toolbar:
        children = toolbar.eles('css:*')
        seen = set()
        for child in children[:50]:
            cls = child.attr('class') or ''
            dc = child.attr('d-c') or ''
            tag = child.tag or ''
            text = (child.text or '').strip()[:40]
            key = f"{tag}.{cls}"
            if key in seen or not cls:
                continue
            seen.add(key)
            if any(k in cls for k in ['toolbar', 'btn-', 'chat-control', 'action']):
                print(f"  <{tag}> class='{cls}' d-c='{dc}' text='{text}'")
    else:
        print("  ⚠️ .chat-controls 未找到")
except Exception as e:
    print(f"  异常: {e}")

# 4. 检查聊天区域其他可交互元素
print("\n[4] 聊天区域其他可交互元素...")
try:
    # 检查顶部信息区
    top_info = page.ele('.top-info-content', timeout=2)
    if top_info:
        print(f"  顶部信息: {top_info.text[:100]}")
    
    # 检查是否有快捷操作
    quick_actions = page.eles('css:.quick-action, .message-action, .card-action, .operate-btn', timeout=2)
    for qa in quick_actions[:5]:
        print(f"  快捷操作: {qa.text[:50]} | class={qa.attr('class')}")
    
    # 检查底部/右侧面板
    panels = page.eles('css:.right-panel, .side-panel, .chat-aside, .panel-wrap', timeout=2)
    for p in panels[:3]:
        print(f"  面板: class={p.attr('class')} text={p.text[:50]}")
        
except Exception as e:
    print(f"  异常: {e}")

# 5. 检查HR请求卡片（同意简历/联系方式卡片）
print("\n[5] 检查HR请求卡片...")
try:
    im_list = page.ele('.im-list', timeout=3)
    if im_list:
        cards = im_list.eles('css:.message-card-wrap')
        print(f"  找到 {len(cards)} 个卡片消息")
        for i, card in enumerate(cards[-5:]):
            text = (card.text or '').strip()[:80]
            # 检查是否有可点击按钮
            btns = card.eles('css:a, button, .btn, [role=button]')
            btn_texts = [b.text.strip()[:20] for b in btns if b.text.strip()]
            print(f"  卡片{i}: {text} | 按钮: {btn_texts}")
        
        # 检查系统消息
        sys_msgs = im_list.eles('css:.item-system')
        print(f"  系统消息: {len(sys_msgs)} 条")
        for sm in sys_msgs[-3:]:
            print(f"    系统: {sm.text[:60]}")
    else:
        print("  im-list 未找到")
except Exception as e:
    print(f"  异常: {e}")

# 6. 检查右侧 HR 信息面板
print("\n[6] 检查HR/职位信息面板...")
try:
    # 尝试各种可能的选择器
    selectors = [
        '.chat-greet', '.start-head', '.job-info', '.boss-info',
        '.chat-header', '.dialog-header', '.info-card',
        'css:[class*="info-panel"]', 'css:[class*="job-detail"]',
        'css:[class*="position"]', '.chat-start',
    ]
    for sel in selectors:
        try:
            el = page.ele(sel, timeout=1)
            if el:
                text = (el.text or '').strip()[:100]
                print(f"  {sel}: {text}")
        except:
            pass
except Exception as e:
    print(f"  异常: {e}")

# 7. 检查页面上所有可见按钮/链接
print("\n[7] 页面按钮/链接扫描...")
try:
    all_btns = page.eles('css:button, .btn, [role=button], a.btn', timeout=2)
    for btn in all_btns[:20]:
        text = (btn.text or '').strip()[:40]
        cls = btn.attr('class') or ''
        if text and len(text) > 1:
            print(f"  按钮: '{text}' | class='{cls[:60]}'")
except Exception as e:
    print(f"  异常: {e}")

print("\n" + "="*60)
print("检查完成")
