# -*- coding: utf-8 -*-
"""
HSBC 线下自动化注册工具

概述:
    直接访问注册页面完成HSBC线下注册流程的Selenium脚本。
    无需选择TIER级别和生成offerId，直接访问固定注册URL。

主要功能:
    1. 直接访问注册页面，无需offerId
    2. 自动化完成注册流程（支持5种浏览器的无痕模式）
    3. 完整的流程：注册→SP授权→公司信息→董事信息→核保→审批→PSP→电子签
    4. 详细的日志记录和错误处理机制
"""

import time
import os
import random
import logging
import re
import socket
import json
from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, Any
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import pymysql
from pymysql.err import OperationalError
from urllib.parse import urlencode
from datetime import datetime, timedelta

# ==============================================================================
# --- 1. 配置与常量 (集中管理，易于维护) ---
# ==============================================================================

# ============================ 环境配置 ============================
# 支持的环境：sit, uat, dev, preprod, reg, local
# 修改此变量以切换环境
ENV = "reg"

# 基础URL映射
BASE_URL_DICT = {
    "sit": "https://sit.api.expressfinance.business.hsbc.com",
    "dev": "https://dpu-gateway-dev.dowsure.com",
    "uat": "https://uat.api.expressfinance.business.hsbc.com",
    "preprod": "https://preprod.api.expressfinance.business.hsbc.com",
    "reg": "https://dpu-gateway-reg.dowsure.com",
    "local": "http://192.168.11.3:8080"
}

# 金额配置（按currency映射流程金额）
FLOW_AMOUNT_CONFIG = {
    "USD": {
        "underwritten_amount": "500000",
        "approved_amount": 500000.00,
        "esign_amount": 500000.00,
        "direct_flow_amount": 2000.00,
    },
    "CNY": {
        "underwritten_amount": "1500000",
        "approved_amount": 1500000.00,
        "esign_amount": 1500000.00,
        "direct_flow_amount": 70000.00,
    },
}

# 数据库配置
DATABASE_CONFIG_DICT = {
    "sit": {
        "host": "18.162.145.173",
        "user": "dpu_sit",
        "password": "20250818dpu_sit",
        "database": "dpu_seller_center",
        "port": 3306,
        "charset": "utf8mb4"
    },
    "dev": {
        "host": "aurora-dpu-dev.cluster-cxm4ce0i8nzq.ap-east-1.rds.amazonaws.com",
        "user": "dpu_dev",
        "password": "J9IUmPpD@Hon8Y#v",
        "database": "dpu_seller_center",
        "port": 3306,
        "charset": "utf8mb4"
    },
    "uat": {
        "host": "aurora-dpu-uat.cluster-cv2aqqmyo5k9.ap-east-1.rds.amazonaws.com",
        "user": "dpu_uat",
        "password": "6S[a=u.*Z;Zt~b&-A4|Ma&q^w8r_3vz[",
        "database": "dpu_seller_center",
        "port": 3306,
        "charset": "utf8mb4"
    },
    "preprod": {
        "host": "43.199.241.190",
        "user": "dpu_preprod",
        "password": "OWBSNfx8cC5c#Or0",
        "database": "dpu_seller_center",
        "port": 3306,
        "charset": "utf8mb4"
    },
    "reg": {
        "host": "aurora-dpu-reg.cluster-cxm4ce0i8nzq.ap-east-1.rds.amazonaws.com",
        "user": "dpu_reg",
        "password": "r4asUYBX3R6LNdp",
        "database": "dpu_seller_center",
        "port": 3306,
        "charset": "utf8mb4"
    },
    "local": {
        "host": "localhost",
        "user": "root",
        "password": "root",
        "database": "dpu_seller_center",
        "port": 3306,
        "charset": "utf8mb4"
    }
}

# 默认token映射
DEFAULT_TOKEN_DICT = {
    "sit": "wfVSribS934y6wZOtUAc5uU5eFcS2nUxcVjmy03OFInKt36rzGCS55EGLLHXS0YZ",
    "uat": "mjx0FpE9gnTC3OTmrX7znQzIgXRNQwV4umkOhF5wVb6AJB0DuVwmqh6zxiwma4B",
    "dev": "",
    "preprod": "",
    "reg": "",
    "local": ""
}

# 获取当前环境的基础URL和金额配置
BASE_URL = BASE_URL_DICT.get(ENV, BASE_URL_DICT["uat"])
CURRENT_AMOUNT_CONFIG = FLOW_AMOUNT_CONFIG["USD"]

# 线下注册固定URL（根据环境切换）
OFFLINE_SIGNUP_URL_DICT = {
    "sit": "https://expressfinance-dpu-sit.dowsure.com/en/",
    "dev": "https://expressfinance-dpu-dev.dowsure.com/en/sign-up-step1",
    "uat": "https://expressfinance-uat.business.hsbc.com/zh-Hans/sign-up",
    "preprod": "https://expressfinance-preprod.business.hsbc.com/zh-Hans/sign-up",
    "reg": "https://expressfinance-dpu-reg.dowsure.com/en/",
}
OFFLINE_SIGNUP_URL = OFFLINE_SIGNUP_URL_DICT.get(ENV, OFFLINE_SIGNUP_URL_DICT["sit"])

# 浏览器配置字典
BROWSER_CONFIG = {
    "CHROME": {
        "binary_path": "",
        "process_name": "chrome.exe"
    },
    "EDGE": {
        "binary_path": "",
        "process_name": "msedge.exe"
    },
    "QQ": {
        "binary_path": r"C:\Program Files\Tencent\QQBrowser\QQBrowser.exe",
        "process_name": "qqbrowser.exe"
    },
    "360": {
        "binary_path": r"C:\Users\PC\AppData\Roaming\360se6\Application\360se.exe",
        "process_name": "360se.exe"
    },
    "FIREFOX": {
        "binary_path": "",
        "process_name": "firefox.exe"
    }
}


@dataclass
class Config:
    """全局配置类"""
    # 文件路径
    DATA_FILE_PATH: str = rf"C:\Users\PC\Desktop\测试数据.txt"
    SCREENSHOT_FOLDER: str = r"C:\Users\PC\Desktop\截图"

    # Selenium配置
    WAIT_TIMEOUT: int = 30
    ACTION_DELAY: float = 1.5
    VERIFICATION_CODE: str = "666666"

    # 新增：密码设置页配置
    PASSWORD: str = "Aa11111111.."  # 密码


CONFIG = Config()


# 元素定位器字典（与线上自动化保持一致）
LOCATORS = {
    # 初始申请按钮
    "INITIAL_APPLY_BTN": (By.XPATH, "//button[contains(., '立即申请')]"),

    # 注册页面
    "PHONE_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[4]/div/div/div/div[2]/input"),
    "VERIFICATION_CODE_INPUTS": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @maxlength='1']"),
    "REG_NEXT_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[8]/button"),

    # 密码设置页 - 使用绝对XPath路径（与线上流程一致）
    "PASSWORD_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[1]/div[2]/div/div[1]/div/input"),
    "CONFIRM_PASSWORD_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[1]/div[5]/div/div[1]/div/input"),
    "SECURITY_QUESTION_DROPDOWN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[2]/div[2]/div/div/div[1]/div[1]/div[2]"),
    "SECURITY_ANSWER_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[2]/div[4]/div/div[1]/div/input"),
    "EMAIL_ADDRESS_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[3]/div[2]/div/div[1]/div/input"),
    # 声明页面的两个复选框
    "AGREE_CONSENT_CHECKBOX": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[4]/div[1]/div/label/span[1]/span"),
    "AUTHORIZATION_CHECKBOX": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[4]/div[2]/div/label/span[1]/span"),
    "FINAL_REGISTER_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[5]/div[2]/button"),

    # 通用下一步按钮
    "NEXT_BTN": (By.XPATH, "//button[contains(., '下一页')]"),

    # 最终申请按钮（跳转页面后）
    "FINAL_APPLY_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div[1]/div[3]/div[6]/button"),

    # 公司信息页
    "COMPANY_EN_NAME_INPUT": (By.XPATH, "(//input[contains(@class, 'el-input__inner') and @autocomplete='off'])[1]"),
    "BUSINESS_REG_NO_INPUT": (By.XPATH, "(//input[contains(@class, 'el-input__inner') and @autocomplete='off'])[3]"),
    # 线下流程特有的公司信息页元素
    "COMPANY_CN_NAME_INPUT": (By.XPATH, "//input[@placeholder='公司中文名称']"),
    "BUSINESS_NATURE_SELECT": (By.XPATH, "//span[text()='企业经营性质']/ancestor::div[contains(@class, 'el-form-item')]//div[contains(@class, 'el-select')]"),
    "BUSINESS_NATURE_OPTIONS": (By.XPATH, "//li[contains(@class, 'el-select-dropdown__item')]"),
    "ESTABLISHED_DATE_INPUT": (By.XPATH, "//input[@placeholder='YYYY/MM/DD']"),
    "REGISTERED_ADDRESS_INPUT": (By.XPATH, "//textarea[@placeholder='请输入注册地址']"),
    "COMPANY_NEXT_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/div[3]/div[2]/button[2]"),

    # 董事股东信息页
    "ID_NUMBER_INPUT": (By.XPATH, "//input[@placeholder='请输入证件号码']"),
    "ID_FRONT_UPLOAD_AREA": (By.XPATH, "//div[contains(@class, 'el-upload-dragger') and .//img[contains(@src, 'PRC%20ID-Front')]]"),
    "ID_BACK_UPLOAD_AREA": (By.XPATH, "//div[contains(@class, 'el-upload-dragger') and .//img[contains(@src, 'PRC%20ID-Back')]]"),
    "BIRTH_DATE_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/form/div/div[1]/div[2]/div/div[3]/div[1]/div/div[1]/div/input"),  # 董事信息-出生日期
    "DIRECTOR_NEXT_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div[5]/div[2]/button[2]"),
    "REFERENCE_PHONE_INPUT": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @maxlength='15']"),
    "REFERENCE_EMAIL_INPUT": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @autocomplete='off' and not(@maxlength) and not(@placeholder)]"),

    # 银行账户信息页
    # 银行选择主定位器（精准定位）
    "BANK_SELECT_CONTAINER": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div/form/div[2]/div/div/div/div[1]"),
    "BANK_SELECT_DROPDOWN": (By.XPATH, "//input[contains(@class, 'el-select__input') and @role='combobox']"),
    "BANK_SELECT_OPTIONS": (By.XPATH, "//li[contains(@class, 'el-select-dropdown__item')]"),
    "BANK_ACCOUNT_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div/form/div[5]/div/div/div/input"),
    # 银行选择备选定位器
    "BANK_SELECT_SVG_ICON": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div/form/div[2]/div/div/div/div[2]/i/svg"),
    "BANK_SELECT_DIV": (By.XPATH, "//div[contains(@class, 'el-select')]"),
    "BANK_SELECT_TRIGGER": (By.XPATH, "//div[contains(@class, 'el-select')]//span[contains(@class, 'el-select__suffix')]"),
    "BANK_SELECT_DISABLED_INPUT": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @readonly]"),
    "BANK_NEXT_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div/div[4]/div[2]/button[2]"),

    # 融资方案选择页 (Tier2)
    "ACTIVATE_NOW_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div/div[2]/div[1]/div/div/button"),
    "APPLY_HIGHER_AMOUNT_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div/div[2]/div[2]/div/div[2]/button"),

    # 审批成功后的额度确定页
    "ACTIVATE_CREDIT_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div[1]/div[3]/div[2]/div[7]/div[2]/button"),
    # 激活额度后的接受按钮
    "ACCEPT_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[3]/div/div/div/div/div/div/div[2]/div[3]/button")
}


