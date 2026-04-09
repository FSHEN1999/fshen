# -*- coding: utf-8 -*-
"""
测试 config.py 配置管理模块
"""

import unittest
import os
from unittest.mock import patch, MagicMock
from libs.config import Config, load_config, DatabaseConfig, UIConfig, FileConfig, PollingConfig


class TestDatabaseConfig(unittest.TestCase):
    """数据库配置测试"""
    
    def test_database_config_creation(self):
        """测试DatabaseConfig对象创建"""
        db_config = DatabaseConfig(
            host="localhost",
            user="test_user",
            password="test_pass",
            database="test_db",
            port=3306,
            charset="utf8mb4"
        )
        
        self.assertEqual(db_config.host, "localhost")
        self.assertEqual(db_config.user, "test_user")
        self.assertEqual(db_config.port, 3306)
        self.assertEqual(db_config.charset, "utf8mb4")
    
    def test_database_config_defaults(self):
        """测试DatabaseConfig默认值"""
        db_config = DatabaseConfig(
            host="localhost",
            user="test_user",
            password="test_pass"
        )
        
        self.assertEqual(db_config.database, "dpu_seller_center")
        self.assertEqual(db_config.port, 3306)
        self.assertEqual(db_config.charset, "utf8mb4")


class TestUIConfig(unittest.TestCase):
    """UI配置测试"""
    
    def test_ui_config_creation(self):
        """测试UIConfig对象创建"""
        ui_config = UIConfig(
            wait_timeout=30,
            action_delay=1.5,
            password="Aa11111111..",
            verification_code="666666",
            email_domain="163.com"
        )
        
        self.assertEqual(ui_config.wait_timeout, 30)
        self.assertEqual(ui_config.action_delay, 1.5)
        self.assertEqual(ui_config.password, "Aa11111111..")
        self.assertEqual(ui_config.verification_code, "666666")


class TestFileConfig(unittest.TestCase):
    """文件配置测试"""
    
    def test_file_config_creation(self):
        """测试FileConfig对象创建"""
        file_config = FileConfig(
            data_file_path=r"C:\test\data.txt",
            screenshot_folder=r"C:\test\screenshots"
        )
        
        self.assertEqual(file_config.data_file_path, r"C:\test\data.txt")
        self.assertEqual(file_config.screenshot_folder, r"C:\test\screenshots")


class TestPollingConfig(unittest.TestCase):
    """轮询配置测试"""
    
    def test_polling_config_creation(self):
        """测试PollingConfig对象创建"""
        polling_config = PollingConfig(
            max_attempts=120,
            interval=5
        )
        
        self.assertEqual(polling_config.max_attempts, 120)
        self.assertEqual(polling_config.interval, 5)


class TestConfig(unittest.TestCase):
    """主配置类测试"""
    
    @patch.dict(os.environ, {
        "ENV": "uat",
        "WAIT_TIMEOUT": "30",
        "ACTION_DELAY": "1.5",
        "PASSWORD": "Aa11111111..",
        "VERIFICATION_CODE": "666666",
        "DATABASE_HOST_UAT": "test-host",
        "DATABASE_USER_UAT": "test-user",
        "DATABASE_PASSWORD_UAT": "test-pass",
        "DATABASE_PORT": "3306"
    })
    def test_config_initialization(self):
        """测试Config初始化"""
        config = Config(env="uat")
        
        self.assertEqual(config.environment, "uat")
        self.assertEqual(config.ui.wait_timeout, 30)
        self.assertEqual(config.ui.verification_code, "666666")
    
    def test_invalid_environment(self):
        """测试无效环境名称"""
        with self.assertRaises(ValueError) as context:
            Config(env="invalid_env")
        
        self.assertIn("不支持的环境", str(context.exception))
    
    @patch.dict(os.environ, {
        "ENV": "uat",
        "DATABASE_HOST_UAT": "",  # 故意设置为空字符串
        "DATABASE_USER_UAT": "",
        "DATABASE_PASSWORD_UAT": ""
    }, clear=True)
    def test_missing_database_config(self):
        """测试缺失数据库配置"""
        with self.assertRaises(ValueError):
            Config(env="uat")  # 没有有效的DATABASE_*变量
    
    @patch.dict(os.environ, {
        "ENV": "uat",
        "DATABASE_HOST_UAT": "test-host",
        "DATABASE_USER_UAT": "test-user",
        "DATABASE_PASSWORD_UAT": "test-pass"
    })
    def test_config_to_dict(self):
        """测试配置导出为字典"""
        config = Config(env="uat")
        config_dict = config.to_dict()
        
        self.assertIn("env", config_dict)
        self.assertIn("database", config_dict)
        self.assertIn("ui", config_dict)
        self.assertEqual(config_dict["database"]["host"], "test-host")


class TestLoadConfig(unittest.TestCase):
    """加载配置函数测试"""
    
    @patch.dict(os.environ, {
        "ENV": "uat",
        "DATABASE_HOST_UAT": "test-host",
        "DATABASE_USER_UAT": "test-user",
        "DATABASE_PASSWORD_UAT": "test-pass"
    })
    def test_load_config_with_env(self):
        """测试加载指定环境的配置"""
        config = load_config(env="uat")
        
        self.assertEqual(config.environment, "uat")
        self.assertEqual(config.database.host, "test-host")
    
    @patch.dict(os.environ, {
        "ENV": "sit",
        "DATABASE_HOST_SIT": "sit-host",
        "DATABASE_USER_SIT": "sit-user",
        "DATABASE_PASSWORD_SIT": "sit-pass"
    })
    def test_load_config_without_env_uses_default(self):
        """测试不指定环境时使用默认环境"""
        config = load_config()
        
        self.assertEqual(config.environment, "sit")


if __name__ == "__main__":
    unittest.main()
