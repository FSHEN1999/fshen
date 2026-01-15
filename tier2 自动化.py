"""
HSBC API 数据生成与自动注册工具

概述:
    一个用于自动化生成测试数据并完成HSBC相关注册流程的Selenium脚本。
    支持不同TIER级别的申请流程，并提供灵活的自动/手动填写选项。

主要功能:
    1. 生成测试数据（调用API获取offerId，生成URL和手机号）。
    2. 自动化完成注册流程（支持Chrome和Edge浏览器的无痕模式）。
    3. 智能处理不同TIER级别的流程差异（如TIER1包含银行账户信息步骤）。
    4. TIER2流程中增加融资方案选择分支。
    5. 详细的日志记录和错误处理机制。
"""

import time
import random
import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, Callable
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests


# ==============================================================================
# --- 1. 配置与常量 (集中管理，易于维护) ---
# ==============================================================================

@dataclass
class AppConfig:
    """应用程序核心配置"""
    # API端点
    REQUEST_URL: str = "https://uat.api.expressfinance.business.hsbc.com/dpu-merchant/mock/generate-shop-performance"
    REDIRECT_URL_PREFIX: str = "https://uat.api.expressfinance.business.hsbc.com/dpu-merchant/amazon/redirect?offerId="
    AUTH_POST_URL: str = "https://uat.api.expressfinance.business.hsbc.com/dpu-merchant/amz/sp/shop/auth"
    LINK_SHOP_API_URL: str = "https://uat.api.expressfinance.business.hsbc.com/dpu-merchant/mock/link-sp-3pl-shops"

    # HTTP请求头
    HEADERS: Dict[str, str] = field(default_factory=lambda: {"Content-Type": "application/json"})

    # 业务配置
    TIER_OPTIONS: Dict[str, Tuple[str, int]] = field(default_factory=lambda: {
        '1': ('TIER1', 120000),
        '2': ('TIER2', 950000),
        '3': ('TIER3', 2000000)
    })

    # 文件路径
    DATA_FILE_PATH: str = r"D:\data\project\test\uat tier2-run.txt"
    SCREENSHOT_FOLDER: str = r"C:\Users\PC\Desktop\截图"

    # Selenium配置
    WAIT_TIMEOUT: int = 30  # 元素等待超时时间（秒）
    ACTION_DELAY: float = 1.5  # 操作间延迟（秒），提高稳定性
    VERIFICATION_CODE: str = "666666"  # 固定验证码


# 实例化配置
CONFIG = AppConfig()

