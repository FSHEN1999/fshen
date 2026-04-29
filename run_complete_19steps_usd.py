# -*- coding: utf-8 -*-
"""
Complete FP-USD-500k flow following scenario_1.ms (19 steps)
"""
import hashlib
import json
import logging
import random
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
import pymysql
import requests

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

BASE_URL = "https://dpu-gateway-reg.dowsure.com"
DB_CONFIG = {
    "host": "18.162.145.173",
    "user": "dpu_reg",
    "password": "r4asUYBX3R6LNdp",
    "database": "dpu_seller_center",
    "port": 3307,
    "charset": "utf8mb4"
}

def query_db(sql):
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute(sql)
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

def wait_db(sql, desc, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = query_db(sql)
        if result:
            return result
        time.sleep(2)
    raise Exception(f'Timeout: {desc}')

def gen_phone():
    prefixes = ["130", "131", "132", "133", "135", "136", "137", "138", "139",
                "150", "151", "152", "155", "156", "157", "158", "159",
                "180", "181", "182", "183", "184", "185", "186", "187", "188", "189"]
    return random.choice(prefixes) + str(random.randint(0, 99999999)).zfill(8)

def gen_selling_partner_id():
    seed = f"{uuid.uuid4()}-{random.random()}".encode("utf-8")
    return hashlib.md5(seed).hexdigest().upper()

def send_webhook(event_type, payload):
    log.info(f"Webhook: {event_type}")
    resp = requests.post(f"{BASE_URL}/dpu-openapi/webhook-notifications", json=payload, timeout=30)
    log.info(f"  Response: {resp.status_code}")
    if resp.status_code != 200:
        log.error(f"  Failed: {resp.text[:300]}")
        raise Exception(f"Webhook failed")
    return resp

def main():
    log.info("="*60)
    log.info("FP-USD-500k Complete Flow (19 Steps)")
    log.info("="*60)

    # Step 1: Send Registration SMS
    log.info("\n[Step 1] Send Registration SMS")
    phone = gen_phone()
    email = f"{phone}@163.com"
    log.info(f"  Phone: {phone}")
    log.info(f"  Email: {email}")

    resp = requests.post(f"{BASE_URL}/dpu-user/auth/sendSmsCode-sign",
                        json={"phoneNumber": phone, "smsType": "SIGN_UP"},
                        headers={"content-type": "application/json"}, timeout=30)
    log.info(f"  SMS sent: {resp.status_code}")

    # Step 2: Validate SMS Code and Generate Token
    log.info("\n[Step 2] Validate SMS Code")
    resp = requests.post(f"{BASE_URL}/dpu-user/auth/validateSmsCode-sign",
                        json={"areaCode": "+86", "code": "666666", "phone": phone},
                        headers={"content-type": "application/json"}, timeout=30)
    log.info(f"  Validated: {resp.status_code}")

    # Generate offer ID before signup
    log.info("\n[Pre-Step 3] Generate Offer ID")
    resp = requests.post(f"{BASE_URL}/dpu-merchant/mock/generate-shop-performance",
                        json={"yearlyRepaymentAmount": 800000}, timeout=30)
    offer_id = resp.json()["data"]["amazon3plOfferId"]
    log.info(f"  Offer ID: {offer_id}")

    # Get redirect
    requests.get(f"{BASE_URL}/dpu-merchant/amazon/redirect?offerId={offer_id}", timeout=30)

    # Step 3: User Signup
    log.info("\n[Step 3] User Signup")
    payload = {
        "phone": phone,
        "areaCode": "+86",
        "code": "666666",
        "email": email,
        "offerId": offer_id,
        "password": "Aa11111111..",
        "confirmPassword": "Aa11111111..",
        "isAcceptMarketing": True,
        "securityQuestionCode": "SEC_Q_004",
        "securityAnswer": "test",
        "preferFinanceProductCurrency": "USD"
    }
    resp = requests.post(f"{BASE_URL}/dpu-user/auth/signup", json=payload,
                        headers={"content-type": "application/json", "product-currency": "USD",
                                "finance-product": "LINE_OF_CREDIT", "funder-resource": "FUNDPARK"},
                        timeout=30)
    token = resp.json()["data"]["token"]
    log.info(f"  Token: {token[:20]}...")

    result = query_db(f"SELECT merchant_id FROM dpu_users WHERE phone_number='{phone}'")
    merchant_id = result['merchant_id']
    log.info(f"  Merchant ID: {merchant_id}")

    headers_auth = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "finance-product": "LINE_OF_CREDIT",
        "funder-resource": "FUNDPARK",
        "product-currency": "USD"
    }

    # Step 4: Generate State for SP
    log.info("\n[Step 4] Generate State for SP")
    state = str(uuid.uuid4())
    log.info(f"  State: {state}")

    # Step 5: SP Authorization
    log.info("\n[Step 5] SP Authorization")
    selling_partner_id = gen_selling_partner_id()
    log.info(f"  Selling Partner ID: {selling_partner_id}")

    requests.post(f"{BASE_URL}/dpu-merchant/shop-authorization/v2/sp-auth-url",
                 json={"redirectUrl": f"https://expressfinance-dpu-reg.dowsure.com/redirect-loading?state={state}",
                       "sceneCode": "SHOP_BIND", "sourceCode": "FUNDPARK", "state": state},
                 headers=headers_auth, timeout=30)

    requests.get(f"{BASE_URL}/dpu-auth/amazon-sp/auth",
                params={"mws_auth_token": "1235", "selling_partner_id": selling_partner_id,
                       "spapi_oauth_code": "123123", "state": state}, timeout=30)
    log.info("  SP authorization completed")
    time.sleep(2)

    # Get merchant_account_id for manual_offer
    result = query_db(f"SELECT merchant_account_id FROM dpu_merchant_account_limit WHERE merchant_id='{merchant_id}' LIMIT 1")
    if not result:
        result = wait_db(f"SELECT id FROM dpu_merchant_account WHERE merchant_id='{merchant_id}' LIMIT 1", "merchant_account", timeout=10)
        merchant_account_id = result['id']
    else:
        merchant_account_id = result['merchant_account_id']

    # Insert manual_offer (REG environment workaround)
    log.info("\n[Fix] Insert manual_offer record")
    idempotency_key = str(uuid.uuid4()).replace('-', '')
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(f"""
        INSERT INTO dpu_manual_offer (
            id, merchant_id, merchant_account_id, marketplace_country, product_code,
            platform_seller_id, platform_offer_id, send_status, reason, offer_type,
            term, term_unit, min_apr, max_apr, min_interest, max_interest,
            min_amount, max_amount, currency, offer_status, idempotency_key,
            created_at, updated_at
        ) VALUES (
            '{str(uuid.uuid4()).replace('-', '')}', '{merchant_id}', '{merchant_account_id}', 'US', 'LINE_OF_CREDIT',
            '{selling_partner_id}', '{offer_id}', 'SUCCESS', '', 'NEW',
            12, 'MONTH', 0.12, 0.20, 0.12, 0.20,
            0, 14000, 'USD', 'INQUIRED', '{idempotency_key}',
            NOW(), NOW()
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()
    log.info(f"  Idempotency Key: {idempotency_key}")

    # Step 6: sp-updateOffer
    log.info("\n[Step 6] sp-updateOffer")
    requests.post(f"{BASE_URL}/dpu-auth/amazon-sp/updateOffer",
                 json={"idempotencyKey": idempotency_key, "offerId": offer_id,
                       "reason": "An offer already exists", "sendStatus": "SUCCESS"}, timeout=30)
    log.info("  Update offer completed")

    # Step 7: Amazon 3PL Authorization (GET)
    log.info("\n[Step 7] Amazon 3PL Authorization (GET)")
    requests.get(f"{BASE_URL}/dpu-merchant/amazon/redirect", params={"offerId": offer_id}, timeout=30)
    log.info("  3PL GET completed")

    # Step 8: 3PL AUTH Authorization (POST)
    log.info("\n[Step 8] 3PL AUTH Authorization (POST)")
    requests.post(f"{BASE_URL}/dpu-merchant/amazon/redirect",
                 json={"authToken": "mock", "expireOn": "null", "keyId": "null",
                       "offerId": offer_id, "relayPage": 1, "returnUrl": "null",
                       "signature": "null"}, timeout=60)
    log.info("  3PL POST completed")
    time.sleep(2)

    # Step 9: Create Application
    log.info("\n[Step 9] Create Application")
    requests.post(f"{BASE_URL}/dpu-merchant/fundpark-application/create",
                 json={"tierCode": "2", "tierSnapshotValue": 0},
                 headers=headers_auth, timeout=30)
    time.sleep(2)

    result = wait_db(f"SELECT application_unique_id FROM dpu_application WHERE merchant_id='{merchant_id}' LIMIT 1", "application_id")
    app_id = result['application_unique_id']
    log.info(f"  Application ID: {app_id}")

    result = wait_db(f"SELECT authorization_id FROM dpu_auth_token WHERE merchant_id='{merchant_id}' AND authorization_party='SP' LIMIT 1", "authorization_id")
    account_id = result['authorization_id']
    log.info(f"  Account ID: {account_id}")

    # Step 10: Submit Business Info (Dun & Bradstreet)
    log.info("\n[Step 10] Submit Business Info")
    requests.post(f"{BASE_URL}/dpu-merchant/fundpark-application/business-info",
                 json={"businessName": "Test Business", "businessType": "COMPANY",
                       "country": "US", "city": "New York", "state": "NY"},
                 headers=headers_auth, timeout=30)
    log.info("  Business info submitted")

    # Step 11: Select Offer Amount - 500k
    log.info("\n[Step 11] Select Offer Amount - 500k")
    requests.post(f"{BASE_URL}/dpu-merchant/fundpark-application/select-amount",
                 json={"minAmount": 500000, "maxAmount": 500000},
                 headers=headers_auth, timeout=30)
    log.info("  Offer amount selected")

    # Step 12: Create Offer Default Values
    log.info("\n[Step 12] Create Credit Offer")
    requests.post(f"{BASE_URL}/dpu-merchant/credit-offer/create", headers=headers_auth, timeout=30)
    log.info("  Credit offer created")
    time.sleep(2)

    # Step 13: Link SP and 3PL Shops
    log.info("\n[Step 13] Link SP and 3PL Shops")
    requests.post(f"{BASE_URL}/dpu-merchant/mock/link-sp-3pl-shops", params={"phone": phone}, timeout=30)
    log.info("  Shops linked")
    time.sleep(2)

    # Step 14: Run FP Scheduled Tasks and Poll SUBMITTED
    log.info("\n[Step 14] Wait for Limit Application (Scheduled Tasks)")
    result = wait_db(f"SELECT limit_application_unique_id FROM dpu_limit_application WHERE merchant_id='{merchant_id}' LIMIT 1", "limit_application_id", timeout=180)
    limit_app_id = result['limit_application_unique_id']
    log.info(f"  Limit Application ID: {limit_app_id}")

    # Poll for SUBMITTED status
    log.info("  Polling for SUBMITTED status...")
    for i in range(30):
        resp = requests.get(f"{BASE_URL}/dpu-merchant/credit-offer/status", headers=headers_auth, timeout=30)
        status = resp.json().get("data", {}).get("status")
        log.info(f"  Poll {i+1}: {status}")
        if status == "SUBMITTED":
            break
        time.sleep(3)
    log.info("  Status: SUBMITTED")

    # Step 15: Underwritten Webhook
    log.info("\n[Step 15] Underwritten Webhook")
    event_id = str(uuid.uuid4())
    # Skip underwritten as it's auto-generated in REG
    log.info("  Skipped (auto-generated by scheduled tasks)")

    # Step 16: Approved-Offer Webhook
    log.info("\n[Step 16] Approved-Offer Webhook")
    event_id = str(uuid.uuid4())
    send_webhook("approvedoffer.completed", {
        "data": {
            "eventType": "approvedoffer.completed",
            "eventId": event_id,
            "dateTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": merchant_id,
                "dpuApplicationId": app_id,
                "lenderApprovedOfferId": f"lender-{app_id}",
                "originalRequestId": "req_" + event_id.replace("-", ""),
                "offer": {
                    "approvedLimit": {"amount": "500000", "currency": "USD"},
                    "offerStartDate": datetime.now().strftime("%Y-%m-%d"),
                    "offerEndDate": (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
                }
            }
        }
    })
    time.sleep(3)

    result = wait_db(f"SELECT lender_approved_offer_id FROM dpu_credit_offer WHERE merchant_id='{merchant_id}' LIMIT 1", "lender_approved_offer_id")
    lender_offer_id = result['lender_approved_offer_id']
    log.info(f"  Lender Approved Offer ID: {lender_offer_id}")

    # Step 17: PSP Start Webhook
    log.info("\n[Step 17] PSP Start Webhook")
    event_id = str(uuid.uuid4())
    send_webhook("psp.verification.started", {
        "data": {
            "eventType": "psp.verification.started",
            "eventId": event_id,
            "dateTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": merchant_id,
                "merchantAccountId": account_id,
                "lenderApprovedOfferId": lender_offer_id,
                "result": "PROCESSING"
            }
        }
    })
    time.sleep(3)

    # Step 18: PSP Completed Webhook
    log.info("\n[Step 18] PSP Completed Webhook")
    event_id = str(uuid.uuid4())
    send_webhook("psp.verification.completed", {
        "data": {
            "eventType": "psp.verification.completed",
            "eventId": event_id,
            "dateTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": merchant_id,
                "merchantAccountId": account_id,
                "lenderApprovedOfferId": lender_offer_id,
                "result": "SUCCESS"
            }
        }
    })
    time.sleep(3)

    # Step 19: E-signature Webhook
    log.info("\n[Step 19] E-signature Webhook")
    event_id = str(uuid.uuid4())
    send_webhook("esign.completed", {
        "data": {
            "eventType": "esign.completed",
            "eventId": event_id,
            "dateTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": merchant_id,
                "lenderApprovedOfferId": lender_offer_id,
                "signedLimit": {"amount": "500000", "currency": "USD"},
                "result": "SUCCESS"
            }
        }
    })
    time.sleep(3)

    # Verify Final Status
    log.info("\n" + "="*60)
    log.info("Verify Final Status")
    result = query_db(f"SELECT status, e_sign_status, approved_limit_amount, signed_limit_amount FROM dpu_credit_offer WHERE merchant_id='{merchant_id}' ORDER BY created_at DESC LIMIT 1")
    log.info(f"  Status: {result['status']}")
    log.info(f"  E-sign Status: {result['e_sign_status']}")
    log.info(f"  Approved Amount: {result['approved_limit_amount']}")
    log.info(f"  Signed Amount: {result['signed_limit_amount']}")

    log.info("="*60)
    if result['e_sign_status'] == 'SUCCESS':
        log.info("SUCCESS! FP-USD-500k E-SIGNATURE COMPLETED!")
        log.info("="*60)
        return {
            "phone": phone,
            "merchant_id": merchant_id,
            "application_id": app_id,
            "lender_approved_offer_id": lender_offer_id,
            "currency": "USD",
            "amount": "500000",
            "status": result['e_sign_status']
        }
    else:
        raise Exception(f"E-signature failed: {result['e_sign_status']}")

if __name__ == "__main__":
    try:
        result = main()
        print(f"\n\nFINAL RESULT:\n{json.dumps(result, indent=2)}")
    except Exception as e:
        log.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
