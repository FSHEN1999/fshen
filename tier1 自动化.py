"""
HSBC API 数据生成与自动注册工具
主要功能：
1. 生成测试数据（调用API获取offerId并生成URL和手机号）
2. 自动化完成注册流程（支持Chrome和Edge浏览器）
3. 支持TIER1级别的申请（包含额外的银行账户信息步骤）
4. 可配置的自动/手动填写选项，提高灵活性
"""

import time
import random
import os
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging

# --- 核心配置 (集中管理，便于修改和维护) ---
CONFIG = {
    "REQUEST_URL": "https://uat.api.expressfinance.business.hsbc.com/dpu-merchant/mock/generate-shop-performance",
    "REDIRECT_URL_PREFIX": "https://uat.api.expressfinance.business.hsbc.com/dpu-merchant/amazon/redirect?offerId=",
    "AUTH_POST_URL": "https://uat.api.expressfinance.business.hsbc.com/dpu-merchant/amz/sp/shop/auth",
    "LINK_SHOP_API_URL": "https://uat.api.expressfinance.business.hsbc.com/dpu-merchant/mock/link-sp-3pl-shops",
    "HEADERS": {"Content-Type": "application/json"},
    # 固定为TIER1级别（金额：120000）
    "TIER": {"NAME": "TIER1", "AMOUNT": 120000},
    "FILE_PATH": r"D:\data\project\test\uat tier1-run.txt",  # 数据存储文件路径
    "SCREENSHOT_FOLDER": r"C:\Users\PC\Desktop\截图",  # 身份证截图文件夹
    "WAIT_TIMEOUT": 30,  # 元素等待超时时间（秒）
    "ACTION_DELAY": 2,  # 操作间延迟时间（秒），提高稳定性
    "VERIFICATION_CODE": "666666"  # 固定验证码
}

# --- 日志配置 (清晰记录执行过程) ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- 元素定位器 (集中管理，便于维护) ---
LOCATORS = {
    "APPLY_BUTTON": (By.XPATH, "//button[contains(., '立即申请')]"),
    "PHONE_INPUT": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @maxlength='15']"),
    "VERIFICATION_CODES": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @maxlength='1']"),
    "EMAIL_INPUT": (By.XPATH,
                    "//input[contains(@class, 'el-input__inner') and @autocomplete='off' and not(@maxlength)]"),
    "AGREE_CHECKBOX": (By.XPATH, "//span[contains(@class, 'el-checkbox__inner')]"),
    "REGISTER_BUTTON": (By.XPATH, "//span[text()='立即注册']"),
    "FINAL_APPLY_BUTTON": (By.XPATH, "//button[contains(@class, 'application-btn') and .//span[text()='立即申请']]"),
    "NEXT_BUTTON": (By.XPATH, "//button[contains(., '下一页')]"),
    "COMPANY_EN_NAME_INPUT": (By.XPATH, "(//input[contains(@class, 'el-input__inner') and @autocomplete='off'])[1]"),
    "BUSINESS_REG_NO_INPUT": (By.XPATH, "(//input[contains(@class, 'el-input__inner') and @autocomplete='off'])[3]"),
    "ID_FRONT_UPLOAD": (By.XPATH,
                        "//div[contains(@class, 'el-upload-dragger') and .//img[contains(@src, 'PRC%20ID-Front')]]"),
    "ID_BACK_UPLOAD": (By.XPATH,
                       "//div[contains(@class, 'el-upload-dragger') and .//img[contains(@src, 'PRC%20ID-Back')]]"),
    "DATE_INPUT": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @placeholder='YYYY/MM/DD']"),
    "REFERENCE_PHONE_INPUT": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @maxlength='15']"),
    "REFERENCE_EMAIL_INPUT": (By.XPATH,
                              "//input[contains(@class, 'el-input__inner') and @autocomplete='off' and not(@maxlength) and not(@placeholder)]"),
    # 银行账户信息字段定位器（TIER1专属）
    "BANK_SELECT_INPUT": (By.XPATH, "//input[contains(@class, 'el-select__input') and @role='combobox']"),
    "BANK_SELECT_OPTION": (By.XPATH, "//li[contains(@class, 'el-select-dropdown__item')]"),
    "BANK_ACCOUNT_INPUT": (By.XPATH, "//input[contains(@class, 'el-input__inner') and @maxlength='12']")
}


# --- 工具函数 (封装通用操作，提高复用性) ---