# ==============================================================================
# --- 2. 日志配置 ---
# ==============================================================================
def setup_logging():
    """配置日志系统，使其输出更美观和实用"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler()
        ]
    )


# ==============================================================================
# --- 4. 工具函数 ---
# ==============================================================================
def generate_uuid() -> str:
    """生成UUID"""
    import uuid
    return str(uuid.uuid4())


def get_utc_time() -> str:
    """获取UTC时间"""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def get_local_time_str() -> str:
    """获取本地时间字符串"""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def get_user_choice(options: Dict[str, str], prompt: str) -> str:
    """通用函数，用于获取用户的有效选择"""
    print(f"\n{prompt}")
    for key, value in options.items():
        print(f"  {key}. {value}")
    while True:
        choice = input("请输入选项: ").strip()
        if choice in options:
            return choice
        print(f"输入无效，请从 {', '.join(options.keys())} 中选择。")


def get_yes_no_choice(prompt: str) -> bool:
    """获取用户的是否选择（返回True表示是，False表示否）"""
    options = {
        '1': '是',
        '2': '否'
    }
    print(f"\n{prompt}")
    for key, value in options.items():
        print(f"  {key}. {value}")
    while True:
        choice = input("请输入选项: ").strip()
        if choice in options:
            return choice == '1'
        print("输入无效，请输入 1 或 2。")


# ==============================================================================
# --- 4. 数据库配置 ---
# ==============================================================================
def get_local_physical_ip() -> Optional[str]:
    """获取本地物理网卡IP地址（用于绕过VPN直连数据库）"""
    try:
        # 创建一个UDP socket连接到公网地址（不会实际发送数据）
        # 这会触发系统选择最佳路由，通常是物理网卡
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # 连接到AWS的公网DNS（不实际发送数据）
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            # 排除常见的VPN虚拟网卡IP段
            if not local_ip.startswith(("10.", "172.16.", "192.168.", "127.")):
                return local_ip
            # 如果获取到的是内网IP，尝试通过主机名解析
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            if not local_ip.startswith(("10.", "172.16.", "192.168.", "127.")):
                return local_ip
    except Exception:
        pass
    # 如果上述方法失败，返回None让系统自动选择
    return None


class DBConfig:
    """数据库配置（支持多环境切换）"""
    _DATABASE_CONFIG = DATABASE_CONFIG_DICT

    @classmethod
    def get_config(cls, env: str = ENV) -> Dict[str, Any]:
        if env not in cls._DATABASE_CONFIG:
            raise ValueError(f"不支持的环境：{env}（支持：{', '.join(cls._DATABASE_CONFIG.keys())}）")
        return cls._DATABASE_CONFIG[env].copy()


class DatabaseExecutor:
    """数据库执行器（带自动重连机制）"""

    MAX_RECONNECT_ATTEMPTS = 3
    RECONNECT_DELAY = 2

    def __init__(self, env: str = ENV):
        self.config = DBConfig.get_config(env)
        self.conn: Optional[pymysql.Connection] = None
        self.cursor: Optional[pymysql.Cursor] = None
        self._connect_with_retry()

    def _connect_with_retry(self) -> None:
        """带重试的连接方法"""
        for attempt in range(1, self.MAX_RECONNECT_ATTEMPTS + 1):
            try:
                self._connect()
                return
            except Exception as e:
                if attempt < self.MAX_RECONNECT_ATTEMPTS:
                    logging.warning(f"⚠️ 数据库连接失败 (尝试 {attempt}/{self.MAX_RECONNECT_ATTEMPTS}): {e}")
                    logging.info(f"⏳ {self.RECONNECT_DELAY}秒后重试...")
                    time.sleep(self.RECONNECT_DELAY)
                else:
                    logging.error(f"❌ 数据库连接失败，已达到最大重试次数 ({self.MAX_RECONNECT_ATTEMPTS})")
                    raise

    def _connect(self) -> None:
        """执行数据库连接（绑定本地物理网卡IP绕过VPN）"""
        # 获取本地物理网卡IP用于绕过VPN
        local_ip = get_local_physical_ip()
        connect_params = self.config.copy()

        if local_ip:
            connect_params['bind_address'] = local_ip
            logging.info(f"🔗 绑定本地IP: {local_ip} 绕过VPN直连数据库")

        try:
            # 清除代理环境变量
            old_proxies = {}
            for proxy_key in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'):
                if os.environ.get(proxy_key):
                    old_proxies[proxy_key] = os.environ[proxy_key]
                    del os.environ[proxy_key]

            self.conn = pymysql.connect(**connect_params, autocommit=True)
            self.cursor = self.conn.cursor()

            if local_ip:
                logging.info(f"✅ 数据库直连成功（已绑定 {local_ip} 绕过VPN）")
            else:
                logging.info("✅ 数据库连接成功（系统自动路由）")
        finally:
            # 恢复代理环境变量
            for k, v in old_proxies.items():
                os.environ[k] = v

    def _ensure_connected(self) -> None:
        """确保数据库连接有效，如果断开则重连"""
        try:
            if self.conn:
                self.conn.ping(reconnect=True)
        except Exception:
            logging.warning("⚠️ 数据库连接已断开，尝试重连...")
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
            self._connect_with_retry()

    def execute_sql(self, sql: str) -> Optional[Any]:
        """执行SQL查询并返回单个结果（带自动重连）"""
        for attempt in range(1, self.MAX_RECONNECT_ATTEMPTS + 1):
            try:
                self._ensure_connected()
                self.cursor.execute(sql)
                result = self.cursor.fetchone()
                return result[0] if result else None
            except OperationalError as e:
                error_code = e.args[0]
                if error_code in [2006, 2013, 10054] and attempt < self.MAX_RECONNECT_ATTEMPTS:
                    logging.warning(f"⚠️ 数据库连接丢失 (错误码: {error_code}, 尝试 {attempt}/{self.MAX_RECONNECT_ATTEMPTS})")
                    logging.info(f"⏳ {self.RECONNECT_DELAY}秒后重试...")
                    time.sleep(self.RECONNECT_DELAY)
                    self._connect_with_retry()
                else:
                    logging.error(f"❌ SQL执行失败: {e}, SQL: {sql[:100]}")
                    raise
            except Exception as e:
                logging.error(f"❌ SQL执行失败: {e}, SQL: {sql[:100]}")
                raise

    def close(self):
        """关闭数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logging.info("✅ 数据库连接已关闭")


# ==============================================================================
# --- 5. 全局数据库连接（单例模式） ---
# ==============================================================================
_global_db: Optional[DatabaseExecutor] = None
_global_currency: Optional[str] = None  # 全局存储用户选择的融资产品货币，初始为空

SUPPORTED_CURRENCIES = {"CNY", "USD"}
CURRENCY_KEY_CANDIDATES = (
    "product-currency", "productCurrency", "product_currency",
    "preferredCurrency", "preferred_currency", "preferFinanceProductCurrency",
    "financeProductCurrency", "finance_product_currency",
    "currency", "Currency", "CURRENCY",
    "selectedCurrency", "selected_currency",
    "defaultCurrency", "default_currency",
    "userCurrency", "user_currency",
    "appCurrency", "app_currency",
    "financingCurrency", "financing_currency",
)
CURRENCY_LOOKUP_KEYS = tuple(dict.fromkeys(key.strip().lower() for key in CURRENCY_KEY_CANDIDATES))


def has_valid_global_currency() -> bool:
    """判断全局货币是否已是可用值。"""
    return _global_currency in SUPPORTED_CURRENCIES


def get_current_flow_amount_config(currency: Optional[str] = None) -> Dict[str, Any]:
    """根据当前currency返回对应的流程金额配置，默认回退到USD。"""
    normalized_currency = normalize_currency_value(currency or _global_currency) or "USD"
    return FLOW_AMOUNT_CONFIG.get(normalized_currency, FLOW_AMOUNT_CONFIG["USD"])


def normalize_currency_value(value: Any) -> Optional[str]:
    """将不同来源的currency值规范化为支持的货币代码。"""
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized in SUPPORTED_CURRENCIES:
            return normalized

        stripped = value.strip()
        if stripped.startswith("{"):
            try:
                return normalize_currency_value(json.loads(stripped))
            except (TypeError, json.JSONDecodeError):
                return None
        return None

    if isinstance(value, dict):
        normalized_mapping = {
            str(key).strip().lower(): item
            for key, item in value.items()
            if isinstance(key, str)
        }
        for lookup_key in CURRENCY_LOOKUP_KEYS:
            if lookup_key in normalized_mapping:
                normalized = normalize_currency_value(normalized_mapping[lookup_key])
                if normalized:
                    return normalized
        return None

    return None


