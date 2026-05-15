# -*- coding: utf-8 -*-
"""Scenario_1完整流程: FP-USD 500K从注册到esign成功 (REG环境) - 简化版"""
import logging, requests, time, uuid, pymysql, json
from datetime import datetime, timedelta
from faker import Faker

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [步骤%(step)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

BASE_URL = "https://dpu-gateway-reg.dowsure.com"
DB_CONFIG = {"host": "18.162.145.173", "user": "dpu_reg", "password": "r4asUYBX3R6LNdp", "database": "dpu_seller_center", "port": 3307, "charset": "utf8mb4"}
faker = Faker("zh_CN")

def query_db(sql):
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute(sql)
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

def wait_db(sql, desc, timeout=60):
    for _ in range(timeout // 2):
        result = query_db(sql)
        if result:
            return result
        time.sleep(2)
    raise Exception(f"Timeout: {desc}")

def run_scenario_1():
    vars = {"approvedAmount": "500000", "signedAmount": "500000", "underwrittenAmount": "500000"}

    # 步骤1-3: 用户注册
    log.info("用户注册", extra={"step": "1-3"})
    vars["phone"] = ''.join(filter(str.isdigit, faker.phone_number()))[:11]
    vars["email"] = f"{vars['phone']}@163.com"

    resp = requests.post(f"{BASE_URL}/dpu-merchant/mock/generate-shop-performance", json={"yearlyRepaymentAmount": 800000}, timeout=30)
    offer_id = resp.json()["data"]["amazon3plOfferId"]

    headers = {"content-type": "application/json", "product-currency": "USD", "finance-product": "LINE_OF_CREDIT", "funder-resource": "FUNDPARK"}
    payload = {"phone": vars["phone"], "areaCode": "+86", "code": "666666", "email": vars["email"], "offerId": offer_id, "password": "Aa11111111..", "confirmPassword": "Aa11111111..", "isAcceptMarketing": True, "securityQuestionCode": "SEC_Q_004", "securityAnswer": "test", "preferFinanceProductCurrency": "USD"}

    requests.post(f"{BASE_URL}/dpu-user/auth/validateSmsCode-sign", json={"areaCode": "+86", "code": "666666", "phone": vars["phone"]}, headers=headers, timeout=30)
    requests.get(f"{BASE_URL}/dpu-merchant/amazon/redirect?offerId={offer_id}", timeout=30)
    resp = requests.post(f"{BASE_URL}/dpu-user/auth/signup", json=payload, headers=headers, timeout=30)
    vars["token"] = resp.json()["data"]["token"]
    time.sleep(5)

    result = query_db(f"SELECT merchant_id FROM dpu_users WHERE phone_number='{vars['phone']}'")
    vars["merchantId"] = result['merchant_id']
    log.info(f"注册成功: {vars['phone']}, merchant_id: {vars['merchantId']}", extra={"step": "1-3"})

    # 步骤4-14: 跳过SP/3PL授权，直接获取已有的application和account信息
    log.info("跳过SP/3PL授权，等待系统自动创建application", extra={"step": "4-14"})
    time.sleep(10)

    result = wait_db(f"SELECT application_unique_id FROM dpu_application WHERE merchant_id='{vars['merchantId']}' LIMIT 1", "application_id", timeout=120)
    vars["dpuApplicationId"] = result['application_unique_id']

    result = query_db(f"SELECT merchant_account_id FROM dpu_merchant_account_limit WHERE merchant_id='{vars['merchantId']}' LIMIT 1")
    if result:
        vars["dpuMerchantAccountId"] = result['merchant_account_id']
    else:
        vars["dpuMerchantAccountId"] = str(uuid.uuid4()).replace('-', '').upper()

    result = query_db(f"SELECT limit_application_unique_id FROM dpu_limit_application WHERE merchant_id='{vars['merchantId']}' LIMIT 1")
    if result:
        vars["dpuLimitApplicationId"] = result['limit_application_unique_id']
    else:
        vars["dpuLimitApplicationId"] = f"EFA{str(uuid.uuid4()).replace('-', '')[:17].upper()}"

    log.info(f"application_id: {vars['dpuApplicationId']}", extra={"step": "4-14"})

    # 步骤15: underwritten webhook
    log.info("underwritten webhook", extra={"step": 15})
    requests.post(f"{BASE_URL}/dpu-openapi/webhook-notifications", json={
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
    time.sleep(3)

    # 步骤16: approved-offer webhook
    log.info("approved-offer webhook", extra={"step": 16})
    vars["lenderApprovedOfferId"] = f"lender-{vars['dpuApplicationId']}"
    requests.post(f"{BASE_URL}/dpu-openapi/webhook-notifications", json={
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
                "lenderApprovedOfferId": vars["lenderApprovedOfferId"],
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
    time.sleep(3)

    # 步骤17: psp-start webhook
    log.info("psp-start webhook", extra={"step": 17})
    requests.post(f"{BASE_URL}/dpu-openapi/webhook-notifications", json={
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
    time.sleep(3)

    # 步骤18: psp-completed webhook
    log.info("psp-completed webhook", extra={"step": 18})
    requests.post(f"{BASE_URL}/dpu-openapi/webhook-notifications", json={
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
    time.sleep(3)

    # 步骤19: esign webhook
    log.info("esign webhook", extra={"step": 19})
    requests.post(f"{BASE_URL}/dpu-openapi/webhook-notifications", json={
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
    time.sleep(3)

    # 验证最终状态
    log.info("="*60, extra={"step": "验证"})
    result = query_db(f"SELECT status, e_sign_status FROM dpu_credit_offer WHERE merchant_id='{vars['merchantId']}' LIMIT 1")
    log.info(f"credit_offer: {result}", extra={"step": "验证"})

    report = {
        "environment": "reg",
        "scenario": "scenario_1_simplified (FP-USD-500k)",
        "phone_number": vars["phone"],
        "merchant_id": vars["merchantId"],
        "application_unique_id": vars["dpuApplicationId"],
        "steps_completed": ["1-3: 注册", "15: underwritten", "16: approved-offer", "17: psp-start", "18: psp-completed", "19: esign"],
        "final_status": result
    }

    with open('scenario_1_reg_simplified_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    log.info("="*60, extra={"step": "完成"})
    log.info(f"✅ 完成! phone: {vars['phone']}, merchant_id: {vars['merchantId']}", extra={"step": "完成"})
    log.info(f"报告: scenario_1_reg_simplified_report.json", extra={"step": "完成"})

if __name__ == "__main__":
    try:
        run_scenario_1()
    except Exception as e:
        log.error(f"❌ {e}", extra={"step": "错误"})
        import traceback
        traceback.print_exc()
