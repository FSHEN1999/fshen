# -*- coding: utf-8 -*-
import logging, requests, time, uuid, pymysql
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

BASE_URL = "https://dpu-gateway-reg.dowsure.com"
DB_CONFIG = {"host": "18.162.145.173", "user": "dpu_reg", "password": "r4asUYBX3R6LNdp", "database": "dpu_seller_center", "port": 3307, "charset": "utf8mb4"}

MERCHANT_ID = "2cc8015ad47d481f988e9d9b0084cbff"
APP_ID = "EFA17773521209302703"
LIMIT_APP_ID = "EFAL17773515942646076"

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
    log.info("Run webhooks to complete esign")
    log.info(f"merchant_id: {MERCHANT_ID}")
    log.info(f"application_id: {APP_ID}")

    # Get account_id
    result = query_db(f"SELECT authorization_id FROM dpu_auth_token WHERE merchant_id='{MERCHANT_ID}' AND authorization_party='SP' LIMIT 1")
    account_id = result['authorization_id']
    log.info(f"account_id: {account_id}")

    # Get lender_approved_offer_id
    result = query_db(f"SELECT lender_approved_offer_id FROM dpu_credit_offer WHERE merchant_id='{MERCHANT_ID}' ORDER BY created_at DESC LIMIT 1")
    lender_offer_id = result['lender_approved_offer_id'] if result else f"lender-{APP_ID}"
    log.info(f"lender_approved_offer_id: {lender_offer_id}")

    # Webhook 1: psp.verification.started
    log.info("="*60)
    event_id1 = str(uuid.uuid4())
    send_webhook("psp.verification.started", {
        "data": {
            "eventType": "psp.verification.started",
            "eventId": event_id1,
            "dateTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": MERCHANT_ID,
                "merchantAccountId": account_id,
                "lenderApprovedOfferId": lender_offer_id,
                "result": "PROCESSING"
            }
        }
    })
    time.sleep(2)

    # Webhook 2: psp.verification.completed
    log.info("="*60)
    event_id2 = str(uuid.uuid4())
    send_webhook("psp.verification.completed", {
        "data": {
            "eventType": "psp.verification.completed",
            "eventId": event_id2,
            "dateTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": MERCHANT_ID,
                "merchantAccountId": account_id,
                "lenderApprovedOfferId": lender_offer_id,
                "result": "SUCCESS"
            }
        }
    })
    time.sleep(2)

    # Webhook 3: esign.completed
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
                    "currency": "USD"
                },
                "result": "SUCCESS"
            }
        }
    })
    time.sleep(3)

    # Verify final status
    log.info("="*60)
    log.info("Verify final status")
    result = query_db(f"SELECT status, e_sign_status, approved_limit_amount FROM dpu_credit_offer WHERE merchant_id='{MERCHANT_ID}' ORDER BY created_at DESC LIMIT 1")
    log.info(f"credit_offer: status={result['status']}, e_sign_status={result['e_sign_status']}, amount={result['approved_limit_amount']}")

    log.info("="*60)
    if result['e_sign_status'] == 'SUCCESS':
        log.info("SUCCESS! E-SIGNATURE COMPLETED!")
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
