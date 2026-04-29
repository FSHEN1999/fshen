"""
浏览器自动化全流程测试脚本
用Selenium打开浏览器，模拟用户操作，记录所有bug
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import time
import json
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

FRONTEND_URL = "http://localhost:3000"
BACKEND_URL = "http://localhost:8001"
# 每次测试用新手机号，避免冲突
TEST_PHONE = f"138{int(time.time()) % 100000000:08d}"
BUGS = []

def log_bug(bug_id, severity, page, description, detail=""):
    bug = {"id": bug_id, "severity": severity, "page": page, "description": description, "detail": detail}
    BUGS.append(bug)
    print(f"  [BUG-{bug_id}] [{severity}] {description}")
    if detail:
        print(f"     -> {detail}")

def get_sms_code(phone):
    """通过后端API发送并获取验证码"""
    res = requests.post(f"{BACKEND_URL}/api/auth/sms-code", json={"phone": phone})
    data = res.json()
    if data["code"] == 0:
        return data["data"]["code"]
    print(f"  [WARN] 获取验证码失败: {data}")
    return None

def api_register(phone):
    """通过API完成注册"""
    code = get_sms_code(phone)
    if not code:
        return None
    res = requests.post(f"{BACKEND_URL}/api/auth/register", json={
        "phone": phone, "code": code,
        "password": "Aa11111111", "confirm_password": "Aa11111111"
    })
    return res.json()

def api_login(phone):
    """通过API完成SMS登录，返回token"""
    code = get_sms_code(phone)
    if not code:
        return None
    res = requests.post(f"{BACKEND_URL}/api/auth/login/sms", json={"phone": phone, "code": code})
    data = res.json()
    if data["code"] == 0:
        return data["data"]["access_token"]
    return None

def inject_token(driver, token, phone):
    """注入token到浏览器localStorage"""
    driver.execute_script(f"""
        localStorage.setItem('dpu_token', '{token}');
        localStorage.setItem('dpu_phone', '{phone}');
    """)

def main():
    print("=" * 60)
    print("DPU模型 - 浏览器全流程自动化测试")
    print(f"测试手机号: {TEST_PHONE}")
    print("=" * 60)

    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1400,900")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(3)
    bug_id = [0]
    def next_id():
        bug_id[0] += 1
        return bug_id[0]

    try:
        # ============================================================
        # 测试1: 登录页加载和UI检查
        # ============================================================
        print("\n[测试1] 登录页加载和UI检查")
        driver.get(FRONTEND_URL)
        time.sleep(2)

        url = driver.current_url
        print(f"  URL: {url}")
        if "/login" not in url:
            log_bug(next_id(), "严重", "路由", "首页未跳转到/login", f"实际: {url}")

        # 标题
        try:
            title = driver.find_element(By.CSS_SELECTOR, "h1")
            print(f"  标题: {title.text}")
        except NoSuchElementException:
            log_bug(next_id(), "一般", "登录页", "页面无h1标题")

        # HSBC Logo
        try:
            driver.find_element(By.CSS_SELECTOR, ".hsbc-logo svg")
            print(f"  HSBC Logo: OK")
        except NoSuchElementException:
            log_bug(next_id(), "一般", "登录页", "HSBC Logo缺失")

        # 右侧图片
        try:
            img = driver.find_element(By.CSS_SELECTOR, ".cover-image")
            src = img.get_attribute("src")
            visible = driver.execute_script("""
                var el = arguments[0];
                var style = getComputedStyle(el.parentElement);
                return style.display !== 'none';
            """, img)
            natural_w = driver.execute_script("return arguments[0].naturalWidth", img)
            print(f"  右侧图片: visible={visible}, naturalWidth={natural_w}")
            if visible and natural_w == 0:
                log_bug(next_id(), "一般", "登录页", "右侧图片加载失败")
        except NoSuchElementException:
            pass

        # 底部footer
        try:
            footer = driver.find_element(By.CSS_SELECTOR, ".hsbc-footer")
            copyright_text = driver.find_element(By.CSS_SELECTOR, ".footer-copyright").text
            print(f"  Footer: {copyright_text}")
        except NoSuchElementException:
            log_bug(next_id(), "一般", "登录页", "页面底部Footer缺失")

        # ============================================================
        # 测试2: 注册模式 - 验证码获取和输入
        # ============================================================
        print("\n[测试2] 注册模式 - 获取验证码并输入")

        # 先通过API获取验证码（绕过60秒冷却问题）
        sms_code = get_sms_code(TEST_PHONE)
        print(f"  API获取验证码: {sms_code}")
        if not sms_code:
            log_bug(next_id(), "致命", "后端", "无法通过API获取验证码")
            return

        # 输入手机号
        phone_input = driver.find_element(By.CSS_SELECTOR, ".phone-input")
        phone_input.clear()
        phone_input.send_keys(TEST_PHONE)
        time.sleep(0.3)

        # 检查"Get code"按钮状态
        get_code_btn = driver.find_element(By.CSS_SELECTOR, ".get-code-btn")
        btn_disabled = get_code_btn.get_attribute("disabled")
        print(f"  Get code按钮: {'禁用' if btn_disabled else '可用'}")
        if btn_disabled:
            log_bug(next_id(), "严重", "登录页", "输入手机号后Get code按钮仍禁用")

        # 输入验证码到6个格子
        code_boxes = driver.find_elements(By.CSS_SELECTOR, ".code-box")
        print(f"  验证码格子数: {len(code_boxes)}")
        for i, d in enumerate(str(sms_code)[:6]):
            code_boxes[i].clear()
            code_boxes[i].send_keys(d)
            time.sleep(0.1)
        time.sleep(0.3)

        filled = "".join([b.get_attribute("value") for b in code_boxes])
        print(f"  已填入: {filled} (期望: {sms_code})")
        if filled != str(sms_code):
            log_bug(next_id(), "严重", "登录页", "验证码输入异常", f"期望{sms_code}, 实际{filled}")

        # ============================================================
        # 测试3: 点击Next注册（注册模式）
        # ============================================================
        print("\n[测试3] 注册模式 - 点击Next")
        next_btn = driver.find_element(By.CSS_SELECTOR, ".btn-next")
        next_btn.click()
        time.sleep(4)

        url_after = driver.current_url
        print(f"  点击Next后URL: {url_after}")

        # 检查toast
        try:
            toast = driver.find_element(By.CSS_SELECTOR, ".toast")
            toast_text = toast.text
            toast_class = toast.get_attribute("class")
            print(f"  Toast: [{toast_class}] {toast_text}")
            if "error" in toast_class:
                log_bug(next_id(), "致命", "登录页",
                       f"注册模式Next失败: {toast_text}",
                       "LoginView注册流程: loginBySms->404->register，但验证码在loginBySms中被消耗")
        except NoSuchElementException:
            pass

        if "/info" in url_after:
            print(f"  OK 成功跳转到信息填写页")
        else:
            log_bug(next_id(), "致命", "登录页", "注册后未跳转到/info页",
                   f"停留在{url_after}。LoginView的注册流程先调用loginBySms(返回404)消耗验证码，再调register时验证码已失效")

        # ============================================================
        # 测试3b: 注册失败后通过API注册+登录，注入token继续测试
        # ============================================================
        if "/info" not in driver.current_url:
            print("\n[测试3b] 通过API注册+登录，注入token")
            reg_result = api_register(TEST_PHONE)
            print(f"  API注册: {reg_result}")
            token = api_login(TEST_PHONE)
            if token:
                driver.get(FRONTEND_URL)
                time.sleep(1)
                inject_token(driver, token, TEST_PHONE)
                driver.get(f"{FRONTEND_URL}/info")
                time.sleep(2)
                print(f"  注入token后URL: {driver.current_url}")
            else:
                log_bug(next_id(), "致命", "后端", "API登录也失败，无法继续测试")
                return

        # ============================================================
        # 测试4: 密码登录模式
        # ============================================================
        print("\n[测试4] 密码登录模式")
        driver.execute_script("localStorage.clear()")
        driver.get(f"{FRONTEND_URL}/login")
        time.sleep(2)

        # 点击"Log in"链接
        try:
            link = driver.find_element(By.CSS_SELECTOR, ".account-link a")
            link.click()
            time.sleep(0.5)

            # 密码框
            try:
                pwd_input = driver.find_element(By.CSS_SELECTOR, ".password-wrap input")
                print(f"  密码输入框: 已显示")

                phone_input = driver.find_element(By.CSS_SELECTOR, ".phone-input")
                phone_input.clear()
                phone_input.send_keys(TEST_PHONE)
                pwd_input.clear()
                pwd_input.send_keys("Aa11111111")

                # 不输验证码直接点Next
                next_btn = driver.find_element(By.CSS_SELECTOR, ".btn-next")
                next_btn.click()
                time.sleep(1)

                try:
                    toast = driver.find_element(By.CSS_SELECTOR, ".toast")
                    t = toast.text
                    print(f"  Toast: {t}")
                    if "验证码" in t:
                        log_bug(next_id(), "致命", "登录页",
                               "密码登录仍强制要求6位验证码",
                               f"Toast: '{t}'。handleSubmit第258行fullCode.length!==6拦截了密码登录")
                except NoSuchElementException:
                    pass
            except NoSuchElementException:
                log_bug(next_id(), "严重", "登录页", "登录模式下密码输入框未显示")
        except NoSuchElementException:
            log_bug(next_id(), "严重", "登录页", "'Log in'链接未找到")

        # ============================================================
        # 测试5: 信息填写页
        # ============================================================
        print("\n[测试5] 信息填写页")
        # 重新注入token
        token = api_login(TEST_PHONE)
        driver.get(FRONTEND_URL)
        time.sleep(1)
        inject_token(driver, token, TEST_PHONE)
        driver.get(f"{FRONTEND_URL}/info")
        time.sleep(2)

        print(f"  URL: {driver.current_url}")
        if "/info" not in driver.current_url:
            log_bug(next_id(), "致命", "路由", "已登录但无法访问/info")
        else:
            # 检查页面标题
            try:
                t = driver.find_element(By.CSS_SELECTOR, ".page-title")
                print(f"  标题: {t.text}")
            except NoSuchElementException:
                pass

            # 统计表单字段
            all_inputs = driver.find_elements(By.TAG_NAME, "input")
            all_selects = driver.find_elements(By.TAG_NAME, "select")
            print(f"  input: {len(all_inputs)}, select: {len(all_selects)}")

            # 填写必填字段
            for inp in all_inputs:
                ph = inp.get_attribute("placeholder") or ""
                if "真实姓名" in ph or "姓名" in ph:
                    inp.clear(); inp.send_keys("张三测试")
                elif "身份证" in ph:
                    inp.clear(); inp.send_keys("110101199003076819")
                elif "收入来源" in ph:
                    inp.clear(); inp.send_keys("salary")
                elif "地址" in ph:
                    inp.clear(); inp.send_keys("北京市朝阳区测试路1号")

            # 选择收入范围 - 用Select类确保Vue v-model更新
            from selenium.webdriver.support.ui import Select as SeleniumSelect
            for sel in all_selects:
                s = SeleniumSelect(sel)
                opts = [o.text for o in s.options]
                print(f"  Select选项: {opts}")
                s.select_by_visible_text("10000-20000")
                print(f"  选择: 10000-20000")

            time.sleep(1)

            # 检查提交按钮
            btn = driver.find_element(By.CSS_SELECTOR, ".btn-primary")
            disabled = btn.get_attribute("disabled")
            print(f"  提交按钮: {'禁用' if disabled else '可用'}")

            if disabled:
                log_bug(next_id(), "严重", "信息填写页",
                       "填写所有必填项后提交按钮仍禁用",
                       "可能是select的v-model未被Selenium的click正确触发")
                # 尝试JS强制设置
                driver.execute_script("""
                    var app = document.querySelector('#app-root').__vue_app__;
                    // 无法直接操作Vue响应式，改用直接提交API
                """)

            if not disabled:
                btn.click()
                time.sleep(3)
                url_after = driver.current_url
                print(f"  提交后URL: {url_after}")

                try:
                    toast = driver.find_element(By.CSS_SELECTOR, ".toast")
                    print(f"  Toast: {toast.text}")
                    if "error" in toast.get_attribute("class"):
                        log_bug(next_id(), "严重", "信息填写页", f"提交失败: {toast.text}")
                except NoSuchElementException:
                    pass

                if "/shareholder" in url_after:
                    print(f"  OK 跳转到股东页")
            else:
                # 通过API直接提交
                print("  => 通过API直接提交个人信息")
                headers = {"Authorization": f"Bearer {token}"}
                res = requests.post(f"{BACKEND_URL}/api/user/profile", json={
                    "name": "张三测试", "id_card": "110101199003076819",
                    "gender": "male", "income_range": "10000-20000",
                    "income_source": "salary", "address": "北京市朝阳区"
                }, headers=headers)
                print(f"  API提交: {res.json()}")

        # ============================================================
        # 测试6: 股东信息页
        # ============================================================
        print("\n[测试6] 股东信息页")
        driver.get(f"{FRONTEND_URL}/shareholder")
        time.sleep(2)
        print(f"  URL: {driver.current_url}")

        if "/shareholder" in driver.current_url:
            all_inputs = driver.find_elements(By.TAG_NAME, "input")
            all_selects = driver.find_elements(By.TAG_NAME, "select")
            print(f"  input: {len(all_inputs)}, select: {len(all_selects)}")

            for inp in all_inputs:
                ph = inp.get_attribute("placeholder") or ""
                if "股东姓名" in ph:
                    inp.clear(); inp.send_keys("李四")
                elif "身份证" in ph:
                    inp.clear(); inp.send_keys("110101198503154016")
                elif "小数点" in ph:
                    inp.clear(); inp.send_keys("100")
                elif "出资额" in ph:
                    inp.clear(); inp.send_keys("500000")

            for sel in all_selects:
                try:
                    s = SeleniumSelect(sel)
                    for o in s.options:
                        if o.text == "货币":
                            s.select_by_visible_text("货币")
                            break
                except:
                    pass

            time.sleep(1)

            # 比例合计
            try:
                ratio = driver.find_element(By.CSS_SELECTOR, ".ratio-total")
                print(f"  比例合计: {ratio.text}")
            except NoSuchElementException:
                pass

            btn = driver.find_element(By.CSS_SELECTOR, ".btn-primary")
            disabled = btn.get_attribute("disabled")
            print(f"  提交按钮: {'禁用' if disabled else '可用'}")

            if not disabled:
                btn.click()
                time.sleep(3)
                print(f"  提交后URL: {driver.current_url}")
                try:
                    toast = driver.find_element(By.CSS_SELECTOR, ".toast")
                    print(f"  Toast: {toast.text}")
                    if "error" in toast.get_attribute("class"):
                        log_bug(next_id(), "严重", "股东页", f"提交失败: {toast.text}")
                except NoSuchElementException:
                    pass
            else:
                log_bug(next_id(), "严重", "股东页", "填写完成后提交按钮禁用")
                # API fallback
                headers = {"Authorization": f"Bearer {token}"}
                res = requests.post(f"{BACKEND_URL}/api/user/shareholder", json={
                    "shareholders": [{
                        "name": "李四", "id_card": "110101198503154016",
                        "share_ratio": 100, "investment_type": "货币",
                        "investment_amount": 500000
                    }]
                }, headers=headers)
                print(f"  API提交: {res.json()}")

        # ============================================================
        # 测试7: 额度展示页
        # ============================================================
        print("\n[测试7] 额度展示页")
        driver.get(f"{FRONTEND_URL}/quota")
        time.sleep(4)
        print(f"  URL: {driver.current_url}")

        try:
            amount_el = driver.find_element(By.CSS_SELECTOR, ".amount")
            print(f"  预估额度: {amount_el.text}")
        except NoSuchElementException:
            try:
                blocked = driver.find_element(By.CSS_SELECTOR, ".blocked-state")
                print(f"  被风控拦截: {blocked.text[:80]}")
            except NoSuchElementException:
                try:
                    empty = driver.find_element(By.CSS_SELECTOR, ".empty-state")
                    print(f"  空状态: {empty.text}")
                    log_bug(next_id(), "严重", "额度页", "额度页显示空状态")
                except NoSuchElementException:
                    log_bug(next_id(), "严重", "额度页", "额度页无任何内容")

        # 点"立即借款"
        try:
            borrow_btn = driver.find_element(By.XPATH, "//button[contains(text(),'立即借款')]")
            borrow_btn.click()
            time.sleep(2)
            url_after = driver.current_url
            print(f"  点击'立即借款'后URL: {url_after}")
            if "/approval" in url_after:
                log_bug(next_id(), "严重", "额度页",
                       "'立即借款'直接跳转审批页，未提交借款申请",
                       "前端缺少借款申请表单，applyLoan API从未被调用。用户无法选择借款金额")
        except NoSuchElementException:
            pass

        # ============================================================
        # 测试8: 审批状态页
        # ============================================================
        print("\n[测试8] 审批状态页")
        if "/approval" not in driver.current_url:
            driver.get(f"{FRONTEND_URL}/approval")
            time.sleep(3)
        print(f"  URL: {driver.current_url}")

        try:
            empty = driver.find_element(By.CSS_SELECTOR, ".empty-state")
            print(f"  空状态: {empty.text}")
            log_bug(next_id(), "严重", "审批页",
                   "审批页显示'暂无借款申请'",
                   "因为额度页'立即借款'未调用applyLoan就跳转了")
        except NoSuchElementException:
            try:
                status = driver.find_element(By.CSS_SELECTOR, ".status-label")
                print(f"  审批状态: {status.text}")
            except NoSuchElementException:
                pass

        # ============================================================
        # 测试9: 路由守卫 - 未登录访问受保护页面
        # ============================================================
        print("\n[测试9] 路由守卫测试")
        driver.execute_script("localStorage.clear()")
        for path in ["/info", "/shareholder", "/quota", "/approval"]:
            driver.get(f"{FRONTEND_URL}{path}")
            time.sleep(1.5)
            u = driver.current_url
            ok = "/login" in u
            print(f"  {path} -> {u} {'OK' if ok else 'FAIL'}")
            if not ok:
                log_bug(next_id(), "致命", "路由守卫", f"未登录可访问{path}", f"URL: {u}")

        # ============================================================
        # 测试10: 404路由
        # ============================================================
        print("\n[测试10] 404路由")
        driver.get(f"{FRONTEND_URL}/nonexistent-page")
        time.sleep(2)
        body = driver.find_element(By.TAG_NAME, "body").text.strip()
        print(f"  URL: {driver.current_url}, body长度: {len(body)}")
        if not body:
            log_bug(next_id(), "一般", "路由", "缺少404页面，不存在的路径显示空白")

        # ============================================================
        # 测试11: UI风格一致性
        # ============================================================
        print("\n[测试11] UI风格一致性")
        driver.get(f"{FRONTEND_URL}/register")
        time.sleep(2)
        try:
            logo = driver.find_element(By.CSS_SELECTOR, ".logo-icon")
            bg = driver.execute_script("return getComputedStyle(arguments[0]).backgroundImage", logo)
            print(f"  注册页Logo背景: {bg}")
            if "667eea" in bg or "764ba2" in bg:
                log_bug(next_id(), "一般", "注册页",
                       "注册页紫色渐变风格与登录页HSBC红色风格不一致")
        except NoSuchElementException:
            pass

        # 登录后的页面(info等)也是紫色渐变按钮
        token = api_login(TEST_PHONE)
        if token:
            driver.get(FRONTEND_URL)
            time.sleep(1)
            inject_token(driver, token, TEST_PHONE)
            driver.get(f"{FRONTEND_URL}/info")
            time.sleep(2)
            try:
                btn = driver.find_element(By.CSS_SELECTOR, ".btn-primary")
                bg = driver.execute_script("return getComputedStyle(arguments[0]).backgroundImage", btn)
                print(f"  信息页按钮背景: {bg}")
                if "667eea" in bg:
                    log_bug(next_id(), "一般", "全局",
                           "登录后页面使用紫色渐变按钮，与HSBC登录页红色风格不一致")
            except NoSuchElementException:
                pass

        # ============================================================
        # 汇总
        # ============================================================
        print("\n" + "=" * 60)
        print(f"浏览器测试完成! 共发现 {len(BUGS)} 个bug")
        print("=" * 60)

        for bug in BUGS:
            icon = {"致命": "[P0]", "严重": "[P1]", "一般": "[P2]", "轻微": "[P3]"}.get(bug["severity"], "[??]")
            print(f"  {icon} BUG-{bug['id']} {bug['page']}: {bug['description']}")

        with open("d:/data/project/dpu/dpu-model/tmp/browser_bugs.json", "w", encoding="utf-8") as f:
            json.dump(BUGS, f, ensure_ascii=False, indent=2)
        print(f"\nBug列表已保存到 tmp/browser_bugs.json")

    except Exception as e:
        print(f"\n测试脚本出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        time.sleep(2)
        driver.quit()

if __name__ == "__main__":
    main()
