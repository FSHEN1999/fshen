# -*- coding: utf-8 -*-
"""
HSBC 线下自动化注册工具 (DMF版本 - 手动输入手机号邮箱版)

概述:
    直接访问HSBC DMF注册页面完成线下注册流程的Selenium脚本。
    无需选择TIER级别和生成offerId，直接访问固定注册URL。
    手机号和邮箱通过控制台手动输入，而非自动生成。

主要功能:
    1. 手动输入手机号和邮箱
    2. 直接访问注册页面，无需offerId
    3. 自动化完成注册流程（支持5种浏览器的无痕模式）
    4. 完整的流程：注册→SP授权→公司信息→董事信息→核保→审批→PSP→电子签
    5. 详细的日志记录和错误处理机制
"""

import time
import os
import random
import logging
import socket
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

# 暂停管理器：支持通过空格键暂停/继续脚本
from pause_manager import get_pause_manager

# 全局暂停管理器实例
_pause_manager = get_pause_manager()

# ==============================================================================
# --- 1. 配置与常量 (集中管理，易于维护) ---
# ==============================================================================

# ============================ 环境配置 ============================
# 支持的环境：sit, uat, dev, preprod, local
# 修改此变量以切换环境
ENV = "uat"

# 基础URL映射
BASE_URL_DICT = {
    "sit": "https://sit.api.expressfinance.business.hsbc.com",
    "dev": "https://dpu-gateway-dev.dowsure.com",
    "uat": "https://uat.api.expressfinance.business.hsbc.com",
    "preprod": "https://preprod.api.expressfinance.business.hsbc.com",
    "local": "http://192.168.11.3:8080"
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
    "local": ""
}

# 金额配置（每个环境的各种额度）
AMOUNT_CONFIG = {
    "sit": {
        "underwritten_amount": "500000",
        "approved_amount": 500000.00,
        "esign_amount": 500000.00
    },
    "uat": {
        "underwritten_amount": "500000",
        "approved_amount": 500000.00,
        "esign_amount": 500000.00
    },
    "dev": {
        "underwritten_amount": "500000",
        "approved_amount": 500000.00,
        "esign_amount": 500000.00
    },
    "preprod": {
        "underwritten_amount": "500000",
        "approved_amount": 500000.00,
        "esign_amount": 500000.00
    },
    "local": {
        "underwritten_amount": "500000",
        "approved_amount": 500000.00,
        "esign_amount": 500000.00
    }
}

# 获取当前环境的基础URL和金额配置
BASE_URL = BASE_URL_DICT.get(ENV, BASE_URL_DICT["uat"])
CURRENT_AMOUNT_CONFIG = AMOUNT_CONFIG.get(ENV, AMOUNT_CONFIG["uat"])

