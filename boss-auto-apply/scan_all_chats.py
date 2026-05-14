"""扫描全部聊天列表，找出所有最后一条是HR发的（需要回复的）"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from auth import BossAuth
import time
from candidate_profile import load_resume

from pathlib import Path
auth = BossAuth(data_dir=Path('data'))
page = auth.page

# 先去聊天页
page.get('https://www.zhipin.com/web/geek/chat')
time.sleep(3)

# 点"全部"tab（不是未读）
try:
    all_tab = page.ele('text:全部', timeout=3)
    if all_tab:
        all_tab.click()
        time.sleep(2)
        print("已切换到「全部」tab")
except:
    print("未找到全部tab，使用当前列表")

# 扫描聊天列表
chat_items = page.eles('css:[d-c="62001"]', timeout=5)
print(f"\n可见聊天数: {len(chat_items)}")

need_reply = []
already_replied = []

for i, item in enumerate(chat_items[:50]):
    try:
        # 获取名称
        name_el = item.ele('css:.name-text', timeout=1)
        name = name_el.text.strip() if name_el else f"未知{i}"
        
        # 获取公司
        company_el = item.ele('css:.company-text', timeout=1)
        company = company_el.text.strip() if company_el else ""
        
        # 获取最后消息
        msg_el = item.ele('css:.last-msg-text', timeout=1)
        last_msg = msg_el.text.strip() if msg_el else ""
        
        # 获取未读标记
        badge_el = item.ele('css:.unread-tips', timeout=0.5)
        unread = badge_el.text.strip() if badge_el else ""
        
        # 判断最后消息是不是自己发的
        # 自己发的消息前面通常没有前缀，HR的有名字前缀
        # 简单判断：如果last_msg以"您好"开头且包含候选人姓名，大概率是自己
        is_mine = False
        candidate_name = load_resume().get("name", "")
        if (candidate_name and candidate_name in last_msg) or last_msg.startswith('您好！我是') or last_msg.startswith('好的，我在BOSS'):
            is_mine = True
        if '我的期望薪资' in last_msg or '随时可以到岗' in last_msg:
            is_mine = True
            
        status = "⬜已回" if is_mine else "🔴需回"
        if unread:
            status = f"🔴未读{unread}"
            
        info = f"  [{i+1}] {name}@{company} | {status} | {last_msg[:40]}"
        print(info)
        
        if not is_mine and not unread:
            need_reply.append(f"{name}@{company}: {last_msg[:50]}")
        elif unread:
            need_reply.append(f"{name}@{company} [未读{unread}]: {last_msg[:50]}")
            
    except Exception as e:
        print(f"  [{i+1}] 错误: {e}")

print(f"\n=== 需要关注的聊天: {len(need_reply)} ===")
for r in need_reply:
    print(f"  {r}")
