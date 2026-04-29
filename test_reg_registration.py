# -*- coding: utf-8 -*-
"""
测试 REG 环境注册流程
目标：从注册开始,一步步测试能走到哪里
"""
import json
import logging
import time
import requests
from faker import Faker
from dataclasses import dataclass

# 环境配置
ENV = "reg"

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

# 初始化 Faker
faker = Faker("zh_CN")


@dataclass(frozen=True)
class ApiConfig:
    """API 配置数据类"""
    base_url: str
    create_offerid_url: str
    redirect_url: str
    register_url: str
    validate_url: str


def get_api_config() -> ApiConfig:
    """获取 REG 环境 API 配置"""
    base_url = "https://dpu-gateway-reg.dowsure.com"

    return ApiConfig(
        base_url=base_url,
        create_offerid_url=f"{base_url}/dpu-merchant/mock/generate-shop-performance",
        redirect_url=f"{base_url}/dpu-merchant/amazon/redirect",
        register_url=f"{base_url}/dpu-user/auth/signup",
        validate_url=f"{base_url}/dpu-user/auth/validateSmsCode-sign"
    )


def test_step_1_create_offer_id(journey: str, api_config: ApiConfig) -> str:
    """步骤 1: 创建 offer_id"""
    log.info(f"\n{'='*60}")
    log.info("步骤 1: 创建 offer_id")
    log.info(f"{'='*60}")

    journey_amount = {"200K": 100000, "500K": 800000, "2000K": 6000000}
    yearly_amount = journey_amount.get(journey.upper())

    try:
        log.info(f"请求 URL: {api_config.create_offerid_url}")
        log.info(f"请求参数: yearlyRepaymentAmount={yearly_amount}")

        resp = requests.post(
            api_config.create_offerid_url,
            json={"yearlyRepaymentAmount": yearly_amount},
            timeout=30
        )

        log.info(f"响应状态码: {resp.status_code}")
        log.info(f"响应内容: {resp.text}")

        if resp.ok:
            offer_id = resp.json().get("data", {}).get("amazon3plOfferId")
            if offer_id:
                log.info(f"✅ offer_id 创建成功: {offer_id}")
                return offer_id
            else:
                log.error("❌ 响应中没有 offer_id")
                return None
        else:
            log.error(f"❌ 创建 offer_id 失败: {resp.status_code}")
            return None

    except Exception as e:
        log.error(f"❌ 创建 offer_id 异常: {e}")
        return None


def test_step_2_activate_offer(offer_id: str, api_config: ApiConfig) -> bool:
    """步骤 2: 激活 offer"""
    log.info(f"\n{'='*60}")
    log.info("步骤 2: 激活 offer")
    log.info(f"{'='*60}")

    try:
        redirect_url = f"{api_config.redirect_url}?offerId={offer_id}"

        # GET 请求
        log.info(f"GET 请求: {redirect_url}")
        resp_get = requests.get(redirect_url, timeout=60)
        log.info(f"GET 响应状态码: {resp_get.status_code}")

        # POST 请求
        post_payload = {"offerId": offer_id, "relayPage": 1}
        log.info(f"POST 请求: {redirect_url}")
        log.info(f"POST 参数: {post_payload}")

        resp_post = requests.post(
            redirect_url,
            json=post_payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        log.info(f"POST 响应状态码: {resp_post.status_code}")
        log.info(f"POST 响应内容: {resp_post.text}")

        if resp_post.ok:
            log.info("✅ offer 激活成功")
            return True
        else:
            log.error(f"❌ offer 激活失败: {resp_post.status_code}")
            return False

    except Exception as e:
        log.error(f"❌ 激活 offer 异常: {e}")
        return False


def test_step_3_validate_sms(phone_number: str, currency: str, api_config: ApiConfig) -> bool:
    """步骤 3: 验证码验证"""
    log.info(f"\n{'='*60}")
    log.info("步骤 3: 验证码验证")
    log.info(f"{'='*60}")

    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "product-currency": currency,
        "finance-product": "LINE_OF_CREDIT",
        "funder-resource": "FUNDPARK",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/146.0.0.0 Safari/537.36"
    }

    validate_payload = {"areaCode": "+86", "code": "666666", "phone": phone_number}

    try:
        log.info(f"请求 URL: {api_config.validate_url}")
        log.info(f"请求参数: {validate_payload}")
        log.info(f"请求头: {headers}")

        resp = requests.post(
            api_config.validate_url,
            json=validate_payload,
            headers=headers,
            timeout=30
        )

        log.info(f"响应状态码: {resp.status_code}")
        log.info(f"响应内容: {resp.text}")

        if resp.ok:
            log.info("✅ 验证码验证成功")
            return True
        else:
            log.warning(f"⚠️ 验证码验证失败: {resp.status_code}")
            return False

    except Exception as e:
        log.warning(f"⚠️ 验证码验证异常: {e}")
        return False