# 线下注册固定URL（根据环境切换）
OFFLINE_SIGNUP_URL_DICT = {
    "sit": "https://expressfinance-dpu-sit.dowsure.com/zh-Hans/hsbc-dmf",
    "dev": "https://expressfinance-dpu-dev.dowsure.com/en/sign-up-step1",
    "uat": "https://expressfinance-uat.business.hsbc.com/zh-Hans/hsbc-dmf",
    "preprod": "https://expressfinance-preprod.business.hsbc.com/zh-Hans/sign-up",
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
    # 产品选择页面的"立即申请"按钮（DMF版本专用）
    "PRODUCT_APPLY_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[3]/div[1]/div[3]/button"),

    # 初始申请按钮
    "INITIAL_APPLY_BTN": (By.XPATH, "//button[contains(., '立即申请')]"),

    # 注册页面
    "PHONE_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[4]/div/div/div/div[2]/input"),
    "VERIFICATION_CODE_INPUTS": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @maxlength='1']"),
    "REG_NEXT_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[8]/button"),

    # 密码设置页 - 使用绝对XPath路径（与线上流程一致）
    "PASSWORD_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[1]/div[2]/div/div[1]/div/input"),
    "CONFIRM_PASSWORD_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[1]/div[5]/div/div[1]/div/input"),
    "SECURITY_QUESTION_DROPDOWN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[2]/div[2]/div/div[1]/div[1]/div[1]/div[1]/input"),
    "SECURITY_ANSWER_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[2]/div[4]/div/div[1]/div/input"),
    "EMAIL_ADDRESS_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[3]/div[2]/div/div[1]/div/input"),
    "AGREE_DECLARATION_CHECKBOX": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[4]/div/div/label/span[1]/span"),
    "AGREE_AUTHORIZATION_CHECKBOX": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[4]/div[2]/div/label/span[1]/span"),
    "FINAL_REGISTER_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[5]/div[2]/button"),

    # 通用下一步按钮
    "NEXT_BTN": (By.XPATH, "//button[contains(., '下一页')]"),

    # 最终申请按钮（跳转页面后）
    "FINAL_APPLY_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div[1]/div[3]/div[5]/button"),

    # 公司信息页
    "COMPANY_EN_NAME_INPUT": (By.XPATH, "(//input[contains(@class, 'el-input__inner') and @autocomplete='off'])[1]"),
    "BUSINESS_REG_NO_INPUT": (By.XPATH, "(//input[contains(@class, 'el-input__inner') and @autocomplete='off'])[3]"),
    # 线下流程特有的公司信息页元素
    "COMPANY_CN_NAME_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[5]/div[2]/div/div/div/input"),
    "BUSINESS_NATURE_SELECT": (By.XPATH, "//span[text()='企业经营性质']/ancestor::div[contains(@class, 'el-form-item')]//div[contains(@class, 'el-select')]"),
    "BUSINESS_NATURE_OPTIONS": (By.XPATH, "//li[contains(@class, 'el-select-dropdown__item')]"),
    "ESTABLISHED_DATE_INPUT": (By.XPATH, "//input[@placeholder='YYYY/MM/DD']"),
    "REGISTERED_ADDRESS_INPUT": (By.XPATH, "//textarea[@placeholder='请输入注册地址']"),
    # 公司区域选择
    "DISTRICT_SELECT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[9]/div[2]/div/div[1]/div[1]/div[1]/div[2]"),
    "DISTRICT_FIRST_OPTION": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[9]/div[2]/div/div[1]/div[2]/div/div/div[1]/ul/li[1]"),
    # 详细经营地址
    "DETAIL_ADDRESS_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[9]/div[3]/div/div[1]/div/input"),
    # 公司地址与经营地址相同复选框
    "SAME_ADDRESS_CHECKBOX": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[10]/div/div/div[1]/label[1]/span[1]/span"),
    # 与汇丰无业务关系复选框
    "NO_HSBC_RELATIONSHIP_CHECKBOX": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[12]/div/div/div/label[2]/span[1]/span"),
    # 公司信息页文件上传区域（商业信息页面）
    "COMPANY_REG_CERT_UPLOAD": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[2]/div[1]/div[2]/div[1]/div/div"),
    "BUSINESS_REG_CERT_UPLOAD": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[2]/div[2]/div[2]/div[1]/div/div"),
    "COMPANY_ARTICLES_UPLOAD": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[3]/div[1]/div[2]/div[1]/div/div"),
    "ANNUAL_RETURN_UPLOAD": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[3]/div[2]/div[2]/div[1]/div/div"),
    "COMPANY_NEXT_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/div[3]/div[2]/button[2]"),

    # 董事股东信息页
    "ID_NUMBER_INPUT": (By.XPATH, "//input[@placeholder='请输入证件号码']"),
    "ID_FRONT_UPLOAD_AREA": (By.XPATH, "//div[contains(@class, 'el-upload-dragger') and .//img[contains(@src, 'PRC%20ID-Front')]]"),
    "ID_BACK_UPLOAD_AREA": (By.XPATH, "//div[contains(@class, 'el-upload-dragger') and .//img[contains(@src, 'PRC%20ID-Back')]]"),
    "DATE_INPUT": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @placeholder='YYYY/MM/DD']"),
    "DIRECTOR_NEXT_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div[5]/div[2]/button[2]"),
    "REFERENCE_PHONE_INPUT": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @maxlength='15']"),
    "REFERENCE_EMAIL_INPUT": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @autocomplete='off' and not(@maxlength) and not(@placeholder)]"),
    # 董事出生日期和身份证号码
    "DIRECTOR_BIRTH_DATE_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/form/div[1]/div[1]/div[2]/div/div[4]/div[1]/div/div[1]/div/input"),
    "DIRECTOR_ID_NUMBER_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/form/div[1]/div[1]/div[2]/div/div[4]/div[2]/div/div/div/input"),
    # 董事称谓下拉框
    "DIRECTOR_TITLE_DROPDOWN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/form/div[1]/div[1]/div[2]/div/div[1]/div/div/div/div[1]/div[1]/div[2]"),
    "DIRECTOR_TITLE_FIRST_OPTION": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/form/div[1]/div[1]/div[2]/div/div[1]/div/div/div[1]/div[2]/div/div/div[1]/ul/li[1]"),
    # 董事详情经营地址
    "DIRECTOR_DETAIL_ADDRESS_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/form/div[1]/div[1]/div[2]/div/div[7]/div[2]/div/div[1]/div/input"),
    # 董事担保人勾选框
    "DIRECTOR_GUARANTOR_CHECKBOX": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/form/div[4]/div/div[1]/div/label/span[1]/span"),

    # 银行账户信息页
    # 银行选择主定位器（精准定位）
    "BANK_SELECT_CONTAINER": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div/form/div[2]/div/div/div/div[1]"),
    "BANK_SELECT_DROPDOWN": (By.XPATH, "//input[contains(@class, 'el-select__input') and @role='combobox']"),
    "BANK_SELECT_OPTIONS": (By.XPATH, "//li[contains(@class, 'el-select-dropdown__item')]"),
    "BANK_ACCOUNT_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div/form/div[4]/div/div/div/input"),
    # 银行选择备选定位器
    "BANK_SELECT_SVG_ICON": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div/form/div[2]/div/div/div/div[2]/i/svg"),
    "BANK_SELECT_DIV": (By.XPATH, "//div[contains(@class, 'el-select')]"),
    "BANK_SELECT_TRIGGER": (By.XPATH, "//div[contains(@class, 'el-select')]//span[contains(@class, 'el-select__suffix')]"),
    "BANK_SELECT_DISABLED_INPUT": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @readonly]"),
    "BANK_NEXT_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div/div[4]/div[2]/button[2]"),

    # 联系人信息页
    "CONTACT_DROPDOWN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/form/div[2]/div[2]/div/div/div/div[1]/div[1]/div[2]"),
    "CONTACT_FIRST_OPTION": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/form/div[2]/div[2]/div/div/div/div[2]/div/div/div[1]/ul/li"),
    "SUBMIT_APPLICATION_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div[5]/div[2]/button[2]"),

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


