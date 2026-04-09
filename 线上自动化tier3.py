"""
HSBC API 数据生成与自动注册工具 - TIER3固定版本

概述:
    一个用于自动化生成测试数据并完成HSBC相关注册流程的Selenium脚本。
    **固定选择TIER3级别（金额: 2000000）**，无需手动选择TIER。
    新增支持：Chrome、Edge、QQ浏览器、360安全浏览器、Firefox（均为无痕模式）

主要功能:
    1. 生成测试数据（固定TIER3，金额2000000）。
    2. 自动化完成注册流程（支持5种浏览器的无痕模式）。
    3. 智能处理TIER3级别的完整流程（核保→审批→PSP→电子签→放款→还款）。
    4. 详细的日志记录和错误处理机制。

TIER3流程:
    核保(underwritten) → 审批(approved) → PSP验证 → 电子签 → 放款 → 还款
"""

import time
import random
import os
import logging
import re
import socket
import subprocess  # 新增：用于关闭进程
import uuid  # 新增：用于生成UUID
import json
from datetime import datetime, timedelta
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
import pymysql  # 新增：数据库连接
from pymysql.err import OperationalError  # 数据库错误类型
from urllib.parse import urlencode

# 暂停管理器：支持通过空格键暂停/继续脚本
from pause_manager import get_pause_manager

# 全局暂停管理器实例
_pause_manager = get_pause_manager()

# ==============================================================================
# --- 1. 配置与常量 (集中管理，易于维护) ---
# ==============================================================================

# ============================ 环境配置 ============================
# 支持的环境：sit, uat, dev, preprod, reg, local
# 修改此变量以切换环境
ENV = "uat"

# 基础URL映射（参考mock_sit.py）
BASE_URL_DICT = {
    "sit": "https://sit.api.expressfinance.business.hsbc.com",
    "dev": "https://dpu-gateway-dev.dowsure.com",
    "uat": "https://uat.api.expressfinance.business.hsbc.com",
    "preprod": "https://preprod.api.expressfinance.business.hsbc.com",
    "reg": "https://dpu-gateway-reg.dowsure.com",
    "local": "http://192.168.11.3:8080"
}

# 金额配置（按currency映射TIER3流程金额）
FLOW_AMOUNT_CONFIG = {
    "USD": {
        "underwritten_amount": "800000",
        "approved_amount": 500000.00,
        "approved_amount_2nd": 800000.00,
        "esign_amount": 800000.00,
    },
    "CNY": {
        "underwritten_amount": "2000000",
        "approved_amount": 1500000.00,
        "approved_amount_2nd": 2000000.00,
        "esign_amount": 2000000.00,
    },
}

# 数据库配置（参考mock_sit.py）
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

# 默认token映射（每个环境可能不同）
DEFAULT_TOKEN_DICT = {
    "sit": "wfVSribS934y6wZOtUAc5uU5eFcS2nUxcVjmy03OFInKt36rzGCS55EGLLHXS0YZ",
    "uat": "mjx0FpE9gnTC3OTmrX7znQzIgGXRNQwV4umkOhF5wVb6AJB0DuVwmqh6zxiwma4B",
    "dev": "",
    "preprod": "",
    "reg": "",
    "local": ""
}

# 获取当前环境的基础URL和金额配置
BASE_URL = BASE_URL_DICT.get(ENV, BASE_URL_DICT["uat"])
CURRENT_AMOUNT_CONFIG = FLOW_AMOUNT_CONFIG["USD"]

# 新增：浏览器配置字典 (统一管理)
BROWSER_CONFIG = {
    "CHROME": {
        "binary_path": "",  # Chrome通常不需要指定路径，除非安装在非默认位置
        "process_name": "chrome.exe"
    },
    "EDGE": {
        "binary_path": "",  # Edge通常不需要指定路径
        "process_name": "msedge.exe"
    },
    "QQ": {
        "binary_path": r"C:\Program Files\Tencent\QQBrowser\QQBrowser.exe",
        "process_name": "QQBrowser.exe"
    },
    "360": {
        "binary_path": r"C:\Users\PC\AppData\Roaming\360se6\Application\360se.exe",
        "process_name": "360se.exe"
    },
    "FIREFOX": {
        "binary_path": r"C:\Program Files\Mozilla Firefox\firefox.exe",
        "process_name": "firefox.exe"
    }
}


@dataclass
class AppConfig:
    """应用程序核心配置（根据ENV变量动态生成）"""
    # API端点（根据ENV动态生成）
    REQUEST_URL: str = field(default_factory=lambda: f"{BASE_URL}/dpu-merchant/mock/generate-shop-performance")
    REDIRECT_URL_PREFIX: str = field(default_factory=lambda: f"{BASE_URL}/dpu-merchant/amazon/redirect?offerId=" if ENV in ("uat", "preprod") else f"https://dpu-gateway-{ENV}.dowsure.com/dpu-merchant/amazon/redirect?offerId=")
    AUTH_POST_URL: str = field(default_factory=lambda: f"{BASE_URL}/dpu-merchant/amz/sp/shop/auth")
    LINK_SHOP_API_URL: str = field(default_factory=lambda: f"{BASE_URL}/dpu-merchant/mock/link-sp-3pl-shops")

    # HTTP请求头
    HEADERS: Dict[str, str] = field(default_factory=lambda: {"Content-Type": "application/json"})

    # 业务配置
    TIER_OPTIONS: Dict[str, Tuple[str, int]] = field(default_factory=lambda: {
        '1': ('TIER1', 120000),
        '2': ('TIER2', 950000),
        '3': ('TIER3', 2000000)
    })

    # 文件路径（根据ENV动态生成）
    DATA_FILE_PATH: str = field(default_factory=lambda: rf"C:\Users\PC\Desktop\测试数据.txt")
    SCREENSHOT_FOLDER: str = r"C:\Users\PC\Desktop\截图"

    # Selenium配置
    WAIT_TIMEOUT: int = 30  # 元素等待超时时间（秒）
    ACTION_DELAY: float = 1.5  # 操作间延迟（秒），提高稳定性
    VERIFICATION_CODE: str = "666666"  # 固定验证码
    # 新增：密码设置页配置
    PASSWORD: str = "Aa11111111.."  # 密码
    SECURITY_ANSWER: str = "Aa11111111.."  # 安全问题答案


# 实例化配置
CONFIG = AppConfig()

