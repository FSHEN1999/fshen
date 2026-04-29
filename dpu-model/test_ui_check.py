"""
UI检查脚本 - 用Selenium浏览器打开每个页面截图检查
"""
import sys, io, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from selenium import webdriver
from selenium.webdriver.common.by import By
import requests

BASE_URL = "http://localhost:3000"
API_URL = "http://localhost:8001"
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def screenshot(driver, name):
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    driver.save_screenshot(path)
    print(f"  截图已保存: {path}")
    return path

def check(driver, by, value, desc):
    try:
        el = driver.find_element(by, value)
        visible = el.is_displayed()
        print(f"  {'✓' if visible else '✗'} {desc} - {'可见' if visible else '不可见'}")
        return visible
    except:
        print(f"  ✗ {desc} - 未找到")
        return False

def check_css(driver, selector, prop, expected, desc):
    try:
        el = driver.find_element(By.CSS_SELECTOR, selector)
        val = el.value_of_css_property(prop)
        ok = expected.lower() in val.lower() if expected else bool(val)
        print(f"  {'✓' if ok else '✗'} {desc}: {val}")
        return ok
    except Exception as e:
        print(f"  ✗ {desc}: 未找到 ({e})")
        return False

def count_elements(driver, selector, desc):
    els = driver.find_elements(By.CSS_SELECTOR, selector)
    print(f"  {desc}: {len(els)}")
    return len(els)

