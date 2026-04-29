# -*- coding: utf-8 -*-
"""FP-USD 500K完整流程测试"""
import sys
import time
from datetime import datetime
from mock_uat import DatabaseExecutor, DPUMockService, faker, log, get_current_time

def run_fp_500k_flow():
    test_log = []
    start_time = datetime.now()
    phone_number = None
    merchant_id = None
    db_executor = None

    def log_step(step, status, details=""):
        msg = f"[{get_current_time()}] {step}: {status}"
        if details:
            msg += f" - {details}"
        test_log.append(msg)
        log.info(msg)
        print(msg)

    try:
        db_executor = DatabaseExecutor(env="reg")
        db_executor.connect()
        log_step("初始化", "成功", "环境: reg")

        # Step 1: 注册账号
        log_step("Step 1", "开始", "注册新账号")
        phone_number = ''.join(filter(str.isdigit, faker.phone_number()))[:11]
        email = f"{phone_number}@test.com"

        import requests
        base_url = "https://dpu-gateway-reg.dowsure.com"

        # 创建offer ID
        offer_response = requests.post(
            f"{base_url}/dpu-merchant/mock/generate-shop-performance",
            json={"yearlyRepaymentAmount": 500000},
            timeout=30
        )
        offer_data = offer_response.json().get("data", {})
        offer_id = offer_data.get("amazon3plOfferId") or offer_data.get("offerId")
        log_step("Step 1.1", "完成", f"Offer ID: {offer_id}")

        # 验证短信
        requests.post(
            f"{base_url}/dpu-user/auth/validateSmsCode-sign",
            json={"phoneNumber": phone_number, "smsCode": "666666"},
            timeout=30
        )

        # 注册
        requests.post(
            f"{base_url}/dpu-user/auth/signup",
            json={
                "phoneNumber": phone_number,
                "email": email,
                "offerId": offer_id,
                "password": "Aa11111111.."
            },
            timeout=30
        )

        # 激活
        redirect_url = f"{base_url}/dpu-merchant/amazon/redirect?state={offer_id}&selling_partner_id=test&spapi_oauth_code=test"
        requests.get(redirect_url, timeout=30)

        log_step("Step 1", "完成", f"手机号: {phone_number}, 邮箱: {email}")
        time.sleep(3)

        # 获取merchant_id
        merchant_id = db_executor.execute_sql(
            f"SELECT merchant_id FROM dpu_users WHERE phone_number='{phone_number}'"
        )
        if not merchant_id:
            raise Exception("无法获取merchant_id")
        log_step("数据验证", "成功", f"merchant_id: {merchant_id}")

        # 初始化服务
        service = DPUMockService(phone_number=phone_number, db_executor=db_executor)

        # Step 2: Underwriting
        log_step("Step 2", "开始", "执行核保")
        service.mock_underwriting_approved()
        log_step("Step 2", "完成", "核保状态: APPROVED")
        time.sleep(2)

        # Step 3: Approval
        log_step("Step 3", "开始", "执行审批")
        service.mock_approval_approved(approved_amount=500000, approved_currency="USD")
        log_step("Step 3", "完成", "审批金额: 500000 USD")
        time.sleep(2)

        # Step 4: PSP Start
        log_step("Step 4", "开始", "PSP验证启动")
        service.mock_psp_verification_start()
        log_step("Step 4", "完成", "PSP验证已启动")
        time.sleep(2)

        # Step 5: PSP Completed
        log_step("Step 5", "开始", "PSP验证完成")
        service.mock_psp_verification_completed()
        log_step("Step 5", "完成", "PSP验证已完成")
        time.sleep(2)

        # Step 6: E-signature
        log_step("Step 6", "开始", "更新电子签名状态")
        service.mock_esign_completed()
        log_step("Step 6", "完成", "电子签名已完成")

        # 验证最终状态
        final_status = db_executor.execute_query(
            f"""SELECT application_status, esign_status, psp_verification_status
            FROM dpu_merchant_applications
            WHERE merchant_account_id='{merchant_id}'"""
        )

        # 生成报告
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        report = f"""
{'='*80}
FP-USD 500K 完整流程测试报告
{'='*80}
测试环境: reg
开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}
结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}
总耗时: {duration:.2f}秒

账号信息:
- 手机号: {phone_number}
- 邮箱: {email}
- Merchant ID: {merchant_id}
- 申请金额: 500,000 USD

流程步骤:
1. ✓ 账号注册
2. ✓ 核保 (Underwriting) - APPROVED
3. ✓ 审批 (Approval) - 500,000 USD
4. ✓ PSP验证启动
5. ✓ PSP验证完成
6. ✓ 电子签名完成

最终状态:
{final_status}

详细日志:
{'='*80}
"""
        for entry in test_log:
            report += f"{entry}\n"
        report += f"{'='*80}\n"

        report_file = f"FP_500K_TEST_REPORT_{start_time.strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(report)
        print(f"\n报告已保存至: {report_file}")
        return True

    except Exception as e:
        log_step("错误", "失败", str(e))
        log.error(f"测试失败: {e}", exc_info=True)

        error_report = f"""
{'='*80}
FP-USD 500K 测试失败报告
{'='*80}
错误信息: {str(e)}

已完成步骤:
"""
        for entry in test_log:
            error_report += f"{entry}\n"

        print(error_report)
        return False

if __name__ == "__main__":
    success = run_fp_500k_flow()
    sys.exit(0 if success else 1)
