# -*- coding: utf-8 -*-
"""在 SIT 环境创建 FP-CNY 账号"""
import sys
sys.path.insert(0, '.')

from batch_register_uat import register_account, get_api_config
from mock_sit import DatabaseExecutor

ENV = "sit"

# 创建 FP-CNY 账号
api_config = get_api_config(ENV)
result = register_account(journey="200K", currency="CNY", api_config=api_config)

if result:
    # 查询 merchant_id
    with DatabaseExecutor(env=ENV) as db:
        merchant_id = db.execute_sql(
            f"SELECT merchant_id FROM dpu_users WHERE phone_number='{result['phone_number']}' LIMIT 1"
        )

    print("\n" + "="*60)
    print("✅ FP-CNY 账号创建成功")
    print("="*60)
    print(f"环境: SIT")
    print(f"流程: FP (200K)")
    print(f"货币: CNY")
    print(f"手机号: {result['phone_number']}")
    print(f"邮箱: {result['email']}")
    print(f"密码: Aa11111111..")
    print(f"Merchant ID: {merchant_id}")
    print(f"Offer ID: {result['offer_id']}")
    print(f"Redirect URL: {result['redirect_url']}")
    print("="*60)
else:
    print("❌ 账号创建失败")