def main():
    print("=" * 60)
    print("DPU借款平台 - UI全面检查（新版）")
    print("=" * 60)

    options = webdriver.ChromeOptions()
    options.add_argument('--window-size=1400,900')
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(3)
    issues = []

    try:
        # ===== 1. 登录页 =====
        print("\n【1】登录页检查")
        driver.get(BASE_URL + "/login")
        time.sleep(2)
        screenshot(driver, "01_login")

        check(driver, By.CSS_SELECTOR, ".hsbc-logo svg", "HSBC Logo SVG")
        check(driver, By.CSS_SELECTOR, ".logo-text", "Logo文字")
        check(driver, By.CSS_SELECTOR, ".country-code", "国区号+86")
        check(driver, By.CSS_SELECTOR, ".phone-input", "手机号输入框")
        check(driver, By.CSS_SELECTOR, ".code-boxes", "6位验证码输入框")
        check(driver, By.CSS_SELECTOR, ".get-code-btn", "Get code按钮")
        check_css(driver, ".btn-next", "background-color", "219, 0, 17", "Next按钮HSBC红")
        check(driver, By.CSS_SELECTOR, ".cover-image", "右侧封面图")
        check(driver, By.CSS_SELECTOR, ".hsbc-footer", "页脚")

        # 切换到登录模式
        try:
            link = driver.find_element(By.CSS_SELECTOR, ".account-link a")
            link.click()
            time.sleep(0.5)
            screenshot(driver, "01b_login_mode")
            check(driver, By.CSS_SELECTOR, ".password-wrap", "密码输入框")
            check(driver, By.CSS_SELECTOR, ".pwd-toggle", "密码显隐切换")
            if not check(driver, By.CSS_SELECTOR, ".forgot-link", "忘记密码"):
                issues.append("登录页缺少忘记密码入口")
            if not check(driver, By.CSS_SELECTOR, ".auto-login", "自动登录勾选"):
                issues.append("登录页缺少自动登录勾选框")
        except:
            issues.append("无法切换到登录模式")

        # ===== 2. 注册页 =====
        print("\n【2】注册页检查")
        driver.get(BASE_URL + "/register")
        time.sleep(2)
        screenshot(driver, "02_register")

        n = count_elements(driver, ".section-block", "红色左边框分区块数")
        if n < 4:
            issues.append(f"注册页分区块不足，期望>=4，实际{n}")
        count_elements(driver, ".pwd-rules li", "密码规则条数")
        check(driver, By.CSS_SELECTOR, ".rule-dot", "规则圆点指示器")
        count_elements(driver, ".pwd-eye", "眼睛图标数")
        check(driver, By.CSS_SELECTOR, "select.field-input", "安全问题下拉框")
        check(driver, By.CSS_SELECTOR, ".declaration-text", "声明文字")
        check(driver, By.CSS_SELECTOR, ".btn-signup", "Sign up按钮")
        check_css(driver, ".btn-signup", "background-color", "219, 0, 17", "Sign up按钮HSBC红")

        # ===== 3. 获取登录token =====
        print("\n【3】登录获取token")
        phone = "18222195858"
        r = requests.post(f"{API_URL}/api/auth/sms-code", json={"phone": phone})
        sms_data = r.json()
        code = sms_data.get("data", {}).get("code", "")
        print(f"  验证码: {code}")

        if not code:
            import random
            phone = f"1822219{random.randint(1000,9999)}"
            r = requests.post(f"{API_URL}/api/auth/sms-code", json={"phone": phone})
            sms_data = r.json()
            code = sms_data.get("data", {}).get("code", "")
            r = requests.post(f"{API_URL}/api/auth/register", json={
                "phone": phone, "code": code,
                "password": "Aa11111111", "confirm_password": "Aa11111111"
            })
            print(f"  注册新号: {phone}")
            r = requests.post(f"{API_URL}/api/auth/sms-code", json={"phone": phone})
            sms_data = r.json()
            code = sms_data.get("data", {}).get("code", "")

        r = requests.post(f"{API_URL}/api/auth/login/sms", json={"phone": phone, "code": code})
        login_data = r.json()
        token = login_data.get("data", {}).get("access_token", "")
        if not token:
            r = requests.post(f"{API_URL}/api/auth/login/password", json={"phone": phone, "password": "Aa11111111"})
            login_data = r.json()
            token = login_data.get("data", {}).get("access_token", "")
        print(f"  登录: {'成功' if token else '失败'}")

        if not token:
            issues.append("无法获取登录token")
            raise Exception("无法登录")

        # 注入token
        driver.get(BASE_URL + "/login")
        time.sleep(1)
        driver.execute_script(f"""
            localStorage.setItem('dpu_token', '{token}');
            localStorage.setItem('dpu_phone', '{phone}');
        """)
        headers = {"Authorization": f"Bearer {token}"}

        # ===== 4. Dashboard =====
        print("\n【4】Dashboard检查")
        driver.get(BASE_URL + "/dashboard")
        time.sleep(2)
        screenshot(driver, "04_dashboard")

        check(driver, By.CSS_SELECTOR, ".dash-header", "红色顶部导航")
        check_css(driver, ".dash-header", "background-color", "219, 0, 17", "导航栏HSBC红色")
        check(driver, By.CSS_SELECTOR, ".dash-nav .nav-item", "导航项")
        check(driver, By.CSS_SELECTOR, ".logout-link", "Log out链接")
        check(driver, By.CSS_SELECTOR, ".welcome-banner", "欢迎横幅")
        check(driver, By.CSS_SELECTOR, ".offer-card", "额度卡片")
        check(driver, By.CSS_SELECTOR, ".limit-amount", "预批额度数字")
        check(driver, By.CSS_SELECTOR, ".btn-apply", "Apply now按钮")
        check_css(driver, ".btn-apply", "background-color", "219, 0, 17", "Apply按钮HSBC红")
        check(driver, By.CSS_SELECTOR, ".steps-title", "步骤标题")
        count_elements(driver, ".step-item", "步骤项数")
        count_elements(driver, ".accordion-header", "手风琴项数")
        check(driver, By.CSS_SELECTOR, ".borrow-warning", "风险提示")
        check(driver, By.CSS_SELECTOR, ".dash-footer", "页脚")

        # ===== 5. Business Information页 =====
        print("\n【5】Business Information页检查")
        driver.get(BASE_URL + "/info")
        time.sleep(2)
        screenshot(driver, "05_info")

        check(driver, By.CSS_SELECTOR, ".progress-bar-wrap", "进度条区域")
        check(driver, By.CSS_SELECTOR, ".progress-fill", "红色进度条")
        t = driver.find_element(By.CSS_SELECTOR, ".page-title").text
        print(f"  页面标题: {t}")
        if "Business" not in t:
            issues.append(f"Info页标题不正确: {t}")
        check(driver, By.CSS_SELECTOR, ".privacy-note", "隐私提示")

        n = count_elements(driver, ".section-block", "红色左边框分区块数")
        if n < 2:
            issues.append(f"Info页分区块不足，期望>=2，实际{n}")

        # 检查第一个分区标题
        heading = driver.find_element(By.CSS_SELECTOR, ".section-heading").text
        print(f"  第一分区标题: {heading}")
        check_css(driver, ".section-block", "border-left-color", "219, 0, 17", "红色左边框")

        # 标签选择器
        count_elements(driver, ".tag-item", "国家标签数量")
        count_elements(driver, ".tag-item.active", "已选中标签数量")

        # 复选框组
        count_elements(driver, ".checkbox-group", "复选框组数")
        count_elements(driver, ".checkbox-label", "复选项总数")

        # 声明和底部栏
        check(driver, By.CSS_SELECTOR, ".declaration-block", "声明文字")
        check(driver, By.CSS_SELECTOR, ".bottom-bar", "固定底部操作栏")
        check_css(driver, ".bottom-bar", "position", "fixed", "底部栏fixed定位")
        check(driver, By.CSS_SELECTOR, ".bar-link", "Back/Save链接")
        check(driver, By.CSS_SELECTOR, ".btn-next", "Next按钮")
        check_css(driver, ".btn-next", "background-color", "219, 0, 17", "Next按钮HSBC红")
        check(driver, By.CSS_SELECTOR, ".page-footer", "页脚")

        # 滚动截图底部
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
        screenshot(driver, "05b_info_bottom")

        # ===== 6. Connected Parties页 =====
        print("\n【6】Connected Parties页检查")
        # 先API提交个人信息
        r = requests.post(f"{API_URL}/api/user/profile", json={
            "name": "张三", "id_card": "110101199003077758",
            "gender": "男", "income_range": "10000-20000",
            "income_source": "工资", "address": "北京市朝阳区xxx"
        }, headers=headers)
        print(f"  提交个人信息: {r.json().get('message', 'ok')}")

        driver.get(BASE_URL + "/shareholder")
        time.sleep(2)
        screenshot(driver, "06_shareholder")

        check(driver, By.CSS_SELECTOR, ".progress-bar-wrap", "进度条区域")
        check(driver, By.CSS_SELECTOR, ".progress-fill", "进度条(100%)")
        t = driver.find_element(By.CSS_SELECTOR, ".page-title").text
        print(f"  页面标题: {t}")
        if "Connected" not in t:
            issues.append(f"Shareholder页标题不正确: {t}")

        check(driver, By.CSS_SELECTOR, ".tip-box", "提示框")
        n = count_elements(driver, ".person-card", "人员卡片数")
        if n < 1:
            issues.append("人员卡片数为0")

        # 第一个卡片展开检查
        check(driver, By.CSS_SELECTOR, ".person-header", "卡片头部(可点击)")
        check(driver, By.CSS_SELECTOR, ".incomplete-badge", "Incomplete状态标识")
        check(driver, By.CSS_SELECTOR, ".chevron", "展开/收起箭头")
        check(driver, By.CSS_SELECTOR, ".person-body", "展开的表单区域")

        # 展开内容检查
        check(driver, By.CSS_SELECTOR, ".radio-group", "证件类型单选组")
        count_elements(driver, ".radio-label", "单选项数")
        count_elements(driver, ".upload-area", "上传区域数")
        check(driver, By.CSS_SELECTOR, ".upload-placeholder", "上传占位提示")
        check(driver, By.CSS_SELECTOR, ".phone-row", "手机号输入行")
        check(driver, By.CSS_SELECTOR, ".phone-code", "区号选择")
        check(driver, By.CSS_SELECTOR, ".field-hint", "字段提示文字")

        # 新增股东按钮
        check(driver, By.CSS_SELECTOR, ".btn-add-shareholder", "新增股东按钮")
        check_css(driver, ".btn-add-shareholder", "border-style", "dashed", "虚线边框")

        check(driver, By.CSS_SELECTOR, ".declaration-block", "声明文字")
        check(driver, By.CSS_SELECTOR, ".bottom-bar", "底部操作栏")
        check(driver, By.CSS_SELECTOR, ".page-footer", "页脚")

        # 滚动截图
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
        screenshot(driver, "06b_shareholder_bottom")

        # ===== 7. 额度页 =====
        print("\n【7】额度页检查")
        r = requests.post(f"{API_URL}/api/user/shareholder", json={
            "shareholders": [{"name": "张三", "id_card": "110101199003077758",
                "share_ratio": 100, "investment_type": "货币", "investment_amount": 1000000}]
        }, headers=headers)
        print(f"  提交股东信息: {r.json().get('message', 'ok')}")

        driver.get(BASE_URL + "/quota")
        time.sleep(3)
        screenshot(driver, "07_quota")

        try:
            amount = driver.find_element(By.CSS_SELECTOR, ".quota-amount")
            print(f"  预估额度: {amount.text}")
            check_css(driver, ".quota-amount", "color", "219, 0, 17", "额度数字HSBC红色")
        except:
            print("  额度数字未找到")

        check(driver, By.CSS_SELECTOR, ".quota-details", "额度详情卡片")
        check(driver, By.CSS_SELECTOR, ".action-buttons .btn-primary", "立即借款按钮")

        # ===== 8. 审批页 =====
        print("\n【8】审批页检查")
        r = requests.post(f"{API_URL}/api/assessment/apply", json={
            "loan_amount": 100000, "loan_purpose": "经营周转"
        }, headers=headers)
        print(f"  申请借款: {r.json().get('message', 'ok')}")

        driver.get(BASE_URL + "/approval")
        time.sleep(2)
        screenshot(driver, "08_approval")

        t = driver.find_element(By.CSS_SELECTOR, ".page-title").text
        print(f"  页面标题: {t}")
        if "Application" not in t:
            issues.append(f"Approval页标题不正确: {t}")

        check(driver, By.CSS_SELECTOR, ".status-card", "状态卡片")
        check(driver, By.CSS_SELECTOR, ".status-icon", "状态图标")
        check(driver, By.CSS_SELECTOR, ".status-icon svg", "SVG图标")

        try:
            label = driver.find_element(By.CSS_SELECTOR, ".status-label")
            color = label.value_of_css_property("color")
            print(f"  状态文字: {label.text} (颜色: {color})")
        except:
            print("  状态文字未找到")

        check(driver, By.CSS_SELECTOR, ".status-desc", "状态描述")
        check(driver, By.CSS_SELECTOR, ".detail-card", "详情卡片")
        n = count_elements(driver, ".detail-row", "详情行数")
        if n < 3:
            issues.append(f"审批详情行不足，期望>=3，实际{n}")

        check(driver, By.CSS_SELECTOR, ".link-refresh", "刷新状态链接")
        check(driver, By.CSS_SELECTOR, ".btn-cancel", "取消申请按钮")
        check_css(driver, ".btn-cancel", "border-color", "219, 0, 17", "取消按钮红色边框")

        # 时间线
        n = count_elements(driver, ".timeline-step", "时间线步骤数")
        if n < 3:
            issues.append(f"时间线步骤不足，期望3，实际{n}")
        count_elements(driver, ".timeline-line", "时间线连接线数")
        check(driver, By.CSS_SELECTOR, ".step-dot.done", "已完成步骤圆点(绿色)")

        check(driver, By.CSS_SELECTOR, ".back-link", "返回Dashboard链接")
        check(driver, By.CSS_SELECTOR, ".page-footer", "页脚")

        # ===== 总结 =====
        print("\n" + "=" * 60)
        print(f"UI检查完成 - 发现 {len(issues)} 个问题")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        if not issues:
            print("  所有页面UI检查通过!")
        print(f"\n截图保存在: {SCREENSHOT_DIR}")
        print("=" * 60)

    except Exception as e:
        print(f"\n!!! 测试异常中断: {e}")
        import traceback
        traceback.print_exc()
        screenshot(driver, "error_page")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
