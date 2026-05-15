# -*- coding: utf-8 -*-
"""FP-USD 500K完整流程：从注册到esign成功"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mockapi'))

import time
import requests
from datetime import datetime
from mock_uat import DatabaseExecutor, faker, log, get_current_time

def run_full_flow():
    test_log = []
    start_time = datetime.now()

    def log_step(step, status, details=""):
        msg = f"[{get_current_time()}] {step}: {status} - {details}" if details else f"[{get_current_time()}] {step}: {status}"
        test_log.append(msg)
        log.info(msg)
        print(msg)

    try:
        base_url = "https://dpu-gateway-reg.dowsure.com"
        phone_number = ''.join(filter(str.isdigit, faker.phone_number()))[:11]
        email = f"{phone_number}y@163doushabao.com"
        currency = "USD"

        log_step("Step 1", "开始", f"注册账号 - 手机号: {phone_number}")

        # 1.1 创建offer ID
        offer_resp = requests.post(
            f"{base_url}/dpu-merchant/mock/generate-shop-performance",
            json={"yearlyRepaymentAmount": 500000},
            timeout=30
        )
        offer_id = offer_resp.json().get("data", {}).get("amazon3plOfferId")
        log_step("Step 1.1", "完成", f"Offer ID: {offer_id}")

        # 1.2 激活offer
        redirect_url = f"{base_url}/dpu-merchant/amazon/redirect?offerId={offer_id}"
        requests.get(redirect_url, timeout=30)

        # 1.3 验证短信
        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "product-currency": currency,
            "finance-product": "LINE_OF_CREDIT",
            "funder-resource": "FUNDPARK"
        }
        requests.post(
            f"{base_url}/dpu-user/auth/validateSmsCode-sign",
            json={"areaCode": "+86", "code": "666666", "phone": phone_number},
            headers=headers,
            timeout=30
        )

        # 1.4 注册
        register_payload = {
            "phone": phone_number,
            "areaCode": "+86",
            "code": "666666",
            "email": email,
            "offerId": offer_id,
            "password": "Aa11111111..",
            "confirmPassword": "Aa11111111..",
            "isAcceptMarketing": True,
            "securityQuestionCode": "SEC_Q_004",
            "securityAnswer": "test",
            "preferFinanceProductCurrency": currency
        }
        signup_resp = requests.post(
            f"{base_url}/dpu-user/auth/signup",
            json=register_payload,
            headers=headers,
            timeout=30
        )
        log_step("Step 1.2", "完成", f"注册响应: {signup_resp.status_code}")

        time.sleep(5)

        db = DatabaseExecutor(env="reg")
        db.connect()

        merchant_id = db.execute_sql(f"SELECT merchant_id FROM dpu_users WHERE phone_number='{phone_number}'")
        if not merchant_id:
            raise Exception(f"注册失败 - 响应: {signup_resp.text}")

        log_step("Step 1", "完成", f"Merchant ID: {merchant_id}")

        # 获取application_unique_id（使用正确的表名）
        application_unique_id = db.execute_sql(
            f"SELECT application_unique_id FROM dpu_application WHERE merchant_id='{merchant_id}' ORDER BY created_at DESC LIMIT 1"
        )

        # Step 2-6: 执行webhook流程
        steps = [
            ("Step 2", "underwritten", {"applicationUniqueId": application_unique_id, "underwrittenAmount": 500000, "underwrittenCurrency": "USD", "underwrittenStatus": "APPROVED"}),
            ("Step 3", "approved_offer", {"applicationUniqueId": application_unique_id, "approvedAmount": 500000, "approvedCurrency": "USD", "approvedStatus": "APPROVED"}),
            ("Step 4", "psp_verification", {"applicationUniqueId": application_unique_id, "pspVerificationStatus": "PROCESSING"}),
            ("Step 5", "psp_verification", {"applicationUniqueId": application_unique_id, "pspVerificationStatus": "SUCCESS"}),
            ("Step 6", "esign", {"applicationUniqueId": application_unique_id, "esignStatus": "SUCCESS"})
        ]

        for step_name, event_type, data in steps:
            log_step(step_name, "开始", event_type)
            requests.post(
                f"{base_url}/dpu-openapi/webhook-notifications",
                json={"eventType": event_type, "eventTime": get_current_time("%Y-%m-%dT%H:%M:%SZ"), "data": data},
                timeout=30
            )
            log_step(step_name, "完成", "")
            time.sleep(2)

        # 查询最终状态（使用正确的表名和字段）
        final_status = db.execute_query(
            f"SELECT application_status FROM dpu_application WHERE merchant_id='{merchant_id}'"
        )

        # 查询其他状态表
        credit_offer = db.execute_query(
            f"SELECT approved_amount, approved_currency FROM dpu_credit_offer WHERE merchant_id='{merchant_id}' ORDER BY created_at DESC LIMIT 1"
        )

        end_time = datetime.now()
        report = f"""
{'='*80}
FP-USD 500K 完整流程测试报告
{'='*80}
环境: reg
耗时: {(end_time - start_time).total_seconds():.2f}秒

账号信息:
- 手机号: {phone_number}
- 邮箱: {email}
- Merchant ID: {merchant_id}
- Application ID: {application_unique_id}

最终状态:
- Application Status: {final_status.get('application_status') if final_status else 'N/A'}
- Approved Amount: {credit_offer.get('approved_amount') if credit_offer else 'N/A'} {credit_offer.get('approved_currency') if credit_offer else ''}

详细日志:
{'='*80}
"""
        for entry in test_log:
            report += f"{entry}\n"

        report_file = f"FP_500K_REPORT_{start_time.strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(report)
        print(f"\n报告: {report_file}")
        return True

    except Exception as e:
        log_step("错误", "失败", str(e))
        log.error(f"测试失败: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    sys.exit(0 if run_full_flow() else 1)
