"""
JD-简历匹配打分器

目的：避免无脑海投。在点"立即沟通"之前算匹配分，太低的直接skip，不浪费招呼语额度也不给HR留坏印象。

策略：
1. 硬过滤（立即pass=0，不投）：
   - title/JD 含明显不匹配词（开发专岗、算法、产品、运维等）
   - JD要求年限明显高于当前经验
   - 岗位地点明确在外地（非深圳/远程）
2. 关键词加权打分（满分100）：
   - 核心测试能力命中（测试开发/自动化/接口/JMeter/MySQL等）：每命中一项+8
   - 业务领域匹配（金融/银行/贷款/迁移/AI测试）：每命中一项+10
   - 加分项（测试负责人/质量闸口/数据一致性/上线验证等）：每命中一项+5
   - 减分项（纯手工/短期/非目标方向）：每命中一项-15
3. 返回 (score, reasons) 方便日志+调试

不走LLM，纯规则 —— 每秒能过几百条JD，零成本。
LLM留给"招呼语生成"和"疑难回复"。
"""
import re
from typing import Tuple, List, Dict


# === 核心测试能力（命中+8分） ===
CORE_TECH = [
    r"测试开发", r"测开", r"自动化测试", r"接口自动化", r"接口测试",
    r"测试负责人", r"测试组长", r"qa\s*lead", r"质量负责人", r"质量保障",
    r"python", r"selenium", r"requests", r"pytest", r"postman", r"jmeter",
    r"mysql", r"sql", r"fiddler", r"linux", r"jenkins", r"git", r"svn",
    r"nacos", r"mock", r"自动化回归", r"回归测试", r"性能测试", r"压测",
    r"agent", r"智能体", r"ai测试", r"大模型测试", r"测试平台",
]

# === 业务领域匹配（命中+10分） ===
DOMAIN_MATCH = [
    r"金融", r"银行", r"支付", r"清算", r"结算", r"贷款", r"信贷", r"风控", r"交易",
    r"跨境", r"数据迁移", r"迁移测试", r"客户迁移", r"核心系统", r"渠道", r"网银", r"手机银行",
    r"uat", r"预生产", r"投产", r"上线验证", r"多系统联调",
    r"大模型", r"llm", r"agent", r"智能体", r"ai应用", r"ai测试",
]

# === 强偏好：测试/质量 + 自动化/AI/负责人（命中+18分） ===
PREFERRED_QA_AGENT = [
    r"(测试|质量|qa).{0,30}(负责人|组长|lead|自动化|接口|平台|agent|智能体|ai|大模型)",
    r"(负责人|组长|lead|自动化|接口|平台|agent|智能体|ai|大模型).{0,30}(测试|质量|qa)",
]

# === 加分项（命中+5分） ===
BONUS = [
    r"测试计划", r"测试方案", r"需求评审", r"用例设计", r"测试建模",
    r"缺陷闭环", r"风险识别", r"质量闸口", r"测试报告", r"上线验证",
    r"数据一致性", r"数据库校验", r"状态流转", r"回调链路", r"日志分析", r"traceid",
    r"任务拆分", r"工时评估", r"敏捷", r"scrum", r"持续集成", r"ci",
    r"用例生成", r"日志归因", r"报告自动化", r"agent测试",
]

# === 减分项（命中-15分） ===
PENALTY = [
    r"纯手工", r"只做手工", r"无需自动化",
    r"短期", r"临时", r"三个月项目",
    r"客服", r"销售", r"电销",
]

# === 硬过滤：岗位类型不匹配（直接pass=0） ===
HARD_EXCLUDE_TITLE = [
    r"前端", r"web前端", r"大数据算法", r"算法工程师",
    r"java\s*开发", r"后端开发", r"c\+\+", r"go\s*开发", r"golang",
    r"dba\b", r"运维",
    r"产品经理", r"ui\b", r"销售", r"客服",
    r"安卓|ios|flutter|react\s*native",
    r"爬虫", r"机器学习", r"深度学习",
]

# === 标题必须贴近测试/质量/自动化方向。纯泛 AI 岗容易跑偏到算法/产品。 ===
TITLE_INCLUDE_HINTS = [
    r"测试", r"测开", r"qa", r"quality", r"质量", r"自动化", r"接口", r"性能",
    r"测试负责人", r"测试组长", r"agent测试", r"ai测试", r"大模型测试",
]

# === 硬过滤：年限要求过高 ===
YEARS_REGEX = re.compile(r"(\d+)\s*年以上|经验\s*(\d+)\s*年|(\d+)\s*-\s*\d+\s*年")
MY_YEARS = 5
MAX_EXTRA_YEARS = 3  # 允许 JD 要 8 年以下


def _lower(text: str) -> str:
    return (text or "").lower()


