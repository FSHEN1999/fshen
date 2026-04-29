# -*- coding: utf-8 -*-
"""数据库配置与应用常量"""

import os

# 数据库配置（开发环境使用SQLite）
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dpu_model.db")

# JWT配置
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dpu-model-secret-key-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7

# 短信验证码配置
SMS_CODE_LENGTH = 6
SMS_CODE_EXPIRE_SECONDS = 300  # 5分钟有效
SMS_CODE_COOLDOWN_SECONDS = 60  # 60秒获取冷却
SMS_CODE_MAX_ERRORS = 3  # 连续错误3次限制

# 登录锁定配置
LOGIN_MAX_FAILURES = 3
LOGIN_LOCK_MINUTES = 30

# 额度配置
QUOTA_VALID_DAYS = 30
QUOTA_MIN = 1000
QUOTA_MAX = 500000

# 接口响应超时（秒）
API_TIMEOUT = 3