def generate_mock_id_number() -> str:
    """生成虚拟的18位身份证号码（用于测试）

    格式：6位地区码 + 8位出生日期 + 3位顺序码 + 1位校验码
    """
    import random

    # 常用地区码（北京市东城区）
    area_code = "110101"

    # 生成出生日期（1970-2000年之间随机）
    year = random.randint(1970, 2000)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    birth_date = f"{year}{month:02d}{day:02d}"

    # 生成3位顺序码（随机数，确保始终是3位）
    sequence = f"{random.randint(1, 999):03d}"

    # 前17位
    id_17 = area_code + birth_date + sequence

    # 计算校验码（根据GB 11643-1999标准）
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    check_codes = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2']

    total = 0
    for i in range(17):
        total += int(id_17[i]) * weights[i]

    check_code = check_codes[total % 11]

    return id_17 + check_code


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
        amount = CURRENT_AMOUNT_CONFIG["underwritten_amount"]
    webhook_url = f"{BASE_URL}/dpu-openapi/webhook-notifications"

    try:
        db = get_global_db()

        merchant_id = db.execute_sql(
            f"SELECT merchant_id FROM dpu_users WHERE phone_number = '{phone}' ORDER BY created_at DESC LIMIT 1;"
        )
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
                            "currency": "CNY",
                            "underwrittenAmount": {"currency": "CNY", "amount": amount},
                            "availableLimit": {"currency": "CNY", "amount": "0.00"},
                            "signedLimit": {"currency": "CNY", "amount": "0.00"},
                            "watermark": {"currency": "CNY", "amount": "0.00"}
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
        amount = CURRENT_AMOUNT_CONFIG["approved_amount"]
    webhook_url = f"{BASE_URL}/dpu-openapi/webhook-notifications"

    try:
        db = get_global_db()

        merchant_id = db.execute_sql(
            f"SELECT merchant_id FROM dpu_users WHERE phone_number = '{phone}' ORDER BY created_at DESC LIMIT 1;"
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
                        "offerEndDate": "2024-10-15",
                        "offerStartDate": "2023-10-16",
                        "approvedLimit": {"currency": "USD", "amount": amount},
                        "warterMark": {"currency": "USD", "amount": 0.00},
                        "signedLimit": {"currency": "USD", "amount": 0.00},
                        "feeOrCharge": {
                            "type": "PROCESSING_FEE",
                            "feeOrChargeDate": "2023-10-16",
                            "netAmount": {"currency": "USD", "amount": 0.00}
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
        amount = CURRENT_AMOUNT_CONFIG["esign_amount"]
    webhook_url = f"{BASE_URL}/dpu-openapi/webhook-notifications"

    try:
        db = get_global_db()

        merchant_id = db.execute_sql(
            f"SELECT merchant_id FROM dpu_users WHERE phone_number = '{phone}' ORDER BY created_at DESC LIMIT 1;"
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
                    "signedLimit": {"amount": amount, "currency": "USD"},
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

        # 检查暂停（按空格键暂停/继续）
        _pause_manager.check_pause()

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

        # 检查暂停（按空格键暂停/继续）
        _pause_manager.check_pause()

        if attempt < max_attempts:
            time.sleep(interval)

    logging.error(f"\n[轮询] 达到最大尝试次数 {max_attempts}，未获取到 SUBMITTED 状态。")
    return False


def send_disbursement_completed_request(phone: str, amount: float = 2000.00) -> bool:
    """发送放款完成请求 (disbursement.completed)"""
    webhook_url = f"{BASE_URL}/dpu-openapi/webhook-notifications"

    try:
        db = get_global_db()

        merchant_id = db.execute_sql(
            f"SELECT merchant_id FROM dpu_users WHERE phone_number = '{phone}' ORDER BY created_at DESC LIMIT 1;"
        )
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
                        "loanAmount": {"currency": "USD", "amount": amount},
                        "rate": {"chargeBases": "Float", "baseRateType": "SOFR", "baseRate": "6.00", "marginRate": "0.00"},
                        "term": "120",
                        "termUnit": "Days",
                        "drawdownSuccessDate": time.strftime("%Y-%m-%d", time.localtime()),
                        "actualDrawdownDate": time.strftime("%Y-%m-%d", time.localtime())
                    },
                    "repayment": {
                        "expectedRepaymentDate": "2026-06-21",
                        "expectedRepaymentAmount": {"currency": "USD", "amount": amount},
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

    # 备选定位器（特别是针对日期输入框）
    fallback_locators = []
    if locator_key == "DATE_INPUT":
        fallback_locators = [
            (By.XPATH, "//input[contains(@class, 'el-input__inner') and @placeholder='YYYY/MM/DD']"),
            (By.XPATH, "//input[contains(@class, 'el-input__inner') and @type='text']"),
            (By.XPATH, "//input[@placeholder='YYYY/MM/DD']"),
            (By.CSS_SELECTOR, "input.el-input__inner"),
        ]

    try:
        # 尝试主定位器
        element = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(EC.visibility_of_element_located(locator))
        # 滚动到元素位置，确保元素可见
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        time.sleep(0.3)
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
                    # 滚动到元素位置
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                    time.sleep(0.3)
                    element.clear()
                    element.send_keys(text)
                    logging.info(f"[UI] 使用备选定位器 #{i} 在 '{field_description}' 中输入: {text}")
                    return
                except Exception:
                    continue

        logging.error(f"[UI] 向 '{field_description}' 输入时发生错误: {e}")
        raise


def upload_image(driver: webdriver.Remote, description: str, custom_path: Optional[str] = None):
    """上传图片到指定区域（优化版，使用JavaScript直接上传避免stale element错误）

    Args:
        driver: WebDriver实例
        description: 图片描述（用于文件名映射）
        custom_path: 自定义图片路径（可选），如果提供则直接使用该路径
    """
    try:
        # 1. 处理图片路径
        if custom_path:
            # 使用自定义路径
            abs_image_path = custom_path
            target_file = os.path.basename(custom_path)
        else:
            # 使用默认文件名映射（支持中英文描述）
            file_mapping = {
                "身份证正面": "身份证正面.png",
                "身份证背面": "身份证反面.png",
                "ID-Front": "身份证正面.png",
                "ID-Back": "身份证反面.png",
            }

            # 根据description获取目标文件
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
            # 转换为绝对路径（JavaScript需要）
            abs_image_path = os.path.abspath(image_path)

            # 验证文件存在
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"图片文件不存在: {image_path}")

        # 3. 使用JavaScript直接上传（避免stale element问题）
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


def upload_company_document(driver: webdriver.Remote, locator_key: str, doc_name: str, doc_path: str):
    """上传公司文档（点击上传区域后选择文件）

    Args:
        driver: WebDriver实例
        locator_key: LOCATORS字典中的定位器键名
        doc_name: 文档名称（用于日志）
        doc_path: 文档完整路径
    """
    try:
        logging.info(f"[UI] 正在上传 {doc_name}...")

        # 1. 点击上传区域（先滚动到元素位置，避免被遮挡）
        upload_area = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(
            EC.presence_of_element_located(LOCATORS[locator_key])
        )

        # 滚动到元素位置，确保元素可见
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", upload_area)
        time.sleep(0.5)

        # 使用JavaScript点击，避免元素遮挡问题
        driver.execute_script("arguments[0].click();", upload_area)
        time.sleep(1)

        # 2. 使用自定义路径上传图片
        upload_image(driver, doc_name, custom_path=doc_path)
        logging.info(f"[UI] ✅ {doc_name} 上传成功")
        time.sleep(CONFIG.ACTION_DELAY * 2)

    except Exception as e:
        logging.error(f"[UI] 上传 {doc_name} 时发生错误: {e}")
        raise


# ==============================================================================
# --- 7. 页面处理函数 ---
# ==============================================================================
def handle_initial_registration(driver: webdriver.Remote, phone: str, email: str) -> Optional[str]:
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

    # 处理密码设置页，并获取token（传递email参数）
    auth_token = handle_password_setup(driver, phone, email)
    return auth_token


def handle_password_setup(driver: webdriver.Remote, phone: str, email: str) -> Optional[str]:
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

    # 5. 输入电子邮件地址 (使用手动输入的邮箱)
    email_address = email
    safe_send_keys(driver, "EMAIL_ADDRESS_INPUT", email_address, "电子邮件地址")
    time.sleep(CONFIG.ACTION_DELAY)

    # 6. 勾选同意声明
    safe_click(driver, "AGREE_DECLARATION_CHECKBOX", "同意声明复选框")
    time.sleep(CONFIG.ACTION_DELAY)

    # 6.5. 勾选同意授权
    safe_click(driver, "AGREE_AUTHORIZATION_CHECKBOX", "同意授权复选框")
    time.sleep(CONFIG.ACTION_DELAY)

    # 7. 点击注册按钮
    safe_click(driver, "FINAL_REGISTER_BTN", "注册按钮")
    time.sleep(CONFIG.ACTION_DELAY * 3)

    # 7. 从浏览器获取token
    auth_token = get_token_from_browser(driver)
    return auth_token


def get_token_from_browser(driver: webdriver.Remote) -> Optional[str]:
    """从浏览器存储中获取授权token"""
    logging.info("[Browser] 正在从浏览器存储中获取token...")

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
    """处理公司信息页面（线下流程：填写英文名称、BRN、上传四份文档）"""
    logging.info("\n" + "=" * 50)
    logging.info("步骤 4: 处理公司信息")
    logging.info("=" * 50)

    # 文档路径配置（添加文件扩展名）
    doc_base_path = r"C:\Users\PC\Desktop\截图"
    documents = [
        ("公司注册证书", os.path.join(doc_base_path, "公司注册证书.png")),
        ("商业登记证", os.path.join(doc_base_path, "商业登记证.png")),
        ("公司章程", os.path.join(doc_base_path, "公司章程.png")),
        ("周年申报表", os.path.join(doc_base_path, "周年申报表.png")),
    ]

    if auto_fill:
        logging.info("[流程] 选择自动填写公司信息...")
        # 1. 上传四份公司文档（优先处理）
        for doc_name, doc_path in documents:
            upload_image(driver, doc_name, custom_path=doc_path)
            time.sleep(CONFIG.ACTION_DELAY * 2)

        # 2. 填写公司英文名称
        safe_send_keys(driver, "COMPANY_EN_NAME_INPUT", "TestingCompany", "公司英文名称")

        # 3. 填写公司中文名称
        safe_send_keys(driver, "COMPANY_CN_NAME_INPUT", "测试有限公司", "公司中文名称")

        # 4. 填写商业登记号(BRN)
        safe_send_keys(driver, "BUSINESS_REG_NO_INPUT", "00000001", "商业登记号(BRN)")

        # 5. 填写公司注册日期
        safe_send_keys(driver, "ESTABLISHED_DATE_INPUT", "2025/12/01", "公司注册日期")

        # 6. 选择公司区域
        safe_click(driver, "DISTRICT_SELECT", "公司区域选择框")
        time.sleep(CONFIG.ACTION_DELAY)
        safe_click(driver, "DISTRICT_FIRST_OPTION", "公司区域第一个选项")

        # 7. 填写详细经营地址
        safe_send_keys(driver, "DETAIL_ADDRESS_INPUT", "shenzhen", "详细经营地址")

        # 8. 勾选公司地址与经营地址相同
        safe_click(driver, "SAME_ADDRESS_CHECKBOX", "公司地址与经营地址相同复选框")

        # 9. 勾选与汇丰无业务关系
        safe_click(driver, "NO_HSBC_RELATIONSHIP_CHECKBOX", "与汇丰无业务关系复选框")
    else:
        logging.info("[流程] 跳过自动填写，请手动填写公司信息")
        input("填写完成后按回车继续...")

    # 点击下一步
    safe_click(driver, "COMPANY_NEXT_BTN", "公司信息页下一步按钮")


def handle_director_info(driver: webdriver.Remote, phone: str, email: str, auto_fill: bool):
    """处理董事股东信息页面（与线上流程一致，从上传身份证开始）"""
    logging.info("\n" + "=" * 50)
    logging.info("步骤 5: 处理董事股东信息")
    logging.info("=" * 50)
    if auto_fill:
        logging.info("[流程] 选择自动填写董事股东信息...")
        # 1. 选择称谓（点击下拉框并选择第一选项'Mr'）
        safe_click(driver, "DIRECTOR_TITLE_DROPDOWN", "董事称谓下拉框")
        time.sleep(CONFIG.ACTION_DELAY)
        safe_click(driver, "DIRECTOR_TITLE_FIRST_OPTION", "董事称谓第一选项'Mr'")
        logging.info("[UI] 已选择称谓: Mr")

        # 2. 上传身份证正面
        upload_image(driver, "身份证正面")
        time.sleep(CONFIG.ACTION_DELAY * 3)

        # 3. 上传身份证背面
        upload_image(driver, "身份证背面")
        time.sleep(CONFIG.ACTION_DELAY * 3)

        # 4. 填写出生日期（格式：2024/12/30）
        safe_send_keys(driver, "DIRECTOR_BIRTH_DATE_INPUT", "2024/12/30", "董事出生日期")

        # 5. 填写身份证号码（生成虚拟的不重复18位身份证号）
        mock_id_number = generate_mock_id_number()
        safe_send_keys(driver, "DIRECTOR_ID_NUMBER_INPUT", mock_id_number, "董事身份证号码")
        logging.info(f"[UI] 已生成并填写虚拟身份证号: {mock_id_number}")

        # 6. 填写参考手机号
        safe_send_keys(driver, "REFERENCE_PHONE_INPUT", phone, "参考手机号")

        # 7. 填写参考邮箱（使用手动输入的邮箱）
        safe_send_keys(driver, "REFERENCE_EMAIL_INPUT", email, "参考邮箱")

        # 8. 填写详情经营地址
        safe_send_keys(driver, "DIRECTOR_DETAIL_ADDRESS_INPUT", "shenzhen", "详情经营地址")

        # 9. 勾选担保人复选框
        safe_click(driver, "DIRECTOR_GUARANTOR_CHECKBOX", "担保人勾选框")
    else:
        logging.info("[流程] 跳过自动填写，请手动填写董事股东信息")
        input("填写完成后按回车继续...")

    # 点击下一步（使用董事股东页专用的下一步按钮）
    safe_click(driver, "DIRECTOR_NEXT_BTN", "董事股东信息页下一步")


def handle_contact_info(driver: webdriver.Remote):
    """处理联系人信息页面填写"""
    import time as time_module
    start_time = time_module.time()

    logging.info("\n" + "=" * 50)
    logging.info("步骤 6: 处理联系人信息页面填写")
    logging.info("=" * 50)

    # 等待页面加载完成
    time.sleep(CONFIG.ACTION_DELAY * 3)

    # 等待联系人下拉框加载
    logging.info("[UI] 等待联系人信息页面加载...")
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(LOCATORS["CONTACT_DROPDOWN"])
        )
        elapsed = time_module.time() - start_time
        logging.info(f"[UI] 联系人信息页面已加载，耗时: {elapsed:.2f}秒")
    except Exception as e:
        logging.warning(f"[UI] 等待联系人信息页超时，尝试继续: {e}")
        time.sleep(3)

    # 步骤一：点击联系人下拉列表
    logging.info("[流程] 步骤一：点击联系人下拉列表...")
    safe_click(driver, "CONTACT_DROPDOWN", "联系人下拉列表")
    time.sleep(CONFIG.ACTION_DELAY)

    # 步骤二：点击下拉列表第一位联系人
    logging.info("[流程] 步骤二：选择第一位联系人...")
    safe_click(driver, "CONTACT_FIRST_OPTION", "联系人第一位选项")
    time.sleep(CONFIG.ACTION_DELAY)

    # 步骤三：点击提交申请按钮
    logging.info("[流程] 步骤三：点击提交申请按钮...")
    safe_click(driver, "SUBMIT_APPLICATION_BTN", "提交申请按钮")

    total_elapsed = time_module.time() - start_time
    logging.info(f"✅ 联系人信息页面填写完成，总耗时: {total_elapsed:.2f}秒")


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

        # 等待银行选择完成后再输入账号
        time.sleep(1)

        # 生成并输入银行账号
        import random
        bank_account = f"{random.randint(100000000000, 999999999999)}"
        logging.info(f"[UI] 准备输入银行账号: {bank_account}")

        # 尝试多种方式找到银行账号输入框
        account_input_found = False

        # 方法1：使用主定位器
        try:
            account_input = WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located(LOCATORS["BANK_ACCOUNT_INPUT"])
            )
            # 确保元素可交互
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", account_input)
            time.sleep(0.3)
            account_input.clear()
            account_input.send_keys(bank_account)
            logging.info(f"[UI] 已输入银行账号: {bank_account}")
            account_input_found = True
        except Exception as e:
            logging.warning(f"[UI] 主定位器失败: {e}，尝试备选方式")

        # 方法2：通过JavaScript输入
        if not account_input_found:
            logging.info("[UI] 尝试通过JavaScript查找并输入银行账号...")
            input_js = f"""
            (function() {{
                // 查找所有可见的输入框
                var inputs = document.querySelectorAll('input');
                for (var i = inputs.length - 1; i >= 0; i--) {{
                    var input = inputs[i];
                    // 检查是否可见且为空
                    if (input.offsetParent !== null &&
                        input.type !== 'hidden' &&
                        input.type !== 'submit' &&
                        !input.readOnly &&
                        !input.value) {{
                        // 尝试设置值
                        input.focus();
                        input.value = '{bank_account}';
                        // 触发事件
                        var events = ['input', 'change', 'blur'];
                        for (var j = 0; j < events.length; j++) {{
                            var event = new Event(events[j], {{bubbles: true}});
                            input.dispatchEvent(event);
                        }}
                        return {{success: true, tagName: input.tagName, type: input.type}};
                    }}
                }}
                return {{success: false}};
            }})();
            """
            result = driver.execute_script(input_js)
            if result and result.get('success'):
                logging.info(f"[UI] 已通过JavaScript输入银行账号: {bank_account} (元素类型: {result.get('type')})")
                account_input_found = True
            else:
                logging.warning("[UI] JavaScript输入失败，尝试第三种方式")

        # 方法3：最后尝试使用更宽松的定位器
        if not account_input_found:
            logging.info("[UI] 尝试查找最后一个空输入框...")
            last_input_js = f"""
            (function() {{
                var inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([readonly])'));
                // 找到最后一个可见的空输入框
                for (var i = inputs.length - 1; i >= 0; i--) {{
                    if (inputs[i].offsetParent !== null && !inputs[i].value) {{
                        inputs[i].focus();
                        inputs[i].value = '{bank_account}';
                        inputs[i].dispatchEvent(new Event('input', {{bubbles: true}}));
                        inputs[i].dispatchEvent(new Event('change', {{bubbles: true}}));
                        return {{success: true}};
                    }}
                }}
                return {{success: false}};
            }})();
            """
            result = driver.execute_script(last_input_js)
            if result and result.get('success'):
                logging.info(f"[UI] 已通过第三种方式输入银行账号: {bank_account}")
                account_input_found = True

        # 验证银行账号是否已成功输入（使用更宽松的验证逻辑）
        if not account_input_found:
            logging.info("[UI] 验证银行账号是否已输入...")
            # 去除可能的空格或分隔符进行匹配
            bank_account_clean = bank_account.replace(' ', '').replace('-', '')
            verify_js = f'''
            (function() {{
                var inputs = document.querySelectorAll('input');
                var allValues = [];
                for (var i = 0; i < inputs.length; i++) {{
                    var value = inputs[i].value;
                    if (value) {{
                        allValues.push(value);
                        // 去除空格和分隔符后比较
                        var cleanValue = value.replace(/\\s/g, '').replace(/-/g, '');
                        if (cleanValue === '{bank_account_clean}') {{
                            return {{success: true, found: true, value: value, method: 'exact'}};
                        }}
                        // 也检查是否包含银行账号（处理格式化显示的情况）
                        if (cleanValue.includes('{bank_account_clean}') || '{bank_account_clean}'.includes(cleanValue)) {{
                            return {{success: true, found: true, partial: true, value: value, method: 'partial'}};
                        }}
                    }}
                }}
                // 还没找到，检查其他可能的元素（如el-input的内部元素）
                var spans = document.querySelectorAll('.el-input__inner');
                for (var j = 0; j < spans.length; j++) {{
                    if (spans[j].value) {{
                        var cleanValue = spans[j].value.replace(/\\s/g, '').replace(/-/g, '');
                        if (cleanValue === '{bank_account_clean}' || cleanValue.includes('{bank_account_clean}')) {{
                            return {{success: true, found: true, value: spans[j].value, method: 'el-input'}};
                        }}
                    }}
                }}
                return {{success: true, found: false, allValues: allValues}};
            }})();
            '''
            result = driver.execute_script(verify_js)
            if result and result.get('found'):
                match_type = "完全匹配" if not result.get('partial') else "部分匹配"
                display_value = result.get('value', 'N/A')
                method = result.get('method', 'unknown')
                logging.info(f"[UI] 验证成功：银行账号 {match_type} ({method}) - 显示值: {display_value}")
                account_input_found = True
            else:
                # 显示所有找到的输入框值用于诊断
                all_values = result.get('allValues', []) if result else []
                logging.warning(f"[UI] ⚠️ 自动验证未找到完全匹配的银行账号")
                logging.warning(f"[UI] 💡 预期银行账号: {bank_account} (清理后: {bank_account_clean})")
                if all_values:
                    logging.warning(f"[UI] 📋 页面上找到的输入框值: {all_values}")
                logging.warning(f"[UI] 📋 请检查页面上的银行账号输入框，如果已填写正确，按Enter继续")
                user_input = input("确认银行账号已正确填写？(直接Enter继续，输入n退出): ").strip()
                if user_input.lower() != 'n':
                    account_input_found = True
                    logging.info("[UI] 用户确认银行账号已正确填写")
                else:
                    raise Exception("用户取消操作，银行账号未填写")

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

        if config["binary_path"] and os.path.exists(config["binary_path"]):
            options.binary_location = config["binary_path"]
            logging.info(f"[Browser] 使用指定的浏览器路径: {config['binary_path']}")
        elif config["binary_path"]:
            logging.warning(f"[Browser] 配置的浏览器路径不存在: {config['binary_path']}，将尝试使用默认路径。")

        # QQ浏览器
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
            return webdriver.Chrome(service=service, options=options)

        # 360浏览器
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
            return webdriver.Chrome(service=service, options=options)

        if browser_name == "CHROME":
            return webdriver.Chrome(options=options)
        elif browser_name == "EDGE":
            return webdriver.Edge(options=options)

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

        # --- 步骤 2: 手动输入手机号和邮箱 ---
        logging.info("\n" + "=" * 50)
        logging.info("步骤 2: 手动输入手机号和邮箱")
        logging.info("=" * 50)

        # 手动输入手机号（8位或11位数字）
        while True:
            phone = input("请输入手机号（8位或11位数字）: ").strip()
            if phone.isdigit() and len(phone) in (8, 11):
                break
            logging.warning("⚠️ 手机号格式不正确，请输入8位或11位数字！")
        logging.info(f"📱 使用手机号: {phone}")

        # 手动输入邮箱
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        while True:
            email = input("请输入邮箱地址: ").strip()
            if re.match(email_pattern, email):
                break
            logging.warning("⚠️ 邮箱格式不正确，请重新输入！")
        logging.info(f"📧 使用邮箱: {email}")

        # 写入测试数据文件
        with open(CONFIG.DATA_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n{ENV.upper()} 线下 {phone} {email}")
        logging.info(f"📝 测试数据已写入: {CONFIG.DATA_FILE_PATH}")

        # --- 步骤 3: 访问线下注册页面 ---
        logging.info("\n" + "=" * 50)
        logging.info("步骤 3: 访问线下注册页面")
        logging.info("=" * 50)
        logging.info(f"[UI] 正在访问URL: {OFFLINE_SIGNUP_URL}")
        driver.get(OFFLINE_SIGNUP_URL)
        time.sleep(CONFIG.ACTION_DELAY * 2)

        # --- 步骤 4: 点击产品选择页面的"立即申请"按钮 ---
        logging.info("\n" + "=" * 50)
        logging.info("步骤 4: 点击产品选择页面的'立即申请'按钮")
        logging.info("=" * 50)
        safe_click(driver, "PRODUCT_APPLY_BTN", "产品选择页面的立即申请按钮")
        time.sleep(CONFIG.ACTION_DELAY * 2)

        # --- 步骤 5: 处理注册流程 ---
        auth_token = handle_initial_registration(driver, phone, email)

        # 检查暂停（按空格键暂停/继续）
        _pause_manager.check_pause()

        # --- 步骤 6: 点击立即申请 ---
        logging.info("\n" + "=" * 50)
        logging.info("步骤 6: 提交最终申请")
        logging.info("=" * 50)
        safe_click(driver, "FINAL_APPLY_BTN", "跳转页面后的立即申请按钮")

        # --- 步骤 7: 完成SP授权请求 ---
        logging.info("\n" + "=" * 50)
        logging.info("步骤 7: 完成SP授权请求")
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
                    AND authorization_party = 'SP'
                )
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

        try:
            logging.info("[AUTH] 正在发送SP授权GET请求...")
            response = requests.get(auth_url, timeout=30)

            if response.status_code == 200:
                logging.info(f"✅ SP授权请求成功 - 响应: {response.text[:100]}...")
            else:
                logging.warning(f"⚠️ SP授权请求返回状态码: {response.status_code} | 响应: {response.text[:200]}...")
        except Exception as e:
            logging.warning(f"⚠️ SP授权请求异常: {e}")

        # --- 步骤 6.5: 查询platform_offer_id并访问redirect URL ---
        logging.info("\n" + "=" * 50)
        logging.info("步骤 6.5: 查询platform_offer_id并访问redirect URL")
        logging.info("=" * 50)

        logging.info("⏳ 等待5秒，确保platform_offer_id已入库...")
        time.sleep(5)

        selling_partner_id = f"spshouquanfs{phone}"
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

        # --- 步骤 6.6: 发送updateOffer请求 (SP完成后、3PL前) ---
        logging.info("\n" + "=" * 50)
        logging.info("步骤 6.6: 发送updateOffer请求")
        logging.info("=" * 50)

        time.sleep(3)
        if send_update_offer_request(phone):
            logging.info("✅ updateOffer请求成功！")
        else:
            logging.warning("⚠️ updateOffer请求失败，继续后续流程")

        # --- 步骤 7: 填写公司信息 ---
        auto_fill_company = get_yes_no_choice("[流程] 是否自动填写公司信息?")
        handle_company_info(driver, auto_fill_company)

        # 检查暂停（按空格键暂停/继续）
        _pause_manager.check_pause()

        # --- 步骤 8: 填写董事股东信息 ---
        auto_fill_director = get_yes_no_choice("[流程] 是否自动填写董事股东信息?")
        handle_director_info(driver, phone, email, auto_fill_director)

        # 检查暂停（按空格键暂停/继续）
        _pause_manager.check_pause()

        # --- 步骤 6: 联系人信息页面填写 ---
        handle_contact_info(driver)

        # 检查暂停（按空格键暂停/继续）
        _pause_manager.check_pause()

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

        # 检查暂停（按空格键暂停/继续）
        _pause_manager.check_pause()

        # --- 步骤 7: 发起核保→审批→点击按钮→PSP→电子签 ---
        if submitted_success:
            logging.info("\n" + "=" * 50)
            logging.info("步骤 7: 发起核保→审批→点击按钮→PSP→电子签")
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
    print("          HSBC 线下自动化注册工具 (DMF版本)")
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
