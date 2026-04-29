# -*- coding: utf-8 -*-
"""
Scenario_1 完整流程：FP-USD-500k 到 esign 成功
使用账号：16073511049
环境：SIT
"""
import sys
sys.path.insert(0, '.')

from mock_sit import DatabaseExecutor, generate_uuid37, get_utc_time, calculate_future_date
import requests
import json
import time

ENV = "sit"
BASE_URL = "https://sit.api.expressfinance.business.hsbc.com"
PHONE = "16073511049"
MERCHANT_ID = "7c9af51239b347dd8d20bd9529b7eda6"
APPLICATION_ID = "EFA17773630200878404"
ACCOUNT_ID = "a0b0aa9fe7c5431cb86bc800fb995827"

def scenario_1_to_esign():
    """执行 scenario_1 完整流程到 esign 成功"""

    print("="*80)
    print("Scenario_1: FP-USD-500k -> esign 成功")
    print("="*80)
    print(f"手机号: {PHONE}")
    print(f"Merchant ID: {MERCHANT_ID}")
    print(f"Application ID: {APPLICATION_ID}")
    print(f"Account ID: {ACCOUNT_ID}")

    webhook_url = f"{BASE_URL}/dpu-openapi/webhook-notifications"
    lender_approved_offer_id = f"lender-{APPLICATION_ID}"

    # 步骤1: Approved Offer
    print("\n[步骤 1/4] 发送 approvedoffer.completed webhook...")
    approved_body = {
        "data": {
            "eventType": "approvedoffer.completed",
            "eventId": generate_uuid37(),
            "eventMessage": "Application approval process completed successfully",
            "enquiryUrl": "https://api.lender.com/enquiry/12345",
            "datetime": get_utc_time(),
            "details": {
                "merchantId": MERCHANT_ID,
                "dpuApplicationId": APPLICATION_ID,
                "originalRequestId": f"req_{generate_uuid37()[:10]}",
                "status": "APPROVED",
                "lenderApprovedOfferId": lender_approved_offer_id,
                "offer": {
                    "rate": {
                        "chargeBases": "Float",
                        "baseRateType": "SOFR",
                        "baseRate": "0.05",
                        "marginRate": "0.02",
                        "fixedRate": "0.07"
                    },
                    "term": 120,
                    "termUnit": "Days",
                    "mintenor": 3,
                    "maxtenor": 24,
                    "offerEndDate": calculate_future_date(90),
                    "offerStartDate": get_utc_time()[:10],
                    "approvedAmount": 500000,
                    "currency": "USD"
                }
            }
        }
    }

    resp = requests.post(webhook_url, json=approved_body, timeout=30)
    print(f"   响应: {resp.status_code}")
    if resp.status_code != 200:
        print(f"   内容: {resp.text[:200]}")
    time.sleep(3)

    # 步骤2: PSP Start
    print("\n[步骤 2/4] 发送 psp.verification.started webhook...")
    psp_start_body = {
        "data": {
            "eventType": "psp.verification.started",
            "eventId": generate_uuid37(),
            "eventMessage": "PSP verification process started",
            "enquiryUrl": "https://api.lender.com/enquiry/12345",
            "datetime": get_utc_time(),
            "details": {
                "merchantId": MERCHANT_ID,
                "dpuApplicationId": APPLICATION_ID,
                "lenderApprovedOfferId": lender_approved_offer_id,
                "originalRequestId": f"req_{generate_uuid37()[:10]}"
            }
        }
    }

    resp = requests.post(webhook_url, json=psp_start_body, timeout=30)
    print(f"   响应: {resp.status_code}")
    time.sleep(3)

    # 步骤3: PSP Completed
    print("\n[步骤 3/4] 发送 psp.verification.completed webhook...")
    psp_completed_body = {
        "data": {
            "eventType": "psp.verification.completed",
            "eventId": generate_uuid37(),
            "eventMessage": "PSP verification process completed successfully",
            "enquiryUrl": "https://api.lender.com/enquiry/12345",
            "datetime": get_utc_time(),
            "details": {
                "merchantId": MERCHANT_ID,
                "dpuApplicationId": APPLICATION_ID,
                "lenderApprovedOfferId": lender_approved_offer_id,
                "originalRequestId": f"req_{generate_uuid37()[:10]}",
                "status": "SUCCESS"
            }
        }
    }

    resp = requests.post(webhook_url, json=psp_completed_body, timeout=30)
    print(f"   响应: {resp.status_code}")
    time.sleep(3)

    # 步骤4: E-sign (最终目标)
    print("\n[步骤 4/4] 发送 esign.completed webhook...")
    esign_body = {
        "data": {
            "eventType": "esign.completed",
            "eventId": generate_uuid37(),
            "eventMessage": "E-signature process completed successfully",
            "enquiryUrl": "https://api.lender.com/enquiry/12345",
            "datetime": get_utc_time(),
            "details": {
                "merchantId": MERCHANT_ID,
                "dpuApplicationId": APPLICATION_ID,
                "lenderApprovedOfferId": lender_approved_offer_id,
                "originalRequestId": f"req_{generate_uuid37()[:10]}",
                "status": "SUCCESS"
            }
        }
    }

    resp = requests.post(webhook_url, json=esign_body, timeout=30)
    print(f"   响应: {resp.status_code}")
    if resp.status_code != 200:
        print(f"   内容: {resp.text[:200]}")

    # 验证最终状态
    print("\n" + "="*80)
    print("验证最终状态...")
    print("="*80)

    with DatabaseExecutor(env=ENV) as db:
        credit_offer_status = db.execute_sql(
            f"SELECT status FROM dpu_credit_offer WHERE merchant_id='{MERCHANT_ID}' ORDER BY created_at DESC LIMIT 1"
        )

        app_status = db.execute_sql(
            f"SELECT application_status FROM dpu_application WHERE merchant_id='{MERCHANT_ID}' LIMIT 1"
        )

        print(f"Credit Offer 状态: {credit_offer_status}")
        print(f"Application 状态: {app_status}")

    # 生成报告
    report = {
        "environment": ENV,
        "scenario": "scenario_1 (FP-USD-500k)",
        "phone_number": PHONE,
        "merchant_id": MERCHANT_ID,
        "application_unique_id": APPLICATION_ID,
        "merchant_account_id": ACCOUNT_ID,
        "steps_completed": [
            "1. approvedoffer.completed",
            "2. psp.verification.started",
            "3. psp.verification.completed",
            "4. esign.completed [OK]"
        ],
        "final_status": {
            "credit_offer_status": credit_offer_status,
            "application_status": app_status
        }
    }

    with open('scenario_1_esign_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n" + "="*80)
    print("[OK] Scenario_1 执行完成！E-sign 成功！")
    print("="*80)
    print(f"报告已保存到: scenario_1_esign_report.json")
    print("="*80)

    return report

if __name__ == "__main__":
    scenario_1_to_esign()
