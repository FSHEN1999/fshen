# 线下 FP-USD 2k MS 场景说明

## 场景目标

基于已经跑通的 `scenario_1`，输出一份适用于线下 `FP-USD 2k` 的 MeterSphere 场景文件，并把关键链路改成符合脚本真实逻辑的版本：

- 注册验证码必须走数据库查询
- 2k 后半段必须包含完整的 `approved / esign / disbursement` webhook

## 关键差异

- `500k` 走高额度链路，核心是 `underwritten -> approved -> psp -> esign`
- `2k` 走直通链路，核心是 `credit-offer轮询 -> approved -> esign -> drawdown轮询 -> disbursement`
- `2k` 不再使用固定验证码
- `2k` 补上了 `FUNDPARK + currency=USD` 的资方切换步骤

## 场景步骤

1. 发送注册短信
2. 从 `dpu_sms_record` 查询验证码并调用校验接口
3. 用户注册并提取 `token`
4. 选择 `FUNDPARK` 流程，显式传 `currency=USD`
5. 生成 SP 授权 `state`
6. 执行 SP 授权
7. 生成 3PL `offerId`
8. 3PL 跳转授权 GET
9. 3PL 跳转授权 POST
10. 创建申请单
11. 提交企业信息
12. 提交董事股东信息
13. 选择 `2k` 额度
14. 查询 offer 选择页
15. 激活 offer
16. 关联 SP 和 3PL 店铺
17. 手动触发 FP sanction 任务
18. 手动触发 FP 首次信用模型任务
19. 手动触发 FP 首次申请启动任务
20. 初始化 `credit_offer_status`
21. 轮询 `credit-offer/status` 直到 `SUBMITTED`
22. 校验 `credit_offer_status = SUBMITTED`
23. 发送 `approvedoffer.completed`
24. 发送 `esign.completed`
25. 初始化 `drawdown_status`
26. 轮询 `drawdown/status` 直到 `SUBMITTED`
27. 校验 `drawdown_status = SUBMITTED`
28. 发送 `disbursement.completed`

## 关键实现点

### 验证码

- 第 2 步前置处理器保留了 SQL 查询
- 查询表：`dpu_seller_center.dpu_sms_record`
- 查询结果通过脚本提取为 `${verificationCode}`
- 接口请求体使用 `${verificationCode}`，不再硬编码 `666666`

### Approved

- `approvedAmount` 默认值改为 `2000`
- `term` 改为 `12`
- `termUnit` 改为 `Months`

### Esign

- `signedAmount` 默认值改为 `2000`

### Disbursement

- 新增 `disbursement-completed` 步骤
- 前置 SQL 查询：
  - `merchant_id`
  - `preferred_currency`
  - `application_unique_id`
  - `loan_id`
- 请求体按脚本逻辑生成：
  - `lenderApprovedOfferId = lender-${application_unique_id}`
  - `lenderLoanId = lender-${loan_id}`
  - `loanAmount.amount = 2000`

## 产物

- MeterSphere 场景文件：`scenario_2_fp_usd_2k.ms`
- 生成脚本：`generate_fp_usd_2k_ms.py`
- 验证脚本：`validate_fp_usd_2k_direct_flow.py`