# 元素定位器 (使用XPATH，增强稳定性)
LOCATORS = {
    "INITIAL_APPLY_BTN": (By.XPATH, "//button[contains(., '立即申请')]"),
    "PHONE_INPUT": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @maxlength='15']"),
    "VERIFICATION_CODE_INPUTS": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @maxlength='1']"),
    "EMAIL_INPUT": (By.XPATH,
                    "//input[contains(@class, 'el-input__inner') and @autocomplete='off' and not(@maxlength)]"),
    "AGREE_TERMS_CHECKBOX": (By.XPATH, "//span[contains(@class, 'el-checkbox__inner')]"),
    "REGISTER_BTN": (By.XPATH, "//span[text()='立即注册']"),
    "FINAL_APPLY_BTN": (By.XPATH, "//button[contains(@class, 'application-btn') and .//span[text()='立即申请']]"),
    "NEXT_BTN": (By.XPATH, "//button[contains(., '下一页')]"),

    # 公司信息页
    "COMPANY_EN_NAME_INPUT": (By.XPATH, "(//input[contains(@class, 'el-input__inner') and @autocomplete='off'])[1]"),
    "BUSINESS_REG_NO_INPUT": (By.XPATH, "(//input[contains(@class, 'el-input__inner') and @autocomplete='off'])[3]"),

    # 董事股东信息页
    "ID_FRONT_UPLOAD_AREA": (By.XPATH,
                             "//div[contains(@class, 'el-upload-dragger') and .//img[contains(@src, 'PRC%20ID-Front')]]"),
    "ID_BACK_UPLOAD_AREA": (By.XPATH,
                            "//div[contains(@class, 'el-upload-dragger') and .//img[contains(@src, 'PRC%20ID-Back')]]"),
    "DATE_INPUT": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @placeholder='YYYY/MM/DD']"),
    "REFERENCE_PHONE_INPUT": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @maxlength='15']"),
    "REFERENCE_EMAIL_INPUT": (By.XPATH,
                              "//input[contains(@class, 'el-input__inner') and @autocomplete='off' and not(@maxlength) and not(@placeholder)]"),

    # 银行账户信息页
    "BANK_SELECT_DROPDOWN": (By.XPATH, "//input[contains(@class, 'el-select__input') and @role='combobox']"),
    "BANK_SELECT_OPTIONS": (By.XPATH, "//li[contains(@class, 'el-select-dropdown__item')]"),
    "BANK_ACCOUNT_INPUT": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @maxlength='12']"),

    # 融资方案选择页 (TIER2)
    "ACTIVATE_NOW_BTN": (By.XPATH, "//button[span[text()='去激活']]"),
    "APPLY_HIGHER_AMOUNT_BTN": (By.XPATH, "//button[span[text()='申请更高额度']]")
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
# --- 3. 通用工具函数 (封装重复操作，提高代码复用性) ---
# ==============================================================================

def send_post_request(url: str, phone: Optional[str] = None, payload: Optional[dict] = None) -> bool:
    """
    发送POST请求的通用封装。

    Args:
        url (str): 请求的URL。
        phone (Optional[str]): 可选，用于拼接URL参数。
        payload (Optional[dict]): 可选，请求体数据。

    Returns:
        bool: 请求是否成功 (状态码为200)。
    """
    try:
        request_url = f"{url}?phone={phone}" if phone else url
        logging.info(f"[API] 发送POST请求到: {request_url}")

        response = requests.post(
            request_url,
            json=payload,
            headers=CONFIG.HEADERS,
            timeout=15
        )

        logging.info(f"[API] 响应状态码: {response.status_code}")
        # 仅在调试时打印完整响应
        # logging.debug(f"[API] 响应内容: {response.text}")

        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logging.error(f"[API] 请求失败: {e}")
        return False


def safe_click(driver: webdriver.Remote, locator_key: str, action_description: str):
    """
    安全地点击一个元素，处理各种可能的异常。

    Args:
        driver (webdriver.Remote): Selenium WebDriver实例。
        locator_key (str): LOCATORS字典中的键。
        action_description (str): 本次操作的描述，用于日志。
    """
    try:
        locator = LOCATORS[locator_key]
        element = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(
            EC.element_to_be_clickable(locator)
        )
        # 滚动到元素视图中，防止被遮挡
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
        raise  # 抛出异常，让调用者决定如何处理


def safe_send_keys(driver: webdriver.Remote, locator_key: str, text: str, field_description: str):
    """
    安全地向输入框输入文本。

    Args:
        driver (webdriver.Remote): Selenium WebDriver实例。
        locator_key (str): LOCATORS字典中的键。
        text (str): 要输入的文本。
        field_description (str): 输入框的描述，用于日志。
    """
    try:
        locator = LOCATORS[locator_key]
        element = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(
            EC.visibility_of_element_located(locator)
        )
        element.clear()
        element.send_keys(text)
        logging.info(f"[UI] 已在 '{field_description}' 中输入: {text}")
    except Exception as e:
        logging.error(f"[UI] 向 '{field_description}' 输入时发生错误: {e}")
        raise


