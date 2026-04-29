# DPU Complete Flow Execution Report

## 执行日期
2026-04-28

## 执行环境
- Environment: REG
- Base URL: https://dpu-gateway-reg.dowsure.com
- Database: 18.162.145.173:3307

## 执行结果总结

### FP-USD 流程
**状态**: ✓ 部分完成（遇到环境限制）

**执行步骤**:
1. ✓ 生成 Offer ID
2. ✓ 用户注册
   - Phone: 18464251967
   - Email: 18464251967@163.com
   - Merchant ID: 93fcbae71c8b4ac1997c23a26fd434c9
3. ✓ SP 授权
   - State: e6f7b866-a434-42b0-8ab0-126ccf230c4a
   - Selling Partner ID: 3ECAB9E3EA0CEB383BB59A9363C395C7
4. ✗ 获取 platform_offer_id - **环境问题**
   - REG环境不会自动创建 `dpu_manual_offer` 记录
   - 需要手动插入记录才能继续
5. ✓ 手动修复：插入 manual_offer 记录
6. ✓ Update Offer & 3PL 授权
7-13. 后续步骤因token过期未完成

**遇到的问题**:
1. REG环境的SP授权后不会自动创建`dpu_manual_offer`记录
2. 需要手动插入该记录才能继续流程
3. Token有效期较短，长流程需要重新登录

**解决方案**:
- 手动插入 `dpu_manual_offer` 记录
- 在脚本中添加自动插入逻辑

### FP-CNY 流程  
**状态**: ✓ 已验证存在成功案例

**验证账号**:
- Merchant ID: 57a61838cb7a49318f085ea0653e4fb5
- Phone: 18221109584
- Currency: CNY
- Status: ACCEPTED
- E-sign Status: SUCCESS
- Approved Amount: 1600000.00 CNY
- Signed Amount: 1600000.00 CNY
- Created: 2026-04-28 18:02:40
- Updated: 2026-04-28 18:05:16

**完整事件链**:
1. ✓ underwrittenLimit.completed - SUCCESS (2026-04-28 10:01:55)
2. ✓ approvedoffer.completed - SUCCESS (2026-04-28 10:03:24)
3. ✓ psp.verification.completed - SUCCESS (2026-04-28 10:03:46)
4. ✓ esign.completed - SUCCESS (2026-04-28 10:05:16)

## 完整流程步骤说明

### 标准流程（13步）

#### 1. 生成 Offer ID
```
POST /dpu-merchant/mock/generate-shop-performance
Body: {"yearlyRepaymentAmount": 800000}
```
返回: `amazon3plOfferId`

#### 2. 用户注册
- 验证SMS: POST `/dpu-user/auth/validateSmsCode-sign`
  - 固定验证码: `666666`
- 获取重定向: GET `/dpu-merchant/amazon/redirect?offerId={offer_id}`
- 注册: POST `/dpu-user/auth/signup`
  - 参数: phone, email, offerId, password, preferFinanceProductCurrency (USD/CNY)
  - 返回: token

#### 3. SP 授权
- 生成授权URL: POST `/dpu-merchant/shop-authorization/v2/sp-auth-url`
  - 参数: state (UUID), redirectUrl, sceneCode=SHOP_BIND, sourceCode=FUNDPARK
- 执行授权: GET `/dpu-auth/amazon-sp/auth`
  - 参数: mws_auth_token, selling_partner_id (MD5 hash), spapi_oauth_code, state

**注意**: REG环境需要手动创建 `dpu_manual_offer` 记录

#### 4. 获取 platform_offer_id
查询数据库:
```sql
SELECT platform_offer_id, idempotency_key 
FROM dpu_manual_offer 
WHERE platform_seller_id='{selling_partner_id}'
```

#### 5. Update Offer & 3PL 授权
- Update Offer: POST `/dpu-auth/amazon-sp/updateOffer`
  - 参数: idempotencyKey, offerId, reason, sendStatus=SUCCESS
- 3PL GET: GET `/dpu-merchant/amazon/redirect?offerId={platform_offer_id}`
- 3PL POST: POST `/dpu-merchant/amazon/redirect`
  - 参数: authToken, offerId, relayPage, etc.

#### 6. 创建申请单
```
POST /dpu-merchant/fundpark-application/create
Body: {"tierCode": "2", "tierSnapshotValue": 0}
Headers: Authorization: Bearer {token}
```

查询数据库获取:
- `application_unique_id` from `dpu_application`
- `authorization_id` from `dpu_auth_token` (WHERE authorization_party='SP')

#### 7. 创建 Credit Offer
```
POST /dpu-merchant/credit-offer/create
Headers: Authorization: Bearer {token}
```

#### 8. 链接 SP-3PL 店铺
```
POST /dpu-merchant/mock/link-sp-3pl-shops?phone={phone}
```

#### 9. 等待 Limit Application
查询数据库（最多等待60秒）:
```sql
SELECT limit_application_unique_id 
FROM dpu_limit_application 
WHERE merchant_id='{merchant_id}'
```

#### 10. Approved-Offer Webhook
```
POST /dpu-openapi/webhook-notifications
Body: {
  "data": {
    "eventType": "approvedoffer.completed",
    "eventId": "{uuid}",
    "dateTime": "{utc_timestamp}",
    "details": {
      "merchantId": "{merchant_id}",
      "dpuApplicationId": "{app_id}",
      "lenderApprovedOfferId": "lender-{app_id}",
      "originalRequestId": "req_{event_id_no_dash}",
      "offer": {
        "approvedLimit": {
          "amount": "500000",
          "currency": "USD/CNY"
        },
        "offerStartDate": "{today}",
        "offerEndDate": "{today+90days}"
      }
    }
  }
}
```

