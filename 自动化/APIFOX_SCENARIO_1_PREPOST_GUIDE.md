# scenario_1 Apifox 前置/后置改造清单

## 导入文件

在 Apifox 选择 `Postman` 导入：

`D:\data\project\dpu\自动化\scenario_1_apifox_postman_collection.json`

这个 collection 已经内置了可迁移的 JS 脚本：

- step 04 自动生成 `phone`、`phoneNumber`、`email`
- step 06 从 signup 响应提取 `token`
- step 07 自动生成 `state`
- step 08 自动生成 `selling_partner_id`
- step 12 从创建申请单响应提取 `dpuApplicationId`
- step 14/16 自动设置 director 文件变量
- step 24.1 提取 `credit_offer_status`，最多轮询 30 次
- step 27/28/29/30 自动生成 webhook `eventId`、时间、金额、offer 变量

MeterSphere 的 SQL 前置/后置不能通过 Postman collection 自动导入到 Apifox，需要在 Apifox 里手工补数据库操作。

## 数据库连接

在 Apifox 项目设置中配置 REG 数据库连接：

- host: `18.162.145.173`
- port: `3307`
- database: `dpu_seller_center`
- user: `dpu_reg`

密码使用本地已有 REG 密码，不要写进导入文件。

## 必须补的数据库操作

### step 05 验证码调用验证生成一次 token

位置：step 05 前置操作。

用途：把短信验证码写入变量 `verificationCode`。

```sql
SELECT JSON_UNQUOTE(JSON_EXTRACT(placeholders, '$.verificationCode')) AS verificationCode
FROM dpu_seller_center.dpu_sms_record
WHERE phone_number = '{{phone}}'
ORDER BY COALESCE(send_time, create_time) DESC, id DESC
LIMIT 1;
```

变量映射：

- `verificationCode` -> `verificationCode`

如果 Apifox 数据库结果不能直接解析 JSON，可以先查 `placeholders`，再用后置脚本正则取 6 位数字。

### step 09 sp-updateOffer

位置：step 09 前置操作。

用途：拿到 SP 授权后生成的 offer 信息。

```sql
SELECT idempotency_key, platform_offer_id
FROM dpu_seller_center.dpu_manual_offer
WHERE platform_seller_id = '{{selling_partner_id}}'
ORDER BY created_at DESC
LIMIT 1;
```

变量映射：

- `idempotency_key` -> `idempotency_key`
- `platform_offer_id` -> `platform_offer_id`
- 同时把 `platform_offer_id` 复制给 `platformOfferId`

### step 16 邓白氏提交股东信息

位置：step 16 后置操作。

用途：修复本次申请的 `VIRUS_SCAN` 依赖，否则后续状态可能长期停在 `NEW`。

```sql
UPDATE dpu_seller_center.dpu_notify_event_dependency d
JOIN dpu_seller_center.dpu_notify_event e
  ON e.id = d.event_id
 AND e.event_type = d.event_type
 AND e.biz_id = d.biz_id
SET d.dependency_status = 'READY',
    d.dependency_finish_time = NOW(),
    d.update_time = NOW()
WHERE e.biz_id = (
  SELECT app_id FROM (
    SELECT a.application_unique_id AS app_id
    FROM dpu_seller_center.dpu_application a
    JOIN dpu_seller_center.dpu_users u ON u.merchant_id = a.merchant_id
    WHERE u.phone_number = '{{phone}}'
    ORDER BY a.created_at DESC
    LIMIT 1
  ) latest_app
)
  AND d.dependency_type = 'VIRUS_SCAN'
  AND d.dependency_status <> 'READY';
```

然后再加一个查询确认：

```sql
SELECT COUNT(*) AS virusScanPendingCount
FROM dpu_seller_center.dpu_notify_event_dependency d
JOIN dpu_seller_center.dpu_notify_event e
  ON e.id = d.event_id
 AND e.event_type = d.event_type
 AND e.biz_id = d.biz_id
WHERE e.biz_id = (
  SELECT app_id FROM (
    SELECT a.application_unique_id AS app_id
    FROM dpu_seller_center.dpu_application a
    JOIN dpu_seller_center.dpu_users u ON u.merchant_id = a.merchant_id
    WHERE u.phone_number = '{{phone}}'
    ORDER BY a.created_at DESC
    LIMIT 1
  ) latest_app
)
  AND d.dependency_type = 'VIRUS_SCAN'
  AND d.dependency_status <> 'READY';
```

