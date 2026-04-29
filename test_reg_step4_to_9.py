# -*- coding: utf-8 -*-
"""
完整的注册到创建申请单流程 (步骤 4-9)
"""
import logging
import requests
import hashlib
import time
import uuid
import pymysql
import json

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

BASE_URL = "https://dpu-gateway-reg.dowsure.com"
PHONE = "18612898782"
MERCHANT_ID = "8499ff6944c1414cb74ae74ba3350243"

DB_CONFIG = {
    "host": "18.162.145.173", "user": "dpu_reg", "password": "r4asUYBX3R6LNdp",
    "database": "dpu_seller_center", "port": 3307, "charset": "utf8mb4"
}

def query_db(sql):
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute(sql)
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

def step4_generate_state(token):
    log.info("="*60)
    log.info("步骤 4: 生成 state 和 SP")
    state = str(uuid.uuid4())
    selling_partner_id = hashlib.md5(f"{uuid.uuid4()}{time.time()}".encode()).hexdigest().upper()

    url = f"{BASE_URL}/dpu-merchant/shop-authorization/v2/sp-auth-url"
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "finance-product": "LINE_OF_CREDIT",
        "funder-resource": "FUNDPARK",
        "product-currency": "USD"
    }
    payload = {
        "redirectUrl": f"https://expressfinance-dpu-reg.dowsure.com/redirect-loading?state={state}",
        "sceneCode": "SHOP_BIND",
        "sourceCode": "FUNDPARK",
        "state": state
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    log.info(f"响应: {resp.status_code} - {resp.text}")
    log.info(f"state: {state}")
    log.info(f"selling_partner_id: {selling_partner_id}")

    if resp.ok:
        data = resp.json()
        log.info(f"响应数据: {json.dumps(data, ensure_ascii=False)}")

    return state, selling_partner_id

def step5_sp_auth(state, selling_partner_id):
    log.info("="*60)
    log.info("步骤 5: 执行 SP 授权")

    url = f"{BASE_URL}/dpu-auth/amazon-sp/auth"
    params = {
        "mws_auth_token": "1235",
        "selling_partner_id": selling_partner_id,
        "spapi_oauth_code": "123123",
        "state": state
    }

    resp = requests.get(url, params=params, timeout=30)
    log.info(f"响应: {resp.status_code} - {resp.text[:200]}")
    return resp.ok

def step6_update_offer(platform_offer_id, idempotency_key):
    log.info("="*60)
    log.info("步骤 6: sp-updateOffer")

    url = f"{BASE_URL}/dpu-auth/amazon-sp/updateOffer"
    payload = {
        "idempotencyKey": idempotency_key,
        "offerId": platform_offer_id,
        "reason": "An offer already exists for the seller for the same partner product combination",
        "sendStatus": "SUCCESS"
    }

    resp = requests.post(url, json=payload, timeout=30)
    log.info(f"响应: {resp.status_code} - {resp.text[:200]}")
    return resp.ok

def step7_3pl_redirect(platform_offer_id):
    log.info("="*60)
    log.info("步骤 7: 亚马逊 3PL 授权 (GET)")

    url = f"{BASE_URL}/dpu-merchant/amazon/redirect"
    params = {"offerId": platform_offer_id}

    resp = requests.get(url, params=params, timeout=30)
    log.info(f"响应: {resp.status_code}")
    return resp.ok

def step8_3pl_auth(platform_offer_id):
    log.info("="*60)
    log.info("步骤 8: 3PL AUTH 授权 (POST)")

    url = f"{BASE_URL}/dpu-merchant/amazon/redirect"
    payload = {
        "authToken": "mock",
        "expireOn": "null",
        "keyId": "null",
        "offerId": platform_offer_id,
        "relayPage": 1,
        "returnUrl": "null",
        "signature": "null"
    }

    resp = requests.post(url, json=payload, timeout=60)
    log.info(f"响应: {resp.status_code} - {resp.text[:200]}")
    return resp.ok

def step9_create_application(token):
    log.info("="*60)
    log.info("步骤 9: 创建申请单")

    url = f"{BASE_URL}/dpu-merchant/fundpark-application/create"
    headers = {
        "Authorization": f"Bearer {token}",
        "content-type": "application/json",
        "finance-product": "LINE_OF_CREDIT",
        "funder-resource": "FUNDPARK",
        "product-currency": "USD"
    }
    payload = {"tierCode": "2", "tierSnapshotValue": 0}

    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    log.info(f"响应: {resp.status_code} - {resp.text[:200]}")
    return resp.ok

def main():
    log.info("开始执行步骤 4-9")

    # 获取 token (从注册时保存的)
    TOKEN = "yNGBRtF1q6fGd3aQxdQJEHZfXXUHBqsZxQMYNVLY9LSBDFB7MhfIOI9VDDfnF9Vj"

    # 步骤 4: 生成 state
    state, selling_partner_id = step4_generate_state(TOKEN)
    time.sleep(2)

    # 步骤 5: SP 授权
    step5_sp_auth(state, selling_partner_id)
    time.sleep(2)

    # 查询 platform_offer_id
    sql = f"SELECT platform_offer_id, idempotency_key FROM dpu_manual_offer WHERE merchant_id='{MERCHANT_ID}' LIMIT 1"
    result = query_db(sql)

    if not result:
        log.error("未找到 platform_offer_id，尝试执行 SP-3PL 绑定")
        resp = requests.post(f"{BASE_URL}/dpu-merchant/mock/link-sp-3pl-shops", params={"phone": PHONE}, timeout=30)
        log.info(f"SP-3PL 绑定: {resp.status_code}")
        time.sleep(2)
        result = query_db(sql)

    if result:
        platform_offer_id = result['platform_offer_id']
        idempotency_key = result['idempotency_key']
        log.info(f"platform_offer_id: {platform_offer_id}")

        # 步骤 6: updateOffer
        step6_update_offer(platform_offer_id, idempotency_key)
        time.sleep(2)

        # 步骤 7: 3PL redirect
        step7_3pl_redirect(platform_offer_id)
        time.sleep(2)

        # 步骤 8: 3PL auth
        step8_3pl_auth(platform_offer_id)
        time.sleep(2)

        # 步骤 9: 创建申请单
        step9_create_application(TOKEN)

        log.info("="*60)
        log.info("执行完成，查询数据库")
        sql = f"SELECT application_unique_id FROM dpu_application WHERE merchant_id='{MERCHANT_ID}'"
        result = query_db(sql)
        log.info(f"application_unique_id: {result}")
    else:
        log.error("无法获取 platform_offer_id")

if __name__ == "__main__":
    main()