def upload_image(driver: webdriver.Remote, description: str):
    """
    上传图片到指定区域。

    Args:
        driver (webdriver.Remote): Selenium WebDriver实例。
        description (str): 上传操作的描述，用于日志。
    """
    try:
        # 查找截图文件夹中的第一个PNG文件
        png_files = [f for f in os.listdir(CONFIG.SCREENSHOT_FOLDER) if f.lower().endswith('.png')]
        if not png_files:
            raise FileNotFoundError(f"在截图文件夹 '{CONFIG.SCREENSHOT_FOLDER}' 中未找到PNG图片。")

        image_path = os.path.abspath(os.path.join(CONFIG.SCREENSHOT_FOLDER, png_files[0]))

        # 文件上传通常通过定位隐藏的 <input type="file"> 元素来完成
        file_input = driver.execute_script("return document.querySelector('input[type=\"file\"]');")
        file_input.send_keys(image_path)

        time.sleep(CONFIG.ACTION_DELAY * 2)  # 等待上传动画完成
        logging.info(f"[UI] 已上传图片 '{os.path.basename(image_path)}' 用于: {description}")
    except Exception as e:
        logging.error(f"[UI] 上传图片 '{description}' 时发生错误: {e}")
        raise


# ==============================================================================
# --- 4. 数据生成函数 ---
# ==============================================================================

def get_user_choice(options: Dict[str, str], prompt: str) -> str:
    """
    通用函数，用于获取用户的有效选择。

    Args:
        options (Dict[str, str]): 选项字典，键为输入值，值为显示文本。
        prompt (str): 显示给用户的提示信息。

    Returns:
        str: 用户选择的键。
    """
    print(f"\n{prompt}")
    for key, value in options.items():
        print(f"  {key}. {value}")

    while True:
        choice = input("请输入选项: ").strip()
        if choice in options:
            return choice
        print(f"输入无效，请从 {', '.join(options.keys())} 中选择。")

