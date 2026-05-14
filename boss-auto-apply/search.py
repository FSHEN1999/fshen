"""
BOSS zhipin job search & filter
2025 DOM: ul.rec-job-list > div.card-area > div.job-card-wrap > li (job card)
  Inside each li:
    a.job-name (title + href to detail)
    .job-salary
    .tag-list li (experience, education tags)
    .boss-name (company)
    .company-location
Strategy: find all a.job-name, walk up to parent li for full card context
"""
import time
import random
import re
from urllib.parse import quote
from anti_detect import random_delay, random_scroll


class JobSearcher:
    SEARCH_URL = "https://www.zhipin.com/web/geek/job?query={keyword}&city=101280600"

    def __init__(self, page, config: dict):
        self.page = page
        self.config = config
        self.max_pages = config["limits"]["max_pages"]
        self.blacklist_companies = config.get("blacklist", {}).get("companies", [])
        self.blacklist_titles = config.get("blacklist", {}).get("title_keywords", [])
        self.salary_min_k = config.get("search", {}).get("salary_min_k", 0)

    def search(self, keyword: str) -> list:
        jobs = []
        url = self.SEARCH_URL.format(keyword=quote(keyword))
        self.page.get(url)
        random_delay(1.5, 3)

        for page_num in range(1, self.max_pages + 1):
            print(f"  Page {page_num}...", flush=True)

            page_jobs = self._parse_job_list()
            if not page_jobs:
                print(f"  Page {page_num} empty, stop.", flush=True)
                break

            filtered = [j for j in page_jobs if self._filter_job(j)]
            jobs.extend(filtered)
            print(f"    Found {len(page_jobs)}, after filter {len(filtered)}", flush=True)

            if not self._next_page():
                break

            random_delay()
            random_scroll(self.page)

        return jobs

    def _parse_job_list(self) -> list:
        jobs = []
        try:
            # Find all job-name elements (a tags with job title + URL)
            # 加超时，避免冷门关键词列表加载卡死
            name_els = self.page.eles(".job-name", timeout=8)
            if not name_els:
                return jobs

            for name_el in name_els:
                try:
                    job = self._extract_from_name_el(name_el)
                    if job:
                        jobs.append(job)
                except Exception:
                    continue
        except Exception as e:
            print(f"    Parse error: {e}", flush=True)

        return jobs

    def _extract_from_name_el(self, name_el) -> dict:
        """Extract job info starting from the .job-name element"""
        try:
            title = name_el.text.strip()
            href = name_el.attr("href") or ""
            if href and not href.startswith("http"):
                href = "https://www.zhipin.com" + href

            if not title or not href:
                return None

            # Walk up to find the card container (li tag)
            card = name_el
            for _ in range(6):
                card = card.parent()
                if card.tag == "li":
                    break

            # Extract other fields from the card
            salary = ""
            salary_el = card.ele(".job-salary", timeout=0.2)
            if salary_el:
                salary = salary_el.text.strip()

            company = ""
            company_el = card.ele(".boss-name", timeout=0.2)
            if not company_el:
                company_el = card.ele(".company-name", timeout=0.2)
            if company_el:
                company = company_el.text.strip()

            location = ""
            loc_el = card.ele(".company-location", timeout=0.2)
            if loc_el:
                location = loc_el.text.strip()

            # Tags
            tags = []
            tag_list = card.ele(".tag-list", timeout=0.2)
            tag_lis = card.eles(".tag-list li", timeout=0.2) if tag_list else []
            if not tag_lis:
                # DrissionPage may not support chained selector, try another way
                if tag_list:
                    tag_lis = tag_list.eles("tag:li", timeout=0.2)
            for tl in tag_lis:
                tags.append(tl.text.strip())

            return {
                "title": title,
                "salary": salary,
                "company": company,
                "url": href,
                "location": location,
                "tags": tags,
                "info": " ".join(tags) + " " + location,
            }
        except:
            return None

    def _filter_job(self, job: dict) -> bool:
        for bc in self.blacklist_companies:
            if bc and bc in job.get("company", ""):
                return False

        title = job.get("title", "")
        for bk in self.blacklist_titles:
            if bk and bk.lower() in title.lower():
                return False

        title_l = title.lower()
        info_l = (job.get("info", "") or "").lower()
        direction_text = f"{title_l} {info_l}"
        direction_hints = (
            "测试", "测开", "qa", "quality", "自动化", "接口", "性能",
            "jmeter", "selenium", "requests", "postman", "质量",
            "测试负责人", "测试组长", "agent", "智能体", "ai", "大模型",
            "金融", "银行", "数据迁移",
        )
        if not any(hint in direction_text for hint in direction_hints):
            print(f"    ⊘ 方向不匹配跳过: {job.get('company','')} {title}", flush=True)
            return False

        # 过滤无效URL
        url = job.get("url", "")
        if not url or "zhipin.com" not in url:
            return False

        # 薪资下限过滤：salary 形如 "15-25K" / "15-30K·13薪" / "面议"
        if self.salary_min_k > 0:
            sal = job.get("salary", "") or ""
            m = re.search(r'(\d+)[-~](\d+)\s*K', sal)
            if m:
                job_min = int(m.group(1))
                if job_min < self.salary_min_k:
                    print(f"    ⊘ 薪资过低跳过: {job.get('company','')} {title} {sal}", flush=True)
                    return False
            # 无法解析(面议/日结等)保守保留，不拒

        return True

    def _next_page(self) -> bool:
        try:
            next_btn = self.page.ele("a.ui-icon-arrow-right", timeout=0.5)
            if not next_btn:
                all_a = self.page.eles(".options-pages a", timeout=0.5)
                for a in all_a:
                    if ">" in a.text or "下" in a.text:
                        next_btn = a
                        break

            if next_btn:
                cls = next_btn.attr("class") or ""
                if "disabled" in cls:
                    return False
                next_btn.click()
                random_delay(1, 2)
                return True
        except:
            pass
        return False
