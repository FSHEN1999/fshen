# -*- coding: utf-8 -*-
"""信息校验服务"""

import re
from typing import Optional


def validate_id_card(id_card: str) -> tuple[bool, str]:
    """身份证号校验（含校验位验证）"""
    if not re.match(r"^\d{17}[\dXx]$", id_card):
        return False, "身份证号格式不正确"

    # 加权因子
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    check_codes = "10X98765432"

    total = sum(int(id_card[i]) * weights[i] for i in range(17))
    expected = check_codes[total % 11]
    if id_card[-1].upper() != expected:
        return False, "身份证号校验位不正确"

    # 提取生日校验
    year = int(id_card[6:10])
    month = int(id_card[10:12])
    day = int(id_card[12:14])
    if not (1900 <= year <= 2026 and 1 <= month <= 12 and 1 <= day <= 31):
        return False, "身份证号中的出生日期不正确"

    return True, "校验通过"


def validate_phone(phone: str) -> tuple[bool, str]:
    """手机号格式校验"""
    if not re.match(r"^1[3-9]\d{9}$", phone):
        return False, "手机号格式不正确，需为11位国内手机号"
    return True, "校验通过"


def validate_income_range(income_range: str) -> tuple[bool, str]:
    """收入范围校验"""
    valid_ranges = [
        "3000以下", "3000-5000", "5000-10000", "10000-20000",
        "20000-50000", "50000以上"
    ]
    if income_range not in valid_ranges:
        return False, f"收入范围应为以下选项之一：{', '.join(valid_ranges)}"
    return True, "校验通过"


def validate_share_ratio(ratio: float) -> tuple[bool, str]:
    """持股比例校验"""
    if ratio <= 0 or ratio > 100:
        return False, "持股比例应在0-100之间"
    # 精确到小数点后2位
    if round(ratio, 2) != ratio:
        return False, "持股比例精确到小数点后2位"
    return True, "校验通过"


def extract_age_from_id_card(id_card: str) -> Optional[int]:
    """从身份证号提取年龄"""
    try:
        year = int(id_card[6:10])
        return 2026 - year
    except (ValueError, IndexError):
        return None


def extract_gender_from_id_card(id_card: str) -> str:
    """从身份证号提取性别"""
    try:
        return "男" if int(id_card[16]) % 2 == 1 else "女"
    except (ValueError, IndexError):
        return "未知"
