"""
HSBC 线上 SP 完成生成数据脚本

概述:
    一个用于自动化生成测试数据并完成SP授权流程，进入商业信息页面的Selenium脚本。
    固定使用TIER2流程和微软Edge浏览器。

主要功能:
    1. 生成测试数据（调用API获取offerId，生成URL和手机号）。
    2. 自动化完成注册流程（使用Edge浏览器无痕模式）。
    3. 完成SP授权流程。
    4. 进入商业信息页面后停止。
"""

import time
import random
import os
import socket
import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import pymysql
from urllib.parse import urlencode

# ==============================================================================
# --- 1. 配置与常量 ---
# ==============================================================================

# 环境配置
ENV = "sit"

# 基础URL映射
BASE_URL_DICT = {
    "sit": "https://sit.api.expressfinance.business.hsbc.com",
    "dev": "https://dpu-gateway-dev.dowsure.com",
    "uat": "https://uat.api.expressfinance.business.hsbc.com",
    "preprod": "https://preprod.api.expressfinance.business.hsbc.com",
    "local": "http://localhost:8080"
}

# 获取当前环境的基础URL
BASE_URL = BASE_URL_DICT.get(ENV, BASE_URL_DICT["uat"])

# 数据库配置（与线上自动化.py保持一致）
DATABASE_CONFIG = {
    "sit": {
        "host": "18.162.145.173",
        "user": "dpu_sit",
        "password": "20250818dpu_sit",
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
    "dev": {
        "host": "aurora-dpu-dev.cluster-cxm4ce0i8nzq.ap-east-1.rds.amazonaws.com",
        "user": "dpu_dev",
        "password": "J9IUmPpD@Hon8Y#v",
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
        "port": 3306,
        "user": "root",
        "password": "123456",
        "database": "dpu"
    }
}

@dataclass
class Config:
    """应用程序核心配置"""
    # API端点
    REQUEST_URL: str = field(default_factory=lambda: f"{BASE_URL}/dpu-merchant/mock/generate-shop-performance")
    REDIRECT_URL_PREFIX: str = field(default_factory=lambda: f"{BASE_URL}/dpu-merchant/amazon/redirect?offerId=")

    # HTTP请求头
    HEADERS: Dict[str, str] = field(default_factory=lambda: {"Content-Type": "application/json"})

    # 业务配置 - 固定TIER2
    YEARLY_REPAYMENT_AMOUNT: int = 950000  # TIER2金额

    # Selenium配置
    WAIT_TIMEOUT: int = 30
    ACTION_DELAY: float = 1.5
    VERIFICATION_CODE: str = "666666"
    PASSWORD: str = "Aa11111111.."
    SECURITY_ANSWER: str = "Aa11111111.."

CONFIG = Config()

# 元素定位器 (参考线上自动化.py，使用XPATH增强稳定性)
LOCATORS = {
    # 初始页面
    "INITIAL_APPLY_BTN": (By.XPATH, "//button[contains(., '立即申请')]"),
    # 注册页面
    "PHONE_INPUT": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @maxlength='15']"),
    "VERIFICATION_CODE_INPUTS": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @maxlength='1']"),
    "REG_NEXT_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[8]/button"),
    # 密码设置页面
    "PASSWORD_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[1]/div[2]/div/div[1]/div/input"),
    "CONFIRM_PASSWORD_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[1]/div[5]/div/div[1]/div/input"),
    "SECURITY_QUESTION_DROPDOWN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[2]/div[2]/div/div[1]/div[1]/div[1]/div[1]/input"),
    "SPECIFIC_SECURITY_QUESTION_OPTION": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[2]/div[2]/div/div/div[2]/div/div/div[1]/ul/li[4]/span"),
    "SECURITY_ANSWER_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[2]/div[4]/div/div[1]/div/input"),
    "EMAIL_ADDRESS_INPUT": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[3]/div[2]/div/div[1]/div/input"),
    "AGREE_DECLARATION_CHECKBOX": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[4]/div/div/label/span[1]/span"),
    "AUTHORIZATION_CHECKBOX": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[4]/div[2]/div/label/span[1]/span"),
    "FINAL_REGISTER_BTN": (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[5]/div[2]/button"),
    # 最终申请按钮
    "FINAL_APPLY_BTN": (By.XPATH, "//button[contains(@class, 'application-btn') and .//span[text()='立即申请']]"),
    # 公司信息页面
    "COMPANY_EN_NAME_INPUT": (By.XPATH, "(//input[contains(@class, 'el-input__inner') and @autocomplete='off'])[1]"),
    "BUSINESS_REG_NO_INPUT": (By.XPATH, "(//input[contains(@class, 'el-input__inner') and @autocomplete='off'])[3]"),
    "NEXT_BTN": (By.XPATH, "//button[contains(., '下一页')]"),
}

