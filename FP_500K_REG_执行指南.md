# FP-USD 500K 完整流程执行指南 (REG环境)

## 环境配置
- 环境: reg
- 配置文件: mock_sit.py (ENV="reg")
- 流程类型: 500K-2M

## 执行步骤

### 前置条件
确保已有注册用户，可以查询数据库获取：
```bash
cd d:/data/project/dpu
python -c "
import sys
sys.path.insert(0, 'mockapi')
from mock_uat import DatabaseExecutor
db = DatabaseExecutor(env='reg')
db.connect()
result = db.execute_query('SELECT merchant_id, phone_number, email FROM dpu_users ORDER BY created_at DESC LIMIT 1')
print(f'手机号: {result[\"phone_number\"]}')
print(f'Merchant ID: {result[\"merchant_id\"]}')
print(f'邮箱: {result[\"email\"]}')
"
```

### 完整流程 (500K-2M)

根据CLAUDE.md中的流程配置：
```
1.underwritten 
2.approved offer
3.psp_start
4.psp completed
5.更新esign状态
6.更新放款状态
```

### 执行命令

1. **启动mock_sit.py**
```bash
cd d:/data/project/dpu
python mock_sit.py
```

2. **选择已注册用户**
   - 输入选项: `2` (使用已注册手机号)
   - 输入手机号: `13334255067` (或从数据库查询的手机号)

3. **Step 1: Underwriting (核保)**
   - 选择操作: `1` (underwritten)
   - 输入核保金额: `500000`
   - 选择核保状态: `1` (APPROVED)

4. **Step 2: Approval (审批)**
   - 选择操作: `2` (approved offer)
   - 输入审批金额: `500000`
   - 选择审批货币: `2` (USD)
   - 选择审批状态: `1` (APPROVED)

5. **Step 3: PSP Start**
   - 选择操作: `5` (psp_start)

6. **Step 4: PSP Completed**
   - 选择操作: `6` (psp completed)

7. **Step 5: E-signature (电子签名)**
   - 选择操作: `3` (更新esign状态)
   - 选择esign状态: `1` (SUCCESS)

8. **Step 6: Drawdown (放款)** [可选]
   - 选择操作: `4` (更新放款状态)
   - 选择放款状态: `1` (APPROVED)

### 验证最终状态

执行以下命令验证流程完成：
```bash
python -c "
import sys
sys.path.insert(0, 'mockapi')
from mock_uat import DatabaseExecutor

db = DatabaseExecutor(env='reg')
db.connect()

phone_number = '13334255067'  # 替换为实际手机号
merchant_id = db.execute_sql(f\"SELECT merchant_id FROM dpu_users WHERE phone_number='{phone_number}'\")

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

print('最终状态:')
print(f'  Application Status: {result[\"application_status\"]}')
print(f'  E-sign Status: {result[\"esign_status\"]}')
print(f'  PSP Status: {result[\"psp_verification_status\"]}')
print(f'  Approved Amount: {result[\"approved_amount\"]} {result[\"approved_currency\"]}')
"
```

## 预期结果

完成后应该看到：
- Application Status: APPROVED
- E-sign Status: SUCCESS
- PSP Status: COMPLETED
- Approved Amount: 500000 USD

## 注意事项

1. 每个步骤之间建议等待2-3秒，确保webhook处理完成
2. 如果某个步骤失败，检查日志中的错误信息
3. reg环境的短信验证码"666666"可能不可用，建议使用已注册账号
4. 所有操作都会记录在日志中，可以查看详细的请求和响应信息