def send_post_request(url, phone=None, payload=None):
    """
    发送POST请求的通用函数

    参数:
        url: 请求URL
        phone: 手机号（用于拼接URL参数）
        payload: 请求体数据

    返回:
        bool: 请求是否成功（状态码200）
    """
    try:
        # 拼接URL（如果有手机号参数）
        request_url = f"{url}?phone={phone}" if phone else url
        logging.info(f"[POST请求] 向 {request_url} 发送请求...")

        # 发送请求
        response = requests.post(
            request_url,
            json=payload,
            headers=CONFIG["HEADERS"],
            timeout=15
        )

        logging.info(f"[POST请求] 状态码: {response.status_code}, 响应: {response.text[:100]}...")
        return response.status_code == 200
    except Exception as e:
        logging.error(f"[POST请求] 失败: {e}")
        return False


def generate_test_data():
    """
    生成测试数据（调用API获取offerId，生成URL和手机号）

    返回:
        tuple: (url, phone, tier_name) 或 (None, None, None)（生成失败时）
    """
    logging.info("--- 步骤 1: 生成测试数据 ---")
    tier_name = CONFIG["TIER"]["NAME"]
    amount = CONFIG["TIER"]["AMOUNT"]
    logging.info(f"使用固定TIER级别: {tier_name} (金额: {amount})")

    try:
        # 调用API生成数据
        response = requests.post(
            CONFIG["REQUEST_URL"],
            json={"yearlyRepaymentAmount": amount},
            headers=CONFIG["HEADERS"],
            timeout=10
        )
        response.raise_for_status()  # 如果响应状态码不是2xx，会抛出异常

        data = response.json()
        # 从响应中获取offerId（处理不同的响应格式）
        offer_id = data.get("amazon3plOfferId") or data.get("data", {}).get("amazon3plOfferId")

        if not offer_id:
            raise ValueError("API响应中未获取到有效的offerId")

        # 生成随机手机号
        phone = f"182{random.randint(10000000, 99999999)}"
        # 生成跳转URL
        url = f"{CONFIG['REDIRECT_URL_PREFIX']}{offer_id}"

        # 保存数据到文件（修正换行问题）
        os.makedirs(os.path.dirname(CONFIG["FILE_PATH"]), exist_ok=True)
        with open(CONFIG["FILE_PATH"], "a", encoding="utf-8") as f:
            # 方式1：使用 \n 实现真实换行，多行拼接更易读
            f.write(
                #f"--- 新数据 ---\n"
                f"TIER: {tier_name}\n"
                f"URL: {url}\n"
                f"Phone: {phone}\n"
                f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                #f"--- 分隔符 ---\n\n"
            )

        logging.info(f"数据生成成功: URL={url}, Phone={phone}, TIER={tier_name}")
        return url, phone, tier_name

    except Exception as e:
        logging.error(f"数据生成失败: {e}")
        return None, None, None


def get_browser_choice():
    """
    获取用户选择的浏览器类型

    返回:
        str: 'chrome' 或 'edge'
    """
    print("\n请选择浏览器:")
    print("  1. 谷歌浏览器 (Chrome)")
    print("  2. 微软浏览器 (Edge)")

    # 循环获取有效输入
    while True:
        choice = input("请输入选项 (1/2): ").strip()
        if choice == '1':
            return 'chrome'
        elif choice == '2':
            return 'edge'
        print("输入无效，请选择 1 或 2。")


def init_browser(browser_type):
    """
    初始化浏览器（无痕模式）

    参数:
        browser_type: 浏览器类型 ('chrome' 或 'edge')

    返回:
        WebDriver: 浏览器驱动实例
    """
    logging.info(f"--- 初始化 {browser_type.capitalize()} 浏览器 (无痕模式) ---")

    if browser_type == 'chrome':
        options = ChromeOptions()
        options.add_argument("--incognito")  # 无痕模式
        options.add_argument("--disable-gpu")  # 禁用GPU加速（解决某些环境问题）
        options.add_argument("--no-sandbox")  # 禁用沙箱模式（解决Linux环境问题）
        options.add_argument("--disable-dev-shm-usage")  # 禁用/dev/shm使用（解决资源限制问题）
        return webdriver.Chrome(options=options)

    elif browser_type == 'edge':
        options = EdgeOptions()
        options.add_argument("--inprivate")  # 无痕模式
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        return webdriver.Edge(options=options)

    else:
        raise ValueError(f"不支持的浏览器类型: {browser_type}")