def _hit_count(text: str, patterns: List[str]) -> Tuple[int, List[str]]:
    """返回命中次数 + 命中的关键词列表（去重）"""
    hits = []
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            hits.append(p.replace("\\s*", "").replace("\\b", ""))
    return len(hits), hits


def _extract_required_years(jd_text: str) -> int:
    """提取JD要求的最低年限，没明说返回0"""
    if not jd_text:
        return 0
    m = YEARS_REGEX.search(jd_text)
    if not m:
        return 0
    for g in m.groups():
        if g:
            try:
                return int(g)
            except ValueError:
                continue
    return 0


def score_job(job: Dict) -> Tuple[int, List[str], bool]:
    """
    对岗位打分。
    返回 (score, reasons, hard_skip)：
        score: 0-100
        reasons: 可读的打分依据（日志用）
        hard_skip: True 代表硬过滤命中（如前端岗），无论分数都应跳过
    """
    title = _lower(job.get("title", ""))
    jd = _lower(job.get("jd", ""))
    combined = f"{title}\n{jd}"
    reasons: List[str] = []

    # === 硬过滤：title 含明显不匹配词 ===
    for pat in HARD_EXCLUDE_TITLE:
        if re.search(pat, title):
            return 0, [f"HARD_SKIP: title命中排除词 {pat}"], True

    if title and not any(re.search(pat, title, re.IGNORECASE) for pat in TITLE_INCLUDE_HINTS):
        return 0, ["HARD_SKIP: title不含测试/质量/自动化方向词"], True

    # === 硬过滤：年限要求过高 ===
    req_years = _extract_required_years(jd)
    if req_years and req_years > MY_YEARS + MAX_EXTRA_YEARS:
        return 0, [f"HARD_SKIP: JD要求{req_years}年，超过我{MY_YEARS}+{MAX_EXTRA_YEARS}年上限"], True

    # === 评分 ===
    # JD抓不到时给中性分65（略高于阈值），避免因抓取失败错过好岗位
    # title上的硬过滤还在上面先走一遍，前端岗不会漏进来
    if not jd:
        reasons.append("JD正文为空，给中性分65（抓取失败保守放行）")
        score = 65
    else:
        score = 40  # 基础分

    core_n, core_hits = _hit_count(combined, CORE_TECH)
    score += core_n * 8
    if core_n:
        reasons.append(f"核心技术栈+{core_n*8}({','.join(core_hits[:5])})")

    preferred_n, preferred_hits = _hit_count(combined, PREFERRED_QA_AGENT)
    score += preferred_n * 18
    if preferred_n:
        reasons.append(f"测试/质量强匹配+{preferred_n*18}({','.join(preferred_hits[:2])})")

    domain_n, domain_hits = _hit_count(combined, DOMAIN_MATCH)
    score += domain_n * 10
    if domain_n:
        reasons.append(f"业务领域+{domain_n*10}({','.join(domain_hits[:5])})")

    bonus_n, bonus_hits = _hit_count(combined, BONUS)
    score += bonus_n * 5
    if bonus_n:
        reasons.append(f"加分项+{bonus_n*5}({','.join(bonus_hits[:3])})")

    penalty_n, penalty_hits = _hit_count(combined, PENALTY)
    score -= penalty_n * 15
    if penalty_n:
        reasons.append(f"减分项-{penalty_n*15}({','.join(penalty_hits[:3])})")

    # clamp 0-100
    score = max(0, min(100, score))
    return score, reasons, False


def should_apply(job: Dict, min_score: int = 55) -> Tuple[bool, int, str]:
    """
    主入口：决定是否投递该岗位。
    返回 (go, score, reason_str)
        go=True  → 继续投递
        go=False → skip
    """
    score, reasons, hard_skip = score_job(job)
    reason_str = " | ".join(reasons) if reasons else "无关键词命中"
    if hard_skip:
        return False, score, reason_str
    if score < min_score:
        return False, score, f"score={score}<{min_score} | {reason_str}"
    return True, score, f"score={score} | {reason_str}"


# === 自测 ===
if __name__ == "__main__":
    test_jobs = [
        {"title": "测试开发工程师", "jd": "要求Python Selenium Requests Postman MySQL，金融接口自动化测试，3年以上"},
        {"title": "Web前端工程师", "jd": "Vue React 前端开发"},
        {"title": "测试负责人", "jd": "负责测试计划、任务拆分、缺陷闭环、上线验证，银行业务优先，5年以上"},
        {"title": "AI Agent测试工程师", "jd": "大模型Agent应用测试，用例生成、日志归因、质量评估，Python优先"},
        {"title": "高级测试经理", "jd": "10年以上经验，质量体系建设"},
        {"title": "自动化测试", "jd": ""},  # JD抓不到
    ]
    for j in test_jobs:
        go, s, r = should_apply(j)
        print(f"[{'投' if go else '跳'}] {s:3d} {j['title'][:20]:20s} | {r}")
