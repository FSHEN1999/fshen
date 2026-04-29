# -*- coding: utf-8 -*-
"""在 SIT 环境创建 FP-CNY 账号"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from mock_sit import DatabaseExecutor, DPUMockService, faker, generate_uuid37
import requests
import json

ENV = "sit"

def create_fp_cny_account():
    """创建 FP-CNY 账号"""
    # 生成测试数据
    phone_number = faker.phone_number()[:11]
    email = f"{phone_number}y@163doushabao.com"
    password = "Aa11111111.."
    yearly_amount = 200000  # FP 通常是 200k

    # API 配置
    base_url = "https://sit.api.expressfinance.business.hsbc.com"

    print(f"正在创建 FP-CNY 账号...")
    print(f"手机号: {phone_number}")
    print(f"邮箱: {email}")

    # 1. 生成 offer ID
    print("\n1. 生成 offer ID...")
    offer_response = requests.post(
        f"{base_url}/dpu-merchant/mock/generate-shop-performance",
        json={"yearlyRepaymentAmount": yearly_amount},
        timeout=30
    )
    offer_data = offer_response.json()
    offer_id = offer_data["data"]["amazon3plOfferId"]
    print(f"Offer ID: {offer_id}")

    # 2. 验证 SMS
    print("\n2. 验证 SMS...")
    sms_response = requests.post(
        f"{base_url}/dpu-user/auth/validateSmsCode-sign",
        json={
            "phoneNumber": phone_number,
            "smsCode": "666666",
            "offerId": offer_id
        },
        timeout=30
    )
    print(f"SMS 验证: {sms_response.status_code}")

    # 3. 注册账号 (FP-CNY)
    print("\n3. 注册账号 (FP-CNY)...")
    signup_response = requests.post(
        f"{base_url}/dpu-user/auth/signup",
        json={
            "phoneNumber": phone_number,
            "email": email,
            "offerId": offer_id,
            "password": password,
            "journey": "200K",  # FP 流程
            "currency": "CNY"   # CNY 货币
        },
        timeout=30
    )
    signup_data = signup_response.json()
    token = signup_data["data"]["token"]
    print(f"注册成功，Token: {token[:50]}...")

    # 4. 获取 redirect URL
    print("\n4. 获取 redirect URL...")
    redirect_url = f"{base_url}/dpu-merchant/amazon/redirect?{offer_id}"

    # 5. 查询 merchant_id
    print("\n5. 查询 merchant_id...")
    with DatabaseExecutor(env=ENV) as db:
        merchant_id = db.execute_sql(
            f"SELECT merchant_id FROM dpu_users WHERE phone_number='{phone_number}' LIMIT 1"
        )
        print(f"Merchant ID: {merchant_id}")

    # 6. 保存到日志
    log_file = f"register_{ENV}.txt"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"200K,{phone_number},{redirect_url}\n")

    # 输出结果
    result = {
        "success": True,
        "env": ENV,
        "journey": "FP (200K)",
        "currency": "CNY",
        "phone_number": phone_number,
        "email": email,
        "password": password,
        "merchant_id": merchant_id,
        "offer_id": offer_id,
        "redirect_url": redirect_url,
        "token": token
    }

    print("\n" + "="*60)
    print("✅ FP-CNY 账号创建成功")
    print("="*60)
    print(f"环境: {ENV.upper()}")
    print(f"流程: FP (200K)")
    print(f"货币: CNY")
    print(f"手机号: {phone_number}")
    print(f"邮箱: {email}")
    print(f"密码: {password}")
    print(f"Merchant ID: {merchant_id}")
    print(f"Offer ID: {offer_id}")
    print(f"Redirect URL: {redirect_url}")
    print(f"\n已保存到: {log_file}")
    print("="*60)

    return result

if __name__ == "__main__":
    create_fp_cny_account()