def safe_click(driver, locator_key, description):
    """
    安全点击元素（处理元素不可见、不可点击等问题）

    参数:
        driver: 浏览器驱动实例
        locator_key: 元素定位器键（来自LOCATORS字典）
        description: 元素描述（用于日志记录）
    """
    try:
        locator = LOCATORS[locator_key]
        # 等待元素可点击
        element = WebDriverWait(driver, CONFIG["WAIT_TIMEOUT"]).until(
            EC.element_to_be_clickable(locator)
        )

        # 滚动到元素可见位置
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        time.sleep(CONFIG["ACTION_DELAY"])

        # 尝试常规点击，如果失败则使用JavaScript点击
        try:
            element.click()
        except:
            logging.warning(f"常规点击 '{description}' 失败，尝试使用JavaScript点击。")
            driver.execute_script("arguments[0].click();", element)

        logging.info(f"已点击: {description}")

    except Exception as e:
        logging.error(f"点击 '{description}' 失败: {e}")
        raise  # 抛出异常，让调用者处理


def safe_send_keys(driver, locator_key, text, description):
    """
    安全输入文本（处理元素不可见、清空输入框等问题）

    参数:
        driver: 浏览器驱动实例
        locator_key: 元素定位器键
        text: 要输入的文本
        description: 元素描述
    """
    try:
        locator = LOCATORS[locator_key]
        # 等待元素可见
        element = WebDriverWait(driver, CONFIG["WAIT_TIMEOUT"]).until(
            EC.visibility_of_element_located(locator)
        )

        # 清空输入框并输入文本
        element.clear()
        element.send_keys(text)

        logging.info(f"已填写 {description}: {text}")

    except Exception as e:
        logging.error(f"填写 '{description}' 失败: {e}")
        raise


def upload_image(driver, locator_key, description):
    """
    上传图片（处理上传控件定位问题）

    参数:
        driver: 浏览器驱动实例
        locator_key: 元素定位器键
        description: 元素描述
    """
    try:
        # 等待上传控件可见
        WebDriverWait(driver, CONFIG["WAIT_TIMEOUT"]).until(
            EC.visibility_of_element_located(LOCATORS[locator_key])
        )

        # 获取截图文件夹中的第一个PNG文件
        png_files = [f for f in os.listdir(CONFIG["SCREENSHOT_FOLDER"]) if f.lower().endswith('.png')]
        if not png_files:
            raise FileNotFoundError(f"在 '{CONFIG['SCREENSHOT_FOLDER']}' 中未找到PNG格式的图片")

        # 获取图片绝对路径
        image_path = os.path.abspath(os.path.join(CONFIG["SCREENSHOT_FOLDER"], png_files[0]))

        # 定位文件输入框并上传图片（上传控件通常是隐藏的input[type="file"]）
        file_input = driver.execute_script("return document.querySelector('input[type=\"file\"]');")
        file_input.send_keys(image_path)

        time.sleep(CONFIG["ACTION_DELAY"] * 3)  # 等待上传完成
        logging.info(f"图片上传操作已执行: {description} ({os.path.basename(image_path)})")

    except Exception as e:
        logging.error(f"图片上传操作执行失败: {description}, 错误: {e}")
        raise


# --- 流程处理函数 (封装各步骤逻辑，提高可读性) ---

def fill_initial_info(driver, phone):
    """
    填写初始注册信息（手机号、验证码、邮箱等）

    参数:
        driver: 浏览器驱动实例
        phone: 手机号
    """
    logging.info("\n--- 步骤 3: 填写初始注册信息 ---")

    # 填写手机号
    safe_send_keys(driver, "PHONE_INPUT", phone, "手机号")

    # 填写验证码（多个输入框）
    verification_inputs = WebDriverWait(driver, CONFIG["WAIT_TIMEOUT"]).until(
        EC.visibility_of_all_elements_located(LOCATORS["VERIFICATION_CODES"])
    )

    for i, code in enumerate(CONFIG["VERIFICATION_CODE"]):
        if i < len(verification_inputs):
            verification_inputs[i].send_keys(code)

    logging.info(f"已填写验证码: {CONFIG['VERIFICATION_CODE']}")
    time.sleep(CONFIG["ACTION_DELAY"])

    # 填写邮箱（手机号+@qq.com）
    email = f"{phone}@qq.com"
    safe_send_keys(driver, "EMAIL_INPUT", email, "邮箱")

    # 同意条款
    safe_click(driver, "AGREE_CHECKBOX", "同意条款")

    # 立即注册
    safe_click(driver, "REGISTER_BUTTON", "立即注册")

    time.sleep(CONFIG["ACTION_DELAY"] * 3)  # 等待注册完成跳转


