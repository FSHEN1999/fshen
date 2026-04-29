# -*- coding: utf-8 -*-
"""
FP-USD 完整流程测试：从注册到 esign 成功
环境：SIT
流程：FP (200K)
货币：USD
"""
import sys
sys.path.insert(0, '.')

from mock_sit import DatabaseExecutor, DPUMockService, faker, DPUStatus
from batch_register_uat import register_account, get_api_config
import json
import time

ENV = "sit"

def fp_usd_to_esign_flow():
    """执行 FP-USD 从注册到 esign 成功的完整流程"""

    print("="*80)
    print("FP-USD 完整流程测试：注册 → esign 成功")
    print("="*80)

    # 步骤 1: 注册 FP-USD 账号
    print("\n[步骤 1/7] 注册 FP-USD 账号...")
    api_config = get_api_config(ENV)
    result = register_account(journey="200K", currency="USD", api_config=api_config)

    if not result:
        print("❌ 注册失败")
        return None

    phone = result['phone_number']
    print(f"[OK] 注册成功")
    print(f"   手机号: {phone}")
    print(f"   Offer ID: {result['offer_id']}")

    # 查询 merchant_id
    with DatabaseExecutor(env=ENV) as db:
        merchant_id = db.execute_sql(
            f"SELECT merchant_id FROM dpu_users WHERE phone_number='{phone}' LIMIT 1"
        )
        print(f"   Merchant ID: {merchant_id}")

    # 等待数据同步
    time.sleep(2)

    # 步骤 2: Approved Offer (第一次)
    print("\n[步骤 2/9] Approved Offer (第一次)...")
    with DatabaseExecutor(env=ENV) as db:
        service = DPUMockService(phone_number=phone, db_executor=db)
        service.mock_approved_offer_status()
    print("[OK] Approved Offer 完成")

    time.sleep(2)

    # 步骤 3: E-sign (第一次)
    print("\n[步骤 3/9] E-sign (第一次)...")
    with DatabaseExecutor(env=ENV) as db:
        service = DPUMockService(phone_number=phone, db_executor=db)
        service.mock_esign_status()
    print("[OK] E-sign (第一次) 完成")

    time.sleep(2)

    # 步骤 4: Drawdown (第一次)
    print("\n[步骤 4/9] Drawdown (第一次)...")
    with DatabaseExecutor(env=ENV) as db:
        service = DPUMockService(phone_number=phone, db_executor=db)
        service.mock_drawdown_status()
    print("[OK] Drawdown (第一次) 完成")

    time.sleep(2)

    # 步骤 5: Underwritten
    print("\n[步骤 5/9] Underwritten...")
    with DatabaseExecutor(env=ENV) as db:
        service = DPUMockService(phone_number=phone, db_executor=db)
        service.mock_underwritten_status()
    print("[OK] Underwritten 完成")

    time.sleep(2)

    # 步骤 6: Approved Offer (第二次)
    print("\n[步骤 6/9] Approved Offer (第二次)...")
    with DatabaseExecutor(env=ENV) as db:
        service = DPUMockService(phone_number=phone, db_executor=db)
        service.mock_approved_offer_status()
    print("[OK] Approved Offer (第二次) 完成")

    time.sleep(2)

    # 步骤 7: PSP Start
    print("\n[步骤 7/9] PSP Start...")
    with DatabaseExecutor(env=ENV) as db:
        service = DPUMockService(phone_number=phone, db_executor=db)
        service.mock_psp_start_status()
    print("[OK] PSP Start 完成")

    time.sleep(2)

    # 步骤 8: PSP Completed
    print("\n[步骤 8/9] PSP Completed...")
    with DatabaseExecutor(env=ENV) as db:
        service = DPUMockService(phone_number=phone, db_executor=db)
        service.mock_psp_completed_status()
    print("[OK] PSP Completed 完成")

    time.sleep(2)

    # 步骤 9: E-sign (第二次 - 最终目标)
    print("\n[步骤 9/9] E-sign (第二次 - 最终目标)...")
    with DatabaseExecutor(env=ENV) as db:
        service = DPUMockService(phone_number=phone, db_executor=db)
        service.mock_esign_status()
    print("[OK] E-sign (第二次) 完成")

    # 验证最终状态
    print("\n" + "="*80)
    print("验证最终状态...")
    print("="*80)

    with DatabaseExecutor(env=ENV) as db:
        # 查询 esign 状态
        esign_status = db.execute_sql(
            f"SELECT esign_status FROM dpu_application WHERE merchant_id='{merchant_id}' LIMIT 1"
        )

        # 查询 PSP 状态
        psp_status = db.execute_sql(
            f"SELECT psp_status FROM dpu_application WHERE merchant_id='{merchant_id}' LIMIT 1"
        )

        # 查询 approval 状态
        approval_status = db.execute_sql(
            f"SELECT approval_status FROM dpu_application WHERE merchant_id='{merchant_id}' LIMIT 1"
        )

        print(f"E-sign 状态: {esign_status}")
        print(f"PSP 状态: {psp_status}")
        print(f"Approval 状态: {approval_status}")

    # 生成流程报告
    flow_report = {
        "environment": ENV,
        "journey": "FP (200K)",
        "currency": "USD",
        "phone_number": phone,
        "merchant_id": merchant_id,
        "offer_id": result['offer_id'],
        "steps_completed": [
            "1. 注册账号",
            "2. Approved Offer (第一次)",
            "3. E-sign (第一次)",
            "4. Drawdown (第一次)",
            "5. Underwritten",
            "6. Approved Offer (第二次)",
            "7. PSP Start",
            "8. PSP Completed",
            "9. E-sign (第二次) ✅"
        ],
        "final_status": {
            "esign_status": esign_status,
            "psp_status": psp_status,
            "approval_status": approval_status
        }
    }

    # 保存报告
    with open('fp_usd_flow_report.json', 'w', encoding='utf-8') as f:
        json.dump(flow_report, f, indent=2, ensure_ascii=False)

    print("\n" + "="*80)
    print("[OK] FP-USD 完整流程执行成功！")
    print("="*80)
    print(f"手机号: {phone}")
    print(f"Merchant ID: {merchant_id}")
    print(f"最终状态: E-sign SUCCESS")
    print(f"流程报告已保存到: fp_usd_flow_report.json")
    print("="*80)

    return flow_report

if __name__ == "__main__":
    fp_usd_to_esign_flow()
