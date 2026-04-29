# -*- coding: utf-8 -*-
"""
步骤 4-8: SP授权到创建申请单
"""
import logging
import requests
import hashlib
import time
import uuid
import pymysql

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger(__name__)

ENV = "reg"
BASE_URL = "https://dpu-gateway-reg.dowsure.com"
PHONE_NUMBER = "18612898782"
MERCHANT_ID = "8499ff6944c1414cb74ae74ba3350243"

DB_CONFIG = {
    "host": "18.162.145.173",
    "user": "dpu_reg",
    "password": "r4asUYBX3R6LNdp",
    "database": "dpu_seller_center",
    "port": 3307,
    "charset": "utf8mb4"
}

def generate_selling_partner_id():
    return hashlib.md5(f"{uuid.uuid4()}{time.time()}".encode()).hexdigest().upper()

def query_db(sql):
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute(sql)
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result

def step4_sp_auth(selling_partner_id, state):
    log.info("="*60)
    log.info("步骤 4: SP API 授权")
    log.info("="*60)

    url = f"{BASE_URL}/dpu-auth/amazon-sp/auth"
    params = {
        "mws_auth_token": "1235",
        "selling_partner_id": selling_partner_id,
        "spapi_oauth_code": "123123",
        "state": state
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
        log.info(f"响应: {resp.status_code} - {resp.text}")
        return resp.ok
    except Exception as e:
        log.error(f"异常: {e}")
        return False

def step5_update_offer(platform_offer_id, idempotency_key):
    log.info("="*60)
    log.info("步骤 5: updateOffer")
    log.info("="*60)

    url = f"{BASE_URL}/dpu-auth/amazon-sp/updateOffer"
    payload = {
        "platformOfferId": platform_offer_id,
        "idempotencyKey": idempotency_key
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        log.info(f"响应: {resp.status_code} - {resp.text}")
        return resp.ok
    except Exception as e:
        log.error(f"异常: {e}")
        return False

def step6_3pl_auth(selling_partner_id, state):
    log.info("="*60)
    log.info("步骤 6: 亚马逊3PL授权")
    log.info("="*60)

    url = f"{BASE_URL}/dpu-auth/amazon-3pl/auth"
    params = {
        "selling_partner_id": selling_partner_id,
        "spapi_oauth_code": "123123",
        "state": state
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
        log.info(f"响应: {resp.status_code} - {resp.text}")
        return resp.ok
    except Exception as e:
        log.error(f"异常: {e}")
        return False

def step7_3pl_auth_complete():
    log.info("="*60)
    log.info("步骤 7: 3PL AUTH授权")
    log.info("="*60)

    url = f"{BASE_URL}/dpu-merchant/mock/link-sp-3pl-shops"

    try:
        resp = requests.post(url, params={"phone": PHONE_NUMBER}, timeout=30)
        log.info(f"响应: {resp.status_code} - {resp.text}")
        return resp.ok
    except Exception as e:
        log.error(f"异常: {e}")
        return False

def step8_create_application():
    log.info("="*60)
    log.info("步骤 8: 创建申请单")
    log.info("="*60)

    # 查询 platform_offer_id
    sql = f"SELECT platform_offer_id, idempotency_key FROM dpu_manual_offer WHERE merchant_id='{MERCHANT_ID}' LIMIT 1"
    result = query_db(sql)

    if not result:
        log.error("未找到 platform_offer_id")
        return False

    platform_offer_id = result.get('platform_offer_id')
    log.info(f"platform_offer_id: {platform_offer_id}")

    # 触发创建申请单的API (通常是通过UI操作或特定API)
    # 这里可能需要调用特定的API来创建申请单
    log.info("需要确认创建申请单的具体API")

    return True

def main():
    log.info("开始执行步骤 4-8")

    # 步骤 3: 生成 state 和 selling_partner_id
    state = str(uuid.uuid4())
    selling_partner_id = generate_selling_partner_id()
    log.info(f"state: {state}")
    log.info(f"selling_partner_id: {selling_partner_id}")

    # 步骤 4: SP授权
    step4_sp_auth(selling_partner_id, state)

    # 查询 platform_offer_id
    time.sleep(2)
    sql = f"SELECT platform_offer_id, idempotency_key FROM dpu_manual_offer WHERE merchant_id='{MERCHANT_ID}' LIMIT 1"
    result = query_db(sql)

    if result:
        platform_offer_id = result.get('platform_offer_id')
        idempotency_key = result.get('idempotency_key')
        log.info(f"platform_offer_id: {platform_offer_id}")
        log.info(f"idempotency_key: {idempotency_key}")

        # 步骤 5: updateOffer
        step5_update_offer(platform_offer_id, idempotency_key)

        # 步骤 6: 3PL授权
        time.sleep(2)
        step6_3pl_auth(selling_partner_id, state)

        # 步骤 7: 3PL AUTH授权
        time.sleep(2)
        step7_3pl_auth_complete()

        # 步骤 8: 创建申请单
        time.sleep(2)
        step8_create_application()
    else:
        log.error("未找到 platform_offer_id，无法继续")

    log.info("="*60)
    log.info("执行完成，查询最终数据库状态")
    log.info("="*60)

if __name__ == "__main__":
    main()