def handle_company_info(driver, auto_fill):
    """
    处理公司信息页面

    参数:
        driver: 浏览器驱动实例
        auto_fill: 是否自动填写（True/False）
    """
    logging.info("\n--- 步骤 5: 处理公司信息 ---")

    # 等待公司信息页面加载完成
    WebDriverWait(driver, CONFIG["WAIT_TIMEOUT"]).until(
        EC.presence_of_element_located(LOCATORS["COMPANY_EN_NAME_INPUT"])
    )

    if auto_fill:
        logging.info("开始自动填写公司信息...")

        # 填写公司英文名称（示例数据）
        safe_send_keys(driver, "COMPANY_EN_NAME_INPUT", "123", "公司英文名称")
        time.sleep(2)

        # 填写商业登记号码（示例数据）
        safe_send_keys(driver, "BUSINESS_REG_NO_INPUT", "11111111", "商业登记号码")
        time.sleep(2)

        logging.info("公司信息填写完毕，准备点击下一步。")
    else:
        input("\n请手动填写公司信息后，按Enter键继续...")

    # 点击下一步
    safe_click(driver, "NEXT_BUTTON", "公司信息页下一页")


def handle_director_info(driver, phone, auto_fill):
    """
    处理董事股东信息页面

    参数:
        driver: 浏览器驱动实例
        phone: 手机号（用于填写参考信息）
        auto_fill: 是否自动填写（True/False）
    """
    logging.info("\n--- 步骤 6: 处理董事股东信息 ---")

    # 等待董事股东信息页面加载完成
    WebDriverWait(driver, CONFIG["WAIT_TIMEOUT"]).until(
        EC.presence_of_element_located(LOCATORS["ID_FRONT_UPLOAD"])
    )

    if auto_fill:
        logging.info("开始自动填写董事股东信息...")

        # 上传身份证正面
        upload_image(driver, "ID_FRONT_UPLOAD", "身份证正面")
        time.sleep(2)

        # 上传身份证背面
        upload_image(driver, "ID_BACK_UPLOAD", "身份证背面")
        time.sleep(2)

        # 填写日期（示例数据）
        safe_send_keys(driver, "DATE_INPUT", "2025/01/01", "日期")

        # 填写参考手机号
        safe_send_keys(driver, "REFERENCE_PHONE_INPUT", phone, "参考手机号")

        # 填写参考邮箱
        email = f"{phone}@qq.com"
        safe_send_keys(driver, "REFERENCE_EMAIL_INPUT", email, "参考邮箱")

        time.sleep(CONFIG["ACTION_DELAY"])
        logging.info("董事股东信息填写完毕，准备点击下一步。")
    else:
        input("\n请手动填写董事股东信息并上传身份证后，按Enter键继续...")

    # 点击下一步
    safe_click(driver, "NEXT_BUTTON", "董事股东信息页下一页")


def handle_bank_info(driver, auto_fill):
    """
    处理银行账户信息页面（TIER1专属）

    参数:
        driver: 浏览器驱动实例
        auto_fill: 是否自动填写（True/False）
    """
    logging.info("\n--- 步骤 7: 处理银行账户信息 (TIER1专属) ---")

    # 等待银行账户信息页面加载完成
    WebDriverWait(driver, CONFIG["WAIT_TIMEOUT"]).until(
        EC.presence_of_element_located(LOCATORS["BANK_SELECT_INPUT"])
    )

    if auto_fill:
        logging.info("开始自动填写银行账户信息...")

        # 选择银行
        logging.info("正在选择银行...")
        safe_click(driver, "BANK_SELECT_INPUT", "银行选择下拉框")

        # 等待下拉选项加载，并选择第一个可见的选项
        try:
            options = WebDriverWait(driver, CONFIG["WAIT_TIMEOUT"]).until(
                EC.presence_of_all_elements_located(LOCATORS["BANK_SELECT_OPTION"])
            )

            if options:
                # 随机选择一个选项
                selected_option_index = random.randint(0, len(options) - 1)
                selected_option_text = options[selected_option_index].text

                # 滚动到选项可见位置并点击
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'nearest'});",
                                      options[selected_option_index])
                time.sleep(CONFIG["ACTION_DELAY"])
                options[selected_option_index].click()

                logging.info(f"已选择银行: {selected_option_text}")
            else:
                raise ValueError("下拉列表中没有找到任何银行选项。")

        except Exception as e:
            logging.error(f"选择银行失败: {e}")
            raise

        time.sleep(2)

        # 填写银行账号（12位随机数字）
        bank_account = f"{random.randint(100000000000, 999999999999)}"
        safe_send_keys(driver, "BANK_ACCOUNT_INPUT", bank_account, "银行账号")

        logging.info("银行账户信息填写完毕，准备点击下一步。")
    else:
        input("\n请手动选择银行并填写账户号码后，按Enter键继续...")

    # 点击下一步
    safe_click(driver, "NEXT_BUTTON", "银行信息页下一页")


