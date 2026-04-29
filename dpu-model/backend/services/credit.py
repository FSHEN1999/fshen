# -*- coding: utf-8 -*-
"""额度测算模型"""

from services.risk import INCOME_MIDPOINTS


def calculate_quota(
    income_range: str,
    risk_level: str,
    risk_score: float,
    age: int | None = None,
) -> tuple[float, int, float]:
    """
    额度测算，返回(额度, 建议还款周期月数, 年利率)
    """
    midpoint = INCOME_MIDPOINTS.get(income_range, 5000)

    # 基础额度 = 月收入 * 系数
    if risk_level == "低":
        base_multiplier = 24
    elif risk_level == "中":
        base_multiplier = 12
    else:
        return 0, 0, 0  # 高风险不给额度

    base_quota = midpoint * base_multiplier

    # 风险分数微调（60-100分对应0.6-1.0倍）
    ratio = max(0.6, risk_score / 100)
    quota = round(base_quota * ratio, -2)  # 百元取整

    # 额度范围限制
    quota = max(1000, min(500000, quota))

    # 还款周期
    if quota <= 10000:
        period = 6
    elif quota <= 50000:
        period = 12
    elif quota <= 200000:
        period = 24
    else:
        period = 36

    # 利率（年化）：低风险低利率
    if risk_level == "低":
        rate = 0.068  # 6.8%
    else:
        rate = 0.098  # 9.8%

    return quota, period, rate
