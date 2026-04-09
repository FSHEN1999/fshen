# -*- coding: utf-8 -*-
"""
配置管理模块 - 从.env文件加载配置，支持环境变量覆盖
"""

import os
from typing import Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# 加载.env文件
load_dotenv(override=True)


@dataclass
class DatabaseConfig:
    """数据库配置"""
    host: str
    user: str
    password: str
    database: str = "dpu_seller_center"
    port: int = 3306
    charset: str = "utf8mb4"


@dataclass
class UIConfig:
    """UI自动化配置"""
    wait_timeout: int  # 元素等待超时（秒）
    action_delay: float  # 操作间隔延迟（秒）
    password: str  # 测试密码
    verification_code: str  # 验证码（固定值）
    email_domain: str  # 邮箱域名


@dataclass
class FileConfig:
    """文件路径配置"""
    data_file_path: str  # 测试数据文件
    screenshot_folder: str  # 截图保存文件夹


@dataclass
class PollingConfig:
    """轮询配置"""
    max_attempts: int  # 最大轮询次数
    interval: int  # 轮询间隔（秒）


class Config:
    """全局配置管理器"""

    def __init__(self, env: str = None):
        # 环境
        if env:
            self.env = env.lower()
        else:
            self.env = os.getenv("ENV", "uat").lower()
        
        # 为兼容性添加environment属性
        self.environment = self.env
        
        # 验证环境值
        valid_envs = ["sit", "uat", "dev", "preprod", "reg", "local"]
        if self.env not in valid_envs:
            raise ValueError(f"不支持的环境: {self.env}（支持: {', '.join(valid_envs)}）")
        
        # 构建数据库配置
        self._setup_database_config()
        
        # UI配置
        self.ui = UIConfig(
            wait_timeout=int(os.getenv("WAIT_TIMEOUT", "30")),
            action_delay=float(os.getenv("ACTION_DELAY", "1.5")),
            password=os.getenv("PASSWORD", "Aa11111111.."),
            verification_code=os.getenv("VERIFICATION_CODE", "666666"),
            email_domain=os.getenv("EMAIL_DOMAIN", "163.com")
        )
        
        # 文件配置
        self.files = FileConfig(
            data_file_path=os.getenv("DATA_FILE_PATH", r"C:\Users\PC\Desktop\测试数据.txt"),
            screenshot_folder=os.getenv("SCREENSHOT_FOLDER", r"C:\Users\PC\Desktop\截图")
        )
        
        # 轮询配置
        self.polling = PollingConfig(
            max_attempts=int(os.getenv("POLL_MAX_ATTEMPTS", "120")),
            interval=int(os.getenv("POLL_INTERVAL", "5"))
        )
        
        # 日志级别
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    def _setup_database_config(self):
        """根据环境设置数据库配置"""
        env_upper = self.env.upper()
        
        host = os.getenv(f"DATABASE_HOST_{env_upper}")
        user = os.getenv(f"DATABASE_USER_{env_upper}")
        password = os.getenv(f"DATABASE_PASSWORD_{env_upper}")
        
        if not all([host, user, password]):
            raise ValueError(f"未找到环境 {self.env} 的数据库配置")
        
        self.database = DatabaseConfig(
            host=host,
            user=user,
            password=password,
            port=int(os.getenv("DATABASE_PORT", "3306")),
            charset=os.getenv("DATABASE_CHARSET", "utf8mb4")
        )

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典"""
        return {
            "env": self.env,
            "database": {
                "host": self.database.host,
                "user": self.database.user,
                "database": self.database.database,
                "port": self.database.port,
                "charset": self.database.charset,
            },
            "ui": {
                "wait_timeout": self.ui.wait_timeout,
                "action_delay": self.ui.action_delay,
                "password": "***" if self.ui.password else None,
                "verification_code": self.ui.verification_code,
                "email_domain": self.ui.email_domain,
            },
            "files": {
                "data_file_path": self.files.data_file_path,
                "screenshot_folder": self.files.screenshot_folder,
            },
            "polling": {
                "max_attempts": self.polling.max_attempts,
                "interval": self.polling.interval,
            }
        }


# 全局配置实例（延迟初始化，避免import时提前执行）
_config = None


def _ensure_config():
    """确保全局配置已初始化"""
    global _config
    if _config is None:
        _config = Config()
    return _config


def load_config(env: str = None) -> Config:
    """
    加载配置实例
    
    Args:
        env: 环境名称（sit/uat/dev/preprod/reg/local），默认为.env中的ENV或uat
    
    Returns:
        Config实例
    """
    if env:
        return Config(env=env)
    else:
        return _ensure_config()


# 为向后兼容添加config属性
config = None
