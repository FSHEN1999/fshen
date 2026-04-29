#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动运行scenario_1完整流程到esign成功
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from mock_uat import DatabaseExecutor, DPUMockService

def run_complete_flow():
    print("\n" + "="*60)
    print("开始执行 scenario_1 完整流程")
    print("="*60)

    env = "uat"

    with DatabaseExecutor(env) as db:
        # 步骤1: 注册新账号
        print("\n[步骤1] 注册新账号...")
        # 先不创建service，直接调用注册函数
        from mock_uat import register_new_account_batch
        phone, redirect_url = register_new_account_batch(db, currency="USD", amount="500000")
        print(f"✓ 注册成功: {phone}")
        print(f"  Redirect URL: {redirect_url[:80]}...")

        # 获取merchant_id
        merchant_id = db.execute_sql(f"SELECT merchant_id FROM dpu_users WHERE phone_number='{phone}'")
        print(f"  Merchant ID: {merchant_id}")

        # 创建service with phone
        service = DPUMockService(phone, db)

        # 步骤2: Underwriting
        print("\n[步骤2] 发送 Underwriting webhook...")
        service.mock_underwriting(phone, "APPROVED")
        print("✓ Underwriting 完成")

        # 步骤3: Approval
        print("\n[步骤3] 发送 Approval webhook...")
        service.mock_approval(phone, "APPROVED", "500000")
        print("✓ Approval 完成")

        # 步骤4: PSP Start
        print("\n[步骤4] 发送 PSP Start webhook...")
        service.mock_psp_verification_start(phone)
        print("✓ PSP Start 完成")

        # 步骤5: PSP Completed
        print("\n[步骤5] 发送 PSP Completed webhook...")
        service.mock_psp_verification_completed(phone)
        print("✓ PSP Completed 完成")

        # 步骤6: E-signature
        print("\n[步骤6] 发送 E-signature webhook...")
        service.mock_esign(phone)
        print("✓ E-signature webhook 发送完成")

        # 验证最终状态
        print("\n" + "="*60)
        print("验证最终状态")
        print("="*60)

        result = db.execute_query(
            f"SELECT status, e_sign_status, approved_limit_amount "
            f"FROM dpu_credit_offer WHERE merchant_id='{merchant_id}' "
            f"ORDER BY created_at DESC LIMIT 1"
        )

        if result:
            print(f"\nCredit Offer 状态:")
            print(f"  Status: {result.get('status')}")
            print(f"  E-sign Status: {result.get('e_sign_status')}")
            print(f"  Approved Amount: {result.get('approved_limit_amount')}")

            if result.get('e_sign_status') == 'SUCCESS':
                print("\n" + "="*60)
                print("✓✓✓ E-SIGNATURE COMPLETED SUCCESSFULLY! ✓✓✓")
                print("="*60)
                return True
            else:
                print(f"\n✗ E-signature 状态不是 SUCCESS: {result.get('e_sign_status')}")
                return False
        else:
            print("\n✗ 未找到 credit_offer 记录")
            return False

if __name__ == "__main__":
    try:
        success = run_complete_flow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
