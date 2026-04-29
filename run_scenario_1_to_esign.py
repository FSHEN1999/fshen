import hashlib
import json
import os
import random
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pymysql
import requests

BASE_URL = "https://dpu-gateway-reg.dowsure.com"
DB_CONFIG = {
    "host": "18.162.145.173",
    "user": "dpu_reg",
    "password": "r4asUYBX3R6LNdp",
    "database": "dpu_seller_center",
    "port": 3307,
    "charset": "utf8mb4",
    "connect_timeout": 15,
    "read_timeout": 15,
    "autocommit": True,
}

def db_fetchone(sql, args=()):
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchone()
    finally:
        conn.close()

def db_execute(sql, args=()):
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            affected = cur.execute(sql, args)
        conn.commit()
        return affected
    finally:
        conn.close()

def gen_phone():
    prefixes = ["130", "131", "132", "133", "135", "136", "137", "138", "139",
                "150", "151", "152", "155", "156", "157", "158", "159",
                "180", "181", "182", "183", "184", "185", "186", "187", "188", "189"]
    return random.choice(prefixes) + str(random.randint(0, 99999999)).zfill(8)

def gen_selling_partner_id():
    seed = f"{uuid.uuid4()}-{random.random()}".encode("utf-8")
    return hashlib.md5(seed).hexdigest().upper()

def fetch_sms_code(phone):
    for _ in range(15):
        row = db_fetchone(
            "SELECT placeholders FROM dpu_sms_record "
            "WHERE phone_number=%s ORDER BY COALESCE(send_time, create_time) DESC, id DESC LIMIT 1",
            (phone,))
        if row and row[0]:
            raw = row[0]
            try:
                payload = json.loads(raw) if isinstance(raw, str) else raw
                code = payload.get("verificationCode") if isinstance(payload, dict) else None
            except:
                match = re.search(r"(?<!\d)(\d{6})(?!\d)", str(raw))
                code = match.group(1) if match else None
            if code:
                return code
        time.sleep(2)
    raise Exception("Failed to fetch SMS code")

def wait_fetchone(sql, args, description, timeout=45):
    deadline = time.time() + timeout
    while time.time() < deadline:
        row = db_fetchone(sql, args)
        if row and any(item not in (None, "") for item in row):
            print(f"[DB] {description}: {row}")
            return row
        time.sleep(2)
    raise Exception(f"Timeout waiting for {description}")

def mark_virus_scan_ready(phone):
    app_row = wait_fetchone(
        "SELECT a.application_unique_id, a.merchant_id "
        "FROM dpu_application a JOIN dpu_users u ON u.merchant_id=a.merchant_id "
        "WHERE u.phone_number=%s ORDER BY a.created_at DESC LIMIT 1",
        (phone,), "application_unique_id", timeout=20)

    app_id = app_row[0]
    affected = db_execute(
        "UPDATE dpu_notify_event_dependency d "
        "JOIN dpu_notify_event e ON e.id=d.event_id AND e.event_type=d.event_type AND e.biz_id=d.biz_id "
        "SET d.dependency_status='READY', d.dependency_finish_time=NOW(), d.update_time=NOW() "
        "WHERE e.biz_id=%s AND d.dependency_type='VIRUS_SCAN' AND d.dependency_status<>'READY'",
        (app_id,))
    print(f"[DB] VIRUS_SCAN dependency ready: application={app_id} affected={affected}")
    return app_id

def send_webhook(event_type, variables):
    event_id = str(uuid.uuid4())
    datetime_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if event_type == "approvedoffer.completed":
        body = {
            "data": {
                "eventType": event_type,
                "eventId": event_id,
                "dateTime": datetime_utc,
                "details": {
                    "merchantId": variables["merchantId"],
                    "dpuApplicationId": variables["dpuApplicationId"],
                    "lenderApprovedOfferId": variables["lenderApprovedOfferId"],
                    "originalRequestId": "req_" + event_id.replace("-", ""),
                    "offer": {
                        "approvedLimit": {
                            "amount": variables["approvedAmount"],
                            "currency": variables["preferredCurrency"]
                        },
                        "offerStartDate": variables["offerStartDate"],
                        "offerEndDate": variables["offerEndDate"]
                    }
                }
            }
        }
    elif event_type == "psp.verification.started":
        body = {
            "data": {
                "eventType": event_type,
                "eventId": event_id,
                "dateTime": datetime_utc,
                "details": {
                    "merchantId": variables["merchantId"],
                    "merchantAccountId": variables["dpuMerchantAccountId"],
                    "lenderApprovedOfferId": variables["lenderApprovedOfferId"],
                    "result": "PROCESSING"
                }
            }
        }
    elif event_type == "psp.verification.completed":
        body = {
            "data": {
                "eventType": event_type,
                "eventId": event_id,
                "dateTime": datetime_utc,
                "details": {
                    "merchantId": variables["merchantId"],
                    "merchantAccountId": variables["dpuMerchantAccountId"],
                    "lenderApprovedOfferId": variables["lenderApprovedOfferId"],
                    "result": "SUCCESS"
                }
            }
        }
    elif event_type == "esign.completed":
        body = {
            "data": {
                "eventType": event_type,
                "eventId": event_id,
                "dateTime": datetime_utc,
                "details": {
                    "merchantId": variables["merchantId"],
                    "lenderApprovedOfferId": variables["lenderApprovedOfferId"],
                    "signedLimit": {
                        "amount": variables["signedAmount"],
                        "currency": variables["preferredCurrency"]
                    },
                    "result": "SUCCESS"
                }
            }
        }

    response = requests.post(
        f"{BASE_URL}/dpu-openapi/webhook-notifications",
        json=body,
        timeout=60
    )
    print(f"[WEBHOOK] {event_type} -> {response.status_code}")
    if response.status_code != 200:
        print(f"[ERROR] {response.text}")
        raise Exception(f"Webhook failed: {event_type}")
    return event_id

