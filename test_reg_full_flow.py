# -*- coding: utf-8 -*-
"""
完整流程: 注册 -> 创建申请单
"""
import logging, requests, hashlib, time, uuid, json
from faker import Faker

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

BASE_URL = "https://dpu-gateway-reg.dowsure.com"
faker = Faker("zh_CN")

def register():
    log.info("="*60)
    log.info("注册新账号")

    phone = ''.join(filter(str.isdigit, faker.phone_number()))
    email = f"{phone}y@163doushabao.com"

    # 创建 offer_id
    resp = requests.post(f"{BASE_URL}/dpu-merchant/mock/generate-shop-performance", json={"yearlyRepaymentAmount": 800000}, timeout=30)
    offer_id = resp.json()["data"]["amazon3plOfferId"]
    log.info(f"offer_id: {offer_id}")

    # 注册
    headers = {"content-type": "application/json", "product-currency": "USD", "finance-product": "LINE_OF_CREDIT", "funder-resource": "FUNDPARK"}
    payload = {"phone": phone, "areaCode": "+86", "code": "666666", "email": email, "offerId": offer_id, "password": "Aa11111111..", "confirmPassword": "Aa11111111..", "isAcceptMarketing": True, "securityQuestionCode": "SEC_Q_004", "securityAnswer": "test", "preferFinanceProductCurrency": "USD"}

    requests.post(f"{BASE_URL}/dpu-user/auth/validateSmsCode-sign", json={"areaCode": "+86", "code": "666666", "phone": phone}, headers=headers, timeout=30)
    requests.get(f"{BASE_URL}/dpu-merchant/amazon/redirect?offerId={offer_id}", timeout=30)

    resp = requests.post(f"{BASE_URL}/dpu-user/auth/signup", json=payload, headers=headers, timeout=30)
    token = resp.json()["data"]["token"]
    log.info(f"注册成功: {phone}, token: {token[:30]}...")

    return phone, token, offer_id

def step4_generate_state(token):
    log.info("="*60)
    log.info("步骤 4: 生成 state")

    state = str(uuid.uuid4())
    selling_partner_id = hashlib.md5(f"{uuid.uuid4()}{time.time()}".encode()).hexdigest().upper()

    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json", "finance-product": "LINE_OF_CREDIT", "funder-resource": "FUNDPARK", "product-currency": "USD"}
    payload = {"redirectUrl": f"https://expressfinance-dpu-reg.dowsure.com/redirect-loading?state={state}", "sceneCode": "SHOP_BIND", "sourceCode": "FUNDPARK", "state": state}

    resp = requests.post(f"{BASE_URL}/dpu-merchant/shop-authorization/v2/sp-auth-url", json=payload, headers=headers, timeout=30)
    log.info(f"响应: {resp.status_code} - {resp.text[:150]}")

    return state, selling_partner_id

def step5_sp_auth(state, selling_partner_id):
    log.info("="*60)
    log.info("步骤 5: SP 授权")

    resp = requests.get(f"{BASE_URL}/dpu-auth/amazon-sp/auth", params={"mws_auth_token": "1235", "selling_partner_id": selling_partner_id, "spapi_oauth_code": "123123", "state": state}, timeout=30)
    log.info(f"响应: {resp.status_code} - {resp.text[:150]}")

def main():
    # 注册
    phone, token, offer_id = register()
    time.sleep(2)

    # 步骤 4-5
    state, selling_partner_id = step4_generate_state(token)
    time.sleep(2)
    step5_sp_auth(state, selling_partner_id)

    log.info("="*60)
    log.info(f"完成! 手机号: {phone}")

if __name__ == "__main__":
    main()
