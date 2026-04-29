# -*- coding: utf-8 -*-
import logging, requests, time, uuid, pymysql, hashlib
from datetime import datetime, timedelta
from faker import Faker

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
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

def register_and_to_esign():
    # 注册
    phone = ''.join(filter(str.isdigit, faker.phone_number()))
    email = f"{phone}@163.com"

    resp = requests.post(f"{BASE_URL}/dpu-merchant/mock/generate-shop-performance", json={"yearlyRepaymentAmount": 800000}, timeout=30)
    offer_id = resp.json()["data"]["amazon3plOfferId"]

    headers = {"content-type": "application/json", "product-currency": "USD", "finance-product": "LINE_OF_CREDIT", "funder-resource": "FUNDPARK"}
    payload = {"phone": phone, "areaCode": "+86", "code": "666666", "email": email, "offerId": offer_id, "password": "Aa11111111..", "confirmPassword": "Aa11111111..", "isAcceptMarketing": True, "securityQuestionCode": "SEC_Q_004", "securityAnswer": "test", "preferFinanceProductCurrency": "USD"}

    requests.post(f"{BASE_URL}/dpu-user/auth/validateSmsCode-sign", json={"areaCode": "+86", "code": "666666", "phone": phone}, headers=headers, timeout=30)
    requests.get(f"{BASE_URL}/dpu-merchant/amazon/redirect?offerId={offer_id}", timeout=30)
    resp = requests.post(f"{BASE_URL}/dpu-user/auth/signup", json=payload, headers=headers, timeout=30)
    token = resp.json()["data"]["token"]

    result = query_db(f"SELECT merchant_id FROM dpu_users WHERE phone_number='{phone}'")
    merchant_id = result['merchant_id']
    log.info(f"✅ 注册: {phone}, merchant_id: {merchant_id}")

    # SP 授权
    state = str(uuid.uuid4())
    selling_partner_id = hashlib.md5(f"{uuid.uuid4()}{time.time()}".encode()).hexdigest().upper()
    headers_auth = {"Authorization": f"Bearer {token}", "content-type": "application/json", "finance-product": "LINE_OF_CREDIT", "funder-resource": "FUNDPARK", "product-currency": "USD"}

    requests.post(f"{BASE_URL}/dpu-merchant/shop-authorization/v2/sp-auth-url", json={"redirectUrl": f"https://expressfinance-dpu-reg.dowsure.com/redirect-loading?state={state}", "sceneCode": "SHOP_BIND", "sourceCode": "FUNDPARK", "state": state}, headers=headers_auth, timeout=30)
    requests.get(f"{BASE_URL}/dpu-auth/amazon-sp/auth", params={"mws_auth_token": "1235", "selling_partner_id": selling_partner_id, "spapi_oauth_code": "123123", "state": state}, timeout=30)
    time.sleep(2)

    result = wait_db(f"SELECT platform_offer_id, idempotency_key FROM dpu_manual_offer WHERE platform_seller_id='{selling_partner_id}' LIMIT 1", "platform_offer_id")
    platform_offer_id = result['platform_offer_id']
    idempotency_key = result['idempotency_key']

    requests.post(f"{BASE_URL}/dpu-auth/amazon-sp/updateOffer", json={"idempotencyKey": idempotency_key, "offerId": platform_offer_id, "reason": "An offer already exists", "sendStatus": "SUCCESS"}, timeout=30)
    requests.get(f"{BASE_URL}/dpu-merchant/amazon/redirect", params={"offerId": platform_offer_id}, timeout=30)
    requests.post(f"{BASE_URL}/dpu-merchant/amazon/redirect", json={"authToken": "mock", "expireOn": "null", "keyId": "null", "offerId": platform_offer_id, "relayPage": 1, "returnUrl": "null", "signature": "null"}, timeout=60)
    time.sleep(2)

    # 创建申请单
    requests.post(f"{BASE_URL}/dpu-merchant/fundpark-application/create", json={"tierCode": "2", "tierSnapshotValue": 0}, headers=headers_auth, timeout=30)
    time.sleep(2)

    result = wait_db(f"SELECT application_unique_id FROM dpu_application WHERE merchant_id='{merchant_id}' LIMIT 1", "application_id")
    app_id = result['application_unique_id']
    result = wait_db(f"SELECT merchant_account_id FROM dpu_merchant_account_limit WHERE merchant_id='{merchant_id}' LIMIT 1", "account_id")
    account_id = result['merchant_account_id']
    log.info(f"✅ 步骤 1-9 完成")

    # 步骤 10: 提交企业信息 (跳过,404)
    log.info("="*60)
    log.info("步骤 10: 跳过 (API 不存在)")

    # 步骤 12: 创建 credit offer
    log.info("步骤 12: 创建 credit offer")
    resp = requests.post(f"{BASE_URL}/dpu-merchant/credit-offer/create", headers=headers_auth, timeout=30)
    log.info(f"响应: {resp.status_code} - {resp.text[:150]}")
    time.sleep(2)

    # 步骤 13: SP-3PL 绑定
    requests.post(f"{BASE_URL}/dpu-merchant/mock/link-sp-3pl-shops", params={"phone": phone}, timeout=30)
    time.sleep(2)

    # 步骤 16: 手动触发后台任务
    log.info("步骤 16: 触发后台任务")
    resp = requests.post(f"{BASE_URL}/dpu-merchant/test/scheduled-tasks/first-application-start", headers=headers_auth, timeout=30)
    log.info(f"响应: {resp.status_code} - {resp.text[:150]}")
    time.sleep(5)

    # 等待 limit_application
    result = wait_db(f"SELECT limit_application_unique_id FROM dpu_limit_application WHERE merchant_id='{merchant_id}' LIMIT 1", "limit_application_id", timeout=60)
    limit_app_id = result['limit_application_unique_id']
    log.info(f"✅ limit_application_id: {limit_app_id}")

    # Webhooks
    def send_webhook(event_type, payload):
        resp = requests.post(f"{BASE_URL}/dpu-openapi/webhook-notifications", json=payload, timeout=30)
        log.info(f"{event_type}: {resp.status_code}")
        if resp.status_code != 200:
            log.error(f"错误: {resp.text[:200]}")
            raise Exception(f"Webhook failed: {event_type}")

    log.info("="*60)
    log.info("发送 webhooks")

    # underwritten
    send_webhook("underwrittenLimit.completed", {
        "data": {
            "eventType": "underwrittenLimit.completed",
            "eventId": str(uuid.uuid4()),
            "eventMessage": "underwrittenLimit completed event",
            "enquiryUrl": "https://api.example.com/enquiry/123",
            "datetime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": merchant_id,
                "lastUpdatedOn": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "lastUpdatedBy": "system",
                "dpuMerchantAccountId": [{"MerchantAccountId": account_id}],
                "dpuLimitApplicationId": limit_app_id,
                "originalRequestId": str(uuid.uuid4()),
                "status": "APPROVED",
                "credit": {
                    "marginRate": "2.5",
                    "chargeBases": "Float",
                    "baseRate": "3.5",
                    "baseRateType": "FIXED",
                    "creditLimit": {
                        "currency": "USD",
                        "underwrittenAmount": {"currency": "USD", "amount": "500000"},
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
    })
    time.sleep(3)

    result = wait_db(f"SELECT application_unique_id FROM dpu_application WHERE merchant_id='{merchant_id}' LIMIT 1", "application after underwritten")
    app_id = result['application_unique_id']

    # approved-offer
    send_webhook("approvedoffer.completed", {
        "data": {
            "eventType": "approvedoffer.completed",
            "eventId": str(uuid.uuid4()),
            "eventMessage": "Application approval process completed successfully",
            "enquiryUrl": "https://api.lender.com/enquiry/12345",
            "datetime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": merchant_id,
                "dpuApplicationId": app_id,
                "originalRequestId": str(uuid.uuid4()),
                "status": "APPROVED",
                "failureReason": None,
                "lenderApprovedOfferId": f"lender-{app_id}",
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

    # psp-start
    send_webhook("psp.verification.started", {
        "data": {
            "eventType": "psp.verification.started",
            "eventId": str(uuid.uuid4()),
            "eventMessage": "psp verification started event",
            "enquiryUrl": "https://api.example.com/enquiry/123",
            "datetime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": merchant_id,
                "lastUpdatedOn": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "lastUpdatedBy": "system",
                "applicationId": app_id,
                "pspId": "pspId123457",
                "pspName": "AirWallex",
                "merchantAccountId": account_id,
                "lenderApprovedOfferId": lender_offer_id,
                "result": "PROCESSING"
            }
        }
    })
    time.sleep(3)

    # psp-completed
    send_webhook("psp.verification.completed", {
        "data": {
            "eventType": "psp.verification.completed",
            "eventId": str(uuid.uuid4()),
            "eventMessage": "psp verification completed event",
            "enquiryUrl": "https://api.example.com/enquiry/123",
            "datetime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": merchant_id,
                "lastUpdatedOn": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "lastUpdatedBy": "system",
                "applicationId": app_id,
                "pspId": "pspId123457",
                "pspName": "AirWallex",
                "merchantAccountId": account_id,
                "lenderApprovedOfferId": lender_offer_id,
                "result": "SUCCESS"
            }
        }
    })
    time.sleep(3)

    # esign
    send_webhook("esign.completed", {
        "data": {
            "eventType": "esign.completed",
            "eventId": str(uuid.uuid4()),
            "eventMessage": "esign completed event",
            "enquiryUrl": "https://api.example.com/enquiry/123",
            "datetime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "details": {
                "merchantId": merchant_id,
                "lastUpdatedOn": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "lastUpdatedBy": "system",
                "lenderApprovedOfferId": lender_offer_id,
                "result": "SUCCESS",
                "signedLimit": {"amount": "500000", "currency": "USD"}
            }
        }
    })
    time.sleep(3)

    # 验证
    log.info("="*60)
    log.info("验证最终状态")
    result = query_db(f"SELECT status, e_sign_status FROM dpu_credit_offer WHERE merchant_id='{merchant_id}' LIMIT 1")
    log.info(f"credit_offer: {result}")

    log.info("="*60)
    log.info(f"✅ 完成! phone: {phone}, merchant_id: {merchant_id}")

if __name__ == "__main__":
    try:
        register_and_to_esign()
    except Exception as e:
        log.error(f"❌ {e}")
        import traceback
        traceback.print_exc()
