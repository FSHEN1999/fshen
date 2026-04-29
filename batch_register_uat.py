# -*- coding: utf-8 -*-
"""
批量注册 UAT 环境测试账号
功能：批量创建指定额度的测试账号，并输出 JSON 格式的账号信息
"""
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import requests
from faker import Faker

# 环境配置
ENV = "uat"
SCRIPT_DIR = Path(__file__).parent.absolute()

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


def get_api_config(env: str = "uat") -> ApiConfig:
    """获取 API 配置"""
    base_url_dict = {
        "sit": "https://sit.api.expressfinance.business.hsbc.com",
        "dev": "https://dpu-gateway-dev.dowsure.com",
        "uat": "https://uat.api.expressfinance.business.hsbc.com",
        "preprod": "https://preprod.api.expressfinance.business.hsbc.com",
    }
    base_url = base_url_dict[env]

    return ApiConfig(
        base_url=base_url,
        create_offerid_url=f"{base_url}/dpu-merchant/mock/generate-shop-performance",
        redirect_url=f"{base_url}/dpu-merchant/amazon/redirect",
        register_url=f"{base_url}/dpu-user/auth/signup",
        validate_url=f"{base_url}/dpu-user/auth/validateSmsCode-sign"
    )


def create_offer_id(journey: str, api_config: ApiConfig) -> Optional[str]:
    """创建 offer_id"""
    journey_amount = {"200K": 100000, "500K": 800000, "2000K": 6000000}
    yearly_amount = journey_amount.get(journey.upper())
    if not yearly_amount:
        log.error(f"不支持的流程: {journey}")
        return None

    try:
        resp = requests.post(
            api_config.create_offerid_url,
            json={"yearlyRepaymentAmount": yearly_amount},
            timeout=30
        )
        offer_id = resp.json().get("data", {}).get("amazon3plOfferId") if resp.ok else None

        if offer_id:
            redirect_url = f"{api_config.redirect_url}?offerId={offer_id}"
            requests.get(redirect_url, timeout=30)
            post_payload = {"offerId": offer_id, "relayPage": 1}
            requests.post(
                redirect_url,
                json=post_payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            log.info(f"offer_id {offer_id} 已创建并激活")
        return offer_id
    except Exception as e:
        log.error(f"创建 offer_id 失败: {e}")
        return None


def register_account(journey: str, currency: str, api_config: ApiConfig) -> Optional[Dict[str, Any]]:
    """注册单个账号"""
    log.info(f"开始注册账号，流程: {journey}，货币: {currency}")

    # 生成账号信息
    phone_number = ''.join(filter(str.isdigit, faker.phone_number()))
    email = f"{phone_number}y@163doushabao.com"
    log.info(f"生成账号信息 | 手机号: {phone_number} | 邮箱: {email}")

    # 创建 offer_id
    offer_id = create_offer_id(journey, api_config)
    if not offer_id:
        log.error("创建 offer_id 失败")
        return None

    # 验证码验证
    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "product-currency": currency,
        "finance-product": "LINE_OF_CREDIT",
        "funder-resource": "FUNDPARK",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/146.0.0.0 Safari/537.36"
    }

    try:
        validate_payload = {"areaCode": "+86", "code": "666666", "phone": phone_number}
        requests.post(api_config.validate_url, json=validate_payload, headers=headers, timeout=30)
    except Exception as e:
        log.warning(f"验证码验证失败: {e}")

    # 注册请求
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
        redirect_url = f"{api_config.redirect_url}?offerId={offer_id}"
        requests.get(redirect_url, timeout=30)

        resp_register = requests.post(
            api_config.register_url,
            json=register_payload,
            headers=headers,
            timeout=30
        )
        resp_register.raise_for_status()

        token = resp_register.json().get("data", {}).get("token", "")
        log.info(f"注册成功！手机号: {phone_number}")

        return {
            "phone_number": phone_number,
            "email": email,
            "password": "Aa11111111..",
            "journey": journey,
            "currency": currency,
            "offer_id": offer_id,
            "token": token,
            "redirect_url": redirect_url,
            "security_question_code": "SEC_Q_004",
            "security_answer": "test"
        }
    except Exception as e:
        log.error(f"注册失败: {e} | 手机号: {phone_number}")
        return None


def batch_register(accounts_config: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """批量注册账号"""
    api_config = get_api_config(ENV)
    results = []

    for idx, config in enumerate(accounts_config, 1):
        journey = config["journey"]
        currency = config.get("currency", "CNY")

        log.info(f"\n{'='*60}")
        log.info(f"正在注册第 {idx}/{len(accounts_config)} 个账号")
        log.info(f"{'='*60}")

        account_info = register_account(journey, currency, api_config)
        if account_info:
            results.append(account_info)
            log.info(f"账号 {idx} 注册成功")
        else:
            log.error(f"账号 {idx} 注册失败")

        # 延迟避免请求过快
        if idx < len(accounts_config):
            time.sleep(2)

    return results


def main():
    """主函数"""
    # 配置要创建的账号：2 个 200k 额度，1 个 1M 额度
    accounts_config = [
        {"journey": "200K", "currency": "CNY"},
        {"journey": "200K", "currency": "CNY"},
        {"journey": "2000K", "currency": "CNY"}  # 1M 额度使用 2000K 流程
    ]

    log.info(f"开始批量注册 {len(accounts_config)} 个账号")
    log.info(f"环境: {ENV}")
    log.info(f"配置: {accounts_config}")

    # 批量注册
    results = batch_register(accounts_config)

    # 输出结果
    log.info(f"\n{'='*60}")
    log.info(f"批量注册完成！成功: {len(results)}/{len(accounts_config)}")
    log.info(f"{'='*60}")

    # 保存 JSON 文件
    output_dir = Path("C:/Users/PC/.claude/plugins/cache/claude-plugins-official/skill-creator/unknown/skills/dpu-test-workspace/iteration-1/batch-registration-json/without_skill/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"batch_registration_{ENV}_{timestamp}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    log.info(f"\n账号信息已保存到: {output_file}")

    # 打印 JSON 格式的账号信息
    print("\n" + "="*60)
    print("账号信息 JSON 格式:")
    print("="*60)
    print(json.dumps(results, ensure_ascii=False, indent=2))

    return results


if __name__ == "__main__":
    main()