# --- 主自动化流程 ---

def automate_signup(url, phone, tier_name):
    """
    自动化注册流程主函数

    参数:
        url: 跳转URL
        phone: 手机号
        tier_name: TIER级别名称
    """
    logging.info("\n--- 步骤 2: 选择浏览器 ---")
    browser_type = get_browser_choice()

    # 初始化浏览器
    driver = init_browser(browser_type)
    driver.set_page_load_timeout(CONFIG["WAIT_TIMEOUT"])

    try:
        # 访问跳转URL
        driver.get(url)
        time.sleep(CONFIG["ACTION_DELAY"] * 2)

        # 点击初始页面的立即申请
        safe_click(driver, "APPLY_BUTTON", "初始页面立即申请")

        # 填写初始注册信息
        fill_initial_info(driver, phone)

        # 点击跳转页面的立即申请
        safe_click(driver, "FINAL_APPLY_BUTTON", "跳转页面立即申请")

        # 发起AUTH POST请求
        logging.info("\n--- 步骤 4: 发起AUTH POST请求 ---")
        send_post_request(
            CONFIG["AUTH_POST_URL"],
            None,
            payload={
                "phone": phone,
                "status": "ACTIVE",
                "dpu_token": "dpu_token",
                "sellerId": f"spshouquanfs{phone}",
                "authorization_code": "authorization_code",
                "refresh_token_expires_time": "2025-09-19T10:09:07.921Z",
                "access_token": "access_token sunt",
                "refresh_token": "refresh_token minim et anim sunt"
            }
        )

        # 处理公司信息
        auto_fill_company = input("\n是否自动化填写公司信息？(y/n): ").strip().lower() == 'y'
        handle_company_info(driver, auto_fill_company)

        # 处理董事股东信息
        auto_fill_director = input("\n是否自动化填写董事股东信息？(y/n): ").strip().lower() == 'y'
        handle_director_info(driver, phone, auto_fill_director)

        # TIER1专属：处理银行账户信息
        if tier_name == "TIER1":
            auto_fill_bank = input("\n是否自动化填写银行账户信息？(y/n): ").strip().lower() == 'y'
            handle_bank_info(driver, auto_fill_bank)

        # 发起关联店铺请求
        logging.info("\n--- 步骤 8: 等待并发起关联店铺请求 ---")
        time.sleep(5)
        if send_post_request(CONFIG["LINK_SHOP_API_URL"], phone):
            logging.info("关联店铺请求成功！")

        # 流程完成
        logging.info(f"\n🎉 所有自动化步骤已完成！手机号: {phone}")
        logging.info("浏览器保持打开状态，以便手动检查...")

    except Exception as e:
        logging.error(f"\n❌ 自动化流程异常终止: {e}")
        # 保存错误截图
        error_screenshot = f"error_final_{phone}_{browser_type}_{time.strftime('%Y%m%d%H%M%S')}.png"
        driver.save_screenshot(error_screenshot)
        logging.error(f"错误状态截图已保存至: {error_screenshot}")

    finally:
        # 保持浏览器打开，直到用户手动关闭
        while True:
            time.sleep(1000)


# --- 入口函数 ---
if __name__ == "__main__":
    print("=== HSBC API 数据生成与自动注册工具 ===")
    print(f"当前固定TIER级别: {CONFIG['TIER']['NAME']} (金额: {CONFIG['TIER']['AMOUNT']})")

    test_url, test_phone, test_tier = generate_test_data()
    if test_url and test_phone and test_tier:
        logging.info("自动注册流程已启动...")
        automate_signup(test_url, test_phone, test_tier)
    else:
        logging.error("数据生成失败，无法启动自动注册流程。")

    logging.info("\n主流程结束。")