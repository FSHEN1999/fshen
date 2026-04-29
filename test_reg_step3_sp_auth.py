# -*- coding: utf-8 -*-
"""
步骤 3: SP API 授权 (SP-3PL 绑定)
目标: 生成 platform_offer_id 和相关数据
"""
import logging
import requests
import hashlib
import time
import uuid

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

# 配置
ENV = "reg"
BASE_URL = "https://dpu-gateway-reg.dowsure.com"
PHONE_NUMBER = "18612898782"


def generate_selling_partner_id() -> str:
    """生成 selling_partner_id"""
    unique_str = f"{uuid.uuid4()}{time.time()}"
    return hashlib.md5(unique_str.encode()).hexdigest().upper()


def test_sp_api_auth():
    """测试 SP API 授权"""
    log.info("="*60)
    log.info("步骤 3: SP API 授权")
    log.info("="*60)

    # 生成 selling_partner_id
    selling_partner_id = generate_selling_partner_id()
    log.info(f"生成 selling_partner_id: {selling_partner_id}")

    # 方法 1: SP API 授权 (GET)
    log.info(f"\n{'='*60}")
    log.info("方法 1: SP API 授权 (GET)")
    log.info(f"{'='*60}")

    sp_auth_url = f"{BASE_URL}/dpu-auth/amazon-sp/auth"
    params = {
        "mws_auth_token": "1235",
        "selling_partner_id": selling_partner_id,
        "spapi_oauth_code": "123123",
        "state": str(uuid.uuid4())
    }

    try:
        log.info(f"请求 URL: {sp_auth_url}")
        log.info(f"请求参数: {params}")

        resp = requests.get(sp_auth_url, params=params, timeout=30)

        log.info(f"响应状态码: {resp.status_code}")
        log.info(f"响应内容: {resp.text}")

        if resp.ok:
            log.info("✅ SP API 授权成功")
        else:
            log.error(f"❌ SP API 授权失败: {resp.status_code}")

    except Exception as e:
        log.error(f"❌ SP API 授权异常: {e}")

    # 方法 2: SP-3PL 绑定 (POST)
    log.info(f"\n{'='*60}")
    log.info("方法 2: SP-3PL 绑定 (POST)")
    log.info(f"{'='*60}")

    link_url = f"{BASE_URL}/dpu-merchant/mock/link-sp-3pl-shops"
    payload = {"phone": PHONE_NUMBER}

    try:
        log.info(f"请求 URL: {link_url}")
        log.info(f"请求参数: {payload}")

        resp = requests.post(link_url, params=payload, timeout=30)

        log.info(f"响应状态码: {resp.status_code}")
        log.info(f"响应内容: {resp.text}")

        if resp.ok:
            log.info("✅ SP-3PL 绑定成功")
            data = resp.json()
            log.info(f"响应数据: {data}")
        else:
            log.error(f"❌ SP-3PL 绑定失败: {resp.status_code}")

    except Exception as e:
        log.error(f"❌ SP-3PL 绑定异常: {e}")

    # 总结
    log.info(f"\n{'='*60}")
    log.info("总结")
    log.info(f"{'='*60}")
    log.info(f"手机号: {PHONE_NUMBER}")
    log.info(f"selling_partner_id: {selling_partner_id}")
    log.info("\n下一步:")
    log.info("1. 查询数据库确认数据是否生成")
    log.info("2. 如果生成了 platform_offer_id，执行 updateOffer")
    log.info("3. 继续后续的 webhook 流程")


if __name__ == "__main__":
    test_sp_api_auth()