# ==============================================================================
# --- 2. 日志配置 ---
# ==============================================================================

def setup_logging():
    """配置日志系统"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('sp_completion.log', encoding='utf-8')
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ==============================================================================
# --- 3. 数据库操作 ---
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


class DatabaseExecutor:
    """数据库执行器，支持自动重连"""

    def __init__(self, env: str = ENV):
        self.env = env
        self.config = DATABASE_CONFIG.get(env, DATABASE_CONFIG["uat"])
        self.connection = None

    def connect(self):
        """建立数据库连接（绑定本地IP绕过VPN）"""
        try:
            # 获取本地物理网卡IP用于绕过VPN
            local_ip = get_local_physical_ip()
            connect_params = self.config.copy()

            if local_ip:
                connect_params['bind_address'] = local_ip
                logger.info(f"🔗 绑定本地IP: {local_ip} 绕过VPN直连数据库")

            # 清除代理环境变量
            old_proxies = {}
            for proxy_key in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'):
                if os.environ.get(proxy_key):
                    old_proxies[proxy_key] = os.environ[proxy_key]
                    del os.environ[proxy_key]

            self.connection = pymysql.connect(
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=10,
                **connect_params
            )

            # 恢复代理环境变量
            for k, v in old_proxies.items():
                os.environ[k] = v

            if local_ip:
                logger.info(f"✅ 数据库直连成功（已绑定 {local_ip} 绕过VPN）")
            else:
                logger.info("✅ 数据库连接成功（系统自动路由）")
            return True
        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            return False

    def execute_sql(self, sql: str) -> Optional[str]:
        """执行SQL并返回单个值"""
        if not self.connection:
            if not self.connect():
                return None

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql)
                result = cursor.fetchone()
                self.connection.commit()
                if result:
                    return str(list(result.values())[0])
                return None
        except pymysql.OperationalError as e:
            if e.args[0] in (2006, 2013, 10054):
                logger.warning(f"⚠️ 数据库连接断开，尝试重连...")
                self.connection = None
                if self.connect():
                    return self.execute_sql(sql)
            logger.error(f"❌ SQL执行错误: {e}")
            return None

    def execute_query(self, sql: str) -> Optional[dict]:
        """执行SQL并返回字典结果"""
        if not self.connection:
            if not self.connect():
                return None

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql)
                result = cursor.fetchone()
                self.connection.commit()
                return result
        except pymysql.OperationalError as e:
            if e.args[0] in (2006, 2013, 10054):
                logger.warning(f"⚠️ 数据库连接断开，尝试重连...")
                self.connection = None
                if self.connect():
                    return self.execute_query(sql)
            logger.error(f"❌ SQL执行错误: {e}")
            return None

    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            self.connection = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# ==============================================================================
# --- 4. 工具函数 ---
# ==============================================================================

def safe_click(driver: webdriver.Remote, locator_key: str, desc: str = "元素"):
    """安全点击元素"""
    try:
        element = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(
            EC.element_to_be_clickable(LOCATORS[locator_key])
        )
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        time.sleep(0.3)
        element.click()
        logger.info(f"✅ 点击{desc}成功")
        return True
    except Exception as e:
        logger.error(f"❌ 点击{desc}失败: {e}")
        return False

def safe_send_keys(driver: webdriver.Remote, locator_key: str, text: str, desc: str = "输入框"):
    """安全输入文本"""
    try:
        element = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(
            EC.presence_of_element_located(LOCATORS[locator_key])
        )
        element.clear()
        element.send_keys(text)
        logger.info(f"✅ 输入{text}到{desc}")
        return True
    except Exception as e:
        logger.error(f"❌ 输入到{desc}失败: {e}")
        return False

# ==============================================================================
# --- 5. 测试数据生成 ---
# ==============================================================================

def generate_test_data() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """生成测试数据（offerId、URL、手机号）"""
    logger.info("\n" + "=" * 50)
    logger.info("步骤 1/7: 生成测试数据")
    logger.info("=" * 50)

    # 手动输入手机号
    logger.info(f"\n{'=' * 50}")
    logger.info("手机号输入")
    logger.info('=' * 50)
    phone = input(f"请输入手机号 (直接按Enter自动生成): ").strip()
    if not phone:
        # 生成手机号（11位，182开头）
        phone = f"182{random.randint(10000000, 99999999)}"
        logger.info(f"自动生成手机号: {phone}")
    else:
        logger.info(f"使用自定义手机号: {phone}")

    try:

        # 构建请求体
        payload = {"yearlyRepaymentAmount": CONFIG.YEARLY_REPAYMENT_AMOUNT}

        logger.info(f"[API] 发送POST请求到: {CONFIG.REQUEST_URL}")
        logger.info(f"[API] 请求体: {payload}")

        response = requests.post(
            CONFIG.REQUEST_URL,
            json=payload,
            headers=CONFIG.HEADERS,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            # API返回的字段是 amazon3plOfferId
            offer_id = result.get("amazon3plOfferId") or result.get("data", {}).get("amazon3plOfferId")

            if offer_id:
                url = f"{CONFIG.REDIRECT_URL_PREFIX}{offer_id}"
                logger.info(f"✅ 测试数据生成成功")
                logger.info(f"   手机号: {phone}")
                logger.info(f"   OfferID: {offer_id}")
                logger.info(f"   URL: {url}")

                # 保存到文件
                with open("register_sp_completed.txt", "a", encoding="utf-8") as f:
                    f.write(f"TIER2,SP完成,{phone},{url}\n")

                return offer_id, url, phone
            else:
                logger.error("❌ 响应中未找到offerId")
        else:
            logger.error(f"❌ API请求失败 | 状态码: {response.status_code}")

    except Exception as e:
        logger.error(f"❌ 生成测试数据异常: {e}")

    return None, None, None

# ==============================================================================
# --- 6. 浏览器操作 ---
# ==============================================================================

def init_edge_browser() -> webdriver.Edge:
    """初始化Edge浏览器（无痕模式）"""
    logger.info("[Browser] 正在初始化Edge浏览器 (无痕模式)...")

    options = EdgeOptions()
    options.add_argument("--inprivate")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    driver = webdriver.Edge(options=options)
    driver.set_page_load_timeout(CONFIG.WAIT_TIMEOUT)
    driver.implicitly_wait(CONFIG.WAIT_TIMEOUT)

    logger.info("✅ Edge浏览器初始化成功")
    return driver

def select_specific_security_question(driver: webdriver.Remote):
    """点击安全问题下拉框并选择指定的第4个选项"""
    try:
        # 点击下拉框展开选项
        safe_click(driver, "SECURITY_QUESTION_DROPDOWN", "安全问题下拉框")
        time.sleep(CONFIG.ACTION_DELAY)

        # 等待选项加载并点击指定的安全问题选项
        safe_click(driver, "SPECIFIC_SECURITY_QUESTION_OPTION", "指定的安全问题选项(第4项)")

        # 获取选中的选项文本
        selected_text = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(
            EC.visibility_of_element_located(LOCATORS["SPECIFIC_SECURITY_QUESTION_OPTION"])
        ).text.strip()
        logger.info(f"[UI] 已选择安全问题: {selected_text}")

        return selected_text
    except Exception as e:
        logger.warning(f"[UI] 选择指定安全问题选项时发生错误: {e}")


def get_token_from_browser(driver: webdriver.Remote) -> Optional[str]:
    """从浏览器存储中获取授权token"""
    logger.info("[Browser] 正在从浏览器存储中获取token...")

    token_keys = [
        'token', 'Token', 'TOKEN',
        'accessToken', 'access_token', 'AccessToken',
        'authToken', 'auth_token', 'AuthToken',
        'authorization', 'Authorization', 'AUTHORIZATION',
        'jwt', 'JWT',
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
        for key in token_keys:
            if key in local_storage and local_storage[key]:
                token_value = local_storage[key]
                logger.info(f"✅ 成功从localStorage获取token (键: {key}): {token_value[:30]}...")
                return token_value
    except Exception as e:
        logger.warning(f"[Browser] 从localStorage获取token失败: {e}")

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
                logger.info(f"✅ 成功从sessionStorage获取token (键: {key}): {token_value[:30]}...")
                return token_value
    except Exception as e:
        logger.warning(f"[Browser] 从sessionStorage获取token失败: {e}")

    logger.warning("⚠️ 未能从浏览器获取token，继续流程...")
    return "auth_token_placeholder"


def handle_initial_registration(driver: webdriver.Remote, phone: str) -> Optional[str]:
    """处理初始注册信息页面，返回从浏览器获取的token"""
    logger.info("\n" + "=" * 50)
    logger.info("步骤 3/7: 填写初始注册信息")
    logger.info("=" * 50)

    # 输入手机号
    safe_send_keys(driver, "PHONE_INPUT", phone, "手机号")

    # 输入验证码（6个单独的输入框）
    logger.info(f"[UI] 正在输入验证码: {CONFIG.VERIFICATION_CODE}")
    code_inputs = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(
        EC.visibility_of_all_elements_located(LOCATORS["VERIFICATION_CODE_INPUTS"])
    )
    for i, char in enumerate(CONFIG.VERIFICATION_CODE):
        if i < len(code_inputs):
            code_inputs[i].send_keys(char)
    time.sleep(CONFIG.ACTION_DELAY)

    # 点击注册页面的下一步按钮
    safe_click(driver, "REG_NEXT_BTN", "注册页面下一步按钮")
    time.sleep(CONFIG.ACTION_DELAY * 3)

    # 处理密码设置页面
    auth_token = handle_password_setup(driver, phone)
    return auth_token


def handle_password_setup(driver: webdriver.Remote, phone: str) -> Optional[str]:
    """处理密码设置页面，包括安全问题、邮箱等"""
    logger.info("\n" + "=" * 50)
    logger.info("步骤 3.5/7: 处理密码设置页面")
    logger.info("=" * 50)

    # 1. 输入密码
    safe_send_keys(driver, "PASSWORD_INPUT", CONFIG.PASSWORD, "新密码")
    time.sleep(CONFIG.ACTION_DELAY)

    # 2. 输入确认密码
    safe_send_keys(driver, "CONFIRM_PASSWORD_INPUT", CONFIG.PASSWORD, "确认新密码")
    time.sleep(CONFIG.ACTION_DELAY)

    # 3. 选择指定的安全问题
    select_specific_security_question(driver)
    time.sleep(CONFIG.ACTION_DELAY)

    # 4. 输入安全问题答案
    safe_send_keys(driver, "SECURITY_ANSWER_INPUT", CONFIG.SECURITY_ANSWER, "安全问题答案")
    time.sleep(CONFIG.ACTION_DELAY)

    # 5. 输入电子邮件地址
    email_address = f"{phone}@163.com"
    safe_send_keys(driver, "EMAIL_ADDRESS_INPUT", email_address, "电子邮件地址")
    time.sleep(CONFIG.ACTION_DELAY)

    # 6. 点击同意声明按钮
    safe_click(driver, "AGREE_DECLARATION_CHECKBOX", "同意声明复选框")
    time.sleep(CONFIG.ACTION_DELAY)

    # 6.1 点击授权复选框
    safe_click(driver, "AUTHORIZATION_CHECKBOX", "授权复选框")
    time.sleep(CONFIG.ACTION_DELAY)

    # 7. 点击最终注册按钮
    safe_click(driver, "FINAL_REGISTER_BTN", "注册按钮")
    time.sleep(CONFIG.ACTION_DELAY * 3)

    # 8. 从浏览器获取token
    auth_token = get_token_from_browser(driver)
    return auth_token

# ==============================================================================
# --- 7. 主流程 ---
# ==============================================================================

def run_sp_completion_flow():
    """执行SP完成流程"""

    # 生成测试数据
    offer_id, url, phone = generate_test_data()
    if not offer_id or not url or not phone:
        logger.error("❌ 测试数据生成失败，流程终止")
        return

    driver = None
    try:
        # 初始化Edge浏览器
        logger.info("\n" + "=" * 50)
        logger.info("步骤 2/7: 初始化Edge浏览器")
        logger.info("=" * 50)

        driver = init_edge_browser()

        # 访问URL
        logger.info(f"\n[UI] 正在访问URL: {url}")
        driver.get(url)
        time.sleep(CONFIG.ACTION_DELAY * 2)

        # 点击立即申请
        if not safe_click(driver, "INITIAL_APPLY_BTN", "初始页面的立即申请按钮"):
            return

        # 处理初始注册（包含密码设置、安全问题、邮箱输入等）
        auth_token = handle_initial_registration(driver, phone)
        if not auth_token:
            return

        # 点击最终申请按钮
        logger.info("\n" + "=" * 50)
        logger.info("步骤 4/7: 提交最终申请")
        logger.info("=" * 50)

        if not safe_click(driver, "FINAL_APPLY_BTN", "跳转页面后的立即申请按钮"):
            return

        # 完成SP授权
        logger.info("\n" + "=" * 50)
        logger.info("步骤 5/7: 完成SP授权请求")
        logger.info("=" * 50)

        # 等待5秒，确保state已入库
        logger.info("⏳ 等待5秒，确保state已入库...")
        time.sleep(5)

        # 从数据库查询state
        state = None
        try:
            with DatabaseExecutor(ENV) as db:
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
                    logger.warning(f"⚠️ 未查询到SP授权的state，手机号: {phone}")
                else:
                    logger.info(f"✅ 查询到state: {state}")
        except Exception as e:
            logger.warning(f"⚠️ 数据库连接失败: {e}")

        # 如果数据库查询失败，提供手动确认选项
        if not state:
            logger.info("\n" + "=" * 50)
            logger.info("数据库连接失败，请选择处理方式:")
            logger.info("1. 手动在浏览器中完成SP授权，然后继续")
            logger.info("2. 退出脚本")
            logger.info("=" * 50)

            choice = input("请选择 (1/2): ").strip()
            if choice != "1":
                logger.info("用户选择退出脚本")
                return

            logger.info("等待用户在浏览器中完成SP授权...")
            input("请在浏览器中完成SP授权后，按Enter键继续...")

            # 跳过SP授权请求，直接进入商业信息页面等待
            logger.info("继续流程，等待进入商业信息页面...")
            time.sleep(3)

            # 等待公司信息页面元素出现
            try:
                WebDriverWait(driver, CONFIG.WAIT_TIMEOUT * 2).until(
                    EC.presence_of_element_located(LOCATORS["COMPANY_EN_NAME_INPUT"])
                )
                logger.info("✅ 已成功进入商业信息页面")
                logger.info("\n" + "=" * 50)
                logger.info("🎉 SP完成流程已成功执行！")
                logger.info("   流程在商业信息页面停止")
                logger.info(f"   手机号: {phone}")
                logger.info(f"   URL: {url}")
                logger.info("=" * 50)

                # 保持浏览器打开，方便用户查看
                input("\n按Enter键关闭浏览器...")

            except Exception as e:
                logger.warning(f"⚠️ 等待商业信息页面超时: {e}")
                logger.info("流程已完成，请手动检查页面状态")
                input("\n按Enter键关闭浏览器...")
            return

        # 构建SP授权URL
        if ENV in ("uat", "preprod"):
            base_domain = BASE_URL.replace("https://", "").replace("http://", "")
            sp_auth_url = f"https://{base_domain}/dpu-auth/amazon-sp/auth"
        else:
            base_domain = BASE_URL.replace("https://", "").replace("http://", "")
            sp_auth_url = f"https://{base_domain}/dpu-auth/amazon-sp/auth"

        # 手动输入seller ID
        default_selling_partner_id = f"spshouquanfs{phone}"
        logger.info(f"\n{'=' * 50}")
        logger.info("SP授权 - Seller ID输入")
        logger.info(f"默认值: {default_selling_partner_id}")
        logger.info('=' * 50)
        selling_partner_id = input(f"请输入Seller ID (直接按Enter使用默认值): ").strip()
        if not selling_partner_id:
            selling_partner_id = default_selling_partner_id
            logger.info(f"使用默认Seller ID: {selling_partner_id}")
        else:
            logger.info(f"使用自定义Seller ID: {selling_partner_id}")

        params = {
            "state": state,
            "selling_partner_id": selling_partner_id,
            "mws_auth_token": "1235",
            "spapi_oauth_code": "123123"
        }

        auth_url = f"{sp_auth_url}?{urlencode(params)}"
        logger.info(f"[AUTH] SP授权URL: {auth_url}")

        # 发送GET请求完成SP授权
        try:
            logger.info("[AUTH] 正在发送SP授权GET请求...")
            response = requests.get(auth_url, timeout=30)

            if response.status_code == 200:
                logger.info(f"✅ SP授权请求成功")
            else:
                logger.warning(f"⚠️ SP授权请求返回状态码: {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ SP授权请求异常: {e}")

        # 进入商业信息页面
        logger.info("\n" + "=" * 50)
        logger.info("步骤 6/7: 等待进入商业信息页面")
        logger.info("=" * 50)

        time.sleep(3)

        # 等待公司信息页面元素出现
        try:
            WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(
                EC.presence_of_element_located(LOCATORS["COMPANY_EN_NAME_INPUT"])
            )
            logger.info("✅ 已成功进入商业信息页面")
            logger.info("\n" + "=" * 50)
            logger.info("🎉 SP完成流程已成功执行！")
            logger.info("   流程在商业信息页面停止")
            logger.info(f"   手机号: {phone}")
            logger.info(f"   URL: {url}")
            logger.info("=" * 50)

            # 保持浏览器打开，方便用户查看
            input("\n按Enter键关闭浏览器...")

        except Exception as e:
            logger.warning(f"⚠️ 等待商业信息页面超时: {e}")
            logger.info("流程已完成，请手动检查页面状态")
            input("\n按Enter键关闭浏览器...")

    except Exception as e:
        logger.error(f"❌ 流程执行异常: {e}")

    finally:
        if driver:
            driver.quit()
            logger.info("📋 浏览器已关闭")

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("HSBC 线上 SP 完成生成数据脚本")
    logger.info("环境: " + ENV.upper())
    logger.info("流程: TIER2 -> SP完成 -> 商业信息页面")
    logger.info("浏览器: Edge (无痕模式)")
    logger.info("=" * 50)

    run_sp_completion_flow()