def run():
    phone = gen_phone()
    email = f"{phone}@163.com"
    print(f"\n[START] phone={phone}")

    # Step 1: Send SMS
    print("\n[STEP 1] Send registration SMS")
    resp = requests.post(f"{BASE_URL}/dpu-user/auth/sendSmsCode-sign",
        json={"phoneNumber": phone, "smsType": "SIGN_UP"},
        headers={"content-type": "application/json"})
    print(f"SMS sent: {resp.status_code}")

    # Step 2: Get verification code
    print("\n[STEP 2] Fetch SMS code")
    code = fetch_sms_code(phone)
    print(f"Code: {code}")

    # Step 3: Validate SMS
    print("\n[STEP 3] Validate SMS code")
    resp = requests.post(f"{BASE_URL}/dpu-user/auth/validateSmsCode-sign",
        json={"phoneNumber": phone, "verificationCode": code},
        headers={"content-type": "application/json"})
    print(f"Validate: {resp.status_code}")

    # Step 4: Signup
    print("\n[STEP 4] Signup")
    resp = requests.post(f"{BASE_URL}/dpu-user/auth/signup",
        json={"phoneNumber": phone, "email": email, "password": "Aa11111111..",
              "confirmPassword": "Aa11111111..", "verificationCode": code},
        headers={"content-type": "application/json"})
    token = resp.json()["data"]["token"]
    print(f"Token: {token[:20]}...")

    # Step 5: Generate SP auth URL
    print("\n[STEP 5] Generate SP auth URL")
    state = str(uuid.uuid4())
    resp = requests.post(f"{BASE_URL}/dpu-user/auth/generate-sp-auth-url",
        json={"state": state},
        headers={"Authorization": f"Bearer {token}", "content-type": "application/json"})
    print(f"State: {state}")

    # Step 6: SP auth
    print("\n[STEP 6] SP authorization")
    selling_partner_id = gen_selling_partner_id()
    resp = requests.get(f"{BASE_URL}/dpu-user/auth/sp",
        params={"state": state, "selling_partner_id": selling_partner_id})
    print(f"SP ID: {selling_partner_id}")

    # Step 7: Get offer ID
    print("\n[STEP 7] Wait for platform_offer_id")
    offer_row = wait_fetchone(
        "SELECT idempotency_key, platform_offer_id FROM dpu_manual_offer "
        "WHERE platform_seller_id=%s ORDER BY created_at DESC LIMIT 1",
        (selling_partner_id,), "platform_offer_id")
    platform_offer_id = offer_row[1]
    print(f"Offer ID: {platform_offer_id}")

    # Step 8: Update offer
    print("\n[STEP 8] Update offer")
    resp = requests.post(f"{BASE_URL}/dpu-user/auth/sp-updateOffer",
        json={"platformOfferId": platform_offer_id},
        headers={"Authorization": f"Bearer {token}", "content-type": "application/json"})
    print(f"Update offer: {resp.status_code}")

    # Step 9: 3PL redirect GET
    print("\n[STEP 9] 3PL redirect GET")
    resp = requests.get(f"{BASE_URL}/dpu-user/auth/3pl",
        params={"state": state, "amazon_callback_uri": "https://expressfinance-sit.business.hsbc.com/redirect-loading",
                "amazon_state": state})
    print(f"3PL GET: {resp.status_code}")

    # Step 10: 3PL redirect POST
    print("\n[STEP 10] 3PL redirect POST")
    resp = requests.post(f"{BASE_URL}/dpu-user/auth/3pl-redirect",
        json={"platformOfferId": platform_offer_id},
        headers={"Authorization": f"Bearer {token}", "content-type": "application/json"})
    print(f"3PL POST: {resp.status_code}")

    # Steps 11-13: Submit application data
    print("\n[STEPS 11-13] Submit application data")
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json",
               "finance-product": "LINE_OF_CREDIT", "funder-resource": "FUNDPARK", "product-currency": "USD"}

    resp = requests.post(f"{BASE_URL}/dpu-application/application/create", json={}, headers=headers)
    print(f"Create application: {resp.status_code}")

    resp = requests.post(f"{BASE_URL}/dpu-application/application/business-info/submit",
        json={"businessName": "Test Business", "businessType": "COMPANY", "country": "US"}, headers=headers)
    print(f"Submit business info: {resp.status_code}")

    resp = requests.post(f"{BASE_URL}/dpu-application/application/credit-offer/select",
        json={"minAmount": 500000, "maxAmount": 500000}, headers=headers)
    print(f"Select offer: {resp.status_code}")

    # Mark virus scan ready
    print("\n[STEP 14] Mark virus scan ready")
    app_id = mark_virus_scan_ready(phone)

    # Wait for SUBMITTED
    print("\n[STEP 15] Wait for credit offer SUBMITTED")
    for i in range(30):
        resp = requests.get(f"{BASE_URL}/dpu-application/application/credit-offer/status", headers=headers)
        status = resp.json().get("data", {}).get("status")
        print(f"Poll {i+1}: {status}")
        if status == "SUBMITTED":
            break
        time.sleep(3)

    # Get merchant info
    print("\n[STEP 16] Get merchant info")
    merchant_row = wait_fetchone(
        "SELECT merchant_id, COALESCE(prefer_finance_product_currency, 'USD') "
        "FROM dpu_users WHERE phone_number=%s ORDER BY created_at DESC LIMIT 1",
        (phone,), "merchant_id")
    merchant_id = merchant_row[0]
    currency = merchant_row[1] or "USD"

    limit_row = wait_fetchone(
        "SELECT limit_application_unique_id FROM dpu_limit_application "
        "WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 1",
        (merchant_id,), "limit_application_id")

    auth_row = wait_fetchone(
        "SELECT authorization_id FROM dpu_auth_token "
        "WHERE merchant_id=%s AND authorization_party='SP' AND status='ACTIVE' "
        "ORDER BY created_at DESC LIMIT 1",
        (merchant_id,), "authorization_id")

    application_row = wait_fetchone(
        "SELECT application_unique_id FROM dpu_application "
        "WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 1",
        (merchant_id,), "application_id")

    variables = {
        "merchantId": merchant_id,
        "preferredCurrency": currency,
        "dpuLimitApplicationId": limit_row[0],
        "dpuMerchantAccountId": auth_row[0],
        "dpuApplicationId": application_row[0],
        "lenderApprovedOfferId": f"lender-{application_row[0]}",
        "approvedAmount": "500000",
        "signedAmount": "500000",
        "offerStartDate": datetime.now().strftime("%Y-%m-%d"),
        "offerEndDate": (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
    }

    print(f"\nMerchant ID: {merchant_id}")
    print(f"Application ID: {application_row[0]}")

    # Send webhooks
    print("\n[STEP 17] Send approved-offer webhook")
    send_webhook("approvedoffer.completed", variables)
    time.sleep(2)

    # Update lenderApprovedOfferId from DB
    credit_offer_row = wait_fetchone(
        "SELECT lender_approved_offer_id FROM dpu_credit_offer "
        "WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 1",
        (merchant_id,), "lender_approved_offer_id")
    variables["lenderApprovedOfferId"] = credit_offer_row[0]

    print("\n[STEP 18] Send psp-start webhook")
    send_webhook("psp.verification.started", variables)
    time.sleep(2)

    print("\n[STEP 19] Send psp-completed webhook")
    send_webhook("psp.verification.completed", variables)
    time.sleep(2)

    print("\n[STEP 20] Send esign webhook")
    send_webhook("esign.completed", variables)
    time.sleep(2)

    # Check final status
    print("\n[FINAL] Check credit offer status")
    final_row = wait_fetchone(
        "SELECT lender_approved_offer_id, status, approved_limit_amount, e_sign_status "
        "FROM dpu_credit_offer WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 1",
        (merchant_id,), "final credit offer", timeout=20)

    print(f"\n{'='*60}")
    print(f"RESULT: {final_row}")
    print(f"Status: {final_row[1]}")
    print(f"E-sign: {final_row[3]}")
    print(f"{'='*60}")

    if final_row[3] == "SUCCESS":
        print("\n✓ E-SIGNATURE COMPLETED SUCCESSFULLY!")
        return True
    else:
        print(f"\n✗ E-signature status: {final_row[3]}")
        return False

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
