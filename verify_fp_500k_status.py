#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证FP-USD 500K流程完成状态"""
import sys
sys.path.insert(0, 'mockapi')
from mock_uat import DatabaseExecutor

db = DatabaseExecutor(env='reg')
db.connect()

phone_number = input("请输入手机号: ").strip()
merchant_id = db.execute_sql(f"SELECT merchant_id FROM dpu_users WHERE phone_number='{phone_number}'")

if not merchant_id:
    print(f"未找到手机号 {phone_number} 对应的用户")
    sys.exit(1)

result = db.execute_query(f'''
    SELECT
        application_status,
        esign_status,
        psp_verification_status,
        approved_amount,
        approved_currency
    FROM dpu_merchant_applications
    WHERE merchant_account_id='{merchant_id}'
''')

print('\n' + '='*60)
print('FP-USD 500K 流程状态验证')
print('='*60)
print(f'手机号: {phone_number}')
print(f'Merchant ID: {merchant_id}')
print('-'*60)
if result:
    print(f'Application Status: {result["application_status"]}')
    print(f'E-sign Status: {result["esign_status"]}')
    print(f'PSP Status: {result["psp_verification_status"]}')
    print(f'Approved Amount: {result["approved_amount"]} {result["approved_currency"]}')
else:
    print('未找到申请记录')
print('='*60)
