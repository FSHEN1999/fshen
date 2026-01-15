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

# --- 核心配置 ---
CONFIG = {
    "REQUEST_URL": "https://uat.api.expressfinance.business.hsbc.com/dpu-merchant/mock/generate-shop-performance",
    "REDIRECT_URL_PREFIX": "https://uat.api.expressfinance.business.hsbc.com/dpu-merchant/amazon/redirect?offerId=",
    "AUTH_POST_URL": "https://uat.api.expressfinance.business.hsbc.com/dpu-merchant/amz/sp/shop/auth",
    "LINK_SHOP_API_URL": "https://uat.api.expressfinance.business.hsbc.com/dpu-merchant/mock/link-sp-3pl-shops",
    "HEADERS": {"Content-Type": "application/json"},
    "TIER": ("TIER3", 2000000),  # 固定选择TIER3
    "FILE_PATH": r"D:\data\project\test\uat tier3-run.txt",
    "SCREENSHOT_FOLDER": r"C:\Users\PC\Desktop\截图",
    "WAIT_TIMEOUT": 30,  # 元素等待超时时间
    "ACTION_DELAY": 2  # 操作间隔时间
}

# --- 日志配置 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- 元素定位器 ---
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
                              "//input[contains(@class, 'el-input__inner') and @autocomplete='off' and not(@maxlength) and not(@placeholder)]")
}


# --- 工具函数 ---
def send_post_request(url, phone=None, payload=None):
    """发送POST请求并返回是否成功"""
    try:
        request_url = f"{url}?phone={phone}" if phone else url
        logging.info(f"[POST请求] 向 {request_url} 发送请求...")
        response = requests.post(request_url, json=payload, headers=CONFIG["HEADERS"], timeout=15)
        logging.info(f"[POST请求] 状态码: {response.status_code}, 响应: {response.text[:100]}...")
        return response.status_code == 200
    except Exception as e:
        logging.error(f"[POST请求] 失败: {e}")
        return False


