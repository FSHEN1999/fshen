# -*- coding: utf-8 -*-
"""
完成 FP-USD 流程：SP API 授权 -> esign 成功
使用已注册账号：13514183158
环境：SIT
"""
import sys
sys.path.insert(0, '.')

from mock_sit import DatabaseExecutor, generate_uuid37, get_utc_time, calculate_future_date
import requests
import json
import time
import hashlib
import uuid

ENV = "sit"
BASE_URL = "https://sit.api.expressfinance.business.hsbc.com"
PHONE = "13514183158"
MERCHANT_ID = "b99447f70c09418da2a858a157e7b417"

def sp_api_auth_and_continue():
    """完成 SP API 授权并继续推进到 esign"""

    print("="*80)
    print("FP-USD 流程继续：SP API 授权 -> esign 成功")
    print("="*80)
    print(f"手机号: {PHONE}")
    print(f"Merchant ID: {MERCHANT_ID}")

    # 步骤 1: 生成 selling_partner_id 和 state
    print("\n[步骤 1] 生成 SP API 授权参数...")
    selling_partner_id = hashlib.md5(f"{uuid.uuid4()}{time.time()}".encode()).hexdigest().upper()
    state = str(uuid.uuid4())
    print(f"   selling_partner_id: {selling_partner_id}")
    print(f"   state: {state}")

    # 步骤 2: 获取 token
    print("\n[步骤 2] 获取 token...")
    with DatabaseExecutor(env=ENV) as db:
        token = db.execute_sql(
            f"SELECT token FROM dpu_users WHERE phone_number='{PHONE}' LIMIT 1"
        )
        print(f"   Token: {token[:50]}...")

    # 步骤 3: SP API 授权
    print("\n[步骤 3] 执行 SP API 授权...")
    sp_auth_url = f"{BASE_URL}/dpu-auth/amazon-sp/auth"
    sp_auth_params = {
        "mws_auth_token": "1235",
        "selling_partner_id": selling_partner_id,
        "spapi_oauth_code": "123123",
        "state": state
    }
    sp_auth_headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "finance-product": "LINE_OF_CREDIT",
        "funder-resource": "FUNDPARK",
        "product-currency": "USD"
    }

    sp_auth_resp = requests.get(sp_auth_url, params=sp_auth_params, headers=sp_auth_headers, timeout=60)
    print(f"   SP Auth 响应: {sp_auth_resp.status_code}")
    if sp_auth_resp.status_code != 200:
        print(f"   响应内容: {sp_auth_resp.text}")

    time.sleep(3)

    # 步骤 4: 查询 platform_offer_id 和 idempotency_key
    print("\n[步骤 4] 查询 platform_offer_id...")
    with DatabaseExecutor(env=ENV) as db:
        result = db.execute_query(
            f"SELECT idempotency_key, platform_offer_id FROM dpu_manual_offer WHERE platform_seller_id='{selling_partner_id}' ORDER BY created_at DESC LIMIT 1"
        )
        if result:
            idempotency_key = result['idempotency_key']
            platform_offer_id = result['platform_offer_id']
            print(f"   idempotency_key: {idempotency_key}")
            print(f"   platform_offer_id: {platform_offer_id}")
        else:
            print("   [WARN] 未找到 platform_offer_id")
            idempotency_key = str(uuid.uuid4())
            platform_offer_id = f"amzn1.lending.offer.us.{generate_uuid37()[:20]}TESTOFFER"

    time.sleep(2)

    # 步骤 5: updateOffer
    print("\n[步骤 5] 执行 updateOffer...")
    update_offer_url = f"{BASE_URL}/dpu-auth/amazon-sp/updateOffer"
    update_offer_body = {
        "idempotencyKey": idempotency_key,
        "offerId": platform_offer_id,
        "reason": "An offer already exists for the seller for the same partner product combination",
        "sendStatus": "SUCCESS"
    }

    update_offer_resp = requests.post(update_offer_url, json=update_offer_body, headers=sp_auth_headers, timeout=60)
    print(f"   updateOffer 响应: {update_offer_resp.status_code}")
    if update_offer_resp.status_code != 200:
        print(f"   响应内容: {update_offer_resp.text}")

    time.sleep(3)

    # 步骤 6: 查询关键 ID
    print("\n[步骤 6] 查询关键 ID...")
    with DatabaseExecutor(env=ENV) as db:
        application_unique_id = db.execute_sql(
            f"SELECT application_unique_id FROM dpu_application WHERE merchant_id='{MERCHANT_ID}' LIMIT 1"
        )
        merchant_account_id = db.execute_sql(
            f"SELECT merchant_account_id FROM dpu_merchant_account_limit WHERE merchant_id='{MERCHANT_ID}' LIMIT 1"
        )
        print(f"   application_unique_id: {application_unique_id}")
        print(f"   merchant_account_id: {merchant_account_id}")

    if not application_unique_id or not merchant_account_id:
        print("\n[WARN] 关键 ID 仍然为空，可能需要更多时间或额外步骤")
        return

    # 步骤 7: 发送 webhook - Approved Offer
    print("\n[步骤 7] 发送 Approved Offer webhook...")
    lender_approved_offer_id = f"lender-{application_unique_id}"
    webhook_url = f"{BASE_URL}/dpu-openapi/webhook-notifications"

    approved_offer_body = {
        "data": {
            "eventType": "approvedoffer.completed",
            "eventId": generate_uuid37(),
            "eventMessage": "Application approval process completed successfully",
            "enquiryUrl": "https://api.lender.com/enquiry/12345",
            "datetime": get_utc_time(),
            "details": {
                "merchantId": MERCHANT_ID,
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
                    "approvedAmount": 500000,
                    "currency": "USD"
                }
            }
        }
    }

    webhook_resp = requests.post(webhook_url, json=approved_offer_body, timeout=30)
    print(f"   Webhook 响应: {webhook_resp.status_code}")
    if webhook_resp.status_code != 200:
        print(f"   响应内容: {webhook_resp.text}")

    time.sleep(3)

    # 步骤 8: PSP Start
    print("\n[步骤 8] 发送 PSP Start webhook...")
    psp_start_body = {
        "data": {
            "eventType": "psp.verification.started",
            "eventId": generate_uuid37(),
            "eventMessage": "PSP verification process started",
            "enquiryUrl": "https://api.lender.com/enquiry/12345",
            "datetime": get_utc_time(),
            "details": {
                "merchantId": MERCHANT_ID,
                "dpuApplicationId": application_unique_id,
                "lenderApprovedOfferId": lender_approved_offer_id,
                "originalRequestId": "req_1111113579"
            }
        }
    }

    webhook_resp = requests.post(webhook_url, json=psp_start_body, timeout=30)
    print(f"   Webhook 响应: {webhook_resp.status_code}")
    time.sleep(3)

    # 步骤 9: PSP Completed
    print("\n[步骤 9] 发送 PSP Completed webhook...")
    psp_completed_body = {
        "data": {
            "eventType": "psp.verification.completed",
            "eventId": generate_uuid37(),
            "eventMessage": "PSP verification process completed successfully",
            "enquiryUrl": "https://api.lender.com/enquiry/12345",
            "datetime": get_utc_time(),
            "details": {
                "merchantId": MERCHANT_ID,
                "dpuApplicationId": application_unique_id,
                "lenderApprovedOfferId": lender_approved_offer_id,
                "originalRequestId": "req_1111113579",
                "status": "SUCCESS"
            }
        }
    }

    webhook_resp = requests.post(webhook_url, json=psp_completed_body, timeout=30)
    print(f"   Webhook 响应: {webhook_resp.status_code}")
    time.sleep(3)

    # 步骤 10: E-sign
    print("\n[步骤 10] 发送 E-sign webhook...")
    esign_body = {
        "data": {
            "eventType": "esign.completed",
            "eventId": generate_uuid37(),
            "eventMessage": "E-signature process completed successfully",
            "enquiryUrl": "https://api.lender.com/enquiry/12345",
            "datetime": get_utc_time(),
            "details": {
                "merchantId": MERCHANT_ID,
                "dpuApplicationId": application_unique_id,
                "lenderApprovedOfferId": lender_approved_offer_id,
                "originalRequestId": "req_1111113579",
                "status": "SUCCESS"
            }
        }
    }

    webhook_resp = requests.post(webhook_url, json=esign_body, timeout=30)
    print(f"   Webhook 响应: {webhook_resp.status_code}")

    # 验证最终状态
    print("\n" + "="*80)
    print("验证最终状态...")
    print("="*80)

    with DatabaseExecutor(env=ENV) as db:
        # 查询 application 状态
        app_status = db.execute_sql(
            f"SELECT application_status FROM dpu_application WHERE merchant_id='{MERCHANT_ID}' LIMIT 1"
        )

        # 查询 credit_offer 状态
        credit_offer_status = db.execute_sql(
            f"SELECT status FROM dpu_credit_offer WHERE merchant_id='{MERCHANT_ID}' ORDER BY created_at DESC LIMIT 1"
        )

        print(f"Application 状态: {app_status}")
        print(f"Credit Offer 状态: {credit_offer_status}")

    # 生成报告
    report = {
        "environment": ENV,
        "phone_number": PHONE,
        "merchant_id": MERCHANT_ID,
        "selling_partner_id": selling_partner_id,
        "application_unique_id": application_unique_id,
        "merchant_account_id": merchant_account_id,
        "platform_offer_id": platform_offer_id,
        "steps_completed": [
            "1. 生成 SP API 授权参数",
            "2. 获取 token",
            "3. 执行 SP API 授权",
            "4. 查询 platform_offer_id",
            "5. 执行 updateOffer",
            "6. 查询关键 ID",
            "7. 发送 Approved Offer webhook",
            "8. 发送 PSP Start webhook",
            "9. 发送 PSP Completed webhook",
            "10. 发送 E-sign webhook"
        ],
        "final_status": {
            "application_status": app_status,
            "credit_offer_status": credit_offer_status
        }
    }

    with open('fp_usd_sp_auth_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n" + "="*80)
    print("[OK] FP-USD 流程执行完成！")
    print("="*80)
    print(f"报告已保存到: fp_usd_sp_auth_report.json")
    print("="*80)

    return report

if __name__ == "__main__":
    sp_api_auth_and_continue()
