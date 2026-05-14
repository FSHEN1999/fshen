"""
投递日志记录 & 报告
"""
import csv
import json
from datetime import datetime, date
from pathlib import Path
from file_ops import safe_write_json


class ApplyLogger:
    LOG_FILE = "jobs_log.csv"
    APPLIED_FILE = "applied.json"
    STATUS_FILE = "apply_status.json"

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.log_path = data_dir / self.LOG_FILE
        self.applied_path = data_dir / self.APPLIED_FILE
        self.status_path = data_dir / self.STATUS_FILE
        self._applied_urls = self._load_applied()

        # 确保CSV文件有表头
        if not self.log_path.exists():
            with open(self.log_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["时间", "公司", "职位", "薪资", "URL", "状态", "备注"])

    def _load_applied(self) -> set:
        """加载已投递URL集合"""
        if self.applied_path.exists():
            try:
                with open(self.applied_path, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except:
                pass
        return set()

    def _save_applied(self):
        """保存已投递URL"""
        with open(self.applied_path, "w", encoding="utf-8") as f:
            json.dump(list(self._applied_urls), f, ensure_ascii=False)

    def is_applied(self, url: str) -> bool:
        """检查是否已投递"""
        return url in self._applied_urls

    def log(self, job: dict, status: str, note: str = ""):
        """记录投递结果"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        url = job.get("url", "")

        # 写入CSV
        with open(self.log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                now,
                job.get("company", ""),
                job.get("title", ""),
                job.get("salary", ""),
                url,
                status,
                note,
            ])

        # 记录到去重集合
        if url and status == "success":
            self._applied_urls.add(url)
            self._save_applied()

    def update_status(self, stage: str, job: dict | None = None, **extra):
        """写入当前执行阶段，供 status/watch 脚本实时查看。"""
        payload = {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stage": stage,
            "job": job or {},
            **extra,
        }
        safe_write_json(self.status_path, payload)

    def daily_summary(self) -> dict:
        """今日投递汇总"""
        today = date.today().strftime("%Y-%m-%d")
        total = success = skipped = failed = 0

        if not self.log_path.exists():
            return {"total": 0, "success": 0, "skipped": 0, "failed": 0}

        with open(self.log_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # 跳过表头
            for row in reader:
                if not row or not row[0].startswith(today):
                    continue
                total += 1
                status = row[5] if len(row) > 5 else ""
                if status == "success":
                    success += 1
                elif status == "skipped":
                    skipped += 1
                elif status == "failed":
                    failed += 1

        return {"total": total, "success": success, "skipped": skipped, "failed": failed}

    def print_report(self):
        """打印详细报告"""
        if not self.log_path.exists():
            print(" 暂无投递记录")
            return

        # 按日期统计
        daily_stats = {}
        total_all = 0

        with open(self.log_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if not row:
                    continue
                day = row[0][:10]
                if day not in daily_stats:
                    daily_stats[day] = {"total": 0, "success": 0, "skipped": 0, "failed": 0}
                daily_stats[day]["total"] += 1
                total_all += 1
                status = row[5] if len(row) > 5 else ""
                if status in daily_stats[day]:
                    daily_stats[day][status] += 1

        print(f"\n 投递报告（共 {total_all} 条记录）")
        print("-" * 50)
        for day, stats in sorted(daily_stats.items(), reverse=True):
            print(f"  {day}: 投递 {stats['total']} |  {stats['success']} | ⏭ {stats['skipped']} |  {stats['failed']}")
        print("-" * 50)
        print(f"  已投递去重URL数: {len(self._applied_urls)}")