变量映射：

- `virusScanPendingCount` -> `virusScanPendingCount`

期望值：`0`

### step 27 approved-offer

位置：step 27 前置操作。

用途：准备 approved-offer webhook 所需核心变量。

```sql
SELECT merchant_id,
       COALESCE(prefer_finance_product_currency, 'USD') AS preferredCurrency
FROM dpu_seller_center.dpu_users
WHERE phone_number = '{{phone}}'
ORDER BY created_at DESC
LIMIT 1;
```

变量映射：

- `merchant_id` -> `merchantId`
- `preferredCurrency` -> `preferredCurrency`

如果 step 12 的 `dpuApplicationId` 没有被自动提取，再补：

```sql
SELECT application_unique_id AS dpuApplicationId
FROM dpu_seller_center.dpu_application
WHERE merchant_id = '{{merchantId}}'
ORDER BY created_at DESC
LIMIT 1;
```

变量映射：

- `dpuApplicationId` -> `dpuApplicationId`

如果 `dpuMerchantAccountId` 为空，可以直接使用 `selling_partner_id`，或补查：

```sql
SELECT authorization_id AS dpuMerchantAccountId
FROM dpu_seller_center.dpu_auth_token
WHERE merchant_id = '{{merchantId}}'
  AND authorization_party = 'SP'
  AND status = 'ACTIVE'
  AND authorization_id IS NOT NULL
ORDER BY created_at DESC
LIMIT 1;
```

变量映射：

- `dpuMerchantAccountId` -> `dpuMerchantAccountId`

### step 28/29/30 PSP 和 eSign

位置：step 28、29、30 前置操作。

用途：确认 `lenderApprovedOfferId`。

```sql
SELECT lender_approved_offer_id AS lenderApprovedOfferId
FROM dpu_seller_center.dpu_credit_offer
WHERE merchant_id = '{{merchantId}}'
ORDER BY created_at DESC
LIMIT 1;
```

变量映射：

- `lenderApprovedOfferId` -> `lenderApprovedOfferId`

导入文件里的 JS 也会在变量为空时尝试使用 `lender-{{dpuApplicationId}}` 兜底。

### step 30 eSign 后置断言

位置：step 30 后置操作。

用途：确认最终 offer 状态。

```sql
SELECT lender_approved_offer_id,
       status,
       approved_limit_amount,
       approved_limit_currency,
       signed_limit_amount,
       signed_limit_currency,
       e_sign_status
FROM dpu_seller_center.dpu_credit_offer
WHERE merchant_id = '{{merchantId}}'
ORDER BY created_at DESC
LIMIT 1;
```

期望：

- `status = ACCEPTED`
- `approved_limit_amount = 500000`
- `e_sign_status = SUCCESS`

再确认 webhook 事件数量：

```sql
SELECT COUNT(*) AS finalWebhookEventCount
FROM dpu_seller_center.dpu_lender_event
WHERE merchant_id = '{{merchantId}}'
  AND event_type IN (
    'approvedoffer.completed',
    'psp.verification.started',
    'psp.verification.completed',
    'esign.completed'
  );
```

期望：

- `finalWebhookEventCount >= 4`

## 运行顺序

按 collection 顺序运行：

1. 04 到 08 可以靠 JS 自动生成基础变量。
2. 09 前必须补 `idempotency_key` / `platform_offer_id`。
3. 16 后必须执行 `VIRUS_SCAN` 修复 SQL。
4. 24.1 会自动轮询 `SUBMITTED`，最多 30 次。
5. 27 前必须有 `merchantId` 和 `dpuApplicationId`。
6. 28/29/30 前确认 `lenderApprovedOfferId`。

如果某一步脚本提示 `Missing variables`，按提示补对应 SQL 变量后重跑该步骤。