def extract_currency_from_mapping(mapping: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """从headers/storage这类键值映射中提取currency，返回命中的键和值。"""
    if not isinstance(mapping, dict):
        return None

    normalized_mapping: Dict[str, Any] = {}
    original_key_map: Dict[str, str] = {}
    for key, value in mapping.items():
        if not isinstance(key, str):
            continue
        normalized_key = key.strip().lower()
        if not normalized_key:
            continue
        normalized_mapping[normalized_key] = value
        original_key_map.setdefault(normalized_key, key)

    for lookup_key in CURRENCY_LOOKUP_KEYS:
        if lookup_key not in normalized_mapping:
            continue
        normalized = normalize_currency_value(normalized_mapping[lookup_key])
        if normalized:
            return original_key_map.get(lookup_key, lookup_key), normalized

    for normalized_key, value in normalized_mapping.items():
        if "currency" not in normalized_key:
            continue
        normalized = normalize_currency_value(value)
        if normalized:
            return original_key_map.get(normalized_key, normalized_key), normalized

    return None


def update_global_currency_from_mapping(mapping: Dict[str, Any], source_name: str) -> bool:
    """尝试从映射中更新全局currency，成功时记录命中来源。"""
    global _global_currency

    found_currency = extract_currency_from_mapping(mapping)
    if not found_currency:
        return False

    matched_key, currency = found_currency
    _global_currency = currency
    logging.info(f"✅ 从{source_name}提取currency (键: {matched_key}): {_global_currency}")
    return True


def enable_network_currency_capture(driver: webdriver.Remote) -> bool:
    """尽早开启Chromium网络监听，避免错过注册阶段的请求头。"""
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        logging.debug("[Browser] 已启用CDP Network监听")
        return True
    except Exception as e:
        logging.debug(f"[Browser] 无法启用CDP Network监听: {e}")
        return False

def get_global_db() -> DatabaseExecutor:
    """获取全局数据库连接（单例模式）"""
    global _global_db
    if _global_db is None:
        try:
            logging.info("🔗 正在建立全局数据库连接...")
            _global_db = DatabaseExecutor()
            logging.info("✅ 全局数据库连接已建立")
        except Exception as e:
            logging.error(f"❌ 全局数据库连接失败: {e}")
            logging.error(f"💡 提示：如果连接了VPN，请先断开VPN")
            raise
    return _global_db

def close_global_db():
    """关闭全局数据库连接"""
    global _global_db
    if _global_db:
        try:
            _global_db.close()
            logging.info("✅ 全局数据库连接已关闭")
        except Exception as e:
            logging.warning(f"⚠️ 关闭数据库连接时出错: {e}")
        finally:
            _global_db = None


# ==============================================================================
# --- 6. Webhook请求函数 --- 
# ==============================================================================
def send_underwritten_request(phone: str, amount: str = None) -> bool:
    """发送核保完成请求 (underwrittenLimit.completed)"""
    if amount is None:
        amount = get_current_flow_amount_config()["underwritten_amount"]
    webhook_url = f"{BASE_URL}/dpu-openapi/webhook-notifications"

    try:
        db = get_global_db()

        merchant_id = db.execute_sql(
            f"SELECT merchant_id FROM dpu_users WHERE phone_number = '{phone}' ORDER BY created_at DESC LIMIT 1;"
        )
        preferred_currency = _global_currency or "USD"  # 使用从浏览器提取的全局货币值，缺省USD
        dpu_auth_token_seller_id = db.execute_sql(
            f"SELECT authorization_id FROM dpu_auth_token WHERE merchant_id = '{merchant_id}' AND authorization_party = 'SP' ORDER BY created_at DESC LIMIT 1;"
        )
        dpu_limit_application_id = db.execute_sql(
            f"SELECT limit_application_unique_id FROM dpu_limit_application WHERE merchant_id = '{merchant_id}' ORDER BY created_at DESC LIMIT 1;"
        )
        application_unique_id = db.execute_sql(
            f"SELECT application_unique_id FROM dpu_application WHERE merchant_id = '{merchant_id}' ORDER BY created_at DESC LIMIT 1;"
        )

        if not all([merchant_id, dpu_limit_application_id, application_unique_id]):
            logging.error("❌ 数据库查询失败，缺少必要信息")
            return False

        lender_approved_offer_id = f"lender-{application_unique_id}"

        request_body = {
            "data": {
                "eventType": "underwrittenLimit.completed",
                "eventId": generate_uuid(),
                "eventMessage": "核保完成通知",
                "enquiryUrl": "https://api.example.com/enquiry/123",
                "datetime": get_utc_time(),
                "details": {
                    "merchantId": merchant_id,
                    "dpuMerchantAccountId": [
                        {"MerchantAccountId": dpu_auth_token_seller_id}] if dpu_auth_token_seller_id else [],
                    "dpuLimitApplicationId": dpu_limit_application_id,
                    "originalRequestId": "req_EFAL17621784619057169",
                    "status": "APPROVED",
                    "failureReason": None,
                    "lastUpdatedOn": get_local_time_str(),
                    "lastUpdatedBy": "system",
                    "lenderLoanId": "lloan_6001",
                    "lenderRepaymentScheduled": "lrs_7001",
                    "lenderCreditId": "lcredit_8001",
                    "lenderRepaymentId": "lrepay_9001",
                    "credit": {
                        "marginRate": "2.5",
                        "chargeBases": "Fixed",
                        "baseRate": "3.5",
                        "baseRateType": "FIXED",
                        "eSign": "PENDING",
                        "creditLimit": {
                            "currency": preferred_currency,
                            "underwrittenAmount": {"currency": preferred_currency, "amount": amount},
                            "availableLimit": {"currency": preferred_currency, "amount": "0.00"},
                            "signedLimit": {"currency": preferred_currency, "amount": "0.00"},
                            "watermark": {"currency": preferred_currency, "amount": "0.00"}
                        }
                    }
                }
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        response = requests.post(webhook_url, json=request_body, headers=headers, timeout=30)

        if response.status_code == 200:
            logging.info(f"✅ 核保(underwritten)请求成功 - 响应: {response.text[:100]}...")
            return True
        else:
            logging.error(f"❌ 核保请求失败 | 状态码: {response.status_code}")
            logging.error(f"📋 完整响应内容:\n{response.text}")
            return False

    except Exception as e:
        logging.error(f"❌ 核保请求异常: {e}")
        return False


def send_approved_request(phone: str, amount: float = None) -> bool:
    """发送审批完成请求 (approvedoffer.completed)"""
    if amount is None:
        amount = get_current_flow_amount_config()["approved_amount"]
    webhook_url = f"{BASE_URL}/dpu-openapi/webhook-notifications"

    try:
        db = get_global_db()

        merchant_id = db.execute_sql(
            f"SELECT merchant_id FROM dpu_users WHERE phone_number = '{phone}' ORDER BY created_at DESC LIMIT 1;"
        )
        preferred_currency = _global_currency or "USD"  # 使用从浏览器提取的全局货币值，缺省USD
        application_unique_id = db.execute_sql(
            f"SELECT application_unique_id FROM dpu_application WHERE merchant_id = '{merchant_id}' ORDER BY created_at DESC LIMIT 1;"
        )

        if not all([merchant_id, application_unique_id]):
            logging.error("❌ 数据库查询失败，缺少必要信息")
            return False

        lender_approved_offer_id = f"lender-{application_unique_id}"

        request_body = {
            "data": {
                "eventType": "approvedoffer.completed",
                "eventId": generate_uuid(),
                "eventMessage": "Application approval process completed successfully",
                "enquiryUrl": "https://api.lender.com/enquiry/12345",
                "datetime": get_utc_time(),
                "details": {
                    "merchantId": merchant_id,
                    "dpuApplicationId": application_unique_id,
                    "originalRequestId": " ",
                    "status": "APPROVED",
                    "failureReason": None,
                    "lastUpdatedOn": get_local_time_str(),
                    "lastUpdatedBy": "system",
                    "lenderApprovedOfferId": lender_approved_offer_id,
                    "offer": {
                        "rate": {
                            "chargeBases": "Float",
                            "baseRateType": "SOFR",
                            "baseRate": "0.05",
                            "marginRate": "0.02",
                            "fixedRate": "0.07"
                        },
                        "term": 12,
                        "termUnit": "Months",
                        "mintenor": 3,
                        "maxtenor": 24,
                        "offerEndDate": (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"),
                        "offerStartDate": datetime.now().strftime("%Y-%m-%d"),
                        "approvedLimit": {"currency": preferred_currency, "amount": amount},
                        "warterMark": {"currency": preferred_currency, "amount": 0.00},
                        "signedLimit": {"currency": preferred_currency, "amount": 0.00},
                        "feeOrCharge": {
                            "type": "PROCESSING_FEE",
                            "feeOrChargeDate": "2023-10-16",
                            "netAmount": {"currency": preferred_currency, "amount": 0.00}
                        }
                    }
                }
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        response = requests.post(webhook_url, json=request_body, headers=headers, timeout=30)

        if response.status_code == 200:
            logging.info(f"✅ 审批(approved)请求成功 - 响应: {response.text[:100]}...")
            return True
        else:
            logging.error(f"❌ 审批请求失败 | 状态码: {response.status_code}")
            logging.error(f"📋 完整响应内容:\n{response.text}")
            return False

    except Exception as e:
        logging.error(f"❌ 审批请求异常: {e}")
        return False


def send_psp_start_request(phone: str) -> bool:
    """发送PSP验证开始请求 (psp.verification.started)"""
    webhook_url = f"{BASE_URL}/dpu-openapi/webhook-notifications"

    try:
        db = get_global_db()

        merchant_id = db.execute_sql(
            f"SELECT merchant_id FROM dpu_users WHERE phone_number = '{phone}' ORDER BY created_at DESC LIMIT 1;"
        )
        dpu_auth_token_seller_id = db.execute_sql(
            f"SELECT authorization_id FROM dpu_auth_token WHERE merchant_id = '{merchant_id}' AND authorization_party = 'SP' ORDER BY created_at DESC LIMIT 1;"
        )
        application_unique_id = db.execute_sql(
            f"SELECT application_unique_id FROM dpu_application WHERE merchant_id = '{merchant_id}' ORDER BY created_at DESC LIMIT 1;"
        )

        if not all([merchant_id, application_unique_id]):
            logging.error("❌ 数据库查询失败，缺少必要信息")
            return False

        lender_approved_offer_id = f"lender-{application_unique_id}"

        request_body = {
            "data": {
                "eventType": "psp.verification.started",
                "eventId": generate_uuid(),
                "eventMessage": "PSP验证已开始",
                "enquiryUrl": "https://api.example.com/enquiry/psp/123",
                "datetime": get_utc_time(),
                "applicationId": "EFA17590311621044381",
                "details": {
                    "pspId": "pspId123457",
                    "pspName": "AirWallex",
                    "merchantAccountId": dpu_auth_token_seller_id,
                    "merchantId": merchant_id,
                    "lenderApprovedOfferId": lender_approved_offer_id,
                    "result": "PROCESSING",
                    "failureReason": None,
                    "lastUpdatedOn": get_local_time_str(),
                    "lastUpdatedBy": "system_psp"
                }
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        response = requests.post(webhook_url, json=request_body, headers=headers, timeout=30)

        if response.status_code == 200:
            logging.info(f"✅ PSP开始请求成功 - 响应: {response.text[:100]}...")
            return True
        else:
            logging.error(f"❌ PSP开始请求失败 | 状态码: {response.status_code}")
            logging.error(f"📋 完整响应内容:\n{response.text}")
            return False

    except Exception as e:
        logging.error(f"❌ PSP开始请求异常: {e}")
        return False


def send_psp_completed_request(phone: str) -> bool:
    """发送PSP验证完成请求 (psp.verification.completed)"""
    webhook_url = f"{BASE_URL}/dpu-openapi/webhook-notifications"

    try:
        db = get_global_db()

        merchant_id = db.execute_sql(
            f"SELECT merchant_id FROM dpu_users WHERE phone_number = '{phone}' ORDER BY created_at DESC LIMIT 1;"
        )
        dpu_auth_token_seller_id = db.execute_sql(
            f"SELECT authorization_id FROM dpu_auth_token WHERE merchant_id = '{merchant_id}' AND authorization_party = 'SP' ORDER BY created_at DESC LIMIT 1;"
        )
        application_unique_id = db.execute_sql(
            f"SELECT application_unique_id FROM dpu_application WHERE merchant_id = '{merchant_id}' ORDER BY created_at DESC LIMIT 1;"
        )

        if not all([merchant_id, application_unique_id]):
            logging.error("❌ 数据库查询失败，缺少必要信息")
            return False

        lender_approved_offer_id = f"lender-{application_unique_id}"

        request_body = {
            "data": {
                "eventType": "psp.verification.completed",
                "eventId": generate_uuid(),
                "eventMessage": "PSP验证已完成",
                "enquiryUrl": "https://api.example.com/enquiry/psp/123",
                "datetime": get_utc_time(),
                "applicationId": "EFA17590311621044381",
                "details": {
                    "pspId": "pspId123457",
                    "pspName": "AirWallex",
                    "merchantAccountId": dpu_auth_token_seller_id,
                    "merchantId": merchant_id,
                    "lenderApprovedOfferId": lender_approved_offer_id,
                    "result": "SUCCESS",
                    "failureReason": None,
                    "lastUpdatedOn": get_local_time_str(),
                    "lastUpdatedBy": "system_psp"
                }
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        response = requests.post(webhook_url, json=request_body, headers=headers, timeout=30)

        if response.status_code == 200:
            logging.info(f"✅ PSP完成请求成功 - 响应: {response.text[:100]}...")
            return True
        else:
            logging.error(f"❌ PSP完成请求失败 | 状态码: {response.status_code}")
            logging.error(f"📋 完整响应内容:\n{response.text}")
            return False

    except Exception as e:
        logging.error(f"❌ PSP完成请求异常: {e}")
        return False


def send_esign_request(phone: str, amount: float = None) -> bool:
    """发送电子签完成请求 (esign.completed)"""
    if amount is None:
        amount = get_current_flow_amount_config()["esign_amount"]
    webhook_url = f"{BASE_URL}/dpu-openapi/webhook-notifications"

    try:
        db = get_global_db()

        merchant_id = db.execute_sql(
            f"SELECT merchant_id FROM dpu_users WHERE phone_number = '{phone}' ORDER BY created_at DESC LIMIT 1;"
        )
        preferred_currency = _global_currency or "USD"  # 使用从浏览器提取的全局货币值，缺省USD
        application_unique_id = db.execute_sql(
            f"SELECT application_unique_id FROM dpu_application WHERE merchant_id = '{merchant_id}' ORDER BY created_at DESC LIMIT 1;"
        )

        if not all([merchant_id, application_unique_id]):
            logging.error("❌ 数据库查询失败，缺少必要信息")
            return False

        lender_approved_offer_id = f"lender-{application_unique_id}"

        request_body = {
            "data": {
                "eventType": "esign.completed",
                "eventId": generate_uuid(),
                "eventMessage": "电子签章已完成",
                "enquiryUrl": "https://api.example.com/enquiry/esign/456",
                "datetime": get_utc_time(),
                "details": {
                    "merchantId": merchant_id,
                    "lenderApprovedOfferId": lender_approved_offer_id,
                    "result": "SUCCESS",
                    "failureReason": None,
                    "signedLimit": {"amount": amount, "currency": preferred_currency},
                    "lastUpdatedOn": get_local_time_str(),
                    "lastUpdatedBy": "esign_system"
                }
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        response = requests.post(webhook_url, json=request_body, headers=headers, timeout=30)

        if response.status_code == 200:
            logging.info(f"✅ 电子签请求成功 - 响应: {response.text[:100]}...")
            return True
        else:
            logging.error(f"❌ 电子签请求失败 | 状态码: {response.status_code}")
            logging.error(f"📋 完整响应内容:\n{response.text}")
            return False

    except Exception as e:
        logging.error(f"❌ 电子签请求异常: {e}")
        return False


def send_post_request(url: str, phone: str = None) -> bool:
    """发送POST请求（用于关联店铺等操作）"""
    try:
        headers = {
            "Content-Type": "application/json",
        }
        data = {"phone": phone} if phone else {}

        # 记录请求的手机号
        if phone:
            logging.info(f"[API] 发送POST请求到: {url}")
            logging.info(f"[API] 请求手机号: {phone}")

        response = requests.post(url, json=data, headers=headers, timeout=30)

        if response.status_code == 200:
            # 检查业务code
            try:
                response_data = response.json()
                business_code = response_data.get("code")
                if business_code == 200 or business_code == "200":
                    logging.info(f"✅ POST请求成功 - 响应: {response.text[:100]}...")
                    return True
                else:
                    logging.error(f"❌ POST请求业务失败 | code: {business_code} | message: {response_data.get('message')} | 响应: {response.text[:200]}...")
                    return False
            except:
                # 无法解析JSON，按HTTP状态码判断
                logging.info(f"✅ POST请求成功 - 响应: {response.text[:100]}...")
                return True
        else:
            logging.warning(f"⚠️ POST请求失败 | 状态码: {response.status_code} | 响应: {response.text[:200]}...")
            return False
    except Exception as e:
        logging.error(f"❌ POST请求异常: {e}")
        return False


def send_update_offer_request(phone: str) -> bool:
    """发送updateOffer请求 (SP完成后、3PL前)"""
    update_offer_url = f"{BASE_URL}/dpu-auth/amazon-sp/updateOffer"

    try:
        db = get_global_db()
        selling_partner_id = f"spshouquanfs{phone}"

        # 查询idempotencyKey和offerId
        idempotency_sql = f"""
            SELECT idempotency_key FROM dpu_seller_center.dpu_manual_offer
            WHERE platform_seller_id = '{selling_partner_id}'
            ORDER BY created_at DESC LIMIT 1
        """
        idempotency_key = db.execute_sql(idempotency_sql)

        offer_id_sql = f"""
            SELECT platform_offer_id FROM dpu_seller_center.dpu_manual_offer
            WHERE platform_seller_id = '{selling_partner_id}'
            ORDER BY created_at DESC LIMIT 1
        """
        offer_id = db.execute_sql(offer_id_sql)

        if not all([idempotency_key, offer_id]):
            logging.error("❌ 数据库查询失败，缺少idempotencyKey或offerId")
            return False

        logging.info(f"✅ 查询到idempotencyKey: {idempotency_key}")
        logging.info(f"✅ 查询到offerId: {offer_id}")

        request_body = {
            "idempotencyKey": idempotency_key,
            "sendStatus": "SUCCESS",
            "offerId": offer_id,
            "reason": ""
        }

        headers = {
            "Content-Type": "application/json"
        }

        logging.info(f"[UPDATE_OFFER] 发送POST请求到: {update_offer_url}")
        response = requests.post(update_offer_url, json=request_body, headers=headers, timeout=30)

        if response.status_code == 200:
            logging.info(f"✅ updateOffer请求成功 - 响应: {response.text[:100]}...")
            return True
        else:
            logging.error(f"❌ updateOffer请求失败 | 状态码: {response.status_code}")
            logging.error(f"📋 完整响应内容:\n{response.text}")
            return False

    except Exception as e:
        logging.error(f"❌ updateOffer请求异常: {e}")
        return False


def poll_credit_offer_status(phone: str, authorization_token: str = None, max_attempts: int = 120, interval: int = 5):
    """轮询信用报价状态，等待SUBMITTED状态"""
    status_url = f"{BASE_URL}/dpu-merchant/credit-offer/status"

    if not authorization_token:
        authorization_token = DEFAULT_TOKEN_DICT.get(ENV, "")

    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-Hans",
        "authorization": f"Bearer {authorization_token}",
        "funder-resource": "FUNDPARK",
        "origin": f"https://expressfinance-dpu-{ENV}.dowsure.com" if ENV in ("sit", "dev") else f"https://expressfinance-{ENV}.business.hsbc.com",
        "priority": "u=1, i",
        "referer": f"https://expressfinance-dpu-{ENV}.dowsure.com/" if ENV in ("sit", "dev") else f"https://expressfinance-{ENV}.business.hsbc.com/",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        "x-hsbc-countrycode": "ISO 3166-1 alpha-2",
        "x-hsbc-request-correlation-id": "",
        "x-hsbc-request-idempotency-key": ""
    }

    logging.info("\n" + "=" * 50)
    logging.info("开始轮询信用报价状态，等待 SUBMITTED 状态...")
    logging.info("=" * 50)

    for attempt in range(1, max_attempts + 1):
        try:
            params = {"phone": phone}
            response = requests.get(status_url, headers=headers, params=params, timeout=15)

            if response.status_code == 200:
                response_data = response.json()
                status = response_data.get("data", {}).get("status", "")

                logging.info(f"[轮询 #{attempt}/{max_attempts}] 当前状态: {status}")

                if status == "SUBMITTED":
                    logging.info(f"\n[轮询] 已获取到目标状态 SUBMITTED！（尝试次数: {attempt}）")
                    return True
                elif status in ["APPROVED", "REJECTED", "FAILED"]:
                    logging.warning(f"[轮询] 状态变为 {status}，轮询终止。")
                    return False
            else:
                logging.warning(f"[轮询 #{attempt}] 响应状态码: {response.status_code}")

        except requests.exceptions.RequestException as e:
            logging.error(f"[轮询 #{attempt}] 请求失败: {e}")

        # 检查暂停（允许用户在轮询过程中暂停）

        if attempt < max_attempts:
            time.sleep(interval)

    logging.error(f"\n[轮询] 达到最大尝试次数 {max_attempts}，未获取到 SUBMITTED 状态。")
    return False


def poll_drawdown_status(phone: str, authorization_token: str = None, max_attempts: int = 120, interval: int = 5):
    """轮询drawdown状态，等待SUBMITTED状态"""
    status_url = f"{BASE_URL}/dpu-merchant/drawdown/status"

    if not authorization_token:
        authorization_token = DEFAULT_TOKEN_DICT.get(ENV, "")

    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-Hans",
        "authorization": f"Bearer {authorization_token}",
        "funder-resource": "FUNDPARK",
        "origin": f"https://expressfinance-dpu-{ENV}.dowsure.com" if ENV in ("sit", "dev") else f"https://expressfinance-{ENV}.business.hsbc.com",
        "priority": "u=1, i",
        "referer": f"https://expressfinance-dpu-{ENV}.dowsure.com/" if ENV in ("sit", "dev") else f"https://expressfinance-{ENV}.business.hsbc.com/",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        "x-hsbc-countrycode": "ISO 3166-1 alpha-2",
        "x-hsbc-request-correlation-id": "",
        "x-hsbc-request-idempotency-key": ""
    }

    logging.info("\n" + "=" * 50)
    logging.info("开始轮询drawdown状态，等待 SUBMITTED 状态...")
    logging.info("=" * 50)

    for attempt in range(1, max_attempts + 1):
        try:
            params = {"phone": phone}
            response = requests.get(status_url, headers=headers, params=params, timeout=15)

            if response.status_code == 200:
                response_data = response.json()
                status = response_data.get("data", {}).get("status", "")

                logging.info(f"[轮询 #{attempt}/{max_attempts}] 当前状态: {status}")

                if status == "SUBMITTED":
                    logging.info(f"\n[轮询] 已获取到目标状态 SUBMITTED！（尝试次数: {attempt}）")
                    return True
                elif status in ["APPROVED", "REJECTED", "FAILED"]:
                    logging.warning(f"[轮询] 状态变为 {status}，轮询终止。")
                    return False
            else:
                logging.warning(f"[轮询 #{attempt}] 响应状态码: {response.status_code}")

        except requests.exceptions.RequestException as e:
            logging.error(f"[轮询 #{attempt}] 请求失败: {e}")

        # 检查暂停（允许用户在轮询过程中暂停）

        if attempt < max_attempts:
            time.sleep(interval)

    logging.error(f"\n[轮询] 达到最大尝试次数 {max_attempts}，未获取到 SUBMITTED 状态。")
    return False


def send_disbursement_completed_request(phone: str, amount: float = None) -> bool:
    """发送放款完成请求 (disbursement.completed)"""
    if amount is None:
        amount = get_current_flow_amount_config()["direct_flow_amount"]
    webhook_url = f"{BASE_URL}/dpu-openapi/webhook-notifications"

    try:
        db = get_global_db()

        merchant_id = db.execute_sql(
            f"SELECT merchant_id FROM dpu_users WHERE phone_number = '{phone}' ORDER BY created_at DESC LIMIT 1;"
        )
        preferred_currency = _global_currency or "USD"  # 使用从浏览器提取的全局货币值，缺省USD
        application_unique_id = db.execute_sql(
            f"SELECT application_unique_id FROM dpu_application WHERE merchant_id = '{merchant_id}' ORDER BY created_at DESC LIMIT 1;"
        )
        loan_id = db.execute_sql(
            f"SELECT loan_id FROM dpu_drawdown WHERE merchant_id = '{merchant_id}' ORDER BY created_at DESC LIMIT 1;"
        )

        if not all([merchant_id, application_unique_id, loan_id]):
            logging.error("❌ 数据库查询失败，缺少必要信息")
            return False

        lender_approved_offer_id = f"lender-{application_unique_id}"
        dpu_loan_id = loan_id
        lender_loan_id = f"lender-{loan_id}"

        request_body = {
            "data": {
                "eventType": "disbursement.completed",
                "eventId": generate_uuid(),
                "eventMessage": "Disbursement completed",
                "enquiryUrl": f"/loans?merchantId={merchant_id}&loanId=LEND1",
                "datetime": get_utc_time(),
                "details": {
                    "merchantId": merchant_id,
                    "lenderApprovedOfferId": lender_approved_offer_id,
                    "dpuLoanId": dpu_loan_id,
                    "lenderLoanId": lender_loan_id,
                    "originalRequestId": "e37b91d056114e48a466b433934e2068",
                    "lenderCreditId": "CR1",
                    "lenderCompanyId": "LEND1",
                    "lenderDrawdownId": "DRA1",
                    "drawdownStatus": "APPROVED",
                    "lastUpdatedOn": get_local_time_str(),
                    "lastUpdatedBy": "system",
                    "disbursement": {
                        "loanAmount": {"currency": preferred_currency, "amount": amount},
                        "rate": {"chargeBases": "Float", "baseRateType": "SOFR", "baseRate": "6.00", "marginRate": "0.00"},
                        "term": "120",
                        "termUnit": "Days",
                        "drawdownSuccessDate": time.strftime("%Y-%m-%d", time.localtime()),
                        "actualDrawdownDate": time.strftime("%Y-%m-%d", time.localtime())
                    },
                    "repayment": {
                        "expectedRepaymentDate": "2026-06-21",
                        "expectedRepaymentAmount": {"currency": preferred_currency, "amount": amount},
                        "repaymentTerm": "90"
                    }
                }
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        response = requests.post(webhook_url, json=request_body, headers=headers, timeout=30)

        if response.status_code == 200:
            logging.info(f"✅ 放款请求成功 - 响应: {response.text[:100]}...")
            return True
        else:
            logging.error(f"❌ 放款请求失败 | 状态码: {response.status_code}")
            logging.error(f"📋 完整响应内容:\n{response.text}")
            return False

    except Exception as e:
        logging.error(f"❌ 放款请求异常: {e}")
        return False


# ==============================================================================
# --- 6. UI操作辅助函数 ---
# ==============================================================================
def safe_click(driver: webdriver.Remote, locator_key: str, action_description: str, fallback_locators: list = None):
    """安全地点击一个元素，支持备选定位器"""
    reg_next_fallbacks = [
        (By.XPATH, "//button[@type='button' and contains(., '下一步')]"),
        (By.XPATH, "//button[contains(@class, 'el-button') and contains(., '下一步')]"),
        (By.XPATH, "//button[text()='下一步']"),
        (By.XPATH, "//button[normalize-space(text())='下一步']"),
        (By.XPATH, "//form//button[contains(@class, 'el-button')]"),
        (By.CSS_SELECTOR, "button.el-button"),
        (By.CSS_SELECTOR, "button[type='submit']"),
        (By.CSS_SELECTOR, "button[type='button']"),
        (By.XPATH, "//div[contains(@class, 'form')]//button[last()]"),
    ]

    if locator_key == "REG_NEXT_BTN":
        fallback_locators = reg_next_fallbacks

    try:
        locator = LOCATORS.get(locator_key)
        if not locator and not fallback_locators:
            raise ValueError(f"定位器 '{locator_key}' 未在 LOCATORS 中定义且未提供备选定位器")

        element = None
        if locator:
            try:
                element = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(EC.element_to_be_clickable(locator))
                logging.info(f"[UI] 使用主定位器找到元素: {action_description}")
            except Exception:
                logging.warning(f"[UI] 主定位器未找到元素 '{action_description}'，尝试备选定位器...")

        if not element and fallback_locators:
            for i, fallback_locator in enumerate(fallback_locators, 1):
                try:
                    element = WebDriverWait(driver, 5).until(EC.element_to_be_clickable(fallback_locator))
                    logging.info(f"[UI] 使用备选定位器 #{i} 找到元素: {action_description}")
                    break
                except Exception:
                    continue

        if not element:
            raise Exception(f"无法通过任何定位器找到元素: {action_description}")

        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        time.sleep(CONFIG.ACTION_DELAY)

        try:
            element.click()
        except Exception:
            logging.warning(f"[UI] 常规点击 '{action_description}' 失败，尝试使用JavaScript点击。")
            driver.execute_script("arguments[0].click();", element)

        logging.info(f"[UI] 已点击: {action_description}")
    except Exception as e:
        logging.error(f"[UI] 点击 '{action_description}' 时发生错误: {e}")
        raise


def safe_send_keys(driver: webdriver.Remote, locator_key: str, text: str, field_description: str):
    """安全地向输入框输入文本（支持备选定位器）"""
    locator = LOCATORS.get(locator_key)
    if not locator:
        raise ValueError(f"定位器 '{locator_key}' 未在 LOCATORS 中定义")

    # 备选定位器（特别是针对出生日期输入框）
    fallback_locators = []
    if locator_key == "BIRTH_DATE_INPUT":
        fallback_locators = [
            (By.XPATH, "//input[contains(@class, 'el-input__inner') and @placeholder='YYYY/MM/DD']"),
            (By.XPATH, "//input[contains(@class, 'el-input__inner') and @type='text']"),
            (By.XPATH, "//input[@placeholder='YYYY/MM/DD']"),
            (By.CSS_SELECTOR, "input.el-input__inner"),
        ]

    try:
        # 尝试主定位器
        element = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(EC.visibility_of_element_located(locator))
        element.clear()
        element.send_keys(text)
        logging.info(f"[UI] 已在 '{field_description}' 中输入: {text}")
    except Exception as e:
        # 尝试备选定位器
        if fallback_locators:
            logging.warning(f"[UI] 主定位器失败，尝试备选定位器...")
            for i, fallback_locator in enumerate(fallback_locators, 1):
                try:
                    element = WebDriverWait(driver, 5).until(EC.visibility_of_element_located(fallback_locator))
                    element.clear()
                    element.send_keys(text)
                    logging.info(f"[UI] 使用备选定位器 #{i} 在 '{field_description}' 中输入: {text}")
                    return
                except Exception:
                    continue

        logging.error(f"[UI] 向 '{field_description}' 输入时发生错误: {e}")
        raise


def upload_image(driver: webdriver.Remote, description: str):
    """上传图片到指定区域（优化版，使用JavaScript直接上传避免stale element错误）"""
    try:
        # 1. 文件名映射（支持中英文描述）
        file_mapping = {
            "身份证正面": "身份证正面.png",
            "身份证背面": "身份证反面.png",
            "ID-Front": "身份证正面.png",
            "ID-Back": "身份证反面.png",
        }

        # 2. 根据description获取目标文件
        target_file = file_mapping.get(description)
        if not target_file:
            # 尝试模糊匹配
            if "正面" in description or "front" in description.lower():
                target_file = "身份证正面.png"
            elif "反面" in description or "back" in description.lower():
                target_file = "身份证反面.png"
            else:
                target_file = "身份证正面.png"  # 默认使用正面

        image_path = os.path.join(CONFIG.SCREENSHOT_FOLDER, target_file)

        # 3. 验证文件存在
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        # 4. 转换为绝对路径（JavaScript需要）
        abs_image_path = os.path.abspath(image_path)

        # 5. 使用JavaScript直接上传（避免stale element问题）
        logging.info(f"[UI] 正在上传图片 '{target_file}' 用于: {description}")

        # JavaScript上传函数：找到file input并设置文件路径
        upload_js = f"""
        (function() {{
            // 查找所有file input
            var inputs = document.querySelectorAll('input[type="file"]');
            var targetInput = null;

            // 优先查找可见的file input
            for (var i = 0; i < inputs.length; i++) {{
                if (inputs[i].offsetParent !== null && inputs[i].offsetParent !== document.body) {{
                    targetInput = inputs[i];
                    break;
                }}
            }}

            // 如果没找到可见的，使用第一个
            if (!targetInput && inputs.length > 0) {{
                targetInput = inputs[0];
            }}

            if (!targetInput) {{
                return {{success: false, message: '未找到file input'}};
            }}

            // 设置文件路径（使用FileList构造器）
            try {{
                // 创建一个File对象来模拟文件选择
                var file = null;
                targetInput.value = '{abs_image_path.replace(os.sep, '/')}';

                // 触发change事件
                var event = new Event('change', {{bubbles: true}});
                targetInput.dispatchEvent(event);

                return {{
                    success: true,
                    message: '上传成功',
                    hasValue: targetInput.value !== ''
                }};
            }} catch (e) {{
                return {{success: false, message: e.toString()}};
            }}
        }})();
        """

        # 执行上传
        upload_result = driver.execute_script(upload_js)

        if not upload_result or not upload_result.get('success'):
            # JavaScript方式失败，尝试使用Selenium方式
            logging.warning(f"[UI] JavaScript上传失败，尝试使用Selenium方式")

            # 使用Selenium的find_element（每次都重新获取元素）
            from selenium.webdriver.common.by import By
            file_input = None

            try:
                file_input = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
                )
            except:
                # 尝试通过CSS选择器
                file_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")

            if file_input:
                file_input.send_keys(abs_image_path)
                logging.info(f"[UI] ✅ 已通过Selenium上传图片 '{target_file}' 用于: {description}")
            else:
                raise Exception("页面上未找到可用的文件上传输入框")
        else:
            logging.info(f"[UI] ✅ 已通过JavaScript上传图片 '{target_file}' 用于: {description}")

        # 6. 等待上传处理完成
        time.sleep(2)

    except Exception as e:
        logging.error(f"[UI] 上传图片 '{description}' 时发生错误: {e}")
        raise


# ==============================================================================
# --- 7. 页面处理函数 ---
# ==============================================================================
def extract_sms_code_from_placeholders(placeholders: Any) -> Optional[str]:
    """Extract a 6-digit verification code from placeholders."""
    if placeholders is None:
        return None
    match = re.search(r"(?<!\d)(\d{6})(?!\d)", str(placeholders))
    return match.group(1) if match else None


def get_sms_verification_code(phone: str, max_attempts: int = 10, interval: float = 2.0) -> str:
    """Fetch the latest SMS verification code from dpu_sms_record."""
    fallback_code = CONFIG.VERIFICATION_CODE
    sql = f"""
        SELECT placeholders FROM dpu_sms_record
        WHERE phone_number = '{phone}'
        ORDER BY COALESCE(send_time, create_time) DESC
        LIMIT 1
    """

    try:
        db = get_global_db()
        for attempt in range(1, max_attempts + 1):
            placeholders = db.execute_sql(sql)
            verification_code = extract_sms_code_from_placeholders(placeholders)
            if verification_code:
                logging.info(f"[DB] SMS code fetched on attempt {attempt}: {verification_code}")
                return verification_code
            if attempt < max_attempts:
                time.sleep(interval)
    except Exception as e:
        logging.warning(f"[DB] Failed to fetch SMS code from dpu_sms_record: {e}")

    logging.warning(f"[DB] SMS code not found, fallback to default code: {fallback_code}")
    return fallback_code


def handle_initial_registration(driver: webdriver.Remote, phone: str) -> Optional[str]:
    logging.info("\n" + "=" * 50)
    logging.info("Step 2: fill registration info")
    logging.info("=" * 50)
    safe_send_keys(driver, "PHONE_INPUT", phone, "phone number")

    send_code_btn_xpath = "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[6]/div/button"
    try:
        send_code_btn = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(
            EC.element_to_be_clickable((By.XPATH, send_code_btn_xpath))
        )
        try:
            send_code_btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", send_code_btn)
        logging.info("[UI] Send verification code button clicked")
        time.sleep(CONFIG.ACTION_DELAY)
    except Exception as e:
        logging.warning(f"[UI] Failed to click send verification code button: {e}")

    verification_code = get_sms_verification_code(phone)
    if len(verification_code) < 6:
        verification_code = CONFIG.VERIFICATION_CODE

    logging.info(f"[UI] Filling verification code: {verification_code}")
    code_inputs = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(
        EC.visibility_of_all_elements_located(LOCATORS["VERIFICATION_CODE_INPUTS"])
    )
    for i, code_input in enumerate(code_inputs):
        if i < len(verification_code):
            code_input.send_keys(verification_code[i])
    logging.info("[UI] Verification code filled")

    safe_click(driver, "REG_NEXT_BTN", "registration next button")
    time.sleep(CONFIG.ACTION_DELAY * 3)
    return handle_password_setup(driver, phone)
    """处理初始注册信息页面，返回从浏览器获取的token"""
    logging.info("\n" + "=" * 50)
    logging.info("步骤 2: 填写注册信息")
    logging.info("=" * 50)
    safe_send_keys(driver, "PHONE_INPUT", phone, "手机号")
    logging.info(f"[UI] 正在输入验证码: {CONFIG.VERIFICATION_CODE}")
    code_inputs = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(
        EC.visibility_of_all_elements_located(LOCATORS["VERIFICATION_CODE_INPUTS"])
    )
    for i, code_input in enumerate(code_inputs):
        code_input.send_keys(CONFIG.VERIFICATION_CODE[i])
    logging.info("[UI] 验证码已输入")

    # 点击下一步
    safe_click(driver, "REG_NEXT_BTN", "注册页面下一步按钮")
    time.sleep(CONFIG.ACTION_DELAY * 3)

    # 处理密码设置页，并获取token
    auth_token = handle_password_setup(driver, phone)
    return auth_token


def handle_password_setup(driver: webdriver.Remote, phone: str) -> Optional[str]:
    """处理密码设置页面，并从浏览器获取token"""
    logging.info("\n" + "=" * 50)
    logging.info("步骤 2.5: 处理密码设置页面")
    logging.info("=" * 50)

    # 1. 输入密码
    safe_send_keys(driver, "PASSWORD_INPUT", CONFIG.PASSWORD, "新密码")
    time.sleep(CONFIG.ACTION_DELAY)

    # 2. 确认密码
    safe_send_keys(driver, "CONFIRM_PASSWORD_INPUT", CONFIG.PASSWORD, "确认密码")
    time.sleep(CONFIG.ACTION_DELAY)

    # 3. 选择安全问题
    safe_click(driver, "SECURITY_QUESTION_DROPDOWN", "安全问题下拉框")
    time.sleep(CONFIG.ACTION_DELAY)

    # 等待选项出现并选择第一个选项
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    first_option = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(
        EC.element_to_be_clickable((By.XPATH, "//li[contains(@class, 'el-select-dropdown__item')][1]"))
    )
    first_option.click()
    logging.info("[UI] 已选择第一个安全问题选项")
    time.sleep(CONFIG.ACTION_DELAY)

    # 4. 输入安全问题答案
    safe_send_keys(driver, "SECURITY_ANSWER_INPUT", "Test123", "安全问题答案")
    time.sleep(CONFIG.ACTION_DELAY)

    # 5. 输入电子邮件地址 (手机号@163.com)
    email_address = f"{phone}@163.com"
    safe_send_keys(driver, "EMAIL_ADDRESS_INPUT", email_address, "电子邮件地址")
    time.sleep(CONFIG.ACTION_DELAY)

    # 6. 勾选第一个复选框：同意
    safe_click(driver, "AGREE_CONSENT_CHECKBOX", "同意复选框")
    time.sleep(CONFIG.ACTION_DELAY)

    # 7. 勾选第二个复选框：授权
    safe_click(driver, "AUTHORIZATION_CHECKBOX", "授权复选框")
    time.sleep(CONFIG.ACTION_DELAY)

    # 8. 点击注册按钮
    safe_click(driver, "FINAL_REGISTER_BTN", "注册按钮")
    time.sleep(CONFIG.ACTION_DELAY * 3)

    # 7. 从浏览器获取token
    auth_token = get_token_from_browser(driver)
    return auth_token


def get_token_from_browser(driver: webdriver.Remote) -> Optional[str]:
    """从浏览器存储中获取授权token，同时提取currency"""
    global _global_currency
    
    logging.info("[Browser] 正在从浏览器存储中获取token和currency...")

    # 优先从请求头提取currency
    if not has_valid_global_currency():
        enable_network_currency_capture(driver)
        currency_from_logs = extract_currency_from_network_logs(driver)
        if currency_from_logs:
            _global_currency = currency_from_logs
            logging.info(f"✅ 从请求头提取currency: {_global_currency}")
        else:
            logging.info("[Browser] 本轮未从网络请求头提取到currency，继续尝试浏览器存储")

    token_keys = [
        'token', 'Token', 'TOKEN',
        'accessToken', 'access_token', 'AccessToken',
        'authToken', 'auth_token', 'AuthToken',
        'authorization', 'Authorization', 'AUTHORIZATION',
        'jwt', 'JWT',
        'bearerToken', 'bearer_token', 'BearerToken',
        'sessionToken', 'session_token', 'SessionToken',
        'userToken', 'user_token', 'UserToken',
        'apiToken', 'api_token', 'ApiToken',
        'auth', 'Auth',
        'sid', 'sessionId'
    ]
    
    # 1. 尝试从 localStorage 获取
    try:
        local_storage = driver.execute_script("""
            const items = {};
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                const value = localStorage.getItem(key);
                items[key] = value;
            }
            return items;
        """)
        logging.info(f"[Browser] localStorage键数量: {len(local_storage)}")
        # 调试输出localStorage内容
        logging.debug(f"[Browser] localStorage内容: {list(local_storage.keys())}")
        
        # 如果还未获取到currency，从localStorage提取
        if not has_valid_global_currency():
            update_global_currency_from_mapping(local_storage, "localStorage")

        # 提取token
        for key in token_keys:
            if key in local_storage and local_storage[key]:
                token_value = local_storage[key]
                if token_value.startswith('{'):
                    try:
                        import json
                        token_obj = json.loads(token_value)
                        if 'token' in token_obj:
                            token_value = token_obj['token']
                            logging.info(f"✅ 从JSON中提取token: {token_value[:30]}...")
                    except:
                        pass
                logging.info(f"✅ 成功从localStorage获取token (键: {key}): {token_value[:30]}...")
                return token_value
    except Exception as e:
        logging.warning(f"[Browser] 从localStorage获取token失败: {e}")

    # 2. 尝试从 sessionStorage 获取
    try:
        session_storage = driver.execute_script("""
            const items = {};
            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                const value = sessionStorage.getItem(key);
                items[key] = value;
            }
            return items;
        """)

        logging.info(f"[Browser] sessionStorage键数量: {len(session_storage)}")
        # 调试输出sessionStorage内容
        logging.debug(f"[Browser] sessionStorage内容: {list(session_storage.keys())}")

        # 如果还未获取到currency，从sessionStorage提取
        if not has_valid_global_currency():
            update_global_currency_from_mapping(session_storage, "sessionStorage")

        # 提取token
        for key in token_keys:
            if key in session_storage and session_storage[key]:
                token_value = session_storage[key]
                if token_value.startswith('{'):
                    try:
                        import json
                        token_obj = json.loads(token_value)
                        if 'token' in token_obj:
                            token_value = token_obj['token']
                            logging.info(f"✅ 从JSON中提取token: {token_value[:30]}...")
                    except:
                        pass
                logging.info(f"✅ 成功从sessionStorage获取token (键: {key}): {token_value[:30]}...")
                return token_value
    except Exception as e:
        logging.warning(f"[Browser] 从sessionStorage获取token失败: {e}")

    logging.error("❌ 未能从浏览器存储中获取到token")
    return None


def handle_company_info(driver: webdriver.Remote, auto_fill: bool):
    """处理公司信息页面（线下流程只需填写英文名称和BRN）"""
    logging.info("\n" + "=" * 50)
    logging.info("步骤 4: 处理公司信息")
    logging.info("=" * 50)
    if auto_fill:
        logging.info("[流程] 选择自动填写公司信息...")
        safe_send_keys(driver, "COMPANY_EN_NAME_INPUT", "测试有限公司", "公司中文名称")
        currency = (_global_currency or "").upper()
        brn_value = "91330201MA2AFFT07Q" if currency == "CNY" else "00000001"
        logging.info(f"[货币] 当前货币: {currency}, BRN值: {brn_value}")
        safe_send_keys(driver, "BUSINESS_REG_NO_INPUT", brn_value, "商业登记号(BRN)")
    else:
        logging.info("[流程] 跳过自动填写，请手动填写公司信息")
        input("填写完成后按回车继续...")

    # 点击下一步
    safe_click(driver, "COMPANY_NEXT_BTN", "公司信息页下一步按钮")


def handle_director_info(driver: webdriver.Remote, phone: str, auto_fill: bool):
    """处理董事股东信息页面（与线上流程一致，从上传身份证开始）"""
    logging.info("\n" + "=" * 50)
    logging.info("步骤 5: 处理董事股东信息")
    logging.info("=" * 50)
    if auto_fill:
        logging.info("[流程] 选择自动填写董事股东信息...")
        # 1. 上传身份证正面
        upload_image(driver, "身份证正面")
        time.sleep(CONFIG.ACTION_DELAY * 3)

        # 2. 上传身份证背面
        upload_image(driver, "身份证背面")
        time.sleep(CONFIG.ACTION_DELAY * 3)

        # 3. 填写出生日期（格式：日/月/年，如 30/12/2025）
        safe_send_keys(driver, "BIRTH_DATE_INPUT", "30/12/2025", "出生日期")

        # 4. 填写参考手机号
        safe_send_keys(driver, "REFERENCE_PHONE_INPUT", phone, "参考手机号")

        # 5. 填写参考邮箱
        safe_send_keys(driver, "REFERENCE_EMAIL_INPUT", f"{phone}@qq.com", "参考邮箱")
    else:
        logging.info("[流程] 跳过自动填写，请手动填写董事股东信息")
        input("填写完成后按回车继续...")

    # 点击下一步（使用董事股东页专用的下一步按钮）
    safe_click(driver, "DIRECTOR_NEXT_BTN", "董事股东信息页下一步")


def handle_financing_choice(driver: webdriver.Remote) -> bool:
    """处理融资方案选择页面 (Tier2专用)

    Returns:
        bool: True表示选择"去激活"(需填写银行账户)，False表示选择"去解锁"(跳过银行账户)
    """
    import time as time_module
    start_time = time_module.time()

    logging.info("\n" + "=" * 50)
    logging.info("步骤 6: 处理融资方案选择 (Tier2)")
    logging.info("=" * 50)

    # 等待页面加载完成
    time.sleep(CONFIG.ACTION_DELAY * 3)

    # 等待融资方案选择页加载（减少超时时间到10秒）
    logging.info("[UI] 等待融资方案选择页面加载...")
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(LOCATORS["ACTIVATE_NOW_BTN"])
        )
        elapsed = time_module.time() - start_time
        logging.info(f"[UI] 融资方案选择页面已加载，耗时: {elapsed:.2f}秒")
    except Exception as e:
        logging.warning(f"[UI] 等待融资方案选择页超时，尝试继续: {e}")
        # 额外等待一下让页面加载
        time.sleep(3)

    options = {
        '1': '去激活 (需填写银行账户信息)',
        '2': '去解锁 (跳过银行账户信息)'
    }
    choice = get_user_choice(options, "请选择融资方案:")

    if choice == '1':
        safe_click(driver, "ACTIVATE_NOW_BTN", "去激活按钮")
        total_elapsed = time_module.time() - start_time
        logging.info(f"✅ 已选择：去激活 (需填写银行账户信息)，总耗时: {total_elapsed:.2f}秒")
        return True
    else:
        safe_click(driver, "APPLY_HIGHER_AMOUNT_BTN", "申请更高额度按钮")
        total_elapsed = time_module.time() - start_time
        logging.info(f"✅ 已选择：去解锁 (跳过银行账户信息)，总耗时: {total_elapsed:.2f}秒")
        return False


def handle_bank_account_info(driver: webdriver.Remote, auto_fill: bool):
    """处理银行账户信息页面"""
    logging.info("\n" + "=" * 50)
    logging.info("步骤 7: 处理银行账户信息")
    logging.info("=" * 50)

    if auto_fill:
        logging.info("[流程] 选择自动填写银行账户信息...")

        # 点击银行选择框
        logging.info("[UI] 点击银行选择框...")
        element = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(LOCATORS["BANK_SELECT_CONTAINER"]))
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        time.sleep(0.3)
        element.click()
        logging.info("[UI] 已点击银行选择框")

        # 点击后等待下拉框展开
        logging.info("[UI] 等待银行选项列表展开...")
        time.sleep(1)

        # 选择银行 - 优先使用JavaScript方式（更可靠）
        bank_selected = False

        # 策略1: 直接使用JavaScript方式（无需先通过Selenium查找元素）
        logging.info("[UI] 使用JavaScript方式选择银行...")
        bank_options_js = """
        (function() {
            var items = document.querySelectorAll('li.el-select-dropdown__item, .el-select-dropdown__item');
            var results = [];
            for (var i = 0; i < items.length; i++) {
                var text = items[i].textContent.trim();
                if (text) {
                    results.push({
                        index: i,
                        text: text
                    });
                }
            }
            return {count: results.length, items: results};
        })();
        """
        result = driver.execute_script(bank_options_js)
        if result and result.get('count', 0) > 0:
            logging.info(f"[UI] JavaScript找到 {result.get('count')} 个银行选项")
            # 显示前几个选项用于调试
            items = result.get('items', [])
            for i, item in enumerate(items[:5]):
                logging.info(f"[UI]   选项{i+1}: {item.get('text')}")

            # 选择第3个选项（跳过前两个，通常是"请选择"之类的）
            if len(items) > 2:
                click_option_js = """
                (function() {
                    var items = document.querySelectorAll('li.el-select-dropdown__item, .el-select-dropdown__item');
                    if (items.length > 2) {
                        items[2].click();
                        return {success: true, text: items[2].textContent.trim()};
                    }
                    return {success: false};
                })();
                """
                click_result = driver.execute_script(click_option_js)
                if click_result and click_result.get('success'):
                    logging.info(f"[UI] 已选择银行: {click_result.get('text')}")
                    bank_selected = True
                else:
                    logging.warning("[UI] JavaScript点击银行选项失败")
            else:
                logging.warning(f"[UI] 银行选项数量不足（只有{len(items)}个）")

        # 策略2: 如果JavaScript方式失败，尝试Selenium方式
        if not bank_selected:
            logging.info("[UI] JavaScript方式失败，尝试Selenium方式...")
            try:
                bank_options = WebDriverWait(driver, 3).until(
                    EC.presence_of_all_elements_located(LOCATORS["BANK_SELECT_OPTIONS"])
                )
                logging.info(f"[UI] Selenium找到 {len(bank_options)} 个银行选项")

                # 尝试直接点击第3个选项（跳过前两个）
                if len(bank_options) > 2:
                    selected_option = bank_options[2]
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'nearest'});", selected_option)
                    time.sleep(0.3)
                    try:
                        selected_option.click()
                        # 尝试获取文本（可能失败）
                        try:
                            bank_name = selected_option.text
                            logging.info(f"[UI] 已选择银行: {bank_name}")
                        except:
                            logging.info(f"[UI] 已选择第3个银行选项")
                        bank_selected = True
                    except Exception as e:
                        logging.warning(f"[UI] Selenium点击失败: {e}")
                else:
                    logging.warning(f"[UI] 银行选项数量不足（只有{len(bank_options)}个）")
            except Exception as e:
                logging.warning(f"[UI] Selenium方式也失败: {e}")

        if not bank_selected:
            raise Exception("无法选择银行选项，所有方式均失败")

        # 等待银行选择完成后再输入账号，增加等待时间确保页面完全更新
        logging.info("[UI] 等待银行选择完成后页面更新...")
        time.sleep(2)  # 从1秒增加到2秒

        # 生成并输入银行账号
        import random
        bank_account = f"{random.randint(100000000000, 999999999999)}"
        logging.info(f"[UI] 准备输入银行账号: {bank_account}")

        # 尝试多种方式找到银行账号输入框
        account_input_found = False

        # 方法1：使用主定位器
        try:
            account_input = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located(LOCATORS["BANK_ACCOUNT_INPUT"])
            )
            # 检查元素是否可见和可交互
            is_interactable = driver.execute_script("""
                var elem = arguments[0];
                if (!elem) return false;
                var style = window.getComputedStyle(elem);
                var rect = elem.getBoundingClientRect();
                return style.display !== 'none' &&
                       style.visibility !== 'hidden' &&
                       style.opacity !== '0' &&
                       !elem.readOnly &&
                       rect.width > 0 &&
                       rect.height > 0;
            """, account_input)

            if is_interactable:
                # 滚动到元素位置
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", account_input)
                time.sleep(0.5)
                # 使用JavaScript直接输入（更可靠）
                driver.execute_script("""
                    arguments[0].focus();
                    arguments[0].value = arguments[1];
                    arguments[0].dispatchEvent(new Event('input', {bubbles: true}));
                    arguments[0].dispatchEvent(new Event('change', {bubbles: true}));
                """, account_input, bank_account)
                logging.info(f"[UI] 已通过主定位器输入银行账号: {bank_account}")
                account_input_found = True
            else:
                logging.warning("[UI] 主定位器元素不可交互，尝试备选方式")
        except Exception as e:
            logging.warning(f"[UI] 主定位器失败: {e}，尝试备选方式")

        # 方法2：通过JavaScript智能查找并输入（增加诊断和更宽松的条件）
        if not account_input_found:
            logging.info("[UI] 尝试通过JavaScript智能查找并输入银行账号...")
            diagnostic_js = """
            (function() {
                // 收集所有输入框信息用于诊断
                var inputs = document.querySelectorAll('input');
                var info = [];
                for (var i = 0; i < inputs.length; i++) {
                    var input = inputs[i];
                    var computedStyle = window.getComputedStyle(input);
                    var isVisible = input.offsetParent !== null &&
                                   computedStyle.display !== 'none' &&
                                   computedStyle.visibility !== 'hidden' &&
                                   computedStyle.opacity !== '0';
                    info.push({
                        index: i,
                        type: input.type,
                        visible: isVisible,
                        readOnly: input.readOnly,
                        hasValue: !!input.value,
                        valueLength: input.value ? input.value.length : 0,
                        maxlength: input.getAttribute('maxlength'),
                        placeholder: input.getAttribute('placeholder') || '',
                        className: input.className || ''
                    });
                }
                // 统计可见且可编辑的输入框
                var editable = info.filter(x => x.visible && !x.readOnly);
                return {total: inputs.length, visible: info.filter(x => x.visible).length, editable: editable.length, details: editable};
            })();
            """
            diag_result = driver.execute_script(diagnostic_js)
            logging.info(f"[UI] 输入框诊断: 总数={diag_result.get('total')}, 可见={diag_result.get('visible')}, 可编辑={diag_result.get('editable')}")
            if diag_result.get('details'):
                for detail in diag_result.get('details')[:5]:  # 只显示前5个
                    logging.info(f"[UI]   - 类型:{detail.get('type')}, maxlength:{detail.get('maxlength')}, placeholder:'{detail.get('placeholder')}', 有值:{detail.get('hasValue')}")

            # 尝试更智能的查找策略
            input_js = f"""
            (function() {{
                var inputs = document.querySelectorAll('input');
                var bestCandidate = null;
                var bestScore = -1;

                for (var i = 0; i < inputs.length; i++) {{
                    var input = inputs[i];
                    var computedStyle = window.getComputedStyle(input);
                    var isVisible = input.offsetParent !== null &&
                                   computedStyle.display !== 'none' &&
                                   computedStyle.visibility !== 'hidden';
                    var isEditable = isVisible && !input.readOnly && input.type !== 'hidden' && input.type !== 'submit';

                    if (isEditable) {{
                        var score = 0;
                        var maxlength = input.getAttribute('maxlength');

                        // 银行账号通常有12-20位的maxlength
                        if (maxlength && parseInt(maxlength) >= 12 && parseInt(maxlength) <= 20) {{
                            score += 50;
                        }}
                        // 没有placeholder的优先（银行账号通常没有placeholder）
                        if (!input.getAttribute('placeholder')) {{
                            score += 20;
                        }}
                        // 是空的优先
                        if (!input.value) {{
                            score += 30;
                        }}
                        // 是text类型的优先
                        if (!input.type || input.type === 'text') {{
                            score += 10;
                        }}

                        if (score > bestScore) {{
                            bestScore = score;
                            bestCandidate = input;
                        }}
                    }}
                }}

                if (bestCandidate) {{
                    bestCandidate.focus();
                    bestCandidate.value = '{bank_account}';
                    ['input', 'change', 'blur', 'keyup'].forEach(function(evt) {{
                        bestCandidate.dispatchEvent(new Event(evt, {{bubbles: true}}));
                    }});
                    return {{success: true, score: bestScore}};
                }}
                return {{success: false}};
            }})();
            """
            result = driver.execute_script(input_js)
            if result and result.get('success'):
                logging.info(f"[UI] 已通过JavaScript输入银行账号: {bank_account} (评分: {result.get('score')})")
                account_input_found = True
            else:
                logging.warning("[UI] JavaScript输入失败，尝试第三种方式")

        # 方法3：尝试不同的XPath位置（因为页面结构可能变化）
        if not account_input_found:
            logging.info("[UI] 尝试不同的XPath位置（div[3]到div[6]）...")
            for div_num in range(3, 7):
                try:
                    xpath = f"/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div/form/div[{div_num}]/div/div/div/input"
                    account_input = driver.find_element(By.XPATH, xpath)
                    # 使用JavaScript输入，避免元素状态问题
                    driver.execute_script("""
                        arguments[0].focus();
                        arguments[0].value = arguments[1];
                        arguments[0].dispatchEvent(new Event('input', {bubbles: true}));
                        arguments[0].dispatchEvent(new Event('change', {bubbles: true}));
                    """, account_input, bank_account)
                    logging.info(f"[UI] 已通过div[{div_num}]定位器输入银行账号: {bank_account}")
                    account_input_found = True
                    break
                except Exception as e:
                    continue

            if not account_input_found:
                logging.warning("[UI] 所有XPath位置均失败，尝试最终备用方法...")
                # 最终备用：找到所有可见可编辑的输入框，尝试每个
                final_attempt_js = f"""
                (function() {{
                    var inputs = document.querySelectorAll('input');
                    for (var i = inputs.length - 1; i >= 0; i--) {{
                        var input = inputs[i];
                        var style = window.getComputedStyle(input);
                        if (style.display !== 'none' && style.visibility !== 'hidden' &&
                            !input.readOnly && input.type !== 'hidden' && input.type !== 'submit') {{
                            // 尝试清除并设置值
                            input.focus();
                            input.value = '';
                            input.value = '{bank_account}';
                            input.dispatchEvent(new Event('input', {{bubbles: true}}));
                            input.dispatchEvent(new Event('change', {{bubbles: true}}));
                            return {{success: true, index: i, type: input.type}};
                        }}
                    }}
                    return {{success: false}};
                }})();
                """
                result = driver.execute_script(final_attempt_js)
                if result and result.get('success'):
                    logging.info(f"[UI] 已通过最终备用方法输入银行账号: {bank_account} (索引: {result.get('index')})")
                    account_input_found = True

        # 验证银行账号是否已成功输入（始终执行验证）
        logging.info("[UI] 验证银行账号是否已输入...")
        verify_js = f"""
        (function() {{
            var inputs = document.querySelectorAll('input');
            for (var i = 0; i < inputs.length; i++) {{
                if (inputs[i].value === '{bank_account}') {{
                    return {{success: true, found: true, index: i}};
                }}
            }}
            // 如果没找到，列出所有输入框的值用于调试
            var allValues = [];
            for (var i = 0; i < inputs.length; i++) {{
                if (inputs[i].value && inputs[i].offsetParent !== null) {{
                    allValues.push({{index: i, value: inputs[i].value, type: inputs[i].type}});
                }}
            }}
            return {{success: true, found: false, visibleValues: allValues}};
        }})();
        """
        result = driver.execute_script(verify_js)
        if result and result.get('found'):
            logging.info(f"[UI] ✓ 验证成功：银行账号 {bank_account} 已在输入框中（索引: {result.get('index')}）")
            account_input_found = True
        else:
            visible_values = result.get('visibleValues', []) if result else []
            logging.warning(f"[UI] ✗ 验证失败：银行账号 {bank_account} 未找到")
            if visible_values:
                logging.warning("[UI] 当前可见输入框的值:")
                for v in visible_values[:5]:
                    logging.warning(f"[UI]   - 索引{v.get('index')}: '{v.get('value')}' (类型: {v.get('type')})")
            if not account_input_found:
                raise Exception("无法找到银行账号输入框，请检查页面结构")

    else:
        logging.info("[流程] 跳过自动填写，请手动填写银行账户信息")
        input("填写完成后按回车继续...")

    # 点击下一步
    safe_click(driver, "BANK_NEXT_BTN", "银行信息页下一步")


# ==============================================================================
# --- 8. 浏览器初始化 ---
# ==============================================================================
from selenium.webdriver.chrome.service import Service as ChromeService


def init_browser(browser_name: str) -> webdriver.Remote:
    """根据浏览器名称初始化并返回一个浏览器驱动实例（均为无痕模式）"""
    browser_name = browser_name.upper()
    if browser_name not in BROWSER_CONFIG:
        raise ValueError(f"不支持的浏览器: {browser_name}")

    config = BROWSER_CONFIG[browser_name]
    logging.info(f"[Browser] 正在初始化 {browser_name} 浏览器 (无痕模式)...")

    if browser_name in ["CHROME", "QQ", "360", "EDGE"]:
        options = ChromeOptions() if browser_name != "EDGE" else EdgeOptions()
        options.add_argument("--incognito")
        if browser_name == "EDGE":
            options.add_argument("--inprivate")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        if browser_name == "EDGE":
            options.set_capability("ms:loggingPrefs", {"performance": "ALL"})

        if browser_name == "QQ":
            qq_driver_path = r"C:\WebDrivers\chromedriver_123.exe"
            if not os.path.exists(qq_driver_path):
                qq_driver_path = r"C:\WebDrivers\chromedriver_qq.exe"
            if not os.path.exists(qq_driver_path):
                raise FileNotFoundError(
                    f"[Browser] ChromeDriver 不存在！\n"
                    f"请从 https://googlechromelabs.github.io/chrome-for-testing/ 下载 ChromeDriver 123\n"
                    f"并将其放置到: C:\\WebDrivers\\chromedriver_123.exe"
                )
            service = ChromeService(executable_path=qq_driver_path)
            driver = webdriver.Chrome(service=service, options=options)
            enable_network_currency_capture(driver)
            return driver

        if browser_name == "360":
            se_driver_path = r"C:\WebDrivers\chromedriver_132.exe"
            if not os.path.exists(se_driver_path):
                se_driver_path = r"C:\WebDrivers\chromedriver_360.exe"
            if not os.path.exists(se_driver_path):
                raise FileNotFoundError(
                    f"[Browser] ChromeDriver 不存在！\n"
                    f"请从 https://googlechromelabs.github.io/chrome-for-testing/ 下载 ChromeDriver 132\n"
                    f"并将其放置到: C:\\WebDrivers\\chromedriver_132.exe"
                )
            options.add_argument("--remote-debugging-port=9222")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-background-networking")
            options.add_argument("--disable-default-apps")
            options.add_argument("--disable-sync")
            options.add_argument("--metrics-recording-only")
            options.add_argument("--mute-audio")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            service = ChromeService(executable_path=se_driver_path)
            driver = webdriver.Chrome(service=service, options=options)
            enable_network_currency_capture(driver)
            return driver

        if browser_name == "CHROME":
            driver = webdriver.Chrome(options=options)
            enable_network_currency_capture(driver)
            return driver
        elif browser_name == "EDGE":
            driver = webdriver.Edge(options=options)
            enable_network_currency_capture(driver)
            return driver

    elif browser_name == "FIREFOX":
        options = FirefoxOptions()
        options.add_argument("--private")
        options.add_argument("--no-remote")

        if config["binary_path"] and os.path.exists(config["binary_path"]):
            options.binary_location = config["binary_path"]
            logging.info(f"[Browser] 使用指定的浏览器路径: {config['binary_path']}")
        elif config["binary_path"]:
            logging.warning(f"[Browser] 配置的浏览器路径不存在: {config['binary_path']}，将尝试使用默认路径。")

        return webdriver.Firefox(options=options)

    else:
        raise ValueError(f"未知的浏览器类型: {browser_name}")


def extract_currency_from_network_logs(driver: webdriver.Remote) -> Optional[str]:
    """从浏览器性能日志中提取请求头中的currency"""
    enable_network_currency_capture(driver)

    for attempt in range(1, 4):
        try:
            logs = driver.get_log("performance")
        except Exception as e:
            logging.debug(f"[Browser] 浏览器不支持performance日志类型，跳过网络日志提取: {e}")
            return None

        if logs:
            logging.info(f"[Browser] 第{attempt}次扫描performance日志，条数: {len(logs)}")

        for entry in logs:
            try:
                message = json.loads(entry.get("message", "{}"))
                payload = message.get("message", {})
                method = payload.get("method")
                params = payload.get("params", {})

                if method == "Network.requestWillBeSent":
                    headers = params.get("request", {}).get("headers", {})
                    request_url = params.get("request", {}).get("url", "")
                elif method == "Network.requestWillBeSentExtraInfo":
                    headers = params.get("headers", {})
                    request_url = params.get("associatedCookies", "")
                else:
                    continue

                found_currency = extract_currency_from_mapping(headers)
                if found_currency:
                    matched_key, currency = found_currency
                    logging.info(
                        f"✅ 从网络日志提取currency: {currency} | method={method} | key={matched_key}"
                    )
                    if request_url:
                        logging.debug(f"[Browser] 命中currency的请求: {request_url}")
                    return currency
            except Exception:
                continue

        if attempt < 3:
            time.sleep(1)

    return None


# ==============================================================================
# --- 9. 主自动化流程 ---
# ==============================================================================
def run_offline_automation():
    """线下自动化注册流程的主控制器"""
    driver = None
    try:
        # --- 步骤 1: 选择浏览器 ---
        logging.info("\n" + "=" * 50)
        logging.info("步骤 1: 初始化浏览器")
        logging.info("=" * 50)

        browser_choice = get_user_choice(
            {
                '1': '谷歌浏览器',
                '2': '微软浏览器',
                '3': 'QQ浏览器',
                '4': '360安全浏览器',
                '5': '火狐浏览器'
            },
            "请选择用于自动化的浏览器（均为无痕模式）:"
        )

        browser_name_map = {'1': 'CHROME', '2': 'EDGE', '3': 'QQ', '4': '360', '5': 'FIREFOX'}
        selected_browser = browser_name_map[browser_choice]

        driver = init_browser(selected_browser)
        driver.set_page_load_timeout(CONFIG.WAIT_TIMEOUT)
        driver.implicitly_wait(CONFIG.WAIT_TIMEOUT)

        # --- 步骤 2: 自动生成手机号 ---
        logging.info("\n" + "=" * 50)
        logging.info("步骤 2: 自动生成手机号")
        logging.info("=" * 50)

        phone = f"182{random.randint(10000000, 99999999)}"
        logging.info(f"📱 自动生成手机号: {phone}")

        # 写入测试数据文件
        with open(CONFIG.DATA_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n{ENV.upper()} 线下 {phone}")
        logging.info(f"📝 测试数据已写入: {CONFIG.DATA_FILE_PATH}")

        # --- 步骤 3: 访问线下注册页面 ---
        logging.info("\n" + "=" * 50)
        logging.info("步骤 3: 访问线下注册页面")
        logging.info("=" * 50)
        logging.info(f"[UI] 正在访问URL: {OFFLINE_SIGNUP_URL}")
        driver.get(OFFLINE_SIGNUP_URL)
        time.sleep(CONFIG.ACTION_DELAY * 2)

        # --- 步骤 4: 处理注册流程 ---
        auth_token = handle_initial_registration(driver, phone)

        # 检查暂停
        # 暂停检查已禁用

        # --- 步骤 5: 点击立即申请 ---
        logging.info("\n" + "=" * 50)
        logging.info("步骤 5: 提交最终申请")
        logging.info("=" * 50)
        safe_click(driver, "FINAL_APPLY_BTN", "跳转页面后的立即申请按钮")

        # --- 步骤 6: 完成SP授权请求 ---
        logging.info("\n" + "=" * 50)
        logging.info("步骤 6: 完成SP授权请求")
        logging.info("=" * 50)

        time.sleep(5)

        # 从数据库查询state
        try:
            db = get_global_db()
            state_sql = f"""
                SELECT state FROM dpu_auth_token
                WHERE merchant_id IN (
                    SELECT merchant_id FROM dpu_users
                    WHERE phone_number = '{phone}'
                )
                AND authorization_party = 'SP'
                ORDER BY created_at DESC LIMIT 1
            """
            state = db.execute_sql(state_sql)

            if not state:
                logging.error(f"❌ 未查询到SP授权的state，手机号: {phone}")
                return

            logging.info(f"✅ 查询到state: {state}")
        except Exception as e:
            logging.error(f"❌ 查询state失败: {e}")
            return

        # 构建SP授权URL
        base_domain = BASE_URL.replace("https://", "").replace("http://", "")
        sp_auth_url = f"https://{base_domain}/dpu-auth/amazon-sp/auth"

        selling_partner_id = f"spshouquanfs{phone}"
        params = {
            "state": state,
            "selling_partner_id": selling_partner_id,
            "mws_auth_token": "1235",
            "spapi_oauth_code": "123123"
        }

        auth_url = f"{sp_auth_url}?{urlencode(params)}"
        logging.info(f"[AUTH] SP授权URL: {auth_url}")
        logging.info(f"[AUTH] selling_partner_id: {selling_partner_id}")

        # 在新窗口中打开SP授权URL
        try:
            logging.info("[AUTH] 正在新窗口中打开SP授权URL...")
            driver.execute_script(f"window.open('{auth_url}', '_blank');")
            time.sleep(CONFIG.ACTION_DELAY)
            logging.info("✅ SP授权页面已在新窗口中打开")
        except Exception as e:
            logging.warning(f"⚠️ SP授权页面打开异常: {e}")

        # --- 步骤 6.5: 发送updateOffer请求 (SP完成后、3PL前) ---
        logging.info("\n" + "=" * 50)
        logging.info("步骤 6.5: 发送updateOffer请求")
        logging.info("=" * 50)

        time.sleep(3)
        if send_update_offer_request(phone):
            logging.info("✅ updateOffer请求成功！")

            # 轮询查询send_status是否为SUCCESS
            logging.info("⏳ 等待send_status更新为SUCCESS...")
            send_status_success = False
            selling_partner_id = f"spshouquanfs{phone}"
            for attempt in range(1, 31):  # 最多尝试30次
                try:
                    db = get_global_db()
                    send_status_sql = f"""
                        SELECT send_status FROM dpu_seller_center.dpu_manual_offer
                        WHERE platform_seller_id = '{selling_partner_id}'
                        ORDER BY created_at DESC LIMIT 1
                    """
                    send_status = db.execute_sql(send_status_sql)

                    if send_status == "SUCCESS":
                        logging.info(f"✅ send_status已更新为SUCCESS（尝试次数: {attempt}）")
                        send_status_success = True
                        break
                    else:
                        logging.info(f"[轮询 {attempt}/30] send_status: {send_status}")
                except Exception as e:
                    logging.warning(f"[轮询 {attempt}/30] 查询send_status失败: {e}")

                if attempt < 30:
                    time.sleep(2)

            if send_status_success:
                # --- 步骤 6.6: 查询platform_offer_id并访问redirect URL ---
                logging.info("\n" + "=" * 50)
                logging.info("步骤 6.6: 查询platform_offer_id并访问redirect URL")
                logging.info("=" * 50)

                logging.info("⏳ 等待5秒，确保platform_offer_id已入库...")
                time.sleep(5)

                try:
                    db = get_global_db()
                    platform_offer_sql = f"""
                        SELECT platform_offer_id FROM dpu_manual_offer
                        WHERE platform_seller_id = '{selling_partner_id}'
                        ORDER BY created_at DESC LIMIT 1
                    """
                    platform_offer_id = db.execute_sql(platform_offer_sql)

                    if not platform_offer_id:
                        logging.warning(f"⚠️ 未查询到platform_offer_id，selling_partner_id: {selling_partner_id}")
                        logging.info("ℹ️  跳过redirect URL访问，继续后续流程")
                    else:
                        logging.info(f"✅ 查询到platform_offer_id: {platform_offer_id}")

                        # 构建redirect URL（根据环境选择正确的域名）
                        if ENV == "sit":
                            redirect_base = "https://dpu-gateway-sit.dowsure.com"
                        elif ENV == "uat":
                            redirect_base = "https://uat.api.expressfinance.business.hsbc.com"
                        elif ENV == "preprod":
                            redirect_base = "https://preprod.api.expressfinance.business.hsbc.com"
                        elif ENV == "reg":
                            redirect_base = "https://dpu-gateway-reg.dowsure.com"
                        else:
                            redirect_base = f"https://expressfinance-dpu-{ENV}.dowsure.com"

                        redirect_url = f"{redirect_base}/dpu-merchant/amazon/redirect?offerId={platform_offer_id}"
                        logging.info(f"[REDIRECT] 正在新窗口中访问: {redirect_url}")

                        # 在新窗口中打开（不切换窗口，保持原窗口激活）
                        try:
                            driver.execute_script(f"window.open('{redirect_url}', '_blank');")
                            time.sleep(CONFIG.ACTION_DELAY)
                            logging.info(f"✅ redirect页面已在新窗口中打开")
                        except Exception as e:
                            logging.warning(f"⚠️ redirect页面访问异常: {e}")

                except Exception as e:
                    logging.warning(f"⚠️ 查询platform_offer_id或访问redirect URL失败: {e}")
                    logging.info("ℹ️  继续后续流程")
            else:
                logging.warning("⚠️ send_status未更新为SUCCESS，跳过platform_offer_id查询和redirect URL访问")
        else:
            logging.warning("⚠️ updateOffer请求失败，跳过后续步骤")

        # --- 步骤 7: 填写公司信息 ---
        auto_fill_company = get_yes_no_choice("[流程] 是否自动填写公司信息?")
        handle_company_info(driver, auto_fill_company)

        # 检查暂停
        # 暂停检查已禁用

        # --- 步骤 8: 填写董事股东信息 ---
        auto_fill_director = get_yes_no_choice("[流程] 是否自动填写董事股东信息?")
        handle_director_info(driver, phone, auto_fill_director)

        # 检查暂停
        # 暂停检查已禁用

        # --- 步骤 8.5: Tier2融资方案选择（线下默认走Tier2流程）---
        need_bank_info = handle_financing_choice(driver)

        # 如果选择"去激活"，需要填写银行账户信息
        if need_bank_info:
            auto_fill_bank = get_yes_no_choice("[流程] 是否自动填写银行账户信息?")
            handle_bank_account_info(driver, auto_fill_bank)

            # 检查暂停
            # 暂停检查已禁用

        # --- 步骤 9: 发起关联店铺API请求 ---
        logging.info("\n" + "=" * 50)
        logging.info("步骤 9: 发起关联店铺API请求")
        logging.info("=" * 50)
        time.sleep(5)

        # 构建带phone参数的URL
        link_shop_url = f"{BASE_URL}/dpu-merchant/mock/link-sp-3pl-shops?phone={phone}"
        try:
            headers = {"Content-Type": "application/json"}
            logging.info(f"[API] 发送POST请求到: {link_shop_url}")
            response = requests.post(link_shop_url, headers=headers, timeout=30)

            if response.status_code == 200:
                logging.info(f"✅ 关联店铺请求成功 - 响应: {response.text[:100]}...")
            else:
                logging.warning(f"⚠️ 关联店铺请求失败 | 状态码: {response.status_code} | 响应: {response.text[:200]}...")
        except Exception as e:
            logging.error(f"❌ 关联店铺请求异常: {e}")

        # --- 步骤 10: 轮询信用报价状态 ---
        submitted_success = poll_credit_offer_status(phone, authorization_token=auth_token, interval=5, max_attempts=120)

        # 检查暂停
        # 暂停检查已禁用

        # --- 步骤 11: 根据融资方案选择走不同流程 ---
        if submitted_success:
            current_flow_amount_config = get_current_flow_amount_config()
            direct_flow_amount = current_flow_amount_config["direct_flow_amount"]
            unlock_flow_amount = current_flow_amount_config["approved_amount"]

            if need_bank_info:
                # 选择了"去激活"：跳过核保/PSP → 直接审批→电子签→drawdown→放款
                logging.info("\n" + "=" * 50)
                logging.info("步骤 11: 发起审批→电子签→drawdown→放款 (去激活流程)")
                logging.info("=" * 50)

                # 1. 直接发起审批请求（跳过核保，USD=2000 / CNY=70000）
                time.sleep(3)
                if send_approved_request(phone, amount=direct_flow_amount):
                    logging.info(f"✅ 审批请求成功（amount={direct_flow_amount}）！")

                    # 2. 直接发起电子签请求（跳过PSP流程，USD=2000 / CNY=70000）
                    time.sleep(5)
                    logging.info(f"\n[2/4] 发送电子签完成请求（amount={direct_flow_amount}）...")
                    if send_esign_request(phone, amount=direct_flow_amount):
                        logging.info(f"✅ 电子签请求成功（amount={direct_flow_amount}）！")

                        # 3. 轮询drawdown状态，等待SUBMITTED
                        time.sleep(5)
                        drawdown_submitted = poll_drawdown_status(phone, authorization_token=auth_token, interval=5, max_attempts=120)
                        if drawdown_submitted:
                            logging.info("✅ drawdown状态已变为SUBMITTED！")

                            # 4. 发送放款完成请求（USD=2000 / CNY=70000）
                            time.sleep(5)
                            logging.info(f"\n[4/4] 发送放款完成请求（disbursement.completed, amount={direct_flow_amount}）...")
                            if send_disbursement_completed_request(phone, amount=direct_flow_amount):
                                logging.info(f"✅ 放款请求成功（amount={direct_flow_amount}）！")
                            else:
                                logging.error("❌ 放款请求失败！")
                        else:
                            logging.warning("⚠️ drawdown状态未达到SUBMITTED！")
                    else:
                        logging.error("❌ 电子签请求失败！")

                    logging.info("\n" + "=" * 50)
                    logging.info("🎉 审批、电子签、drawdown轮询和放款请求已完成！")
                    logging.info("=" * 50)
                else:
                    logging.error("❌ 审批请求失败！")
            else:
                # 选择了"去解锁"：核保→审批→点击按钮→PSP→电子签
                # USD=500000 / CNY=1500000
                logging.info("\n" + "=" * 50)
                logging.info(f"步骤 11: 发起核保→审批→点击按钮→PSP→电子签 (去解锁流程, amount={unlock_flow_amount})")
                logging.info("=" * 50)

                # 1. 核保请求
                time.sleep(3)
                if send_underwritten_request(phone):
                    logging.info("✅ 核保请求成功！")
                else:
                    logging.error("❌ 核保请求失败！")
                    return

                # 2. 审批请求
                time.sleep(3)
                if send_approved_request(phone):
                    logging.info("✅ 审批请求成功！")

                    # 3. 点击激活额度按钮
                    time.sleep(5)
                    safe_click(driver, "ACTIVATE_CREDIT_BTN", "激活额度按钮")
                    logging.info("✅ 已点击激活额度按钮")

                    # 4. 点击接受按钮
                    time.sleep(5)
                    safe_click(driver, "ACCEPT_BTN", "接受按钮")
                    logging.info("✅ 已点击接受按钮")

                    # 5. PSP开始请求
                    time.sleep(5)
                    logging.info("\n[5/6] 发送PSP验证开始请求...")
                    if send_psp_start_request(phone):
                        logging.info("✅ PSP开始请求成功！")
                    else:
                        logging.error("❌ PSP开始请求失败！")

                    # 6. PSP完成请求
                    time.sleep(5)
                    logging.info("\n[6/6] 发送PSP验证完成请求...")
                    if send_psp_completed_request(phone):
                        logging.info("✅ PSP完成请求成功！")
                    else:
                        logging.error("❌ PSP完成请求失败！")

                    # 7. 电子签请求
                    time.sleep(5)
                    logging.info("\n[7/7] 发送电子签完成请求...")
                    if send_esign_request(phone):
                        logging.info("✅ 电子签请求成功！")
                    else:
                        logging.error("❌ 电子签请求失败！")

                    logging.info("\n" + "=" * 50)
                    logging.info("🎉 核保、审批、PSP和电子签请求已完成！")
                    logging.info("=" * 50)
                else:
                    logging.error("❌ 审批请求失败！")
        else:
            logging.warning("⚠️ 信用报价状态未达到SUBMITTED，跳过后续流程")

        logging.info("\n" + "=" * 50)
        logging.info("🎉 所有自动化步骤已成功完成！")
        logging.info(f"📱 本次操作的手机号: {phone}")
        logging.info("ℹ️  浏览器将保持打开状态，供您手动检查。")
        logging.info("=" * 50)

        while True:
            time.sleep(10)

    except Exception as e:
        logging.error("\n" + "=" * 50)
        logging.error(f"❌ 自动化流程在执行过程中发生致命错误: {e}")
        logging.error("=" * 50)
        if driver:
            error_screenshot_path = f"error_screenshot_{time.strftime('%Y%m%d%H%M%S')}.png"
            driver.save_screenshot(error_screenshot_path)
            logging.error(f"📸 错误状态截图已保存至: {os.path.abspath(error_screenshot_path)}")
    finally:
        if driver:
            try:
                while True:
                    time.sleep(60)
            except KeyboardInterrupt:
                logging.info("\n[流程] 用户手动中断，正在关闭浏览器...")
                driver.quit()
                logging.info("[流程] 浏览器已关闭。")


# ==============================================================================
# --- 10. 入口函数 ---
# ==============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("          HSBC 线下自动化注册工具")
    print("=" * 60)

    setup_logging()

    logging.info(f"📌 当前环境: {ENV.upper()}")
    logging.info(f"📌 API基础URL: {BASE_URL}")
    logging.info(f"📌 线下注册URL: {OFFLINE_SIGNUP_URL}")
    logging.info(f"📌 数据库: {DATABASE_CONFIG_DICT[ENV]['host']}")
    print()

    # 建立全局数据库连接（单例模式，保持连接不关闭）
    get_global_db()

    run_offline_automation()

    logging.info("\n程序主流程结束。")

    # 关闭全局数据库连接
    close_global_db()