def test_step_4_register(phone_number: str, email: str, offer_id: str, currency: str, api_config: ApiConfig) -> dict:
    """步骤 4: 注册账号"""
    log.info(f"\n{'='*60}")
    log.info("步骤 4: 注册账号")
    log.info(f"{'='*60}")

    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "product-currency": currency,
        "finance-product": "LINE_OF_CREDIT",
        "funder-resource": "FUNDPARK",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/146.0.0.0 Safari/537.36"
    }

    register_payload = {
        "phone": phone_number,
        "areaCode": "+86",
        "code": "666666",
        "email": email,
        "offerId": offer_id,
        "password": "Aa11111111..",
        "confirmPassword": "Aa11111111..",
        "isAcceptMarketing": True,
        "securityQuestionCode": "SEC_Q_004",
        "securityAnswer": "test",
        "preferFinanceProductCurrency": currency
    }

    try:
        # 先访问 redirect URL
        redirect_url = f"{api_config.redirect_url}?offerId={offer_id}"
        log.info(f"访问 redirect URL: {redirect_url}")
        requests.get(redirect_url, timeout=30)

        # 注册请求
        log.info(f"请求 URL: {api_config.register_url}")
        log.info(f"请求参数: {json.dumps(register_payload, indent=2)}")
        log.info(f"请求头: {headers}")

        resp = requests.post(
            api_config.register_url,
            json=register_payload,
            headers=headers,
            timeout=30
        )

        log.info(f"响应状态码: {resp.status_code}")
        log.info(f"响应内容: {resp.text}")

        if resp.ok:
            data = resp.json().get("data", {})
            token = data.get("token", "")
            log.info(f"✅ 注册成功！Token: {token[:50]}...")
            return {
                "success": True,
                "token": token,
                "data": data
            }
        else:
            log.error(f"❌ 注册失败: {resp.status_code}")
            return {
                "success": False,
                "status_code": resp.status_code,
                "response": resp.text
            }

    except Exception as e:
        log.error(f"❌ 注册异常: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def main():
    """主函数：测试完整注册流程"""
    log.info("="*60)
    log.info("开始测试 REG 环境注册流程")
    log.info("="*60)

    # 配置
    journey = "500K"  # 测试 500K 流程
    currency = "USD"  # 测试 USD 货币

    # 生成账号信息
    phone_number = ''.join(filter(str.isdigit, faker.phone_number()))
    email = f"{phone_number}y@163doushabao.com"

    log.info(f"\n测试配置:")
    log.info(f"  环境: {ENV}")
    log.info(f"  流程: {journey}")
    log.info(f"  货币: {currency}")
    log.info(f"  手机号: {phone_number}")
    log.info(f"  邮箱: {email}")

    # 获取 API 配置
    api_config = get_api_config()

    # 步骤 1: 创建 offer_id
    offer_id = test_step_1_create_offer_id(journey, api_config)
    if not offer_id:
        log.error("❌ 流程终止：无法创建 offer_id")
        return

    # 步骤 2: 激活 offer
    activate_success = test_step_2_activate_offer(offer_id, api_config)
    if not activate_success:
        log.warning("⚠️ offer 激活失败，但继续尝试后续步骤")

    # 步骤 3: 验证码验证
    test_step_3_validate_sms(phone_number, currency, api_config)

    # 步骤 4: 注册账号
    result = test_step_4_register(phone_number, email, offer_id, currency, api_config)

    # 总结
    log.info(f"\n{'='*60}")
    log.info("测试总结")
    log.info(f"{'='*60}")

    if result.get("success"):
        log.info("✅ 注册流程完成！")
        log.info(f"  手机号: {phone_number}")
        log.info(f"  邮箱: {email}")
        log.info(f"  密码: Aa11111111..")
        log.info(f"  Offer ID: {offer_id}")
        log.info(f"  Token: {result.get('token', '')[:50]}...")

        # 保存到文件
        with open("register_reg.txt", "a", encoding="utf-8") as f:
            f.write(f"{journey}-{currency},{phone_number},{offer_id}\n")
        log.info(f"  已保存到: register_reg.txt")
    else:
        log.error("❌ 注册流程失败")
        log.error(f"  错误信息: {result}")

    log.info(f"\n{'='*60}")
    log.info("下一步可以做什么？")
    log.info(f"{'='*60}")
    log.info("1. 查询数据库确认账号数据")
    log.info("2. 执行 SP API 授权")
    log.info("3. 发送 webhook 模拟状态变化")
    log.info("4. 测试完整的业务流程")


if __name__ == "__main__":
    main()
