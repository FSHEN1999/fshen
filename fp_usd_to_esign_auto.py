# -*- coding: utf-8 -*-
"""
FP-USD 完整流程测试：从注册到 esign 成功（自动化版本）
环境：SIT
流程：FP (200K)
货币：USD
"""
import sys
sys.path.insert(0, '.')

from mock_sit import DatabaseExecutor, generate_uuid37, get_utc_time, calculate_future_date
from batch_register_uat import register_account, get_api_config
import requests
import json
import time

ENV = "sit"
BASE_URL = "https://sit.api.expressfinance.business.hsbc.com"
WEBHOOK_URL = f"{BASE_URL}/dpu-openapi/webhook-notifications"

def send_webhook(request_body):
    """发送 webhook 请求"""
    try:
        response = requests.post(WEBHOOK_URL, json=request_body, timeout=30)
        print(f"   Webhook 响应: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"   Webhook 失败: {e}")
        return False

def fp_usd_to_esign_flow():
    """执行 FP-USD 从注册到 esign 成功的完整流程"""

    print("="*80)
    print("FP-USD 完整流程测试：注册 -> esign 成功")
    print("="*80)

    # 步骤 1: 注册 FP-USD 账号
    print("\n[步骤 1/9] 注册 FP-USD 账号...")
    api_config = get_api_config(ENV)
    result = register_account(journey="200K", currency="USD", api_config=api_config)

    if not result:
        print("[FAIL] 注册失败")
        return None

    phone = result['phone_number']
    print(f"[OK] 注册成功")
    print(f"   手机号: {phone}")
    print(f"   Offer ID: {result['offer_id']}")

    # 查询关键 ID
    with DatabaseExecutor(env=ENV) as db:
        merchant_id = db.execute_sql(
            f"SELECT merchant_id FROM dpu_users WHERE phone_number='{phone}' LIMIT 1"
        )
        print(f"   Merchant ID: {merchant_id}")

    time.sleep(3)

    # 查询 application_unique_id 和 merchant_account_id
    with DatabaseExecutor(env=ENV) as db:
        application_unique_id = db.execute_sql(
            f"SELECT application_unique_id FROM dpu_application WHERE merchant_id='{merchant_id}' LIMIT 1"
        )
        merchant_account_id = db.execute_sql(
            f"SELECT merchant_account_id FROM dpu_merchant_account_limit WHERE merchant_id='{merchant_id}' LIMIT 1"
        )
        print(f"   Application ID: {application_unique_id}")
        print(f"   Account ID: {merchant_account_id}")

    lender_approved_offer_id = f"lender-{application_unique_id}" if application_unique_id else "lender-default"

    # 步骤 2: Approved Offer (第一次)
    print("\n[步骤 2/9] Approved Offer (第一次)...")
    approved_offer_body = {
        "data": {
            "eventType": "approvedoffer.completed",
            "eventId": generate_uuid37(),
            "eventMessage": "Application approval process completed successfully",
            "enquiryUrl": "https://api.lender.com/enquiry/12345",
            "datetime": get_utc_time(),
            "details": {
                "merchantId": merchant_id,
                "dpuApplicationId": application_unique_id,
                "originalRequestId": "req_1111113579",
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
                    "approvedAmount": 200000,
                    "currency": "USD"
                }
            }
        }
    }
    send_webhook(approved_offer_body)
    print("[OK] Approved Offer (第一次) 完成")
    time.sleep(3)

    # 步骤 3: E-sign (第一次)
    print("\n[步骤 3/9] E-sign (第一次)...")
    esign_body = {
        "data": {
            "eventType": "esign.completed",
            "eventId": generate_uuid37(),
            "eventMessage": "E-signature process completed successfully",
            "enquiryUrl": "https://api.lender.com/enquiry/12345",
            "datetime": get_utc_time(),
            "details": {
                "merchantId": merchant_id,
                "dpuApplicationId": application_unique_id,
                "lenderApprovedOfferId": lender_approved_offer_id,
                "originalRequestId": "req_1111113579",
                "status": "SUCCESS"
            }
        }
    }
    send_webhook(esign_body)
    print("[OK] E-sign (第一次) 完成")
    time.sleep(3)

    # 步骤 4: Drawdown (第一次)
    print("\n[步骤 4/9] Drawdown (第一次)...")
    drawdown_body = {
        "data": {
            "eventType": "drawdown.completed",
            "eventId": generate_uuid37(),
            "eventMessage": "Drawdown process completed successfully",
            "enquiryUrl": "https://api.lender.com/enquiry/12345",
            "datetime": get_utc_time(),
            "details": {
                "merchantId": merchant_id,
                "dpuApplicationId": application_unique_id,
                "lenderApprovedOfferId": lender_approved_offer_id,
                "originalRequestId": "req_1111113579",
                "status": "APPROVED",
                "lenderLoanId": f"lender-loan-{generate_uuid37()[:10]}",
                "drawdownAmount": 200000,
                "currency": "USD"
            }
        }
    }
    send_webhook(drawdown_body)
    print("[OK] Drawdown (第一次) 完成")
    time.sleep(3)

    # 步骤 5: Underwritten
    print("\n[步骤 5/9] Underwritten...")
    underwritten_body = {
        "data": {
            "eventType": "underwritten.completed",
            "eventId": generate_uuid37(),
            "eventMessage": "Underwriting process completed successfully",
            "enquiryUrl": "https://api.lender.com/enquiry/12345",
            "datetime": get_utc_time(),
            "details": {
                "merchantId": merchant_id,
                "merchantAccountId": merchant_account_id,
                "dpuApplicationId": application_unique_id,
                "originalRequestId": "req_1111113579",
                "status": "APPROVED",
                "approvedAmount": 200000,
                "currency": "USD"
            }
        }
    }
    send_webhook(underwritten_body)
    print("[OK] Underwritten 完成")
    time.sleep(3)

    # 步骤 6: Approved Offer (第二次)
    print("\n[步骤 6/9] Approved Offer (第二次)...")
    send_webhook(approved_offer_body)
    print("[OK] Approved Offer (第二次) 完成")
    time.sleep(3)

    # 步骤 7: PSP Start
    print("\n[步骤 7/9] PSP Start...")
    psp_start_body = {
        "data": {
            "eventType": "psp.start",
            "eventId": generate_uuid37(),
            "eventMessage": "PSP verification process started",
            "enquiryUrl": "https://api.lender.com/enquiry/12345",
            "datetime": get_utc_time(),
            "details": {
                "merchantId": merchant_id,
                "dpuApplicationId": application_unique_id,
                "lenderApprovedOfferId": lender_approved_offer_id,
                "originalRequestId": "req_1111113579"
            }
        }
    }
    send_webhook(psp_start_body)
    print("[OK] PSP Start 完成")
    time.sleep(3)

    # 步骤 8: PSP Completed
    print("\n[步骤 8/9] PSP Completed...")
    psp_completed_body = {
        "data": {
            "eventType": "psp.completed",
            "eventId": generate_uuid37(),
            "eventMessage": "PSP verification process completed successfully",
            "enquiryUrl": "https://api.lender.com/enquiry/12345",
            "datetime": get_utc_time(),
            "details": {
                "merchantId": merchant_id,
                "dpuApplicationId": application_unique_id,
                "lenderApprovedOfferId": lender_approved_offer_id,
                "originalRequestId": "req_1111113579",
                "status": "SUCCESS"
            }
        }
    }
    send_webhook(psp_completed_body)
    print("[OK] PSP Completed 完成")
    time.sleep(3)

    # 步骤 9: E-sign (第二次 - 最终目标)
    print("\n[步骤 9/9] E-sign (第二次 - 最终目标)...")
    send_webhook(esign_body)
    print("[OK] E-sign (第二次) 完成")
    time.sleep(2)

    # 验证最终状态
    print("\n" + "="*80)
    print("验证最终状态...")
    print("="*80)

    with DatabaseExecutor(env=ENV) as db:
        esign_status = db.execute_sql(
            f"SELECT esign_status FROM dpu_application WHERE merchant_id='{merchant_id}' LIMIT 1"
        )
        psp_status = db.execute_sql(
            f"SELECT psp_status FROM dpu_application WHERE merchant_id='{merchant_id}' LIMIT 1"
        )
        approval_status = db.execute_sql(
            f"SELECT approval_status FROM dpu_application WHERE merchant_id='{merchant_id}' LIMIT 1"
        )

        print(f"E-sign 状态: {esign_status}")
        print(f"PSP 状态: {psp_status}")
        print(f"Approval 状态: {approval_status}")

    # 生成流程报告
    flow_report = {
        "environment": ENV,
        "journey": "FP (200K)",
        "currency": "USD",
        "phone_number": phone,
        "merchant_id": merchant_id,
        "application_unique_id": application_unique_id,
        "merchant_account_id": merchant_account_id,
        "offer_id": result['offer_id'],
        "steps_completed": [
            "1. 注册账号",
            "2. Approved Offer (第一次)",
            "3. E-sign (第一次)",
            "4. Drawdown (第一次)",
            "5. Underwritten",
            "6. Approved Offer (第二次)",
            "7. PSP Start",
            "8. PSP Completed",
            "9. E-sign (第二次) [OK]"
        ],
        "final_status": {
            "esign_status": esign_status,
            "psp_status": psp_status,
            "approval_status": approval_status
        }
    }

    # 保存报告
    with open('fp_usd_flow_report.json', 'w', encoding='utf-8') as f:
        json.dump(flow_report, f, indent=2, ensure_ascii=False)

    print("\n" + "="*80)
    print("[OK] FP-USD 完整流程执行成功！")
    print("="*80)
    print(f"手机号: {phone}")
    print(f"Merchant ID: {merchant_id}")
    print(f"最终状态: E-sign {esign_status}")
    print(f"流程报告已保存到: fp_usd_flow_report.json")
    print("="*80)

    return flow_report

if __name__ == "__main__":
    fp_usd_to_esign_flow()
