"""
面试管理模块
- 识别面试邀约
- 记录面试安排
- 提醒（输出到文件/飞书通知）
"""
import json
import re
from pathlib import Path
from datetime import datetime, date


class InterviewManager:
    INTERVIEWS_FILE = "interviews.json"

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.path = data_dir / self.INTERVIEWS_FILE
        self.interviews = self._load()

    def _load(self) -> list:
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return []

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.interviews, f, ensure_ascii=False, indent=2)

    def add(self, company: str, job: str, hr_name: str, 
            interview_type: str = "", time_str: str = "", 
            location: str = "", raw_msg: str = ""):
        """记录一个面试安排"""
        raw_key = (raw_msg or "")[:200]
        for item in self.interviews:
            if (
                item.get("company") == company
                and item.get("job") == job
                and item.get("hr_name") == hr_name
                and item.get("raw_msg") == raw_key
            ):
                print(f"  📅 面试记录已存在: {company} - {job}")
                return {**item, "_duplicate": True}

        entry = {
            "id": len(self.interviews) + 1,
            "company": company,
            "job": job,
            "hr_name": hr_name,
            "type": interview_type,  # 线上/线下/电话
            "time": time_str,
            "location": location,
            "raw_msg": raw_key,
            "status": "pending",  # pending/confirmed/completed/cancelled
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.interviews.append(entry)
        self._save()
        print(f"  📅 面试记录已保存: {company} - {job}")
        return entry

    def get_upcoming(self) -> list:
        """获取待进行的面试"""
        return [i for i in self.interviews if i["status"] == "pending"]

    def summary(self) -> str:
        """生成面试汇总"""
        total = len(self.interviews)
        pending = len([i for i in self.interviews if i["status"] == "pending"])
        completed = len([i for i in self.interviews if i["status"] == "completed"])
        
        lines = [f"📅 面试管理 (共{total}个)"]
        lines.append(f"  待面试: {pending} | 已完成: {completed}")
        lines.append("")
        
        for iv in self.interviews:
            status_icon = {"pending": "⏳", "confirmed": "✅", "completed": "✔", "cancelled": "❌"}.get(iv["status"], "?")
            lines.append(f"  {status_icon} [{iv['id']}] {iv['company']} - {iv['job']}")
            if iv.get("time"):
                lines.append(f"     时间: {iv['time']}")
            if iv.get("type"):
                lines.append(f"     形式: {iv['type']}")
            if iv.get("location"):
                lines.append(f"     地点: {iv['location']}")
        
        return "\n".join(lines)


def extract_interview_info(text: str) -> dict:
    """从消息中提取面试信息"""
    info = {}

    # 面试类型
    if re.search(r"线上|远程|视频面|腾讯会议|zoom|teams|飞书面", text, re.I):
        info["type"] = "线上面试"
    elif re.search(r"电话面|电话沟通", text, re.I):
        info["type"] = "电话面试"
    elif re.search(r"线下|到公司|现场|来.*面", text, re.I):
        info["type"] = "线下面试"
    elif re.search(r"笔试|机试|在线测", text, re.I):
        info["type"] = "笔试/机试"

    # 时间
    time_patterns = [
        r"(\d{1,2}月\d{1,2}[日号]\s*[上下]午?\s*\d{1,2}[：:]\d{2})",
        r"(明天|后天|周[一二三四五六日天])\s*([上下]午)?\s*(\d{1,2}[：:]\d{2})?",
        r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}\s*\d{1,2}[：:]\d{2})",
        r"(\d{1,2}[：:]\d{2})\s*(开始|面试)",
    ]
    for pat in time_patterns:
        m = re.search(pat, text)
        if m:
            info["time"] = m.group(0).strip()
            break

    # 地点
    loc_patterns = [
        r"地[址点][:：]?\s*(.{5,50})",
        r"(南山|福田|宝安|龙华|龙岗|罗湖|前海|科技园|软件产业基地|粤海街道).{0,30}",
    ]
    for pat in loc_patterns:
        m = re.search(pat, text)
        if m:
            info["location"] = m.group(0).strip()[:80]
            break

    return info
