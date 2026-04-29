# -*- coding: utf-8 -*-
"""风控引擎"""

from typing import Optional


# 收入范围对应的中位数
INCOME_MIDPOINTS = {
    "3000以下": 2000,
    "3000-5000": 4000,
    "5000-10000": 7500,
    "10000-20000": 15000,
    "20000-50000": 35000,
    "50000以上": 75000,
}


def assess_risk(
    age: Optional[int],
    income_range: str,
    income_source: str,
    id_card_valid: bool,
) -> tuple[str, str, float]:
    """
    风险评估，返回(风险等级, 风险说明, 风险分数0-100)
    分数越低风险越高
    """
    score = 60.0  # 基础分

    # 年龄因素
    if age is not None:
        if 25 <= age <= 50:
            score += 15
        elif 18 <= age < 25 or 50 < age <= 60:
            score += 5
        else:
            score -= 10

    # 收入因素
    midpoint = INCOME_MIDPOINTS.get(income_range, 0)
    if midpoint >= 20000:
        score += 20
    elif midpoint >= 10000:
        score += 15
    elif midpoint >= 5000:
        score += 10
    elif midpoint >= 3000:
        score += 5
    else:
        score -= 5

    # 收入来源稳定性
    stable_sources = ["工资", "经营收入", "公务员", "事业单位"]
    if any(s in income_source for s in stable_sources):
        score += 10
    else:
        score += 3

    # 身份证有效性
    if not id_card_valid:
        score -= 30

    # 映射到风险等级
    score = max(0, min(100, score))
    if score >= 70:
        return "低", "", score
    elif score >= 40:
        return "中", "建议适当降低借款额度", score
    else:
        return "高", "风险较高，暂时无法通过资质评估", score
