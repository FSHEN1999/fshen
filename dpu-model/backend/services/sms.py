# -*- coding: utf-8 -*-
"""短信验证码服务（开发环境模拟）"""

import random
import time
from typing import Optional


class SmsService:
    """验证码管理，开发环境存内存"""

    def __init__(self):
        # {phone: {"code": str, "expire_at": float, "error_count": int, "cooldown_until": float}}
        self._store: dict[str, dict] = {}

    def send_code(self, phone: str) -> tuple[bool, str]:
        """发送验证码，返回(是否成功, 消息)"""
        now = time.time()
        record = self._store.get(phone, {})

        # 冷却检查
        cooldown_until = record.get("cooldown_until", 0)
        if now < cooldown_until:
            remaining = int(cooldown_until - now)
            return False, f"请{remaining}秒后再获取验证码"

        # 错误次数限制检查
        if record.get("error_count", 0) >= 3:
            block_until = record.get("block_until", 0)
            if now < block_until:
                return False, "验证码错误次数过多，请稍后重试"
            # 解除限制
            record["error_count"] = 0

        # 生成6位验证码
        code = f"{random.randint(0, 999999):06d}"

        self._store[phone] = {
            "code": code,
            "expire_at": now + 300,  # 5分钟有效
            "error_count": record.get("error_count", 0),
            "cooldown_until": now + 60,  # 60秒冷却
            "block_until": record.get("block_until", 0),
        }

        # 开发环境直接打印验证码
        print(f"[短信模拟] 手机号={phone} 验证码={code}")
        return True, code

    def verify_code(self, phone: str, code: str) -> tuple[bool, str]:
        """验证验证码，返回(是否正确, 消息)"""
        record = self._store.get(phone)
        if not record:
            return False, "请先获取验证码"

        now = time.time()

        # 错误次数限制检查
        block_until = record.get("block_until", 0)
        if record.get("error_count", 0) >= 3 and now < block_until:
            return False, "验证码错误次数过多，请稍后重试"

        if now > record.get("expire_at", 0):
            return False, "验证码已过期，请重新获取"

        if record["code"] != code:
            record["error_count"] = record.get("error_count", 0) + 1
            if record["error_count"] >= 3:
                record["block_until"] = now + 300  # 限制5分钟
            return False, "验证码错误"

        # 验证成功，清除记录
        del self._store[phone]
        return True, "验证成功"

    def clear_cooldown(self, phone: str):
        """清除指定手机号的冷却时间（注册成功后调用）"""
        record = self._store.get(phone)
        if record:
            record["cooldown_until"] = 0


# 全局单例
sms_service = SmsService()
