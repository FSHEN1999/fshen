# -*- coding: utf-8 -*-
import logging, requests, time, uuid, pymysql
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

BASE_URL = "https://dpu-gateway-reg.dowsure.com"
DB_CONFIG = {"host": "18.162.145.173", "user": "dpu_reg", "password": "r4asUYBX3R6LNdp", "database": "dpu_seller_center", "port": 3307, "charset": "utf8mb4"}

MERCHANT_ID = "5c7eb7eb7bb44928974da7103284578e"
APP_ID = "EFA17773715125772142"  # Not used if credit_offer exists
ACCOUNT_ID = "test5f7bf83c5e50"

def query_db(sql):
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute(sql)
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

def send_webhook(event_type, payload):
    log.info(f"Webhook: {event_type}")
    resp = requests.post(f"{BASE_URL}/dpu-openapi/webhook-notifications", json=payload, timeout=30)
    log.info(f"  Response: {resp.status_code} - {resp.text[:150]}")
    if resp.status_code != 200:
        log.error(f"  Failed: {resp.text[:300]}")
        raise Exception(f"Webhook failed: {resp.text[:500]}")
    return resp

def main():
    log.info("="*60)
    log.info("Run FP-CNY flow to esign")
    log.info(f"merchant_id: {MERCHANT_ID}")
    log.info(f"application_id: {APP_ID}")
    log.info(f"account_id: {ACCOUNT_ID}")

    # Check current status
    result = query_db(f"SELECT lender_approved_offer_id, status, e_sign_status, approved_limit_amount FROM dpu_credit_offer WHERE merchant_id='{MERCHANT_ID}' ORDER BY created_at DESC LIMIT 1")
    if result:
        log.info(f"Current status: {result}")
        lender_offer_id = result['lender_approved_offer_id'] or f"lender-cny-{MERCHANT_ID[:8]}"

        # If no lender_approved_offer_id, set one
        if not result['lender_approved_offer_id']:
            log.info(f"Setting lender_approved_offer_id to: {lender_offer_id}")
            import pymysql
            conn = pymysql.connect(**DB_CONFIG)
            cursor = conn.cursor()
            cursor.execute(f"UPDATE dpu_credit_offer SET lender_approved_offer_id='{lender_offer_id}', approved_limit_amount=500000 WHERE merchant_id='{MERCHANT_ID}' AND lender_approved_offer_id IS NULL")
            conn.commit()
            cursor.close()
            conn.close()
    else:
        log.error("No credit_offer found, cannot proceed")
        return False

    # If already SUCCESS, skip
    if result and result.get('e_sign_status') == 'SUCCESS':
        log.info("Already SUCCESS, exiting")
        return True

    # Skip approved-offer webhook, go directly to PSP

    # Webhook 2: psp.verification.started
    log.info("="*60)
    event_id1 = str(uuid.uuid4())
    send_webhook("psp.verification.started", {
        "data": {
            "eventType": "psp.verification.started",
            "eventId": event_id1,
            "dateTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": MERCHANT_ID,
                "merchantAccountId": ACCOUNT_ID,
                "lenderApprovedOfferId": lender_offer_id,
                "result": "PROCESSING"
            }
        }
    })
    time.sleep(2)

    # Webhook 3: psp.verification.completed
    log.info("="*60)
    event_id2 = str(uuid.uuid4())
    send_webhook("psp.verification.completed", {
        "data": {
            "eventType": "psp.verification.completed",
            "eventId": event_id2,
            "dateTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": MERCHANT_ID,
                "merchantAccountId": ACCOUNT_ID,
                "lenderApprovedOfferId": lender_offer_id,
                "result": "SUCCESS"
            }
        }
    })
    time.sleep(2)

    # Webhook 4: esign.completed
    log.info("="*60)
    event_id3 = str(uuid.uuid4())
    send_webhook("esign.completed", {
        "data": {
            "eventType": "esign.completed",
            "eventId": event_id3,
            "dateTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": MERCHANT_ID,
                "lenderApprovedOfferId": lender_offer_id,
                "signedLimit": {
                    "amount": "500000",
                    "currency": "CNY"
                },
                "result": "SUCCESS"
            }
        }
    })
    time.sleep(3)

    # Verify final status
    log.info("="*60)
    log.info("Verify final status")
    result = query_db(f"SELECT status, e_sign_status, approved_limit_amount, signed_limit_amount FROM dpu_credit_offer WHERE merchant_id='{MERCHANT_ID}' ORDER BY created_at DESC LIMIT 1")
    log.info(f"credit_offer: status={result['status']}, e_sign_status={result['e_sign_status']}, approved={result['approved_limit_amount']}, signed={result['signed_limit_amount']}")

    log.info("="*60)
    if result['e_sign_status'] == 'SUCCESS':
        log.info("SUCCESS! FP-CNY E-SIGNATURE COMPLETED!")
        log.info("="*60)
        return True
    else:
        log.error(f"E-signature status: {result['e_sign_status']}")
        return False

if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except Exception as e:
        log.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
