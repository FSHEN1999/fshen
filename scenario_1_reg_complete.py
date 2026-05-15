# -*- coding: utf-8 -*-
"""Scenario_1完整流程: FP-USD 500K从注册到esign成功 (REG环境)"""
import logging, requests, time, uuid, pymysql, hashlib, json
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

    # 步骤1: 生成注册信息
    log.info("生成注册信息", extra={"step": 1})
    vars["phone"] = ''.join(filter(str.isdigit, faker.phone_number()))[:11]
    vars["email"] = f"{vars['phone']}@163.com"

    # 步骤2: 跳过验证码
    log.info("跳过 (使用固定验证码 666666)", extra={"step": 2})

    # 步骤3: 用户注册
    log.info("用户注册", extra={"step": 3})
    resp = requests.post(f"{BASE_URL}/dpu-merchant/mock/generate-shop-performance", json={"yearlyRepaymentAmount": 800000}, timeout=30)
    offer_id = resp.json()["data"]["amazon3plOfferId"]

    headers = {"content-type": "application/json", "product-currency": "USD", "finance-product": "LINE_OF_CREDIT", "funder-resource": "FUNDPARK"}
    payload = {"phone": vars["phone"], "areaCode": "+86", "code": "666666", "email": vars["email"], "offerId": offer_id, "password": "Aa11111111..", "confirmPassword": "Aa11111111..", "isAcceptMarketing": True, "securityQuestionCode": "SEC_Q_004", "securityAnswer": "test", "preferFinanceProductCurrency": "USD"}

    requests.post(f"{BASE_URL}/dpu-user/auth/validateSmsCode-sign", json={"areaCode": "+86", "code": "666666", "phone": vars["phone"]}, headers=headers, timeout=30)
    requests.get(f"{BASE_URL}/dpu-merchant/amazon/redirect?offerId={offer_id}", timeout=30)
    resp = requests.post(f"{BASE_URL}/dpu-user/auth/signup", json=payload, headers=headers, timeout=30)
    vars["token"] = resp.json()["data"]["token"]

    result = query_db(f"SELECT merchant_id FROM dpu_users WHERE phone_number='{vars['phone']}'")
    vars["merchantId"] = result['merchant_id']
    log.info(f"注册成功: {vars['phone']}, merchant_id: {vars['merchantId']}", extra={"step": 3})

    # 步骤4-5: 生成state和SP授权
    log.info("生成state和SP授权", extra={"step": "4-5"})
    vars["state"] = str(uuid.uuid4())
    vars["selling_partner_id"] = hashlib.md5(f"{uuid.uuid4()}{time.time()}".encode()).hexdigest().upper()
    headers_auth = {"Authorization": f"Bearer {vars['token']}", "content-type": "application/json", "finance-product": "LINE_OF_CREDIT", "funder-resource": "FUNDPARK", "product-currency": "USD"}

    requests.post(f"{BASE_URL}/dpu-merchant/shop-authorization/v2/sp-auth-url", json={"redirectUrl": f"https://expressfinance-dpu-reg.dowsure.com/redirect-loading?state={vars['state']}", "sceneCode": "SHOP_BIND", "sourceCode": "FUNDPARK", "state": vars["state"]}, headers=headers_auth, timeout=30)
    requests.get(f"{BASE_URL}/dpu-auth/amazon-sp/auth", params={"mws_auth_token": "1235", "selling_partner_id": vars["selling_partner_id"], "spapi_oauth_code": "123123", "state": vars["state"]}, timeout=30)
    time.sleep(5)

    result = wait_db(f"SELECT idempotency_key, platform_offer_id FROM dpu_manual_offer WHERE platform_seller_id='{vars['selling_partner_id']}' LIMIT 1", "platform_offer_id", timeout=90)
    vars["idempotency_key"] = result['idempotency_key']
    vars["platform_offer_id"] = result['platform_offer_id']
    log.info(f"platform_offer_id: {vars['platform_offer_id']}", extra={"step": "4-5"})

    # 步骤6-8: sp-updateOffer和3PL授权
    log.info("sp-updateOffer和3PL授权", extra={"step": "6-8"})
    requests.post(f"{BASE_URL}/dpu-auth/amazon-sp/updateOffer", json={"idempotencyKey": vars["idempotency_key"], "offerId": vars["platform_offer_id"], "reason": "An offer already exists", "sendStatus": "SUCCESS"}, timeout=30)
    requests.get(f"{BASE_URL}/dpu-merchant/amazon/redirect", params={"offerId": vars["platform_offer_id"]}, timeout=30)
    requests.post(f"{BASE_URL}/dpu-merchant/amazon/redirect", json={"authToken": "mock", "expireOn": "null", "keyId": "null", "offerId": vars["platform_offer_id"], "relayPage": 1, "returnUrl": "null", "signature": "null"}, timeout=60)

    # 步骤9: 创建申请单
    log.info("创建申请单", extra={"step": 9})
    requests.post(f"{BASE_URL}/dpu-merchant/fundpark-application/create", json={"tierCode": "2", "tierSnapshotValue": 0}, headers=headers_auth, timeout=30)
    time.sleep(2)

    result = wait_db(f"SELECT application_unique_id FROM dpu_application WHERE merchant_id='{vars['merchantId']}' LIMIT 1", "application_id")
    vars["dpuApplicationId"] = result['application_unique_id']
    result = wait_db(f"SELECT authorization_id FROM dpu_auth_token WHERE merchant_id='{vars['merchantId']}' AND authorization_party='SP' AND status='ACTIVE' LIMIT 1", "account_id")
    vars["dpuMerchantAccountId"] = result['authorization_id']

    # 步骤10-13: 创建offer和绑定店铺
    log.info("创建offer和绑定店铺", extra={"step": "10-13"})
    requests.post(f"{BASE_URL}/dpu-merchant/credit-offer/create", headers=headers_auth, timeout=30)
    requests.post(f"{BASE_URL}/dpu-merchant/mock/link-sp-3pl-shops", params={"phone": vars["phone"]}, timeout=30)

    # 步骤14: 触发后台任务
    log.info("触发后台任务", extra={"step": 14})
    requests.post(f"{BASE_URL}/dpu-merchant/test/scheduled-tasks/first-application-start", headers=headers_auth, timeout=30)
    time.sleep(5)

    result = wait_db(f"SELECT limit_application_unique_id FROM dpu_limit_application WHERE merchant_id='{vars['merchantId']}' LIMIT 1", "limit_application_id", timeout=60)
    vars["dpuLimitApplicationId"] = result['limit_application_unique_id']

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
    time.sleep(3)

    result = wait_db(f"SELECT lender_approved_offer_id FROM dpu_credit_offer WHERE merchant_id='{vars['merchantId']}' LIMIT 1", "lender_approved_offer_id")
    vars["lenderApprovedOfferId"] = result['lender_approved_offer_id']

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

    # 生成报告
    report = {
        "environment": "reg",
        "scenario": "scenario_1 (FP-USD-500k)",
        "phone_number": vars["phone"],
        "merchant_id": vars["merchantId"],
        "application_unique_id": vars["dpuApplicationId"],
        "merchant_account_id": vars["dpuMerchantAccountId"],
        "steps_completed": list(range(1, 20)),
        "final_status": result
    }

    with open('scenario_1_reg_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    log.info("="*60, extra={"step": "完成"})
    log.info(f"✅ 完成! phone: {vars['phone']}, merchant_id: {vars['merchantId']}", extra={"step": "完成"})
    log.info(f"报告: scenario_1_reg_report.json", extra={"step": "完成"})

if __name__ == "__main__":
    try:
        run_scenario_1()
    except Exception as e:
        log.error(f"❌ {e}", extra={"step": "错误"})
        import traceback
        traceback.print_exc()
