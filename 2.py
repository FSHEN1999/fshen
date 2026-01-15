# -*- coding: utf-8 -*-
"""
单独提取的 validateSmsCode-sign 验证 + signup 注册核心逻辑
可独立运行，保留完整依赖和异常处理
"""
import logging
import traceback
import requests
from faker import Faker

# ============================ 基础配置 =============================
# 环境配置（支持：sit/local/dev/uat/preprod）
ENV = "sit"

# 日志配置（极简版，保证日志输出）
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

# 初始化工具
faker = Faker("zh_CN")


# ============================ 数据类定义（极简版）============================
class ApiConfig:
    """API配置（仅保留注册相关）"""

    def __init__(self, base_url, create_offerid_url, redirect_url, register_url, txt_path):
        self.base_url = base_url
        self.create_offerid_url = create_offerid_url
        self.redirect_url = redirect_url
        self.register_url = register_url
        self.txt_path = txt_path


# ============================ 核心逻辑 =============================
def _create_offer_id(journey: str, api_config: ApiConfig) -> str:
    """创建offer_id（按流程生成对应额度）"""
    journey_amount = {"200K": 100000, "500K": 800000, "2000K": 6000000}
    yearly_amount = journey_amount.get(journey.upper(), 100000)  # 默认200K额度

    try:
        resp = requests.post(
            api_config.create_offerid_url,
            json={"yearlyRepaymentAmount": yearly_amount},
            timeout=30
        )
        resp.raise_for_status()
        offer_id = resp.json().get("data", {}).get("amazon3plOfferId")
        if not offer_id:
            log.error("创建offer_id失败：接口返回无amazon3plOfferId")
            raise Exception("offer_id创建失败")
        return offer_id
    except Exception as e:
        # 打印完整的异常堆栈信息
        log.error(f"创建offer_id异常：{e}\n完整报错堆栈：\n{traceback.format_exc()}")
        raise


def _validate_sms_code(phone: str) -> None:
    """validateSmsCode-sign 验证码验证"""
    # 固定的验证接口地址（UAT环境）
    validate_url = "https://uat.api.expressfinance.business.hsbc.com/dpu-user/auth/validateSmsCode-sign"

    # 精简的核心请求头
    headers = {
        "accept": "application/json, */*",
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/143.0.0.0 Safari/537.36"
    }

    # 验证请求体
    payload = {
        "areaCode": "+86",
        "code": "666666",
        "phone": phone
    }

    try:
        log.info(f"开始验证验证码 | 手机号：{phone}")
        resp = requests.post(validate_url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        log.info(f"验证码验证成功 | 响应：{resp.text[:100]}")
    except requests.exceptions.RequestException as e:
        # 打印完整的验证码验证错误信息
        log.error(f"验证码验证失败 | 原因：{str(e)}\n完整报错堆栈：\n{traceback.format_exc()}")
        # 验证失败不阻断注册流程，仅记录日志


def register_new_account() -> str:
    """
    完整的注册流程：
    1. 选择流程额度
    2. 生成手机号/邮箱
    3. 创建offer_id
    4. 调用validateSmsCode-sign验证
    5. 发送signup注册请求
    """
    # 1. 选择注册流程（简化版，默认200K）
    journey = "200K"
    log.info(f"开始注册新账号 | 流程：{journey}")

    # 2. 生成账号信息
    phone_number = faker.phone_number()
    email = f"{phone_number}y@163doushabao.com"
    log.info(f"生成账号信息 | 手机号：{phone_number} | 邮箱：{email}")

    # 3. 初始化API配置
    base_url_dict = {
        "sit": "https://sit.api.expressfinance.business.hsbc.com",
        "dev": "https://dpu-gateway-dev.dowsure.com",
        "uat": "https://uat.api.expressfinance.business.hsbc.com",
        "preprod": "https://preprod.api.expressfinance.business.hsbc.com",
        "local": "http://192.168.11.3:8080"
    }
    base_url = base_url_dict[ENV]

    api_config = ApiConfig(
        base_url=base_url,
        create_offerid_url=f"{base_url}/dpu-merchant/mock/generate-shop-performance",
        redirect_url=f"{base_url}/dpu-merchant/amazon/redirect" if ENV in ("uat", "preprod")
        else f"https://dpu-gateway-{ENV}.dowsure.com/dpu-merchant/amazon/redirect",
        register_url=f"{base_url}/dpu-user/auth/signup",
        txt_path=f"./register_{ENV}.txt"
    )

    # 4. 创建offer_id
    offer_id = _create_offer_id(journey, api_config)
    log.info(f"创建offer_id成功 | ID：{offer_id}")

    # 5. 核心：调用validateSmsCode-sign验证
    _validate_sms_code(phone_number)

    # 6. 构建注册请求参数
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
        "securityAnswer": "test"
    }

    # 7. 先访问重定向URL
    redirect_url = f"{api_config.redirect_url}?offerId={offer_id}"
    try:
        requests.get(redirect_url, timeout=30)
    except Exception as e:
        log.warning(f"访问重定向URL失败：{e}\n完整报错堆栈：\n{traceback.format_exc()}")

    # 8. 发送注册请求
    try:
        log.info(f"发送注册请求 | 手机号：{phone_number}")
        resp_register = requests.post(
            api_config.register_url,
            json=register_payload,
            timeout=30
        )
        resp_register.raise_for_status()

        # 解析响应
        resp_data = resp_register.json()
        token = resp_data.get("data", {}).get("token", "未获取到token")

        # 记录结果
        log.info(f"注册成功 | 手机号：{phone_number} | Token：{token}")
        with open(api_config.txt_path, 'a', encoding='utf-8') as f:
            f.write(f"\n{journey}\n{phone_number}\n{redirect_url}\n")

        return phone_number
    except Exception as e:
        # 打印完整的注册错误信息和响应内容
        error_resp = getattr(resp_register, 'text', '无响应内容')
        log.error(f"注册失败 | 原因：{e}\n响应内容：{error_resp}\n完整报错堆栈：\n{traceback.format_exc()}")
        raise


# ============================ 测试运行 =============================
if __name__ == '__main__':
    try:
        # 执行注册流程
        phone = register_new_account()
        print(f"\n✅ 注册完成，手机号：{phone}")
    except Exception as e:
        # 顶层异常捕获，打印完整的报错信息
        log.error(f"程序执行失败：{e}\n完整报错堆栈：\n{traceback.format_exc()}")
        # 控制台也打印完整报错，方便调试
        print(f"\n❌ 程序执行失败：{e}")
        print(f"完整报错堆栈：\n{traceback.format_exc()}")