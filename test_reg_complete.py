# -*- coding: utf-8 -*-
"""
完整流程测试: 从注册到能走多远
"""
import logging, requests, hashlib, time, uuid, json, pymysql
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

def register():
    log.info("="*60)
    log.info("步骤 1-3: 注册账号")

    phone = ''.join(filter(str.isdigit, faker.phone_number()))
    email = f"{phone}y@163doushabao.com"

    resp = requests.post(f"{BASE_URL}/dpu-merchant/mock/generate-shop-performance", json={"yearlyRepaymentAmount": 800000}, timeout=30)
    offer_id = resp.json()["data"]["amazon3plOfferId"]

    headers = {"content-type": "application/json", "product-currency": "USD", "finance-product": "LINE_OF_CREDIT", "funder-resource": "FUNDPARK"}
    payload = {"phone": phone, "areaCode": "+86", "code": "666666", "email": email, "offerId": offer_id, "password": "Aa11111111..", "confirmPassword": "Aa11111111..", "isAcceptMarketing": True, "securityQuestionCode": "SEC_Q_004", "securityAnswer": "test", "preferFinanceProductCurrency": "USD"}

    requests.post(f"{BASE_URL}/dpu-user/auth/validateSmsCode-sign", json={"areaCode": "+86", "code": "666666", "phone": phone}, headers=headers, timeout=30)
    requests.get(f"{BASE_URL}/dpu-merchant/amazon/redirect?offerId={offer_id}", timeout=30)
    resp = requests.post(f"{BASE_URL}/dpu-user/auth/signup", json=payload, headers=headers, timeout=30)
    token = resp.json()["data"]["token"]

    # 查询 merchant_id
    result = query_db(f"SELECT merchant_id FROM dpu_users WHERE phone_number='{phone}'")
    merchant_id = result['merchant_id']

    log.info(f"✅ 注册成功: {phone}, merchant_id: {merchant_id}")
    return phone, token, merchant_id

def step4_5(token):
    log.info("="*60)
    log.info("步骤 4-5: 生成 state 并 SP 授权")

    state = str(uuid.uuid4())
    selling_partner_id = hashlib.md5(f"{uuid.uuid4()}{time.time()}".encode()).hexdigest().upper()

    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json", "finance-product": "LINE_OF_CREDIT", "funder-resource": "FUNDPARK", "product-currency": "USD"}
    payload = {"redirectUrl": f"https://expressfinance-dpu-reg.dowsure.com/redirect-loading?state={state}", "sceneCode": "SHOP_BIND", "sourceCode": "FUNDPARK", "state": state}

    resp = requests.post(f"{BASE_URL}/dpu-merchant/shop-authorization/v2/sp-auth-url", json=payload, headers=headers, timeout=30)
    log.info(f"步骤 4: {resp.status_code}")

    resp = requests.get(f"{BASE_URL}/dpu-auth/amazon-sp/auth", params={"mws_auth_token": "1235", "selling_partner_id": selling_partner_id, "spapi_oauth_code": "123123", "state": state}, timeout=30)
    log.info(f"步骤 5: {resp.status_code}")

    return selling_partner_id

def step6_7_8(merchant_id, phone):
    log.info("="*60)
    log.info("步骤 6-8: updateOffer 和 3PL 授权")

    # 查询 platform_offer_id
    result = query_db(f"SELECT platform_offer_id, idempotency_key FROM dpu_manual_offer WHERE merchant_id='{merchant_id}' LIMIT 1")

    if not result:
        log.info("未找到 platform_offer_id，执行 SP-3PL 绑定")
        resp = requests.post(f"{BASE_URL}/dpu-merchant/mock/link-sp-3pl-shops", params={"phone": phone}, timeout=30)
        log.info(f"SP-3PL 绑定: {resp.status_code}")
        time.sleep(2)
        result = query_db(f"SELECT platform_offer_id, idempotency_key FROM dpu_manual_offer WHERE merchant_id='{merchant_id}' LIMIT 1")

    if not result:
        log.error("❌ 无法获取 platform_offer_id")
        return False

    platform_offer_id = result['platform_offer_id']
    idempotency_key = result['idempotency_key']
    log.info(f"platform_offer_id: {platform_offer_id}")

    # 步骤 6: updateOffer
    resp = requests.post(f"{BASE_URL}/dpu-auth/amazon-sp/updateOffer", json={"idempotencyKey": idempotency_key, "offerId": platform_offer_id, "reason": "An offer already exists", "sendStatus": "SUCCESS"}, timeout=30)
    log.info(f"步骤 6: {resp.status_code}")

    # 步骤 7: 3PL redirect
    resp = requests.get(f"{BASE_URL}/dpu-merchant/amazon/redirect", params={"offerId": platform_offer_id}, timeout=30)
    log.info(f"步骤 7: {resp.status_code}")

    # 步骤 8: 3PL auth
    resp = requests.post(f"{BASE_URL}/dpu-merchant/amazon/redirect", json={"authToken": "mock", "expireOn": "null", "keyId": "null", "offerId": platform_offer_id, "relayPage": 1, "returnUrl": "null", "signature": "null"}, timeout=60)
    log.info(f"步骤 8: {resp.status_code}")

    return True

def step9(token):
    log.info("="*60)
    log.info("步骤 9: 创建申请单")

    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json", "finance-product": "LINE_OF_CREDIT", "funder-resource": "FUNDPARK", "product-currency": "USD"}
    resp = requests.post(f"{BASE_URL}/dpu-merchant/fundpark-application/create", json={"tierCode": "2", "tierSnapshotValue": 0}, headers=headers, timeout=30)
    log.info(f"步骤 9: {resp.status_code} - {resp.text[:150]}")

def check_db(merchant_id):
    log.info("="*60)
    log.info("查询数据库")

    result = query_db(f"SELECT application_unique_id FROM dpu_application WHERE merchant_id='{merchant_id}'")
    log.info(f"application_unique_id: {result['application_unique_id'] if result else 'None'}")

    result = query_db(f"SELECT merchant_account_id FROM dpu_merchant_account_limit WHERE merchant_id='{merchant_id}'")
    log.info(f"merchant_account_id: {result['merchant_account_id'] if result else 'None'}")

def main():
    phone, token, merchant_id = register()
    time.sleep(2)

    step4_5(token)
    time.sleep(2)

    if step6_7_8(merchant_id, phone):
        time.sleep(2)
        step9(token)
        time.sleep(2)
        check_db(merchant_id)

    log.info("="*60)
    log.info(f"✅ 完成! 手机号: {phone}, merchant_id: {merchant_id}")

if __name__ == "__main__":
    main()
