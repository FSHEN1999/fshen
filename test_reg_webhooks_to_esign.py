# -*- coding: utf-8 -*-
import logging, requests, time, uuid, pymysql
from datetime import datetime, timedelta

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
    log.info(f"  响应: {resp.status_code} - {resp.text[:150]}")
    if resp.status_code != 200:
        log.error(f"  失败: {resp.text[:300]}")
        raise Exception(f"Webhook failed")

def main():
    log.info("="*60)
    log.info("使用已有账号测试 webhook 流程到 esign")
    log.info(f"merchant_id: {MERCHANT_ID}")
    log.info(f"application_id: {APP_ID}")
    log.info(f"limit_application_id: {LIMIT_APP_ID}")

    # 查询 account_id
    result = query_db(f"SELECT authorization_id FROM dpu_auth_token WHERE merchant_id='{MERCHANT_ID}' AND authorization_party='SP' AND status='ACTIVE' LIMIT 1")
    account_id = result['authorization_id']
    log.info(f"account_id (authorization_id): {account_id}")

    # 跳过 underwritten (已存在或状态不对)
    log.info("跳过 underwritten webhook")

    # Webhook 2: approved-offer
    log.info("="*60)
    send_webhook("approvedoffer.completed", {
        "data": {
            "eventType": "approvedoffer.completed",
            "eventId": str(uuid.uuid4()),
            "eventMessage": "Application approval process completed successfully",
            "enquiryUrl": "https://api.lender.com/enquiry/12345",
            "datetime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": MERCHANT_ID,
                "dpuApplicationId": APP_ID,
                "originalRequestId": str(uuid.uuid4()),
                "status": "APPROVED",
                "failureReason": None,
                "lenderApprovedOfferId": f"lender-{APP_ID}",
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
                    "offerEndDate": (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"),
                    "offerStartDate": datetime.now().strftime("%Y-%m-%d"),
                    "approvedLimit": {"currency": "USD", "amount": "500000"},
                    "warterMark": {"currency": "USD", "amount": 0.0},
                    "signedLimit": {"currency": "USD", "amount": 0.0},
                    "feeOrCharge": {
                        "type": "PROCESSING_FEE",
                        "feeOrChargeDate": "2023-10-16",
                        "netAmount": {"currency": "USD", "amount": 0.0}
                    }
                }
            }
        }
    })
    time.sleep(3)

    # 查询 lender_approved_offer_id
    result = query_db(f"SELECT lender_approved_offer_id FROM dpu_credit_offer WHERE merchant_id='{MERCHANT_ID}' ORDER BY created_at DESC LIMIT 1")
    if not result:
        log.error("未找到 credit_offer")
        return
    lender_offer_id = result['lender_approved_offer_id']
    log.info(f"lender_approved_offer_id: {lender_offer_id}")

    # Webhook 3: psp.verification.started
    log.info("="*60)
    send_webhook("psp.verification.started", {
        "data": {
            "eventType": "psp.verification.started",
            "eventId": str(uuid.uuid4()),
            "eventMessage": "psp verification started event",
            "enquiryUrl": "https://api.example.com/enquiry/123",
            "datetime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": MERCHANT_ID,
                "lastUpdatedOn": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "lastUpdatedBy": "system",
                "applicationId": APP_ID,
                "pspId": "pspId123457",
                "pspName": "AirWallex",
                "merchantAccountId": account_id,
                "lenderApprovedOfferId": lender_offer_id,
                "result": "PROCESSING"
            }
        }
    })
    time.sleep(3)

    # Webhook 4: psp.verification.completed
    log.info("="*60)
    send_webhook("psp.verification.completed", {
        "data": {
            "eventType": "psp.verification.completed",
            "eventId": str(uuid.uuid4()),
            "eventMessage": "psp verification completed event",
            "enquiryUrl": "https://api.example.com/enquiry/123",
            "datetime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": MERCHANT_ID,
                "lastUpdatedOn": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "lastUpdatedBy": "system",
                "applicationId": APP_ID,
                "pspId": "pspId123457",
                "pspName": "AirWallex",
                "merchantAccountId": account_id,
                "lenderApprovedOfferId": lender_offer_id,
                "result": "SUCCESS"
            }
        }
    })
    time.sleep(3)

    # Webhook 5: esign.completed
    log.info("="*60)
    send_webhook("esign.completed", {
        "data": {
            "eventType": "esign.completed",
            "eventId": str(uuid.uuid4()),
            "eventMessage": "esign completed event",
            "enquiryUrl": "https://api.example.com/enquiry/123",
            "datetime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": MERCHANT_ID,
                "lastUpdatedOn": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "lastUpdatedBy": "system",
                "lenderApprovedOfferId": lender_offer_id,
                "result": "SUCCESS",
                "signedLimit": {"amount": "500000", "currency": "USD"}
            }
        }
    })
    time.sleep(3)

    # 验证最终状态
    log.info("="*60)
    log.info("验证最终状态")
    result = query_db(f"SELECT status, e_sign_status, approved_limit_amount FROM dpu_credit_offer WHERE merchant_id='{MERCHANT_ID}' ORDER BY created_at DESC LIMIT 1")
    log.info(f"credit_offer: status={result['status']}, e_sign_status={result['e_sign_status']}, amount={result['approved_limit_amount']}")

    result = query_db(f"SELECT COUNT(*) as cnt FROM dpu_lender_event WHERE merchant_id='{MERCHANT_ID}'")
    log.info(f"lender_event count: {result['cnt']}")

    log.info("="*60)
    log.info("✅ 完成! 已成功执行到 esign")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.error(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
