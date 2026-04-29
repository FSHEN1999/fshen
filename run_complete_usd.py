# -*- coding: utf-8 -*-
"""
Complete FP-USD flow: Registration -> SP Auth -> Application -> Webhooks -> E-signature
"""
import hashlib
import json
import logging
import os
import random
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
import pymysql
import requests
from faker import Faker

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

faker = Faker("zh_CN")

def query_db(sql):
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute(sql)
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

def wait_db(sql, desc, timeout=30):
    for _ in range(timeout // 2):
        result = query_db(sql)
        if result:
            return result
        time.sleep(2)
    raise Exception(f"Timeout: {desc}")

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
    log.info("FP-USD Complete Flow: Registration -> E-signature")
    log.info("="*60)

    # Step 1: Generate offer ID
    log.info("\n[Step 1] Generate offer ID")
    resp = requests.post(f"{BASE_URL}/dpu-merchant/mock/generate-shop-performance",
                        json={"yearlyRepaymentAmount": 800000}, timeout=30)
    offer_id = resp.json()["data"]["amazon3plOfferId"]
    log.info(f"  Offer ID: {offer_id}")

    # Step 2: Registration
    log.info("\n[Step 2] User registration")
    phone = gen_phone()
    email = f"{phone}@163.com"
    log.info(f"  Phone: {phone}")
    log.info(f"  Email: {email}")

    headers = {
        "content-type": "application/json",
        "product-currency": "USD",
        "finance-product": "LINE_OF_CREDIT",
        "funder-resource": "FUNDPARK"
    }

    # Validate SMS
    requests.post(f"{BASE_URL}/dpu-user/auth/validateSmsCode-sign",
                 json={"areaCode": "+86", "code": "666666", "phone": phone},
                 headers=headers, timeout=30)

    # Get redirect
    requests.get(f"{BASE_URL}/dpu-merchant/amazon/redirect?offerId={offer_id}", timeout=30)

    # Signup
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
    resp = requests.post(f"{BASE_URL}/dpu-user/auth/signup", json=payload, headers=headers, timeout=30)
    token = resp.json()["data"]["token"]
    log.info(f"  Token: {token[:20]}...")

    result = query_db(f"SELECT merchant_id FROM dpu_users WHERE phone_number='{phone}'")
    merchant_id = result['merchant_id']
    log.info(f"  Merchant ID: {merchant_id}")

    # Step 3: SP Authorization
    log.info("\n[Step 3] SP Authorization")
    state = str(uuid.uuid4())
    selling_partner_id = gen_selling_partner_id()
    log.info(f"  State: {state}")
    log.info(f"  Selling Partner ID: {selling_partner_id}")

    headers_auth = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "finance-product": "LINE_OF_CREDIT",
        "funder-resource": "FUNDPARK",
        "product-currency": "USD"
    }

    requests.post(f"{BASE_URL}/dpu-merchant/shop-authorization/v2/sp-auth-url",
                 json={"redirectUrl": f"https://expressfinance-dpu-reg.dowsure.com/redirect-loading?state={state}",
                       "sceneCode": "SHOP_BIND", "sourceCode": "FUNDPARK", "state": state},
                 headers=headers_auth, timeout=30)

    requests.get(f"{BASE_URL}/dpu-auth/amazon-sp/auth",
                params={"mws_auth_token": "1235", "selling_partner_id": selling_partner_id,
                       "spapi_oauth_code": "123123", "state": state}, timeout=30)
    log.info("  SP authorization completed")
    time.sleep(2)

    # Step 4: Get platform_offer_id
    log.info("\n[Step 4] Get platform_offer_id")
    result = wait_db(f"SELECT platform_offer_id, idempotency_key FROM dpu_manual_offer "
                    f"WHERE platform_seller_id='{selling_partner_id}' LIMIT 1", "platform_offer_id")
    platform_offer_id = result['platform_offer_id']
    idempotency_key = result['idempotency_key']
    log.info(f"  Platform Offer ID: {platform_offer_id}")

    # Step 5: Update offer & 3PL
    log.info("\n[Step 5] Update offer and 3PL authorization")
    requests.post(f"{BASE_URL}/dpu-auth/amazon-sp/updateOffer",
                 json={"idempotencyKey": idempotency_key, "offerId": platform_offer_id,
                       "reason": "An offer already exists", "sendStatus": "SUCCESS"}, timeout=30)

    requests.get(f"{BASE_URL}/dpu-merchant/amazon/redirect",
                params={"offerId": platform_offer_id}, timeout=30)

    requests.post(f"{BASE_URL}/dpu-merchant/amazon/redirect",
                 json={"authToken": "mock", "expireOn": "null", "keyId": "null",
                       "offerId": platform_offer_id, "relayPage": 1, "returnUrl": "null",
                       "signature": "null"}, timeout=60)
    log.info("  3PL authorization completed")
    time.sleep(2)

    # Step 6: Create application
    log.info("\n[Step 6] Create application")
    requests.post(f"{BASE_URL}/dpu-merchant/fundpark-application/create",
                 json={"tierCode": "2", "tierSnapshotValue": 0},
                 headers=headers_auth, timeout=30)
    time.sleep(2)

    result = wait_db(f"SELECT application_unique_id FROM dpu_application "
                    f"WHERE merchant_id='{merchant_id}' LIMIT 1", "application_id")
    app_id = result['application_unique_id']
    log.info(f"  Application ID: {app_id}")

    result = wait_db(f"SELECT authorization_id FROM dpu_auth_token "
                    f"WHERE merchant_id='{merchant_id}' AND authorization_party='SP' LIMIT 1",
                    "authorization_id")
    account_id = result['authorization_id']
    log.info(f"  Account ID: {account_id}")

    # Step 7: Create credit offer
    log.info("\n[Step 7] Create credit offer")
    requests.post(f"{BASE_URL}/dpu-merchant/credit-offer/create", headers=headers_auth, timeout=30)
    time.sleep(2)

    # Step 8: Link SP-3PL
    log.info("\n[Step 8] Link SP-3PL shops")
    requests.post(f"{BASE_URL}/dpu-merchant/mock/link-sp-3pl-shops",
                 params={"phone": phone}, timeout=30)
    time.sleep(2)

    # Step 9: Wait for limit_application
    log.info("\n[Step 9] Wait for limit_application")
    result = wait_db(f"SELECT limit_application_unique_id FROM dpu_limit_application "
                    f"WHERE merchant_id='{merchant_id}' LIMIT 1", "limit_application_id", timeout=60)
    limit_app_id = result['limit_application_unique_id']
    log.info(f"  Limit Application ID: {limit_app_id}")

    # Step 10: Approved-offer webhook
    log.info("\n[Step 10] Send approved-offer webhook")
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

    result = wait_db(f"SELECT lender_approved_offer_id FROM dpu_credit_offer "
                    f"WHERE merchant_id='{merchant_id}' LIMIT 1", "lender_approved_offer_id")
    lender_offer_id = result['lender_approved_offer_id']
    log.info(f"  Lender Approved Offer ID: {lender_offer_id}")

    # Step 11: PSP start
    log.info("\n[Step 11] Send psp.verification.started webhook")
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

    # Step 12: PSP completed
    log.info("\n[Step 12] Send psp.verification.completed webhook")
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

    # Step 13: E-signature
    log.info("\n[Step 13] Send esign.completed webhook")
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

    # Verify final status
    log.info("\n" + "="*60)
    log.info("Verify final status")
    result = query_db(f"SELECT status, e_sign_status, approved_limit_amount, signed_limit_amount "
                     f"FROM dpu_credit_offer WHERE merchant_id='{merchant_id}' "
                     f"ORDER BY created_at DESC LIMIT 1")
    log.info(f"  Status: {result['status']}")
    log.info(f"  E-sign Status: {result['e_sign_status']}")
    log.info(f"  Approved Amount: {result['approved_limit_amount']}")
    log.info(f"  Signed Amount: {result['signed_limit_amount']}")

    log.info("="*60)
    if result['e_sign_status'] == 'SUCCESS':
        log.info("SUCCESS! FP-USD E-SIGNATURE COMPLETED!")
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
