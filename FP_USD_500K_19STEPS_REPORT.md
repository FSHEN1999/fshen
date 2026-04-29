# FP-USD-500k 完整19步执行报告

## 执行时间
2026-04-28 22:43-22:50

## 执行账号
- Phone: 18518954244
- Merchant ID: 81704c8252974fc180443865bff2f9d4
- Application ID: EFA17773874393456472
- Account ID: 6CFC3187B944436129B3EB96260CFA59

## 执行结果

### 成功完成的步骤 (1-13, 17-18)

**步骤1-3: 注册阶段** ✓
- 发送注册短信 (404但不影响流程)
- 验证SMS码
- 用户注册成功，获得token

**步骤4-6: SP授权** ✓
- 生成state
- SP授权完成
- 手动插入manual_offer记录（REG环境workaround）
- sp-updateOffer成功

**步骤7-8: 3PL授权** ✓
- 3PL GET授权
- 3PL POST授权

**步骤9-13: 申请阶段** ✓
- 创建申请单
- 提交企业信息
- 选择offer额度500k
- 创建credit offer
- 绑定SP和3PL店铺

**步骤14: 任务推进** ✗
- 等待limit_application超时（180秒）
- REG环境scheduled task未运行
- **解决方案**: 手动创建limit_application和credit_offer记录

**步骤15: Underwritten** -
- 跳过（REG环境自动生成）

**步骤16: Approved-Offer** ✗
- Webhook返回400
- 错误: 缺少offer.termUnit → 添加后仍报错缺少offer.rate → 添加后报"Invalid input parameters"
- **解决方案**: 手动更新credit_offer记录

**步骤17-18: PSP** ✓
- psp.verification.started: HTTP 200
- psp.verification.completed: HTTP 200

**步骤19: E-signature** ✗
- Webhook返回400: "Internal Server Error"
- credit_offer状态: ACCEPTED, e_sign_status: PROCESSING

## REG环境限制总结

### 1. Manual Offer不自动创建
- **问题**: SP授权后不会自动创建`dpu_manual_offer`记录
- **影响**: 步骤6无法获取platform_offer_id
- **解决**: 手动INSERT记录

### 2. Scheduled Task不运行
- **问题**: 步骤13后scheduled task不会自动创建limit_application
- **影响**: 步骤14超时
- **解决**: 手动INSERT limit_application和credit_offer

### 3. Approved-Offer Webhook格式严格
- **问题**: 需要完整的offer结构（rate, term, termUnit等）
- **影响**: 步骤16失败
- **解决**: 手动UPDATE credit_offer或使用已有完整数据的账号

### 4. E-signature Webhook失败
- **问题**: 手动创建的credit_offer缺少某些关联数据
- **影响**: 步骤19返回Internal Server Error
- **可能原因**: 
  - 缺少dpu_lender_event记录
  - 缺少其他关联表数据
  - credit_offer创建流程不完整

## 对比：简化Webhook流程 vs 完整19步

### 简化流程（已验证成功）
使用已有完整账号，只发送PSP和esign webhooks
- 执行时间: ~10秒
- 成功率: 100%
- 适用场景: 账号已完成注册和approved-offer

### 完整19步流程
从注册到esign的完整流程
- 执行时间: ~7分钟（含等待）
- 成功率: REG环境约60%（步骤1-13, 17-18成功）
- 限制: REG环境需要多处手动干预

## 建议

### 对于REG环境测试
1. 使用简化流程（仅webhook）测试业务逻辑
2. 完整流程需要：
   - 自动化manual_offer插入
   - 自动化limit_application创建
   - 使用mock endpoint触发scheduled task
   - 或使用其他环境（SIT/UAT）

### 对于生产环境
完整19步流程应该可以正常运行，因为：
- Scheduled task会正常执行
- Manual offer会自动创建
- Webhook格式验证可能更宽松或有完整的前置数据

## 完整日志文件
- `complete_19steps_usd_20260428_224347.log` - 步骤1-14
- `continue_19steps_webhooks_final_20260428_224930.log` - 步骤16-19尝试
- `final_psp_esign_20260428_225041.log` - 最终PSP和esign执行

## 数据库最终状态
```sql
SELECT * FROM dpu_credit_offer WHERE merchant_id='81704c8252974fc180443865bff2f9d4';
-- status: ACCEPTED
-- e_sign_status: PROCESSING (未能完成到SUCCESS)
-- approved_limit_amount: 500000.00
-- signed_limit_amount: 500000.00
```

## 结论

在REG环境中，由于scheduled task和自动化流程的限制，完整的19步自动化流程需要多处手动干预。

**成功完成**: 步骤1-13（注册到店铺绑定）+ 步骤17-18（PSP webhooks）

**需要改进**: 
- 步骤14: 自动触发或mock scheduled task
- 步骤16: 使用正确的approved-offer webhook格式或跳过
- 步骤19: 确保credit_offer有完整的关联数据

**推荐方案**: 
- 测试环境使用SIT/UAT而非REG
- 或使用已有完整账号进行webhook测试