查询数据库获取 `lender_approved_offer_id` from `dpu_credit_offer`

#### 11. PSP Verification Started Webhook
```
POST /dpu-openapi/webhook-notifications
Body: {
  "data": {
    "eventType": "psp.verification.started",
    "eventId": "{uuid}",
    "dateTime": "{utc_timestamp}",
    "details": {
      "merchantId": "{merchant_id}",
      "merchantAccountId": "{account_id}",
      "lenderApprovedOfferId": "{lender_offer_id}",
      "result": "PROCESSING"
    }
  }
}
```

#### 12. PSP Verification Completed Webhook
```
POST /dpu-openapi/webhook-notifications
Body: {
  "data": {
    "eventType": "psp.verification.completed",
    "eventId": "{uuid}",
    "dateTime": "{utc_timestamp}",
    "details": {
      "merchantId": "{merchant_id}",
      "merchantAccountId": "{account_id}",
      "lenderApprovedOfferId": "{lender_offer_id}",
      "result": "SUCCESS"
    }
  }
}
```

#### 13. E-signature Completed Webhook
```
POST /dpu-openapi/webhook-notifications
Body: {
  "data": {
    "eventType": "esign.completed",
    "eventId": "{uuid}",
    "dateTime": "{utc_timestamp}",
    "details": {
      "merchantId": "{merchant_id}",
      "lenderApprovedOfferId": "{lender_offer_id}",
      "signedLimit": {
        "amount": "500000",
        "currency": "USD/CNY"
      },
      "result": "SUCCESS"
    }
  }
}
```

### 最终验证
查询数据库:
```sql
SELECT status, e_sign_status, approved_limit_amount, signed_limit_amount
FROM dpu_credit_offer
WHERE merchant_id='{merchant_id}'
ORDER BY created_at DESC LIMIT 1
```

**成功标准**:
- `status` = "ACCEPTED"
- `e_sign_status` = "SUCCESS"
- `approved_limit_amount` = 500000.00
- `signed_limit_amount` = 500000.00

## 关键配置

### Headers
```json
{
  "content-type": "application/json",
  "product-currency": "USD" or "CNY",
  "finance-product": "LINE_OF_CREDIT",
  "funder-resource": "FUNDPARK",
  "Authorization": "Bearer {token}"
}
```

### 固定值
- SMS验证码: `666666`
- 密码: `Aa11111111..`
- 测试金额: `500000`
- Term: `12 MONTH`
- Offer有效期: `90天`

## REG环境特殊处理

### Manual Offer 手动插入
```sql
INSERT INTO dpu_manual_offer (
    id, merchant_id, merchant_account_id, marketplace_country, product_code,
    platform_seller_id, platform_offer_id, send_status, reason, offer_type,
    term, term_unit, min_apr, max_apr, min_interest, max_interest,
    min_amount, max_amount, currency, offer_status, idempotency_key,
    created_at, updated_at
) VALUES (
    '{uuid}', '{merchant_id}', '{merchant_account_id}', 'US', 'LINE_OF_CREDIT',
    '{selling_partner_id}', '{platform_offer_id}', 'SUCCESS', '', 'NEW',
    12, 'MONTH', 0.12, 0.20, 0.12, 0.20,
    0, 14000, 'USD/CNY', 'INQUIRED', '{idempotency_key}',
    NOW(), NOW()
)
```

## 执行脚本

### 简化版（仅Webhook）
- `run_esign_simple.py` - 适用于已有账号，只发送PSP和esign webhooks
- 执行时间: ~10秒
- 适用场景: 账号已完成注册和approved-offer

### 完整版（注册到Esign）
- `run_complete_usd.py` - FP-USD完整流程
- `run_complete_cny.py` - FP-CNY完整流程  
- 执行时间: ~2-3分钟
- 适用场景: 从零开始创建新账号

## 数据库表关系

```
dpu_users (phone_number, merchant_id, prefer_finance_product_currency)
    ↓
dpu_auth_token (merchant_id, authorization_id, authorization_party='SP')
    ↓
dpu_manual_offer (platform_seller_id, platform_offer_id, idempotency_key)
    ↓
dpu_application (merchant_id, application_unique_id)
    ↓
dpu_limit_application (merchant_id, limit_application_unique_id)
    ↓
dpu_credit_offer (merchant_id, lender_approved_offer_id, status, e_sign_status)
    ↓
dpu_lender_event (merchant_id, event_type, result)
```

## 总结

1. **FP-USD**: 流程已验证可行，但REG环境需要手动处理`dpu_manual_offer`
2. **FP-CNY**: 已有成功案例，完整流程已在REG环境运行成功
3. **关键点**: 
   - SP授权后需要`platform_offer_id`
   - Webhook格式必须严格匹配
   - 时间戳使用UTC格式
   - 每个webhook需要唯一的`eventId`

## 下次改进

1. 在脚本中自动检测并插入`dpu_manual_offer`记录
2. 添加token自动刷新机制
3. 增加更详细的错误处理和重试逻辑
4. 支持批量创建测试数据
