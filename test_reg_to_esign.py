# -*- coding: utf-8 -*-
import logging, requests, time, uuid, pymysql, json
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

BASE_URL = "https://dpu-gateway-reg.dowsure.com"
DB_CONFIG = {"host": "18.162.145.173", "user": "dpu_reg", "password": "r4asUYBX3R6LNdp", "database": "dpu_seller_center", "port": 3307, "charset": "utf8mb4"}

PHONE = "18503433073"
MERCHANT_ID = "639d60f1e5b749faae613630bae855f3"
APPLICATION_ID = "EFA17773697336035815"
ACCOUNT_ID = "0fec7e18aff243499725b952859df224"

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
            log.info(f"✅ {desc}: {result}")
            return result
        time.sleep(2)
    raise Exception(f"Timeout waiting for {desc}")

def send_webhook(event_type, payload):
    log.info(f"发送 webhook: {event_type}")
    resp = requests.post(f"{BASE_URL}/dpu-openapi/webhook-notifications", json=payload, timeout=30)
    log.info(f"响应: {resp.status_code} - {resp.text[:150]}")
    if resp.status_code != 200:
        raise Exception(f"Webhook failed: {resp.text}")

def main():
    log.info("="*60)
    log.info("继续执行 scenario_1 流程")
    log.info(f"merchant_id: {MERCHANT_ID}")
    log.info(f"application_id: {APPLICATION_ID}")
    log.info(f"account_id: {ACCOUNT_ID}")

    # 查询 limit_application_id
    result = wait_db(
        f"SELECT limit_application_unique_id FROM dpu_limit_application WHERE merchant_id='{MERCHANT_ID}' ORDER BY created_at DESC LIMIT 1",
        "limit_application_id"
    )
    limit_app_id = result['limit_application_unique_id']

    # Webhook 1: underwritten (如果不存在)
    result = query_db(f"SELECT COUNT(*) as cnt FROM dpu_lender_event WHERE merchant_id='{MERCHANT_ID}' AND event_type='underwrittenLimit.completed'")
    if result['cnt'] == 0:
        log.info("="*60)
        log.info("Webhook 1: underwrittenLimit.completed")
        payload = {
            "eventId": str(uuid.uuid4()),
            "eventType": "underwrittenLimit.completed",
            "eventTime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "merchantId": MERCHANT_ID,
            "dpuLimitApplicationId": limit_app_id,
            "dpuMerchantAccountId": ACCOUNT_ID,
            "underwrittenAmount": "500000",
            "preferredCurrency": "USD"
        }
        send_webhook("underwrittenLimit.completed", payload)
        time.sleep(3)
    else:
        log.info("跳过 underwritten webhook (已存在)")

    # 等待 application 创建
    result = wait_db(
        f"SELECT application_unique_id FROM dpu_application WHERE merchant_id='{MERCHANT_ID}' ORDER BY created_at DESC LIMIT 1",
        "application_unique_id"
    )
    app_id = result['application_unique_id']
    log.info(f"application_id: {app_id}")

    # Webhook 2: approved-offer
    log.info("="*60)
    log.info("Webhook 2: approvedoffer.completed")
    offer_start = datetime.now().strftime("%Y-%m-%d")
    offer_end = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
    payload = {
        "eventId": str(uuid.uuid4()),
        "eventType": "approvedoffer.completed",
        "eventTime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "merchantId": MERCHANT_ID,
        "dpuApplicationId": app_id,
        "lenderApprovedOfferId": f"lender-{app_id}",
        "approvedAmount": "500000",
        "offerStartDate": offer_start,
        "offerEndDate": offer_end,
        "preferredCurrency": "USD"
    }
    send_webhook("approvedoffer.completed", payload)
    time.sleep(3)

    # 等待 credit_offer 创建
    result = wait_db(
        f"SELECT lender_approved_offer_id FROM dpu_credit_offer WHERE merchant_id='{MERCHANT_ID}' ORDER BY created_at DESC LIMIT 1",
        "lender_approved_offer_id"
    )
    lender_offer_id = result['lender_approved_offer_id']

    # Webhook 3: psp.verification.started
    log.info("="*60)
    log.info("Webhook 3: psp.verification.started")
    payload = {
        "eventId": str(uuid.uuid4()),
        "eventType": "psp.verification.started",
        "eventTime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "merchantId": MERCHANT_ID,
        "dpuMerchantAccountId": ACCOUNT_ID,
        "lenderApprovedOfferId": lender_offer_id,
        "signedAmount": "500000",
        "preferredCurrency": "USD"
    }
    send_webhook("psp.verification.started", payload)
    time.sleep(3)

    # Webhook 4: psp.verification.completed
    log.info("="*60)
    log.info("Webhook 4: psp.verification.completed")
    payload = {
        "eventId": str(uuid.uuid4()),
        "eventType": "psp.verification.completed",
        "eventTime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "merchantId": MERCHANT_ID,
        "dpuMerchantAccountId": ACCOUNT_ID,
        "lenderApprovedOfferId": lender_offer_id,
        "signedAmount": "500000",
        "preferredCurrency": "USD"
    }
    send_webhook("psp.verification.completed", payload)
    time.sleep(3)

    # Webhook 5: esign.completed
    log.info("="*60)
    log.info("Webhook 5: esign.completed")
    payload = {
        "eventId": str(uuid.uuid4()),
        "eventType": "esign.completed",
        "eventTime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "merchantId": MERCHANT_ID,
        "dpuMerchantAccountId": ACCOUNT_ID,
        "lenderApprovedOfferId": lender_offer_id,
        "signedAmount": "500000",
        "preferredCurrency": "USD"
    }
    send_webhook("esign.completed", payload)
    time.sleep(3)

    # 验证最终状态
    log.info("="*60)
    log.info("验证最终状态")
    result = query_db(f"SELECT status, e_sign_status, approved_limit_amount FROM dpu_credit_offer WHERE merchant_id='{MERCHANT_ID}' ORDER BY created_at DESC LIMIT 1")
    log.info(f"credit_offer: {result}")

    result = query_db(f"SELECT COUNT(*) as cnt FROM dpu_lender_event WHERE merchant_id='{MERCHANT_ID}'")
    log.info(f"lender_event count: {result['cnt']}")

    log.info("="*60)
    log.info("✅ 完成! 已执行到 esign 成功")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.error(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
