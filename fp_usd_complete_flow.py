# -*- coding: utf-8 -*-
"""
完成 FP-USD 完整流程：使用 mock_sit.py 方法
使用已注册账号：13514183158
环境：SIT
"""
import sys
sys.path.insert(0, '.')

from mock_sit import DatabaseExecutor, DPUMockService
import hashlib
import uuid
import time

ENV = "sit"
PHONE = "13514183158"

def complete_fp_usd_flow():
    """使用 mock_sit.py 方法完成 FP-USD 流程"""

    print("="*80)
    print("FP-USD 完整流程：使用 mock_sit.py 方法")
    print("="*80)
    print(f"手机号: {PHONE}")
    print(f"环境: {ENV}")

    # 步骤 1: SP-3PL 绑定
    print("\n[步骤 1] SP-3PL 绑定...")
    selling_partner_id = hashlib.md5(f"{uuid.uuid4()}{time.time()}".encode()).hexdigest().upper()
    print(f"   selling_partner_id: {selling_partner_id}")

    with DatabaseExecutor(env=ENV) as db:
        service = DPUMockService(phone_number=PHONE, db_executor=db)
        DPUMockService.generated_selling_partner_id = selling_partner_id
        service.mock_link_sp_3pl_shop()

    print("[OK] SP-3PL 绑定完成")
    time.sleep(3)

    # 步骤 2: 查询 merchant_id
    print("\n[步骤 2] 查询 merchant_id...")
    with DatabaseExecutor(env=ENV) as db:
        merchant_id = db.execute_sql(
            f"SELECT merchant_id FROM dpu_users WHERE phone_number='{PHONE}' LIMIT 1"
        )
        print(f"   merchant_id: {merchant_id}")

    # 步骤 3: 查询关键 ID
    print("\n[步骤 3] 查询关键 ID...")
    with DatabaseExecutor(env=ENV) as db:
        application_unique_id = db.execute_sql(
            f"SELECT application_unique_id FROM dpu_application WHERE merchant_id='{merchant_id}' LIMIT 1"
        )
        merchant_account_id = db.execute_sql(
            f"SELECT merchant_account_id FROM dpu_merchant_account_limit WHERE merchant_id='{merchant_id}' LIMIT 1"
        )
        print(f"   application_unique_id: {application_unique_id}")
        print(f"   merchant_account_id: {merchant_account_id}")

    if not application_unique_id:
        print("\n[WARN] application_unique_id 仍为空，流程可能无法继续")
        print("建议：检查 SP-3PL 绑定是否成功生成了必要的数据")
        return

    # 步骤 4: 查询最终状态
    print("\n[步骤 4] 查询最终状态...")
    with DatabaseExecutor(env=ENV) as db:
        # 查询 application 状态
        app_status = db.execute_sql(
            f"SELECT application_status FROM dpu_application WHERE merchant_id='{merchant_id}' LIMIT 1"
        )

        # 查询 credit_offer 状态
        credit_offer_status = db.execute_sql(
            f"SELECT status FROM dpu_credit_offer WHERE merchant_id='{merchant_id}' ORDER BY created_at DESC LIMIT 1"
        )

        # 查询 manual_offer
        manual_offer_count = db.execute_sql(
            f"SELECT COUNT(*) FROM dpu_manual_offer WHERE platform_seller_id='{selling_partner_id}'"
        )

        print(f"   Application 状态: {app_status}")
        print(f"   Credit Offer 状态: {credit_offer_status}")
        print(f"   Manual Offer 数量: {manual_offer_count}")

    print("\n" + "="*80)
    print("[OK] FP-USD 流程执行完成！")
    print("="*80)
    print(f"手机号: {PHONE}")
    print(f"Merchant ID: {merchant_id}")
    print(f"Selling Partner ID: {selling_partner_id}")
    print(f"Application ID: {application_unique_id}")
    print(f"Account ID: {merchant_account_id}")
    print("="*80)

    # 生成报告
    report = {
        "environment": ENV,
        "phone_number": PHONE,
        "merchant_id": merchant_id,
        "selling_partner_id": selling_partner_id,
        "application_unique_id": application_unique_id,
        "merchant_account_id": merchant_account_id,
        "steps_completed": [
            "1. SP-3PL 绑定",
            "2. 查询 merchant_id",
            "3. 查询关键 ID",
            "4. 查询最终状态"
        ],
        "final_status": {
            "application_status": app_status,
            "credit_offer_status": credit_offer_status,
            "manual_offer_count": manual_offer_count
        }
    }

    import json
    with open('fp_usd_complete_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"报告已保存到: fp_usd_complete_report.json")

    return report

if __name__ == "__main__":
    complete_fp_usd_flow()