def generate_test_data() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    第一步：生成测试数据。
    调用API获取offerId，生成随机手机号和跳转URL。
    (已固定为TIER2)

    Returns:
        Tuple[Optional[str], Optional[str], Optional[str]]: 一个包含 (url, phone, tier_name) 的元组，
                                                             如果生成失败，所有值为None。
    """
    logging.info("=" * 50)
    logging.info("步骤 1/8: 生成测试数据")
    logging.info("=" * 50)

    # --- MODIFICATION START ---
    # 固定选择TIER2，不再提供用户选择
    tier_choice_key = '2'
    tier_name, amount = CONFIG.TIER_OPTIONS[tier_choice_key]
    logging.info(f"已固定选择TIER级别: '{tier_name}' (金额: {amount})")
    # --- MODIFICATION END ---

    try:
        logging.info(f"正在为TIER '{tier_name}' (金额: {amount}) 生成数据...")

        # 调用API
        response = requests.post(
            CONFIG.REQUEST_URL,
            json={"yearlyRepaymentAmount": amount},
            headers=CONFIG.HEADERS,
            timeout=10
        )
        response.raise_for_status()  # 如果响应码不是2xx，会抛出异常
        data = response.json()

        # 健壮地获取offerId
        offer_id = data.get("amazon3plOfferId") or data.get("data", {}).get("amazon3plOfferId")
        if not offer_id:
            raise ValueError("从API响应中未找到有效的 'amazon3plOfferId'。")

        # 生成随机手机号
        phone = f"182{random.randint(10000000, 99999999)}"
        # 构建跳转URL
        url = f"{CONFIG.REDIRECT_URL_PREFIX}{offer_id}"

        # 保存数据到文件
        os.makedirs(os.path.dirname(CONFIG.DATA_FILE_PATH), exist_ok=True)
        with open(CONFIG.DATA_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(
                f"--- 新数据 ---\nTIER: {tier_name}\nURL: {url}\nPhone: {phone}\n生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n--- 分隔符 ---\n\n")

        logging.info(f"数据生成成功: URL={url}, Phone={phone}, TIER={tier_name}")
        return url, phone, tier_name

    except Exception as e:
        logging.error(f"生成测试数据失败: {e}")
        return None, None, None


# ==============================================================================
# --- 5. 页面处理函数 (封装每个页面的具体操作) ---
# ==============================================================================

def handle_initial_registration(driver: webdriver.Remote, phone: str):
    """
    第三步：处理初始注册信息页面（手机号、验证码、邮箱）。
    """
    logging.info("\n" + "=" * 50)
    logging.info("步骤 3/8: 填写初始注册信息")
    logging.info("=" * 50)

    safe_send_keys(driver, "PHONE_INPUT", phone, "手机号")

    # 处理验证码输入框（通常是多个输入框）
    logging.info(f"[UI] 正在输入验证码: {CONFIG.VERIFICATION_CODE}")
    code_inputs = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(
        EC.visibility_of_all_elements_located(LOCATORS["VERIFICATION_CODE_INPUTS"])
    )
    for i, char in enumerate(CONFIG.VERIFICATION_CODE):
        if i < len(code_inputs):
            code_inputs[i].send_keys(char)
    time.sleep(CONFIG.ACTION_DELAY)

    email = f"{phone}@qq.com"
    safe_send_keys(driver, "EMAIL_INPUT", email, "邮箱")

    safe_click(driver, "AGREE_TERMS_CHECKBOX", "同意服务条款")
    safe_click(driver, "REGISTER_BTN", "立即注册按钮")

    time.sleep(CONFIG.ACTION_DELAY * 3)  # 等待注册完成并跳转


def handle_company_info(driver: webdriver.Remote, auto_fill: bool):
    """
    第五步：处理公司信息页面。
    """
    logging.info("\n" + "=" * 50)
    logging.info("步骤 5/8: 处理公司信息")
    logging.info("=" * 50)

    if auto_fill:
        logging.info("[流程] 选择自动填写公司信息...")
        safe_send_keys(driver, "COMPANY_EN_NAME_INPUT", "123", "公司英文名称")
        time.sleep(CONFIG.ACTION_DELAY)
        safe_send_keys(driver, "BUSINESS_REG_NO_INPUT", "11111111", "商业登记号码")
    else:
        input("[流程] 请手动填写公司信息，完成后按Enter键继续...")

    safe_click(driver, "NEXT_BTN", "公司信息页下一步")


def handle_director_info(driver: webdriver.Remote, phone: str, auto_fill: bool):
    """
    第六步：处理董事股东信息页面。
    """
    logging.info("\n" + "=" * 50)
    logging.info("步骤 6/8: 处理董事股东信息")
    logging.info("=" * 50)

    if auto_fill:
        logging.info("[流程] 选择自动填写董事股东信息...")
        upload_image(driver, "身份证正面")
        upload_image(driver, "身份证背面")
        safe_send_keys(driver, "DATE_INPUT", "2025/01/01", "日期")
        safe_send_keys(driver, "REFERENCE_PHONE_INPUT", phone, "参考手机号")
        safe_send_keys(driver, "REFERENCE_EMAIL_INPUT", f"{phone}@qq.com", "参考邮箱")
    else:
        input("[流程] 请手动填写董事股东信息并上传身份证，完成后按Enter键继续...")

    safe_click(driver, "NEXT_BTN", "董事股东信息页下一步")


def handle_bank_account_info(driver: webdriver.Remote, auto_fill: bool):
    """
    第七步：处理银行账户信息页面 (TIER1或TIER2"去激活"流程)。
    """
    logging.info("\n" + "=" * 50)
    logging.info("步骤 7/8: 处理银行账户信息")
    logging.info("=" * 50)

    if auto_fill:
        logging.info("[流程] 选择自动填写银行账户信息...")
        # 选择银行
        safe_click(driver, "BANK_SELECT_DROPDOWN", "银行选择下拉框")
        bank_options = WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(
            EC.presence_of_all_elements_located(LOCATORS["BANK_SELECT_OPTIONS"])
        )
        if bank_options:
            selected_option = random.choice(bank_options)
            bank_name = selected_option.text
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'nearest'});",
                                  selected_option)
            time.sleep(CONFIG.ACTION_DELAY)
            selected_option.click()
            logging.info(f"[UI] 已选择银行: {bank_name}")

        # 填写账号
        bank_account = f"{random.randint(100000000000, 999999999999)}"
        safe_send_keys(driver, "BANK_ACCOUNT_INPUT", bank_account, "银行账号")
    else:
        input("[流程] 请手动选择银行并填写账户信息，完成后按Enter键继续...")

    safe_click(driver, "NEXT_BTN", "银行信息页下一步")


def handle_financing_choice(driver: webdriver.Remote) -> bool:
    """
    处理融资方案选择页面 (仅TIER2)。

    Returns:
        bool: 如果选择 "去激活" 返回 True，选择 "申请更高额度" 返回 False。
    """
    logging.info("\n" + "=" * 50)
    logging.info("步骤 7/8: 处理融资方案选择 (TIER2)")
    logging.info("=" * 50)

    # 等待页面加载
    WebDriverWait(driver, CONFIG.WAIT_TIMEOUT).until(
        EC.presence_of_element_located(LOCATORS["ACTIVATE_NOW_BTN"])
    )

    options = {
        '1': '去激活 (需填写银行账户信息)',
        '2': '申请更高额度 (跳过银行账户信息)'
    }
    choice = get_user_choice(options, "请选择融资方案:")

    if choice == '1':
        safe_click(driver, "ACTIVATE_NOW_BTN", "去激活按钮")
        return True  # 需要后续处理银行信息
    else:
        safe_click(driver, "APPLY_HIGHER_AMOUNT_BTN", "申请更高额度按钮")
        return False  # 不需要处理银行信息


# ==============================================================================
# --- 6. 主自动化流程 ---
# ==============================================================================

def run_automation(url: str, phone: str, tier_name: str):
    """
    自动化注册流程的主控制器。
    编排了从打开浏览器到完成所有步骤的整个流程。
    """
    driver = None
    try:
        # --- 步骤 2: 初始化浏览器 ---
        logging.info("\n" + "=" * 50)
        logging.info("步骤 2/8: 初始化浏览器")
        logging.info("=" * 50)

        browser_choice = get_user_choice(
            {'1': '谷歌浏览器 (Chrome)', '2': '微软浏览器 (Edge)'},
            "请选择用于自动化的浏览器:"
        )

        driver = init_browser(browser_choice)
        driver.set_page_load_timeout(CONFIG.WAIT_TIMEOUT)
        driver.implicitly_wait(CONFIG.WAIT_TIMEOUT)  # 设置隐式等待

        # --- 步骤 3: 访问URL并开始流程 ---
        logging.info(f"\n[UI] 正在访问URL: {url}")
        driver.get(url)
        time.sleep(CONFIG.ACTION_DELAY * 2)

        safe_click(driver, "INITIAL_APPLY_BTN", "初始页面的立即申请按钮")

        # --- 步骤 4: 填写初始注册信息 ---
        handle_initial_registration(driver, phone)

        # --- 步骤 5: 点击最终申请按钮 ---
        logging.info("\n" + "=" * 50)
        logging.info("步骤 4/8: 提交最终申请")
        logging.info("=" * 50)
        safe_click(driver, "FINAL_APPLY_BTN", "跳转页面后的立即申请按钮")

        # --- 步骤 6: 发起AUTH API请求 ---
        logging.info("\n" + "=" * 50)
        logging.info("步骤 5/8: 发起AUTH API请求")
        logging.info("=" * 50)
        auth_payload = {
            "phone": phone, "status": "ACTIVE", "dpu_token": "dpu_token",
            "sellerId": f"spshouquanfs{phone}", "authorization_code": "authorization_code",
            "refresh_token_expires_time": "2025-09-19T10:09:07.921Z",
            "access_token": "access_token sunt", "refresh_token": "refresh_token minim et anim sunt"
        }
        if not send_post_request(CONFIG.AUTH_POST_URL, payload=auth_payload):
            logging.warning("[流程] AUTH请求失败，可能会影响后续步骤。")

        # --- 步骤 7: 处理公司信息 ---
        auto_fill_company = input("\n[流程] 是否自动填写公司信息? (y/n): ").strip().lower() == 'y'
        handle_company_info(driver, auto_fill_company)

        # --- 步骤 8: 处理董事股东信息 ---
        auto_fill_director = input("\n[流程] 是否自动填写董事股东信息? (y/n): ").strip().lower() == 'y'
        handle_director_info(driver, phone, auto_fill_director)

        # --- 步骤 9: 根据TIER处理后续流程 ---
        need_bank_info = False
        if tier_name == "TIER2":
            need_bank_info = handle_financing_choice(driver)
        elif tier_name == "TIER1":
            need_bank_info = True

        if need_bank_info:
            auto_fill_bank = input("\n[流程] 是否自动填写银行账户信息? (y/n): ").strip().lower() == 'y'
            handle_bank_account_info(driver, auto_fill_bank)

        # --- 步骤 10: 发起关联店铺API请求 ---
        logging.info("\n" + "=" * 50)
        logging.info("步骤 8/8: 发起关联店铺API请求")
        logging.info("=" * 50)
        time.sleep(5)  # 等待页面状态稳定
        if send_post_request(CONFIG.LINK_SHOP_API_URL, phone=phone):
            logging.info("[API] 关联店铺请求成功！")
        else:
            logging.error("[API] 关联店铺请求失败！")

        # --- 流程结束 ---
        logging.info("\n" + "=" * 50)
        logging.info("🎉 所有自动化步骤已成功完成！")
        logging.info(f"📱 本次操作的手机号: {phone}")
        logging.info("ℹ️  浏览器将保持打开状态，供您手动检查。")
        logging.info("=" * 50)

        # 保持浏览器打开
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
                # 等待用户手动关闭或超时
                while True:
                    time.sleep(60)
            except KeyboardInterrupt:
                logging.info("\n[流程] 用户手动中断，正在关闭浏览器...")
                driver.quit()
                logging.info("[流程] 浏览器已关闭。")


def init_browser(browser_choice: str) -> webdriver.Remote:
    """
    根据用户选择初始化并返回一个浏览器驱动实例。

    Args:
        browser_choice (str): '1' 代表Chrome, '2' 代表Edge.

    Returns:
        webdriver.Remote: 一个配置好的Selenium WebDriver实例。
    """
    browser_name = "Chrome" if browser_choice == '1' else "Edge"
    logging.info(f"正在初始化 {browser_name} 浏览器 (无痕模式)...")

    if browser_choice == '1':
        options = ChromeOptions()
        options.add_argument("--incognito")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")  # 解决资源限制问题
        return webdriver.Chrome(options=options)
    elif browser_choice == '2':
        options = EdgeOptions()
        options.add_argument("--inprivate")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        return webdriver.Edge(options=options)
    else:
        raise ValueError(f"不支持的浏览器选择: {browser_choice}")


# ==============================================================================
# --- 7. 入口函数 ---
# ==============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("          HSBC API 数据生成与自动注册工具 (优化版)")
    print("=" * 60)

    setup_logging()

    # 生成测试数据
    test_url, test_phone, test_tier = generate_test_data()

    # 如果数据生成成功，则启动自动化流程
    if test_url and test_phone and test_tier:
        logging.info("\n✅ 测试数据生成成功，即将启动自动化注册流程...")
        run_automation(test_url, test_phone, test_tier)
    else:
        logging.error("\n❌ 测试数据生成失败，无法启动自动化流程。")

    logging.info("\n程序主流程结束。")