# 元素定位器 (使用XPATH，增强稳定性)
LOCATORS = {
    "INITIAL_APPLY_BTN": (By.XPATH, "//button[contains(., '立即申请')]"),
    "PHONE_INPUT": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @maxlength='15']"),
    "VERIFICATION_CODE_INPUTS": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @maxlength='1']"),
    # "EMAIL_INPUT": (By.XPATH,
    #                 "//input[contains(@class, 'el-input__inner') and @autocomplete='off' and not(@maxlength)]"),
    # "AGREE_TERMS_CHECKBOX": (By.XPATH, "//span[contains(@class, 'el-checkbox__inner')]"),
    # "REGISTER_BTN": (By.XPATH, "//span[text()='立即注册']"),
    "FINAL_APPLY_BTN": (By.XPATH, "//button[contains(@class, 'application-btn') and .//span[text()='立即申请']]"),
    "NEXT_BTN": (By.XPATH, "//button[contains(., '下一页')]"),
    # 注册页面的下一步按钮定位器 - 使用浏览器开发者工具复制的绝对路径
    "REG_NEXT_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[8]/button"),

    # 新增：密码设置页元素定位器
    "PASSWORD_INPUT": (By.XPATH,
                       "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[1]/div[2]/div/div[1]/div/input"),
    "CONFIRM_PASSWORD_INPUT": (By.XPATH,
                               "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[1]/div[5]/div/div[1]/div/input"),
    "SECURITY_QUESTION_DROPDOWN": (By.XPATH,
                                   "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[2]/div[2]/div/div/div[1]/div[1]/div[2]"),
    "SECURITY_ANSWER_INPUT": (By.XPATH,
                              "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[2]/div[4]/div/div[1]/div/input"),
    "EMAIL_ADDRESS_INPUT": (By.XPATH,
                            "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[3]/div[2]/div/div[1]/div/input"),
    # 声明页面的两个复选框
    "AGREE_CONSENT_CHECKBOX": (By.XPATH,
                               "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[4]/div[1]/div/label/span[1]/span"),
    "AUTHORIZATION_CHECKBOX": (By.XPATH,
                               "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[4]/div[2]/div/label/span[1]/span"),
    "FINAL_REGISTER_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[5]/div[2]/button"),

    # 公司信息页
    "COMPANY_EN_NAME_INPUT": (By.XPATH, "(//input[contains(@class, 'el-input__inner') and @autocomplete='off'])[1]"),
    "BUSINESS_REG_NO_INPUT": (By.XPATH, "(//input[contains(@class, 'el-input__inner') and @autocomplete='off'])[3]"),

    # 董事股东信息页
    "ID_FRONT_UPLOAD_AREA": (By.XPATH,
                             "//div[contains(@class, 'el-upload-dragger') and .//img[contains(@src, 'PRC%20ID-Front')]]"),
    "ID_BACK_UPLOAD_AREA": (By.XPATH,
                            "//div[contains(@class, 'el-upload-dragger') and .//img[contains(@src, 'PRC%20ID-Back')]]"),
    "BIRTH_DATE_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/form/div/div[1]/div[2]/div/div[3]/div[1]/div/div[1]/div/input"),  # 董事信息-出生日期
    "REFERENCE_PHONE_INPUT": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @maxlength='15']"),
    "REFERENCE_EMAIL_INPUT": (By.XPATH,
                              "//input[contains(@class, 'el-input__inner') and @autocomplete='off' and not(@maxlength) and not(@placeholder)]"),

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

    # 融资方案选择页 (TIER2)
    "ACTIVATE_NOW_BTN": (By.XPATH, "//button[span[text()='去激活']]"),
    "APPLY_HIGHER_AMOUNT_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div/div[2]/div[2]/div/div[2]/button"),

    # TIER3额度选择页 (审批成功后)
    "TIER3_ACTIVATE_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[2]/div[1]/div[2]/div[2]/button"),  # 去激活
    "TIER3_SUBMIT_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[2]/div[2]/div[2]/div[2]/button"),  # 去提交

    # TIER3额外信息填写页 (去提交后 - 银行流水)
    "BANK_STATEMENT_UPLOAD_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div/form/div[2]/div[2]/div[1]/div/div"),  # 上传按钮
    "EXTRA_INFO_NEXT_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div/div[4]/div[2]/button[2]"),  # 下一页按钮

    # TIER3股东董事额外信息页 (第二页)
    "CREDIT_REPORT_UPLOAD_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div/form/div/div/div[2]/div/div[1]/div[2]/div[1]/div/div"),  # 个人信用报告上传
    "SINGLE_STATUS_CHECKBOX": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div/form/div/div/div[2]/div/div[3]/div/div/label[2]/span[1]/span"),  # 未婚状态勾选框
    "DIRECTOR_INFO_NEXT_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div/div[4]/div[2]/button[2]"),  # 下一页按钮

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
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


# ==============================================================================
# --- 4. 通用工具函数 (封装重复操作，提高代码复用性) ---
# ==============================================================================

