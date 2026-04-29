# -*- coding: utf-8 -*-
"""
Scenario_1: 使用已有账号,从 underwritten 开始执行到 esign
"""
import logging, requests, time, uuid, pymysql
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [步骤%(step)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

BASE_URL = "https://dpu-gateway-reg.dowsure.com"
DB_CONFIG = {"host": "18.162.145.173", "user": "dpu_reg", "password": "r4asUYBX3R6LNdp", "database": "dpu_seller_center", "port": 3307, "charset": "utf8mb4"}

# 使用已有的完整测试账号
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

def run_webhooks():
    vars = {
        "merchantId": MERCHANT_ID,
        "dpuApplicationId": APP_ID,
        "dpuLimitApplicationId": LIMIT_APP_ID,
        "approvedAmount": "500000",
        "signedAmount": "500000",
        "underwrittenAmount": "500000"
    }

    # 查询 account_id
    result = query_db(f"SELECT authorization_id FROM dpu_auth_token WHERE merchant_id='{MERCHANT_ID}' AND authorization_party='SP' AND status='ACTIVE' LIMIT 1")
    vars["dpuMerchantAccountId"] = result['authorization_id']
    log.info(f"account_id: {vars['dpuMerchantAccountId']}", extra={"step": "初始化"})

    # 步骤 15: underwritten webhook
    log.info("underwritten webhook", extra={"step": 15})
    resp = requests.post(f"{BASE_URL}/dpu-openapi/webhook-notifications", json={
        "data": {
            "eventType": "underwrittenLimit.completed",
            "eventId": str(uuid.uuid4()),
            "eventMessage": "underwrittenLimit completed event",
            "enquiryUrl": "https://api.example.com/enquiry/123",
            "datetime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": vars["merchantId"],
                "lastUpdatedOn": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "lastUpdatedBy": "system",
                "dpuMerchantAccountId": [{"MerchantAccountId": vars["dpuMerchantAccountId"]}],
                "dpuLimitApplicationId": vars["dpuLimitApplicationId"],
                "originalRequestId": str(uuid.uuid4()),
                "status": "APPROVED",
                "credit": {
                    "marginRate": "2.5",
                    "chargeBases": "Float",
                    "baseRate": "3.5",
                    "baseRateType": "FIXED",
                    "creditLimit": {
                        "currency": "USD",
                        "underwrittenAmount": {"currency": "USD", "amount": vars["underwrittenAmount"]},
                        "availableLimit": {"currency": "USD", "amount": "0.00"},
                        "signedLimit": {"currency": "USD", "amount": "0.00"},
                        "watermark": {"currency": "USD", "amount": "0.00"}
                    },
                    "eSign": "PENDING"
                },
                "failureReason": None,
                "lenderLoanId": str(uuid.uuid4()),
                "lenderRepaymentScheduled": str(uuid.uuid4()),
                "lenderCreditId": str(uuid.uuid4()),
                "lenderRepaymentId": str(uuid.uuid4())
            }
        }
    }, timeout=30)
    log.info(f"响应: {resp.status_code} - {resp.text[:100]}", extra={"step": 15})
    if resp.status_code != 200:
        log.warning("underwritten webhook 失败,跳过", extra={"step": 15})
    time.sleep(3)

    # 步骤 16: approved-offer webhook
    log.info("approved-offer webhook", extra={"step": 16})
    resp = requests.post(f"{BASE_URL}/dpu-openapi/webhook-notifications", json={
        "data": {
            "eventType": "approvedoffer.completed",
            "eventId": str(uuid.uuid4()),
            "eventMessage": "Application approval process completed successfully",
            "enquiryUrl": "https://api.lender.com/enquiry/12345",
            "datetime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": vars["merchantId"],
                "dpuApplicationId": vars["dpuApplicationId"],
                "originalRequestId": str(uuid.uuid4()),
                "status": "APPROVED",
                "failureReason": None,
                "lenderApprovedOfferId": f"lender-{vars['dpuApplicationId']}",
                "offer": {
                    "rate": {"chargeBases": "Float", "baseRateType": "SOFR", "baseRate": "0.05", "marginRate": "0.02", "fixedRate": "0.07"},
                    "term": 120,
                    "termUnit": "Days",
                    "mintenor": 3,
                    "maxtenor": 24,
                    "offerEndDate": (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"),
                    "offerStartDate": datetime.now().strftime("%Y-%m-%d"),
                    "approvedLimit": {"currency": "USD", "amount": vars["approvedAmount"]},
                    "warterMark": {"currency": "USD", "amount": 0.0},
                    "signedLimit": {"currency": "USD", "amount": 0.0},
                    "feeOrCharge": {"type": "PROCESSING_FEE", "feeOrChargeDate": "2023-10-16", "netAmount": {"currency": "USD", "amount": 0.0}}
                }
            }
        }
    }, timeout=30)
    log.info(f"响应: {resp.status_code} - {resp.text[:100]}", extra={"step": 16})
    if resp.status_code != 200:
        raise Exception(f"approved-offer webhook 失败: {resp.text}")
    time.sleep(3)

    result = query_db(f"SELECT lender_approved_offer_id FROM dpu_credit_offer WHERE merchant_id='{vars['merchantId']}' ORDER BY created_at DESC LIMIT 1")
    vars["lenderApprovedOfferId"] = result['lender_approved_offer_id']
    log.info(f"lender_approved_offer_id: {vars['lenderApprovedOfferId']}", extra={"step": 16})

    # 步骤 17: psp-start webhook
    log.info("psp-start webhook", extra={"step": 17})
    resp = requests.post(f"{BASE_URL}/dpu-openapi/webhook-notifications", json={
        "data": {
            "eventType": "psp.verification.started",
            "eventId": str(uuid.uuid4()),
            "eventMessage": "psp verification started event",
            "enquiryUrl": "https://api.example.com/enquiry/123",
            "datetime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": vars["merchantId"],
                "lastUpdatedOn": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "lastUpdatedBy": "system",
                "applicationId": vars["dpuApplicationId"],
                "pspId": "pspId123457",
                "pspName": "AirWallex",
                "merchantAccountId": vars["dpuMerchantAccountId"],
                "lenderApprovedOfferId": vars["lenderApprovedOfferId"],
                "result": "PROCESSING"
            }
        }
    }, timeout=30)
    log.info(f"响应: {resp.status_code} - {resp.text[:100]}", extra={"step": 17})
    if resp.status_code != 200:
        raise Exception(f"psp-start webhook 失败: {resp.text}")
    time.sleep(3)

    # 步骤 18: psp-completed webhook
    log.info("psp-completed webhook", extra={"step": 18})
    resp = requests.post(f"{BASE_URL}/dpu-openapi/webhook-notifications", json={
        "data": {
            "eventType": "psp.verification.completed",
            "eventId": str(uuid.uuid4()),
            "eventMessage": "psp verification completed event",
            "enquiryUrl": "https://api.example.com/enquiry/123",
            "datetime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": vars["merchantId"],
                "lastUpdatedOn": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "lastUpdatedBy": "system",
                "applicationId": vars["dpuApplicationId"],
                "pspId": "pspId123457",
                "pspName": "AirWallex",
                "merchantAccountId": vars["dpuMerchantAccountId"],
                "lenderApprovedOfferId": vars["lenderApprovedOfferId"],
                "result": "SUCCESS"
            }
        }
    }, timeout=30)
    log.info(f"响应: {resp.status_code} - {resp.text[:100]}", extra={"step": 18})
    if resp.status_code != 200:
        raise Exception(f"psp-completed webhook 失败: {resp.text}")
    time.sleep(3)

    # 步骤 19: esign webhook
    log.info("esign webhook", extra={"step": 19})
    resp = requests.post(f"{BASE_URL}/dpu-openapi/webhook-notifications", json={
        "data": {
            "eventType": "esign.completed",
            "eventId": str(uuid.uuid4()),
            "eventMessage": "esign completed event",
            "enquiryUrl": "https://api.example.com/enquiry/123",
            "datetime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": vars["merchantId"],
                "lastUpdatedOn": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "lastUpdatedBy": "system",
                "lenderApprovedOfferId": vars["lenderApprovedOfferId"],
                "result": "SUCCESS",
                "signedLimit": {"amount": vars["signedAmount"], "currency": "USD"}
            }
        }
    }, timeout=30)
    log.info(f"响应: {resp.status_code} - {resp.text[:100]}", extra={"step": 19})
    if resp.status_code != 200:
        raise Exception(f"esign webhook 失败: {resp.text}")
    time.sleep(3)

    # 验证最终状态
    log.info("="*60, extra={"step": "验证"})
    result = query_db(f"SELECT status, e_sign_status FROM dpu_credit_offer WHERE merchant_id='{vars['merchantId']}' ORDER BY created_at DESC LIMIT 1")
    log.info(f"credit_offer: status={result['status']}, e_sign_status={result['e_sign_status']}", extra={"step": "验证"})

    log.info("="*60, extra={"step": "完成"})
    log.info(f"✅ 完成! merchant_id: {vars['merchantId']}", extra={"step": "完成"})

if __name__ == "__main__":
    try:
        run_webhooks()
    except Exception as e:
        log.error(f"❌ {e}", extra={"step": "错误"})
        import traceback
        traceback.print_exc()