def generate_test_data():
    """生成测试数据（固定TIER3）并保存到文件"""
    logging.info("--- 步骤 1: 生成测试数据 ---")
    tier_name, amount = CONFIG["TIER"]
    logging.info(f"使用固定TIER: {tier_name} (金额: {amount})")

    try:
        # 发送请求获取offerId
        response = requests.post(
            CONFIG["REQUEST_URL"],
            json={"yearlyRepaymentAmount": amount},
            headers=CONFIG["HEADERS"],
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        # 提取offerId（兼容不同响应格式）
        offer_id = data.get("amazon3plOfferId") or data.get("data", {}).get("amazon3plOfferId")
        if not offer_id:
            raise ValueError("API响应中未获取到有效的offerId")

        # 生成随机手机号和URL
        phone = f"182{random.randint(10000000, 99999999)}"
        url = f"{CONFIG['REDIRECT_URL_PREFIX']}{offer_id}"

        # 保存数据到文件
        os.makedirs(os.path.dirname(CONFIG["FILE_PATH"]), exist_ok=True)
        with open(CONFIG["FILE_PATH"], "a", encoding="utf-8") as f:
            f.write(
                f"--- 新数据 ---\n"
                f"TIER: {tier_name}\n"
                f"URL: {url}\n"
                f"Phone: {phone}\n"
                f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"--- 分隔符 ---\n\n"
            )

        logging.info(f"数据生成成功: URL={url}, Phone={phone}")
        return url, phone
    except Exception as e:
        logging.error(f"数据生成失败: {e}")
        return None, None


def get_browser_choice():
    """获取用户选择的浏览器类型"""
    print("\n请选择浏览器:")
    print("  1. 谷歌浏览器 (Chrome)")
    print("  2. 微软浏览器 (Edge)")

    while True:
        choice = input("请输入选项 (1/2): ").strip()
        if choice == '1':
            return 'chrome'
        elif choice == '2':
            return 'edge'
        print("输入无效，请选择 1 或 2。")


def init_browser(browser_type):
    """初始化指定类型的浏览器（无痕模式）"""
    logging.info(f"--- 初始化 {browser_type.capitalize()} 浏览器 (无痕模式) ---")
    if browser_type == 'chrome':
        options = ChromeOptions()
        options.add_argument("--incognito")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        return webdriver.Chrome(options=options)
    elif browser_type == 'edge':
        options = EdgeOptions()
        options.add_argument("--inprivate")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        return webdriver.Edge(options=options)
    else:
        raise ValueError(f"不支持的浏览器类型: {browser_type}")


def safe_click(driver, locator_key, description):
    """安全点击元素（等待可点击状态，支持JS点击）"""
    try:
        locator = LOCATORS[locator_key]
        element = WebDriverWait(driver, CONFIG["WAIT_TIMEOUT"]).until(
            EC.element_to_be_clickable(locator)
        )
        # 滚动到元素可见位置
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        time.sleep(CONFIG["ACTION_DELAY"])

        # 尝试常规点击，失败则用JS点击
        try:
            element.click()
        except:
            logging.warning(f"常规点击 '{description}' 失败，尝试使用JavaScript点击。")
            driver.execute_script("arguments[0].click();", element)

        logging.info(f"已点击: {description}")
        return True
    except Exception as e:
        logging.error(f"点击 '{description}' 失败: {e}")
        raise


def safe_send_keys(driver, locator_key, text, description):
    """安全输入文本（等待元素可见，清空后输入）"""
    try:
        locator = LOCATORS[locator_key]
        element = WebDriverWait(driver, CONFIG["WAIT_TIMEOUT"]).until(
            EC.visibility_of_element_located(locator)
        )
        element.clear()
        element.send_keys(text)
        logging.info(f"已填写 {description}: {text}")
        return True
    except Exception as e:
        logging.error(f"填写 '{description}' 失败: {e}")
        raise


def upload_image(driver, locator_key, description):
    """上传图片（从指定文件夹选择第一张PNG图片）"""
    try:
        # 等待上传控件可见
        WebDriverWait(driver, CONFIG["WAIT_TIMEOUT"]).until(
            EC.visibility_of_element_located(LOCATORS[locator_key])
        )

        # 获取文件夹中第一张PNG图片
        png_files = [f for f in os.listdir(CONFIG["SCREENSHOT_FOLDER"]) if f.lower().endswith('.png')]
        if not png_files:
            raise FileNotFoundError(f"在 '{CONFIG['SCREENSHOT_FOLDER']}' 中未找到PNG格式的图片")

        # 上传图片
        image_path = os.path.abspath(os.path.join(CONFIG["SCREENSHOT_FOLDER"], png_files[0]))
        file_input = driver.execute_script("return document.querySelector('input[type=\"file\"]');")
        file_input.send_keys(image_path)
        time.sleep(CONFIG["ACTION_DELAY"] * 3)  # 等待上传完成

        logging.info(f"图片上传成功: {description} ({os.path.basename(image_path)})")
        return True
    except Exception as e:
        logging.error(f"图片上传失败: {description}, 错误: {e}")
        raise


# --- 流程函数 ---
def fill_initial_info(driver, phone):
    """填写初始注册信息（手机号、验证码、邮箱等）"""
    logging.info("\n--- 步骤 3: 填写初始注册信息 ---")
    safe_send_keys(driver, "PHONE_INPUT", phone, "手机号")

    # 填写验证码（固定为666666）
    verification_inputs = WebDriverWait(driver, CONFIG["WAIT_TIMEOUT"]).until(
        EC.visibility_of_all_elements_located(LOCATORS["VERIFICATION_CODES"])
    )
    for i, code in enumerate("666666"):
        if i < len(verification_inputs):
            verification_inputs[i].send_keys(code)
    logging.info("已填写验证码: 666666")

    time.sleep(CONFIG["ACTION_DELAY"])
    safe_send_keys(driver, "EMAIL_INPUT", f"{phone}@qq.com", "邮箱")
    safe_click(driver, "AGREE_CHECKBOX", "同意条款")
    safe_click(driver, "REGISTER_BUTTON", "立即注册")
    time.sleep(CONFIG["ACTION_DELAY"] * 3)


def handle_company_info(driver, auto_fill):
    """处理公司信息页面（支持自动/手动填写）"""
    logging.info("\n--- 步骤 5: 处理公司信息 ---")
    WebDriverWait(driver, CONFIG["WAIT_TIMEOUT"]).until(
        EC.presence_of_element_located(LOCATORS["COMPANY_EN_NAME_INPUT"])
    )

    if auto_fill:
        logging.info("开始自动填写公司信息...")
        safe_send_keys(driver, "COMPANY_EN_NAME_INPUT", "123", "公司英文名称")
        time.sleep(5)
        safe_send_keys(driver, "BUSINESS_REG_NO_INPUT", "11111111", "商业登记号码")
        logging.info("公司信息填写完毕")
    else:
        input("\n请手动填写公司信息后，按Enter键继续...")

    safe_click(driver, "NEXT_BUTTON", "公司信息页下一页")


def handle_director_info(driver, phone, email, auto_fill):
    """处理董事股东信息页面（支持自动/手动填写）"""
    logging.info("\n--- 步骤 6: 处理董事股东信息 ---")
    WebDriverWait(driver, CONFIG["WAIT_TIMEOUT"]).until(
        EC.presence_of_element_located(LOCATORS["ID_FRONT_UPLOAD"])
    )

    if auto_fill:
        logging.info("开始自动填写董事股东信息...")
        upload_image(driver, "ID_FRONT_UPLOAD", "身份证正面")
        upload_image(driver, "ID_BACK_UPLOAD", "身份证背面")

        safe_send_keys(driver, "DATE_INPUT", "2025/01/01", "日期")
        safe_send_keys(driver, "REFERENCE_PHONE_INPUT", phone, "手机号")
        safe_send_keys(driver, "REFERENCE_EMAIL_INPUT", email, "邮箱")
        logging.info("董事股东信息填写完毕")
    else:
        input("\n请手动填写董事股东信息并上传身份证后，按Enter键继续...")

    safe_click(driver, "NEXT_BUTTON", "董事股东信息页下一页")


# --- 主自动化流程 ---
def automate_signup(url, phone):
    """自动化注册流程主函数"""
    logging.info("\n--- 步骤 2: 选择浏览器 ---")
    browser_type = get_browser_choice()
    driver = init_browser(browser_type)
    driver.set_page_load_timeout(CONFIG["WAIT_TIMEOUT"])
    email = f"{phone}@qq.com"

    try:
        # 访问生成的URL
        driver.get(url)
        time.sleep(CONFIG["ACTION_DELAY"] * 2)

        # 点击初始申请按钮
        safe_click(driver, "APPLY_BUTTON", "初始页面立即申请")

        # 填写初始注册信息
        fill_initial_info(driver, phone)

        # 点击最终申请按钮
        safe_click(driver, "FINAL_APPLY_BUTTON", "跳转页面立即申请")

        # 发起AUTH POST请求
        logging.info("\n--- 步骤 4: 发起AUTH POST请求 ---")
        send_post_request(CONFIG["AUTH_POST_URL"], None, payload={
            "phone": phone,
            "status": "ACTIVE",
            "dpu_token": "dpu_token",
            "sellerId": f"spshouquanfs{phone}",
            "authorization_code": "authorization_code",
            "refresh_token_expires_time": "2025-09-19T10:09:07.921Z",
            "access_token": "access_token sunt",
            "refresh_token": "refresh_token minim et anim sunt"
        })

        # 处理公司信息（询问是否自动填写）
        auto_fill_company = input("\n是否自动化填写公司信息？(y/n): ").strip().lower() == 'y'
        handle_company_info(driver, auto_fill_company)

        # 处理董事股东信息（询问是否自动填写）
        auto_fill_director = input("\n是否自动化填写董事股东信息？(y/n): ").strip().lower() == 'y'
        handle_director_info(driver, phone, email, auto_fill_director)

        # 发起关联店铺请求
        logging.info("\n--- 步骤 7: 发起关联店铺请求 ---")
        time.sleep(5)
        if send_post_request(CONFIG["LINK_SHOP_API_URL"], phone):
            logging.info("关联店铺请求成功！")

        logging.info(f"\n🎉 所有自动化步骤已完成！手机号: {phone}")
        logging.info("浏览器保持打开状态，以便手动检查...")

    except Exception as e:
        logging.error(f"\n❌ 自动化流程异常终止: {e}")
        # 保存错误截图
        error_screenshot = f"error_final_{phone}_{browser_type}_{time.strftime('%Y%m%d%H%M%S')}.png"
        driver.save_screenshot(error_screenshot)
        logging.error(f"错误截图已保存至: {error_screenshot}")
    finally:
        # 保持浏览器打开
        while True:
            time.sleep(1000)


# --- 入口函数 ---
if __name__ == "__main__":
    print("=== HSBC API 数据生成与自动注册工具 ===")
    test_url, test_phone = generate_test_data()
    if test_url and test_phone:
        logging.info("自动注册流程已启动...")
        automate_signup(test_url, test_phone)
    logging.info("\n主流程结束。")