def send_post_request(url: str, phone: Optional[str] = None, payload: Optional[dict] = None) -> bool:
    """
    发送POST请求的通用封装。
    """
    try:
        request_url = f"{url}?phone={phone}" if phone else url
        logging.info(f"[API] 发送POST请求到: {request_url}")
        if phone:
            logging.info(f"[API] 请求手机号: {phone}")

        response = requests.post(
            request_url,
            json=payload,
            headers=CONFIG.HEADERS,
            timeout=15
        )
        logging.info(f"[API] 响应状态码: {response.status_code}")

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
                return True
        else:
            logging.warning(f"⚠️ POST请求HTTP失败 | 状态码: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        logging.error(f"[API] 请求失败: {e}")
        return False


def poll_credit_offer_status(phone: str, authorization_token: str = None, max_attempts: int = 120, interval: int = 5):
    """
    轮询信用报价状态，直到获取到"SUBMITTED"状态。

    Args:
        phone: 手机号
        authorization_token: 授权令牌（可选）
        max_attempts: 最大尝试次数（默认60次）
        interval: 轮询间隔秒数（默认5秒）

    Returns:
        bool: 是否成功获取到SUBMITTED状态
    """
    status_url = f"{BASE_URL}/dpu-merchant/credit-offer/status"

    # 如果没有提供token，使用环境对应的默认token
    if not authorization_token:
        authorization_token = DEFAULT_TOKEN_DICT.get(ENV, "")

    headers = {
        "accept": "application/json, text/plain, */*",
        "authorization": f"Bearer {authorization_token}",
        "funder-resource": "FUNDPARK",
        "origin": f"https://expressfinance-dpu-{ENV}.dowsure.com" if ENV in ("sit", "dev") else f"https://expressfinance-{ENV}.business.hsbc.com",
        "referer": f"https://expressfinance-dpu-{ENV}.dowsure.com/" if ENV in ("sit", "dev") else f"https://expressfinance-{ENV}.business.hsbc.com/",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "x-hsbc-countrycode": "ISO 3166-1 alpha-2"
    }

    logging.info("\n" + "=" * 50)
    logging.info("开始轮询信用报价状态，等待 SUBMITTED 状态...")
    logging.info("=" * 50)

    for attempt in range(1, max_attempts + 1):
        try:
            # 添加phone参数到URL
            params = {"phone": phone}
            response = requests.get(status_url, headers=headers, params=params, timeout=15)

            if response.status_code == 200:
                response_data = response.json()
                # status字段在data对象内部
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

        # 等待指定间隔后继续下一次轮询
        if attempt < max_attempts:
            time.sleep(interval)

    logging.error(f"\n[轮询] 达到最大尝试次数 {max_attempts}，未获取到 SUBMITTED 状态。")
    return False


def poll_drawdown_status(phone: str, authorization_token: str = None, max_attempts: int = 120, interval: int = 5):
    """
    轮询drawdown状态，直到获取到"SUBMITTED"状态。

    Args:
        phone: 手机号
        authorization_token: 授权令牌（可选）
        max_attempts: 最大尝试次数（默认120次）
        interval: 轮询间隔秒数（默认5秒）

    Returns:
        bool: 是否成功获取到SUBMITTED状态
    """
    status_url = f"{BASE_URL}/dpu-merchant/drawdown/status"

    # 如果没有提供token，使用环境对应的默认token
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
            # 添加phone参数到URL
            params = {"phone": phone}
            response = requests.get(status_url, headers=headers, params=params, timeout=15)

            if response.status_code == 200:
                response_data = response.json()
                # status字段在data对象内部
                status = response_data.get("data", {}).get("status", "")

                logging.info(f"[drawdown轮询 #{attempt}/{max_attempts}] 当前状态: {status}")

                if status == "SUBMITTED":
                    drawdown_limit = response_data.get("data", {}).get("drawdownLimit", {})
                    logging.info(f"\n[drawdown轮询] 已获取到目标状态 SUBMITTED！（尝试次数: {attempt}）")
                    logging.info(f"[drawdown轮询] drawdownLimit: {drawdown_limit}")
                    return True
                elif status in ["APPROVED", "REJECTED", "FAILED"]:
                    logging.warning(f"[drawdown轮询] 状态变为 {status}，轮询终止。")
                    return False
            else:
                logging.warning(f"[drawdown轮询 #{attempt}] 响应状态码: {response.status_code}")

        except requests.exceptions.RequestException as e:
            logging.error(f"[drawdown轮询 #{attempt}] 请求失败: {e}")

        # 检查暂停（按空格键暂停/继续）
        _pause_manager.check_pause()

        # 等待指定间隔后继续下一次轮询
        if attempt < max_attempts:
            time.sleep(interval)

    logging.error(f"\n[drawdown轮询] 达到最大尝试次数 {max_attempts}，未获取到 SUBMITTED 状态。")
    return False


# ==============================================================================
# --- 数据库配置与核保/审批请求 ---
# ==============================================================================

def get_local_physical_ip() -> Optional[str]:
    """获取本地物理网卡IP地址（用于绕过VPN直连数据库）"""
    try:
        # 创建UDP socket连接公网地址，获取系统选择的最佳路由IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            # 排除VPN虚拟网卡常见IP段
            if not local_ip.startswith(("10.", "172.16.", "192.168.", "127.")):
                return local_ip
            # 尝试通过主机名解析
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            if not local_ip.startswith(("10.", "172.16.", "192.168.", "127.")):
                return local_ip
    except Exception:
        pass
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
    RECONNECT_DELAY = 2  # 秒

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
            # 测试连接是否有效
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
                # 连接错误代码：2006=MySQL server has gone away, 2013=Lost connection
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


def generate_uuid() -> str:
    """生成UUID"""
    return str(uuid.uuid4())


def get_utc_time() -> str:
    """获取UTC时间"""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def get_local_time_str() -> str:
    """获取本地时间字符串"""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def send_underwritten_request(phone: str, amount: str = None) -> bool:
    """
    发送核保完成请求 (underwrittenLimit.completed)

    Args:
        phone: 手机号
        amount: 核保额度（默认从环境配置读取）

    Returns:
        bool: 请求是否成功
    """
    if amount is None:
        amount = get_current_flow_amount_config()["underwritten_amount"]
    webhook_url = f"{BASE_URL}/dpu-openapi/webhook-notifications"

    try:
        # 从数据库获取必要信息
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

        preferred_currency = resolve_preferred_currency(db, merchant_id)

        if not all([merchant_id, dpu_limit_application_id]):
            logging.error("❌ 数据库查询失败，缺少必要信息")
            return False

        request_body = {
            "data": {
                "eventType": "underwrittenLimit.completed",
                "eventId": generate_uuid(),
                "eventMessage": "核保完成通知",
                "enquiryUrl": "https://api.example.com/enquiry/123",
                "datetime": get_utc_time(),
                "details": {
                    "merchantId": merchant_id,
                    "dpuMerchantAccountId": [{"MerchantAccountId": dpu_auth_token_seller_id}] if dpu_auth_token_seller_id else [],
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
    """
    发送审批完成请求 (approvedoffer.completed)

    Args:
        phone: 手机号
        amount: 审批额度（默认从环境配置读取）

    Returns:
        bool: 请求是否成功
    """
    if amount is None:
        amount = get_current_flow_amount_config()["approved_amount"]
    webhook_url = f"{BASE_URL}/dpu-openapi/webhook-notifications"

    try:
        # 从数据库获取必要信息
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

        preferred_currency = resolve_preferred_currency(db, merchant_id)

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
    """
    发送PSP验证开始请求 (psp.verification.started)

    Args:
        phone: 手机号

    Returns:
        bool: 请求是否成功
    """
    webhook_url = f"{BASE_URL}/dpu-openapi/webhook-notifications"

    try:
        # 从数据库获取必要信息
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
    """
    发送PSP验证完成请求 (psp.verification.completed)

    Args:
        phone: 手机号

    Returns:
        bool: 请求是否成功
    """
    webhook_url = f"{BASE_URL}/dpu-openapi/webhook-notifications"

    try:
        # 从数据库获取必要信息
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
    """
    发送电子签完成请求 (esign.completed)

    Args:
        phone: 手机号
        amount: 电子签额度（默认从环境配置读取）

    Returns:
        bool: 请求是否成功
    """
    if amount is None:
        amount = get_current_flow_amount_config()["esign_amount"]
    webhook_url = f"{BASE_URL}/dpu-openapi/webhook-notifications"

    try:
        # 从数据库获取必要信息
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

        preferred_currency = resolve_preferred_currency(db, merchant_id)

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


def send_disbursement_completed_request(phone: str, amount: float = 2000.00) -> bool:
    """
    发送放款完成请求 (disbursement.completed)

    Args:
        phone: 手机号
        amount: 放款金额（默认2000.00）

    Returns:
        bool: 请求是否成功
    """
    webhook_url = f"{BASE_URL}/dpu-openapi/webhook-notifications"

    try:
        # 从数据库获取必要信息
        db = get_global_db()

        merchant_id = db.execute_sql(
            f"SELECT merchant_id FROM dpu_users WHERE phone_number = '{phone}' ORDER BY created_at DESC LIMIT 1;"
        )
        application_unique_id = db.execute_sql(
            f"SELECT application_unique_id FROM dpu_application WHERE merchant_id = '{merchant_id}' ORDER BY created_at DESC LIMIT 1;"
        )
        # 查询loan_id（需要从dpu_drawdown表获取）
        loan_id = db.execute_sql(
            f"SELECT loan_id FROM dpu_drawdown WHERE merchant_id = '{merchant_id}' ORDER BY created_at DESC LIMIT 1;"
        )

        if not all([merchant_id, application_unique_id, loan_id]):
            logging.error("❌ 数据库查询失败，缺少必要信息（merchant_id/application_unique_id/loan_id）")
            return False

        preferred_currency = resolve_preferred_currency(db, merchant_id)

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
                        "rate": {"chargeBases": "Float", "baseRateType": "SOFR", "baseRate": "6.00",
                                 "marginRate": "0.00"},
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
            logging.info(f"✅ 放款(disbursement.completed)请求成功 - 响应: {response.text[:100]}...")
            return True
        else:
            logging.error(f"❌ 放款请求失败 | 状态码: {response.status_code}")
            logging.error(f"📋 完整响应内容:\n{response.text}")
            return False

    except Exception as e:
        logging.error(f"❌ 放款请求异常: {e}")
        return False


def safe_click(driver: webdriver.Remote, locator_key: str, action_description: str, fallback_locators: list = None):
    """
    安全地点击一个元素，支持备选定位器。
    """
    # 注册页面的备选定位器列表
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

    # 如果是注册页面下一步按钮，使用备选定位器
    if locator_key == "REG_NEXT_BTN":
        fallback_locators = reg_next_fallbacks

    try:
        locator = LOCATORS.get(locator_key)
        if not locator and not fallback_locators:
            raise ValueError(f"定位器 '{locator_key}' 未在 LOCATORS 中定义且未提供备选定位器")

        # 尝试主定位器
        element = None
        if locator:
            try:
                element = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(EC.element_to_be_clickable(locator))
                logging.info(f"[UI] 使用主定位器找到元素: {action_description}")
            except Exception:
                logging.warning(f"[UI] 主定位器未找到元素 '{action_description}'，尝试备选定位器...")

        # 如果主定位器失败，尝试备选定位器
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

        # 滚动到元素可见
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        time.sleep(CONFIG.ACTION_DELAY)

        # 尝试点击
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
    """
    安全地向输入框输入文本。
    """
    try:
        locator = LOCATORS[locator_key]
        element = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(EC.visibility_of_element_located(locator))
        element.clear()
        element.send_keys(text)
        logging.info(f"[UI] 已在 '{field_description}' 中输入: {text}")
    except Exception as e:
        logging.error(f"[UI] 向 '{field_description}' 输入时发生错误: {e}")
        raise


def select_specific_security_question(driver: webdriver.Remote):
    """
    使用线下自动化相同的定位器与选择方式，展开后选择第一个安全问题选项
    """
    try:
        safe_click(driver, "SECURITY_QUESTION_DROPDOWN", "安全问题下拉框")
        time.sleep(CONFIG.ACTION_DELAY)

        first_option = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(
            EC.element_to_be_clickable((By.XPATH, "//li[contains(@class, 'el-select-dropdown__item')][1]"))
        )
        selected_text = first_option.text.strip()
        first_option.click()
        logging.info(f"[UI] 已选择安全问题: {selected_text}")

        return selected_text
    except Exception as e:
        logging.error(f"[UI] 选择安全问题选项时发生错误: {e}")
        raise


# ==============================================================================
# --- 4. 数据生成函数 ---
# ==============================================================================
def get_user_choice(options: Dict[str, str], prompt: str) -> str:
    """
    通用函数，用于获取用户的有效选择。
    """
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


def generate_test_data() -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    第一步：生成测试数据（固定TIER3）。

    Returns:
        Tuple[url, phone, tier_name, offer_id]
    """
    logging.info("=" * 50)
    logging.info("步骤 1/8: 生成测试数据 (固定TIER3)")
    logging.info("=" * 50)

    # 固定选择TIER3
    tier_name = "TIER3"
    amount = 2000000
    logging.info(f"已固定选择: {tier_name} (金额: {amount})")

    try:
        logging.info(f"正在为TIER '{tier_name}' (金额: {amount}) 生成数据...")
        response = requests.post(
            CONFIG.REQUEST_URL,
            json={"yearlyRepaymentAmount": amount},
            headers=CONFIG.HEADERS,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        offer_id = data.get("amazon3plOfferId") or data.get("data", {}).get("amazon3plOfferId")
        if not offer_id:
            raise ValueError("从API响应中未找到有效的 'amazon3plOfferId'。")
        phone = f"182{random.randint(10000000, 99999999)}"
        url = f"{CONFIG.REDIRECT_URL_PREFIX}{offer_id}"
        # 使用mock_uat格式的写入方式：环境+TIER类型, 手机号, URL
        with open(CONFIG.DATA_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n{ENV.upper()} {tier_name}\n{phone}\n{url}\n")
        logging.info(f"数据生成成功: TIER={tier_name}, Phone={phone}, URL={url}, OfferID={offer_id}")
        return url, phone, tier_name, offer_id
    except Exception as e:
        logging.error(f"生成测试数据失败: {e}")
        return None, None, None, None


# ==============================================================================
# --- 5. 页面处理函数 (封装每个页面的具体操作) ---
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
    logging.info("Step 3/8: fill initial registration info")
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
    for i, char in enumerate(verification_code):
        if i < len(code_inputs):
            code_inputs[i].send_keys(char)
    time.sleep(CONFIG.ACTION_DELAY)
    safe_click(driver, "REG_NEXT_BTN", "registration next button")
    time.sleep(CONFIG.ACTION_DELAY * 3)
    return handle_password_setup(driver, phone)
    """第三步：处理初始注册信息页面，返回从浏览器获取的token"""
    logging.info("\n" + "=" * 50)
    logging.info("步骤 3/8: 填写初始注册信息")
    logging.info("=" * 50)
    safe_send_keys(driver, "PHONE_INPUT", phone, "手机号")
    logging.info(f"[UI] 正在输入验证码: {CONFIG.VERIFICATION_CODE}")
    code_inputs = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(
        EC.visibility_of_all_elements_located(LOCATORS["VERIFICATION_CODE_INPUTS"])
    )
    for i, char in enumerate(CONFIG.VERIFICATION_CODE):
        if i < len(code_inputs):
            code_inputs[i].send_keys(char)
    time.sleep(CONFIG.ACTION_DELAY)
    # email = f"{phone}@qq.com"
    # safe_send_keys(driver, "EMAIL_INPUT", email, "邮箱")
    # safe_click(driver, "AGREE_TERMS_CHECKBOX", "同意服务条款")
    # safe_click(driver, "REGISTER_BTN", "立即注册按钮")
    # 新增：点击注册页面的下一步按钮
    safe_click(driver, "REG_NEXT_BTN", "注册页面下一步按钮")
    time.sleep(CONFIG.ACTION_DELAY * 3)

    # 新增：处理密码设置页，并获取token
    auth_token = handle_password_setup(driver, phone)
    return auth_token


def handle_password_setup(driver: webdriver.Remote, phone: str) -> Optional[str]:
    """处理密码设置页面，并从浏览器获取token"""
    logging.info("\n" + "=" * 50)
    logging.info("步骤 3.5/8: 处理密码设置页面")
    logging.info("=" * 50)

    # 1. 输入密码
    safe_send_keys(driver, "PASSWORD_INPUT", CONFIG.PASSWORD, "新密码")
    time.sleep(CONFIG.ACTION_DELAY)

    # 2. 输入确认密码
    safe_send_keys(driver, "CONFIRM_PASSWORD_INPUT", CONFIG.PASSWORD, "确认新密码")
    time.sleep(CONFIG.ACTION_DELAY)

    # 3. 选择指定的安全问题（替换原来的随机选择）
    select_specific_security_question(driver)
    time.sleep(CONFIG.ACTION_DELAY)

    # 4. 输入安全问题答案
    safe_send_keys(driver, "SECURITY_ANSWER_INPUT", CONFIG.SECURITY_ANSWER, "安全问题答案")
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

    # 8. 点击最终注册按钮
    safe_click(driver, "FINAL_REGISTER_BTN", "注册按钮")
    time.sleep(CONFIG.ACTION_DELAY * 3)

    # 8. 从浏览器获取token
    auth_token = get_token_from_browser(driver)
    return auth_token


def get_token_from_browser(driver: webdriver.Remote) -> Optional[str]:
    """
    从浏览器存储中获取授权token (localStorage/sessionStorage/cookies)

    Args:
        driver: WebDriver实例

    Returns:
        Optional[str]: 授权token，失败返回None
    """
    global _global_currency

    logging.info("[Browser] 正在从浏览器存储中获取token和currency...")

    if not has_valid_global_currency():
        enable_network_currency_capture(driver)
        currency_from_logs = extract_currency_from_network_logs(driver)
        if currency_from_logs:
            _global_currency = currency_from_logs
            logging.info(f"✅ 从请求头提取currency: {_global_currency}")
        else:
            logging.info("[Browser] 本轮未从网络请求头提取到currency，继续尝试浏览器存储")

    # 扩展的token键名列表（包含更多可能的后端变量命名）
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
        if not has_valid_global_currency():
            update_global_currency_from_mapping(local_storage, "localStorage")
        for key, value in local_storage.items():
            logging.info(f"  - {key}: {value[:50] if len(value) > 50 else value}...")

        for key in token_keys:
            if key in local_storage and local_storage[key]:
                token_value = local_storage[key]
                # 检查是否是JSON格式的token（如 {"token":"xxx"}）
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
        if not has_valid_global_currency():
            update_global_currency_from_mapping(session_storage, "sessionStorage")
        for key, value in session_storage.items():
            logging.info(f"  - {key}: {value[:50] if len(value) > 50 else value}...")

        for key in token_keys:
            if key in session_storage and session_storage[key]:
                token_value = session_storage[key]
                # 检查是否是JSON格式的token（如 {"token":"xxx"}）
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

    # 3. 尝试从 cookies 获取
    try:
        cookies = driver.get_cookies()
        logging.info(f"[Browser] cookies数量: {len(cookies)}")
        for cookie in cookies:
            logging.info(f"  - {cookie['name']}: {cookie['value'][:30] if cookie['value'] else '(empty)'}...")

        for cookie in cookies:
            cookie_name = cookie['name'].lower()
            if any(key.lower() in cookie_name for key in token_keys):
                token_value = cookie.get('value')
                if token_value:
                    logging.info(f"✅ 成功从cookies获取token (键: {cookie['name']}): {token_value[:30]}...")
                    return token_value
    except Exception as e:
        logging.warning(f"[Browser] 从cookies获取token失败: {e}")

    logging.error("❌ 未能从浏览器存储中获取到token")
    return None


def handle_company_info(driver: webdriver.Remote, auto_fill: bool):
    """第五步：处理公司信息页面。"""
    logging.info("\n" + "=" * 50)
    logging.info("步骤 5/8: 处理公司信息")
    logging.info("=" * 50)
    if auto_fill:
        logging.info("[流程] 选择自动填写公司信息...")
        safe_send_keys(driver, "COMPANY_EN_NAME_INPUT", "123", "公司英文名称")
        time.sleep(CONFIG.ACTION_DELAY)
        safe_send_keys(driver, "BUSINESS_REG_NO_INPUT", "00000001", "商业登记号码")
    else:
        input("[流程] 请手动填写公司信息，完成后按Enter键继续...")
    safe_click(driver, "NEXT_BTN", "公司信息页下一步")


def handle_director_info(driver: webdriver.Remote, phone: str, auto_fill: bool):
    """第六步：处理董事股东信息页面。"""
    logging.info("\n" + "=" * 50)
    logging.info("步骤 6/8: 处理董事股东信息")
    logging.info("=" * 50)
    if auto_fill:
        logging.info("[流程] 选择自动填写董事股东信息...")
        # 上传身份证正面
        id_front_path = os.path.join(CONFIG.SCREENSHOT_FOLDER, "身份证正面.png")
        upload_image(driver, id_front_path, "身份证正面")
        time.sleep(CONFIG.ACTION_DELAY * 3)
        # 上传身份证反面
        id_back_path = os.path.join(CONFIG.SCREENSHOT_FOLDER, "身份证反面.png")
        upload_image(driver, id_back_path, "身份证反面")
        time.sleep(CONFIG.ACTION_DELAY * 3)
        safe_send_keys(driver, "BIRTH_DATE_INPUT", "30/12/2025", "出生日期")
        safe_send_keys(driver, "REFERENCE_PHONE_INPUT", phone, "参考手机号")
        safe_send_keys(driver, "REFERENCE_EMAIL_INPUT", f"{phone}@qq.com", "参考邮箱")
    else:
        input("[流程] 请手动填写董事股东信息并上传身份证，完成后按Enter键继续...")
    safe_click(driver, "NEXT_BTN", "董事股东信息页下一步")


def handle_bank_account_info(driver: webdriver.Remote, auto_fill: bool):
    """第七步：处理银行账户信息页面。"""
    logging.info("\n" + "=" * 50)
    logging.info("步骤 7/8: 处理银行账户信息")
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
        input("[流程] 请手动选择银行并填写账户信息，完成后按Enter键继续...")
    safe_click(driver, "NEXT_BTN", "银行信息页下一步")


def handle_financing_choice(driver: webdriver.Remote) -> bool:
    """处理融资方案选择页面 (仅TIER2)。"""
    import time as time_module
    start_time = time_module.time()

    logging.info("\n" + "=" * 50)
    logging.info("步骤 7/8: 处理融资方案选择 (TIER2)")
    logging.info("=" * 50)

    # 等待融资方案选择页面加载（减少超时时间到10秒）
    logging.info("[UI] 等待融资方案选择页面加载...")
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located(LOCATORS["ACTIVATE_NOW_BTN"]))
        elapsed = time_module.time() - start_time
        logging.info(f"[UI] 融资方案选择页面已加载，耗时: {elapsed:.2f}秒")
    except Exception as e:
        logging.warning(f"[UI] 等待融资方案选择页面超时，尝试继续: {e}")

    options = {'1': '去激活 (需填写银行账户信息)', '2': '去解锁 (跳过银行账户信息)'}
    choice = get_user_choice(options, "请选择融资方案:")
    if choice == '1':
        safe_click(driver, "ACTIVATE_NOW_BTN", "去激活按钮")
        total_elapsed = time_module.time() - start_time
        logging.info(f"[UI] 融资方案选择完成，总耗时: {total_elapsed:.2f}秒")
        return True
    else:
        safe_click(driver, "APPLY_HIGHER_AMOUNT_BTN", "申请更高额度按钮")
        total_elapsed = time_module.time() - start_time
        logging.info(f"[UI] 融资方案选择完成，总耗时: {total_elapsed:.2f}秒")
        return False


def handle_tier3_credit_choice(driver: webdriver.Remote) -> str:
    """
    处理TIER3审批成功后的额度选择页面

    Returns:
        'activate' - 选择"去激活"，走完整流程（激活额度→PSP→电子签）
        'submit' - 选择"去提交"，进入额外信息填写页面
    """
    import time as time_module
    start_time = time_module.time()

    logging.info("\n" + "=" * 50)
    logging.info("步骤: TIER3额度选择")
    logging.info("=" * 50)

    # 等待额度选择页面加载
    logging.info("[UI] 等待额度选择页面加载...")
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located(LOCATORS["TIER3_ACTIVATE_BTN"]))
        elapsed = time_module.time() - start_time
        logging.info(f"[UI] 额度选择页面已加载，耗时: {elapsed:.2f}秒")
    except Exception as e:
        logging.warning(f"[UI] 等待额度选择页面超时，尝试继续: {e}")

    options = {'1': '去激活 (完整流程: 激活额度→PSP→电子签)', '2': '去提交 (额外信息填写页面)'}
    choice = get_user_choice(options, "请选择TIER3额度方案:")

    if choice == '1':
        safe_click(driver, "TIER3_ACTIVATE_BTN", "去激活按钮")
        total_elapsed = time_module.time() - start_time
        logging.info(f"[UI] 已选择：去激活，总耗时: {total_elapsed:.2f}秒")
        return 'activate'
    else:
        safe_click(driver, "TIER3_SUBMIT_BTN", "去提交按钮")
        total_elapsed = time_module.time() - start_time
        logging.info(f"[UI] 已选择：去提交，总耗时: {total_elapsed:.2f}秒")
        return 'submit'


def upload_image(driver: webdriver.Remote, image_path: str, description: str):
    """
    上传图片（使用成功的upload_image逻辑）

    Args:
        driver: WebDriver实例
        image_path: 图片文件的绝对路径
        description: 描述信息（用于日志）
    """
    import os as os_module
    import time as time_module

    # 转换为绝对路径
    abs_image_path = os_module.path.abspath(image_path)

    # 确保文件存在
    if not os_module.path.exists(image_path):
        raise FileNotFoundError(f"图片文件不存在: {image_path}")

    target_file = os_module.path.basename(image_path)
    logging.info(f"[UI] 正在上传图片 '{target_file}' 用于: {description}")

    # JavaScript上传函数
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

        // 设置文件路径
        try {{
            targetInput.value = '{abs_image_path.replace(os_module.sep, '/')}';

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

    # 执行JavaScript上传
    upload_result = driver.execute_script(upload_js)

    if not upload_result or not upload_result.get('success'):
        # JavaScript方式失败，尝试使用Selenium方式
        logging.warning(f"[UI] JavaScript上传失败，尝试使用Selenium方式")

        from selenium.webdriver.common.by import By
        file_input = None

        try:
            file_input = WebDriverWait(driver, 10).until(
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

    # 等待上传处理完成
    time_module.sleep(2)


def handle_extra_info_page(driver: webdriver.Remote, phone: str):
    """
    处理TIER3额外信息填写页面（去提交后）

    功能：上传银行流水图片并点击下一页

    Args:
        driver: WebDriver实例
        phone: 手机号，用于后续API请求
    """
    import time as time_module
    import glob
    import os as os_module

    start_time = time_module.time()

    logging.info("\n" + "=" * 50)
    logging.info("步骤: 额外信息填写 - 银行流水上传")
    logging.info("=" * 50)

    # 等待额外信息页面加载
    logging.info("[UI] 等待额外信息页面加载...")
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located(LOCATORS["BANK_STATEMENT_UPLOAD_BTN"]))
        elapsed = time_module.time() - start_time
        logging.info(f"[UI] 额外信息页面已加载，耗时: {elapsed:.2f}秒")
    except Exception as e:
        logging.warning(f"[UI] 等待额外信息页面超时，尝试继续: {e}")

    # 选择填写方式
    options = {'1': '自动填写（上传银行流水）', '2': '手动填写'}
    choice = get_user_choice(options, "请选择填写方式:")

    if choice == '1':
        logging.info("[流程] 选择自动填写...")

        # 银行流水图片文件夹路径
        screenshot_folder = r"C:\Users\PC\Desktop\截图"

        # 优先查找包含"银行流水"的文件，否则查找任意图片
        image_extensions = ['*.png', '*.jpg', '*.jpeg', '*.bmp']
        image_files = []
        for ext in image_extensions:
            image_files.extend(glob.glob(os_module.path.join(screenshot_folder, ext)))

        # 优先选择文件名包含"银行流水"的文件
        bank_statement_file = None
        for file in image_files:
            if '银行流水' in os_module.path.basename(file):
                bank_statement_file = file
                break

        # 如果没找到包含"银行流水"的文件，使用第一个找到的文件
        if bank_statement_file:
            image_path = bank_statement_file
            logging.info(f"[UI] 找到银行流水图片: {os_module.path.basename(image_path)}")
        elif image_files:
            image_path = image_files[0]
            logging.info(f"[UI] 未找到包含'银行流水'的文件，使用: {os_module.path.basename(image_path)}")
        else:
            logging.error(f"❌ 在文件夹 {screenshot_folder} 中未找到图片！")
            logging.info("[流程] 请手动选择图片上传")
            input("上传完成后按Enter继续...")
            return  # 结束函数执行

        try:
            # 使用upload_image函数上传
            upload_image(driver, image_path, "银行流水")

        except Exception as e:
            logging.error(f"❌ 自动填写失败: {e}")
            logging.info("[流程] 请手动完成上传和点击下一页")
            input("上传完成后按Enter继续...")

        # 点击下一页按钮
        logging.info("[UI] 点击下一页按钮...")
        safe_click(driver, "EXTRA_INFO_NEXT_BTN", "下一页按钮")

        total_elapsed = time_module.time() - start_time
        logging.info(f"✅ 银行流水上传完成，总耗时: {total_elapsed:.2f}秒")

        # 进入股东董事额外信息页面
        time_module.sleep(2)
        handle_director_extra_info_page(driver, phone)

    else:
        logging.info("[流程] 选择手动填写...")
        input("填写完成后按Enter继续...")


def handle_director_extra_info_page(driver: webdriver.Remote, phone: str):
    """
    处理TIER3股东董事额外信息页面（第二页）

    功能：上传个人信用报告、勾选未婚状态、点击下一页、第二次审批、激活额度、PSP、电子签

    Args:
        driver: WebDriver实例
        phone: 手机号，用于后续API请求
    """
    import time as time_module
    import glob
    import os as os_module

    start_time = time_module.time()

    logging.info("\n" + "=" * 50)
    logging.info("步骤: 股东董事额外信息 - 个人信用报告上传")
    logging.info("=" * 50)

    # 等待页面加载
    logging.info("[UI] 等待股东董事额外信息页面加载...")
    time_module.sleep(2)

    # 选择填写方式
    options = {'1': '自动输入（上传信用报告+勾选未婚）', '2': '手动输入'}
    choice = get_user_choice(options, "请选择填写方式:")

    if choice == '1':
        logging.info("[流程] 选择自动输入...")

        # 个人信用报告图片文件夹路径
        screenshot_folder = r"C:\Users\PC\Desktop\截图"

        # 查找个人信用报告图片
        image_extensions = ['*.png', '*.jpg', '*.jpeg', '*.bmp']
        image_files = []
        for ext in image_extensions:
            image_files.extend(glob.glob(os_module.path.join(screenshot_folder, ext)))

        # 优先选择文件名包含"个人信用报告"的文件
        credit_report_file = None
        for file in image_files:
            if '个人信用报告' in os_module.path.basename(file):
                credit_report_file = file
                break

        # 如果没找到包含"个人信用报告"的文件，使用第一个找到的文件
        if credit_report_file:
            image_path = credit_report_file
            logging.info(f"[UI] 找到个人信用报告图片: {os_module.path.basename(image_path)}")
        elif image_files:
            image_path = image_files[0]
            logging.info(f"[UI] 未找到包含'个人信用报告'的文件，使用: {os_module.path.basename(image_path)}")
        else:
            logging.error(f"❌ 在文件夹 {screenshot_folder} 中未找到图片！")
            logging.info("[流程] 请手动选择图片上传")
            input("上传完成后按Enter继续...")
            return  # 结束函数执行

        try:
            # 使用upload_image函数上传个人信用报告
            upload_image(driver, image_path, "个人信用报告")

            # 2. 勾选未婚状态
            logging.info("[UI] 勾选未婚状态...")
            try:
                checkbox = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(LOCATORS["SINGLE_STATUS_CHECKBOX"])
                )
                # 检查是否已勾选
                if not checkbox.is_selected():
                    checkbox.click()
                    logging.info("✅ 已勾选未婚状态")
                else:
                    logging.info("ℹ️  未婚状态已勾选")
            except Exception as e:
                logging.warning(f"⚠️ 勾选未婚状态失败: {e}，尝试JavaScript方式...")
                # 尝试JavaScript方式
                checkbox_js = """
                (function() {
                    var checkbox = document.querySelector("label[class*='el-radio'] span[class*='el-radio__input']");
                    if (checkbox) {
                        checkbox.click();
                        return {success: true};
                    }
                    return {success: false};
                })();
                """
                result = driver.execute_script(checkbox_js)
                if result and result.get('success'):
                    logging.info("✅ 已通过JavaScript勾选未婚状态")

            time_module.sleep(1)

            # 3. 点击下一页按钮
            logging.info("[UI] 点击下一页按钮...")
            safe_click(driver, "DIRECTOR_INFO_NEXT_BTN", "下一页按钮")

            total_elapsed = time_module.time() - start_time
            logging.info(f"✅ 股东董事额外信息填写完成，总耗时: {total_elapsed:.2f}秒")

            # 4. 发送第二次审批请求
            logging.info("\n" + "=" * 50)
            logging.info("步骤: 第二次审批请求")
            logging.info("=" * 50)

            second_amount = get_current_flow_amount_config()["approved_amount_2nd"]
            logging.info(f"[API] 发送第二次审批请求（金额: {second_amount}）...")

            time_module.sleep(3)
            if send_approved_request(phone, amount=second_amount):
                logging.info(f"✅ 第二次审批请求成功（金额: {second_amount}）！")

                # 5. 点击激活额度按钮
                time_module.sleep(5)
                logging.info("\n[UI] 点击激活额度按钮...")
                safe_click(driver, "ACTIVATE_CREDIT_BTN", "激活额度按钮")
                logging.info("✅ 已点击激活额度按钮")

                # 6. 点击接受按钮
                time_module.sleep(5)
                safe_click(driver, "ACCEPT_BTN", "接受按钮")
                logging.info("✅ 已点击接受按钮")

                # 7. PSP开始请求
                time_module.sleep(5)
                logging.info("\n[1/3] 发送PSP验证开始请求...")
                if send_psp_start_request(phone):
                    logging.info("✅ PSP开始请求成功！")
                else:
                    logging.error("❌ PSP开始请求失败！")

                # 8. PSP完成请求
                time_module.sleep(5)
                logging.info("\n[2/3] 发送PSP验证完成请求...")
                if send_psp_completed_request(phone):
                    logging.info("✅ PSP完成请求成功！")
                else:
                    logging.error("❌ PSP完成请求失败！")

                # 9. 电子签请求
                time_module.sleep(5)
                logging.info("\n[3/3] 发送电子签完成请求...")
                if send_esign_request(phone):
                    logging.info("✅ 电子签请求成功！")

                    logging.info("\n" + "=" * 50)
                    logging.info("🎉 TIER3去提交流程已完成！")
                    logging.info("=" * 50)

                else:
                    logging.error("❌ 电子签请求失败！")

            else:
                logging.error("❌ 第二次审批请求失败！")

        except Exception as e:
            logging.error(f"❌ 自动填写失败: {e}")
            logging.info("[流程] 请手动完成上传、勾选和点击下一页")
            input("完成后按Enter继续...")

    else:
        logging.info("[流程] 选择手动输入...")
        input("填写完成后按Enter继续...")


# ==============================================================================
# --- 6. 全局数据库连接（单例模式）---
# ==============================================================================
_global_db: Optional[DatabaseExecutor] = None
_global_currency: Optional[str] = None  # 全局存储注册流程中识别到的融资产品货币

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
    """判断当前全局货币是否有效。"""
    return _global_currency in SUPPORTED_CURRENCIES


def get_current_flow_amount_config(currency: Optional[str] = None) -> Dict[str, Any]:
    """根据当前currency返回TIER3流程金额配置，默认回退到USD。"""
    normalized_currency = normalize_currency_value(currency or _global_currency) or "USD"
    return FLOW_AMOUNT_CONFIG.get(normalized_currency, FLOW_AMOUNT_CONFIG["USD"])


def normalize_currency_value(value: Any) -> Optional[str]:
    """把不同来源的currency值归一化为标准货币代码。"""
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
    """从headers/storage映射里提取currency，返回命中的键和值。"""
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
    """尝试从映射中提取并更新全局currency。"""
    global _global_currency

    found_currency = extract_currency_from_mapping(mapping)
    if not found_currency:
        return False

    matched_key, currency = found_currency
    _global_currency = currency
    logging.info(f"✅ 从{source_name}提取currency (键: {matched_key}): {_global_currency}")
    return True


def enable_network_currency_capture(driver: webdriver.Remote) -> bool:
    """尽早开启Chromium网络监听，避免错过注册阶段请求头。"""
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        logging.debug("[Browser] 已启用CDP Network监听")
        return True
    except Exception as e:
        logging.debug(f"[Browser] 无法启用CDP Network监听: {e}")
        return False


def resolve_preferred_currency(db: DatabaseExecutor, merchant_id: Optional[str]) -> str:
    """优先使用浏览器抓到的currency，缺失时回退数据库。"""
    global _global_currency

    if has_valid_global_currency():
        return _global_currency or "USD"

    if not merchant_id:
        return "USD"

    preferred_currency = normalize_currency_value(
        db.execute_sql(
            f"SELECT prefer_finance_product_currency FROM dpu_users WHERE merchant_id = '{merchant_id}' LIMIT 1;"
        )
    )
    if preferred_currency:
        _global_currency = preferred_currency
        logging.info(f"✅ 从数据库回退获取currency: {_global_currency}")
        return preferred_currency

    return "USD"


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


def open_url_in_new_window(driver: webdriver.Remote, url: str, page_name: str) -> bool:
    """通过浏览器新窗口访问URL，并保持当前窗口上下文不变。"""
    try:
        current_handle = driver.current_window_handle
        previous_window_count = len(driver.window_handles)
        driver.execute_script("window.open(arguments[0], '_blank');", url)
        WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(
            lambda d: len(d.window_handles) > previous_window_count
        )
        driver.switch_to.window(current_handle)
        time.sleep(CONFIG.ACTION_DELAY)
        logging.info(f"✅ {page_name}已在新窗口中打开")
        return True
    except Exception as e:
        logging.warning(f"⚠️ {page_name}打开异常: {e}")
        return False


# ==============================================================================
# --- 7. 浏览器初始化函数 (优化版) ---
# ==============================================================================
from selenium.webdriver.chrome.service import Service as ChromeService  # 确保已导入


# def _kill_processes(process_name: str):
#     """尝试强制关闭指定名称的所有进程。"""
#     if not process_name:
#         return
#     try:
#         subprocess.run(f'taskkill /F /IM {process_name}', check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
#                        shell=True)
#         logging.info(f"[Browser] 已强制关闭所有 '{process_name}' 进程。")
#     except Exception as e:
#         logging.debug(f"[Browser] 尝试关闭 '{process_name}' 时发生异常 (通常是进程未运行): {e}")


def init_browser(browser_name: str) -> webdriver.Remote:
    """
    根据浏览器名称初始化并返回一个浏览器驱动实例（均为无痕模式）。
    """
    browser_name = browser_name.upper()
    if browser_name not in BROWSER_CONFIG:
        raise ValueError(f"不支持的浏览器: {browser_name}")

    config = BROWSER_CONFIG[browser_name]
    logging.info(f"[Browser] 正在初始化 {browser_name} 浏览器 (无痕模式)...")

    # 1. 清理残留进程
    # _kill_processes(config["process_name"])

    # 2. 根据浏览器类型配置并创建Driver
    if browser_name in ["CHROME", "QQ", "360", "EDGE"]:
        options = ChromeOptions() if browser_name != "EDGE" else EdgeOptions()
        options.add_argument("--incognito")  # Chrome/QQ/360
        if browser_name == "EDGE":
            options.add_argument("--inprivate")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        if browser_name == "EDGE":
            options.set_capability("ms:loggingPrefs", {"performance": "ALL"})

        if config["binary_path"] and os.path.exists(config["binary_path"]):
            options.binary_location = config["binary_path"]
            logging.info(f"[Browser] 使用指定的浏览器路径: {config['binary_path']}")
        elif config["binary_path"]:
            logging.warning(f"[Browser] 配置的浏览器路径不存在: {config['binary_path']}，将尝试使用默认路径。")

        # --- 为QQ浏览器指定特定的ChromeDriver (支持Chrome 123) ---
        if browser_name == "QQ":
            # QQ浏览器使用Chrome 123内核，直接使用ChromeDriver 123
            qq_driver_path = r"C:\WebDrivers\chromedriver_123.exe"
            #if not os.path.exists(qq_driver_path):
                # 备选路径
                #qq_driver_path = r"C:\WebDrivers\chromedriver_132.exe"
            if not os.path.exists(qq_driver_path):
                # 再次备选
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

        # --- 为360浏览器指定特定的ChromeDriver (支持Chrome 132) ---
        if browser_name == "360":
            # ChromeDriver 132 支持路径
            se_driver_path = r"C:\WebDrivers\chromedriver_132.exe"
            #if not os.path.exists(se_driver_path):
                # 备选路径
                #se_driver_path = r"C:\WebDrivers\chromedriver_123.exe"
            if not os.path.exists(se_driver_path):
                # 再次备选
                se_driver_path = r"C:\WebDrivers\chromedriver_360.exe"
            if not os.path.exists(se_driver_path):
                raise FileNotFoundError(
                    f"[Browser] ChromeDriver 不存在！\n"
                    f"请从 https://googlechromelabs.github.io/chrome-for-testing/ 下载 ChromeDriver 132\n"
                    f"并将其放置到: C:\\WebDrivers\\chromedriver_132.exe"
                )
            # 360浏览器需要额外的启动参数
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
    """从浏览器性能日志中提取请求头中的currency。"""
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
                elif method == "Network.requestWillBeSentExtraInfo":
                    headers = params.get("headers", {})
                else:
                    continue

                found_currency = extract_currency_from_mapping(headers)
                if found_currency:
                    matched_key, currency = found_currency
                    logging.info(f"✅ 从网络日志提取currency: {currency} | method={method} | key={matched_key}")
                    return currency
            except Exception:
                continue

        if attempt < 3:
            time.sleep(1)

    return None


# ==============================================================================
# --- 7. 主自动化流程 ---
# ==============================================================================
def run_automation(url: str, phone: str, tier_name: str):
    """自动化注册流程的主控制器。"""
    driver = None
    try:
        # --- 步骤 2: 初始化浏览器 (优化后的选择逻辑) ---
        logging.info("\n" + "=" * 50)
        logging.info("步骤 2/8: 初始化浏览器")
        logging.info("=" * 50)

        browser_choice = get_user_choice(
            {
                '1': '谷歌浏览器 (Chrome)',
                '2': '微软浏览器 (Edge)',
                '3': 'QQ浏览器',
                '4': '360安全浏览器',
                '5': '火狐浏览器 (Firefox)'
            },
            "请选择用于自动化的浏览器（均为无痕模式）:"
        )

        browser_name_map = {'1': 'CHROME', '2': 'EDGE', '3': 'QQ', '4': '360', '5': 'FIREFOX'}
        selected_browser = browser_name_map[browser_choice]

        driver = init_browser(selected_browser)
        driver.set_page_load_timeout(CONFIG.WAIT_TIMEOUT)
        driver.implicitly_wait(CONFIG.WAIT_TIMEOUT)

        # --- 后续流程不变 ---
        logging.info(f"\n[UI] 正在访问URL: {url}")
        driver.get(url)
        time.sleep(CONFIG.ACTION_DELAY * 2)

        safe_click(driver, "INITIAL_APPLY_BTN", "初始页面的立即申请按钮")
        # 处理初始注册并获取token
        auth_token = handle_initial_registration(driver, phone)

        # 检查暂停（按空格键暂停/继续）
        _pause_manager.check_pause()

        logging.info("\n" + "=" * 50)
        logging.info("步骤 4/8: 提交最终申请")
        logging.info("=" * 50)
        safe_click(driver, "FINAL_APPLY_BTN", "跳转页面后的立即申请按钮")

        logging.info("\n" + "=" * 50)
        logging.info("步骤 5/8: 完成SP授权请求")
        logging.info("=" * 50)

        # 等待5秒，确保state已入库
        logging.info("⏳ 等待5秒，确保state已入库...")
        time.sleep(5)

        # 1. 从数据库查询state
        try:
            db = get_global_db()
            # 使用子查询获取SP授权的state
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

        # 2. 构建SP授权URL
        # 从BASE_URL中提取协议和域名，替换为dpu-auth
        if ENV in ("uat", "preprod"):
            # uat/preprod环境使用 expressfinance-{ENV}
            base_domain = BASE_URL.replace("https://", "").replace("http://", "")
            sp_auth_url = f"https://{base_domain}/dpu-auth/amazon-sp/auth"
        else:
            # sit/dev环境使用 dpu-gateway-{ENV}
            base_domain = BASE_URL.replace("https://", "").replace("http://", "")
            sp_auth_url = f"https://{base_domain}/dpu-auth/amazon-sp/auth"

        # 3. 构建完整的授权URL参数
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

        logging.info("[AUTH] 正在新窗口中打开SP授权URL...")
        open_url_in_new_window(driver, auth_url, "SP授权页面")

        auto_fill_company = get_yes_no_choice("[流程] 是否自动填写公司信息?")
        handle_company_info(driver, auto_fill_company)

        # 检查暂停（按空格键暂停/继续）
        _pause_manager.check_pause()

        auto_fill_director = get_yes_no_choice("[流程] 是否自动填写董事股东信息?")
        handle_director_info(driver, phone, auto_fill_director)

        # 检查暂停（按空格键暂停/继续）
        _pause_manager.check_pause()

        need_bank_info = False
        if tier_name == "TIER2":
            need_bank_info = handle_financing_choice(driver)
        elif tier_name == "TIER1":
            need_bank_info = True

        if need_bank_info:
            auto_fill_bank = get_yes_no_choice("[流程] 是否自动填写银行账户信息?")
            handle_bank_account_info(driver, auto_fill_bank)

            # 检查暂停（按空格键暂停/继续）
            _pause_manager.check_pause()

        logging.info("\n" + "=" * 50)
        logging.info("步骤 8/8: 发起关联店铺API请求")
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

        # 轮询信用报价状态，等待 SUBMITTED 状态
        submitted_success = poll_credit_offer_status(phone, authorization_token=auth_token, interval=5, max_attempts=120)

        # 检查暂停（按空格键暂停/继续）
        _pause_manager.check_pause()

        # 如果获取到SUBMITTED状态，根据need_bank_info走不同流程
        if submitted_success:
            # need_bank_info=True表示选择了"去激活"或TIER1，走新流程（跳过核保/PSP）
            if need_bank_info:
                logging.info("\n" + "=" * 50)
                logging.info("步骤 9/9: 发起审批→电子签→drawdown轮询→放款（amount=2000）")
                logging.info("=" * 50)

                # 1. 直接发起审批请求（跳过核保，amount=2000）
                time.sleep(3)
                if send_approved_request(phone, amount=2000.00):
                    logging.info("✅ 审批请求成功（amount=2000）！")

                    # 2. 直接发起电子签请求（跳过PSP流程，amount=2000）
                    time.sleep(5)
                    logging.info("\n[2/4] 发送电子签完成请求（amount=2000）...")
                    if send_esign_request(phone, amount=2000.00):
                        logging.info("✅ 电子签请求成功（amount=2000）！")

                        # 3. 轮询drawdown状态，等待SUBMITTED
                        time.sleep(5)
                        drawdown_submitted = poll_drawdown_status(phone, authorization_token=auth_token, interval=5, max_attempts=120)
                        if drawdown_submitted:
                            logging.info("✅ drawdown状态已变为SUBMITTED！")

                            # 4. 发送放款完成请求（amount=2000）
                            time.sleep(5)
                            logging.info("\n[4/4] 发送放款完成请求（disbursement.completed, amount=2000）...")
                            if send_disbursement_completed_request(phone, amount=2000.00):
                                logging.info("✅ 放款请求成功（amount=2000）！")
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
                # TIER3走完整流程（核保→审批→额度选择→后续流程）
                logging.info("\n" + "=" * 50)
                logging.info("步骤 9/9: TIER3流程 - 核保→审批→额度选择")
                logging.info("=" * 50)

                # 1. 核保请求
                time.sleep(3)
                if send_underwritten_request(phone):
                    logging.info("✅ 核保请求成功！")
                else:
                    logging.error("❌ 核保请求失败！")

                # 2. 审批请求
                time.sleep(3)
                if send_approved_request(phone):
                    logging.info("✅ 审批请求成功！")

                    # 3. 额度选择（TIER3特有）
                    time.sleep(3)
                    tier3_choice = handle_tier3_credit_choice(driver)

                    if tier3_choice == 'activate':
                        # 选择"去激活"：走完整流程（激活额度→PSP→电子签）
                        logging.info("\n" + "=" * 50)
                        logging.info("后续流程: 激活额度→PSP→电子签")
                        logging.info("=" * 50)

                        # 4. 点击激活额度按钮
                        time.sleep(5)
                        safe_click(driver, "ACTIVATE_CREDIT_BTN", "激活额度按钮")
                        logging.info("✅ 已点击激活额度按钮")

                        # 5. 点击接受按钮
                        time.sleep(5)
                        safe_click(driver, "ACCEPT_BTN", "接受按钮")
                        logging.info("✅ 已点击接受按钮")

                        # 6. PSP开始请求
                        time.sleep(5)
                        logging.info("\n[1/3] 发送PSP验证开始请求...")
                        if send_psp_start_request(phone):
                            logging.info("✅ PSP开始请求成功！")
                        else:
                            logging.error("❌ PSP开始请求失败！")

                        # 7. PSP完成请求
                        time.sleep(5)
                        logging.info("\n[2/3] 发送PSP验证完成请求...")
                        if send_psp_completed_request(phone):
                            logging.info("✅ PSP完成请求成功！")
                        else:
                            logging.error("❌ PSP完成请求失败！")

                        # 8. 电子签请求
                        time.sleep(5)
                        logging.info("\n[3/3] 发送电子签完成请求...")
                        if send_esign_request(phone):
                            logging.info("✅ 电子签请求成功！")
                        else:
                            logging.error("❌ 电子签请求失败！")

                        logging.info("\n" + "=" * 50)
                        logging.info("🎉 TIER3去激活流程已完成！")
                        logging.info("=" * 50)

                    else:
                        # 选择"去提交"：进入额外信息填写页面
                        logging.info("\n" + "=" * 50)
                        logging.info("已选择：去提交")
                        logging.info("=" * 50)

                        # 处理额外信息填写页面（上传银行流水、股东董事信息、第二次审批等）
                        time.sleep(3)  # 等待页面加载
                        handle_extra_info_page(driver, phone)

                else:
                    logging.error("❌ 审批请求失败！")

        logging.info("\n" + "=" * 50)
        logging.info("🎉 所有自动化步骤已成功完成！")
        logging.info(f"📱 本次操作的手机号: {phone}")
        logging.info("ℹ️  浏览器将保持打开状态，供您手动检查。")
        logging.info("=" * 50)

        while True: time.sleep(10)

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
                while True: time.sleep(60)
            except KeyboardInterrupt:
                logging.info("\n[流程] 用户手动中断，正在关闭浏览器...")
                driver.quit()
                logging.info("[流程] 浏览器已关闭。")


# ==============================================================================
# --- 8. 入口函数 ---
# ==============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("          HSBC API 数据生成与自动注册工具 (支持5种浏览器)")
    print("=" * 60)

    setup_logging()

    # 输出当前环境配置
    logging.info(f"📌 当前环境: {ENV.upper()}")
    logging.info(f"📌 API基础URL: {BASE_URL}")
    logging.info(f"📌 数据库: {DATABASE_CONFIG_DICT[ENV]['host']}")
    print()  # 空行分隔

    # 建立全局数据库连接（单例模式，保持连接不关闭）
    get_global_db()

    test_url, test_phone, test_tier, test_offer_id = generate_test_data()

    if test_url and test_phone and test_tier and test_offer_id:
        logging.info("\n✅ 测试数据生成成功，即将启动自动化注册流程...")
        run_automation(test_url, test_phone, test_tier)
    else:
        logging.error("\n❌ 测试数据生成失败，无法启动自动化流程。")

    logging.info("\n程序主流程结束。")

    # 关闭全局数据库连接
    close_global_db()
