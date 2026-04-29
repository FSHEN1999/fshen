# scenario_1.ms Apifox JS 前后置脚本

来源文件：`自动化/scenario_1.ms`

说明：

- Apifox 自定义脚本使用 JavaScript，下面把 MeterSphere 里的 Python / Beanshell / Groovy 脚本转换成 JS。
- MeterSphere 的 SQL 前后置不建议硬改成 JS。Apifox 支持“数据库操作”，请把 SQL 放进对应步骤的“前置操作/后置操作 -> 数据库操作”，并把结果提取到文档里标注的变量名。
- 下面的 `setVar` 同时写入临时变量和环境变量，方便后续接口读取。如果你不希望污染环境变量，把 `pm.environment.set(...)` 那一行删掉即可。
- SQL 里的 MeterSphere 变量 `${phone}` 在 Apifox 数据库操作里建议改成 `{{phone}}`。

## 0. 公共 JS 工具

建议每个自定义脚本顶部都带上这一段；或者放到 Apifox 公共脚本里，然后普通脚本调用其中的纯函数。

```javascript
function getVar(name, defaultValue = "") {
  const v = pm.variables.get(name);
  if (v !== undefined && v !== null && String(v) !== "") return v;
  const env = pm.environment.get(name);
  if (env !== undefined && env !== null && String(env) !== "") return env;
  return defaultValue;
}

function setVar(name, value) {
  const v = value === undefined || value === null ? "" : String(value);
  pm.variables.set(name, v);
  pm.environment.set(name, v);
}

function uuidv4() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    const v = c === "x" ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

function randomHex(length) {
  let s = "";
  while (s.length < length) {
    s += Math.floor(Math.random() * 0xffffffff).toString(16).padStart(8, "0");
  }
  return s.slice(0, length).toUpperCase();
}

function pad2(n) {
  return String(n).padStart(2, "0");
}

function utcTime() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function localDateTime() {
  const d = new Date();
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}

function dateOnly(offsetDays = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

function extractValue(raw) {
  if (raw === undefined || raw === null) return "";

  if (typeof raw === "object") {
    if (Array.isArray(raw)) {
      if (raw.length === 0) return "";
      const first = raw[0];
      if (typeof first === "object" && first !== null) {
        const values = Object.values(first);
        return values.length ? String(values[0]).trim() : "";
      }
      return String(first).trim();
    }
    const values = Object.values(raw);
    return values.length ? String(values[0]).trim() : "";
  }

  const s = String(raw).trim();
  if (["", "None", "null", "undefined", "[]"].includes(s)) return "";

  try {
    const parsed = JSON.parse(s);
    if (parsed !== s) return extractValue(parsed);
  } catch (e) {}

  const match = s.match(/=\s*([^}\]]+)/);
  if (match) return match[1].trim();
  return s;
}

function assertHttp200AndLog(stepNo, stepName) {
  const code = pm.response.code;
  const body = pm.response.text();
  console.log(`[scenario_1][step ${stepNo}][${stepName}] responseCode=${code}`);
  console.log(`[scenario_1][step ${stepNo}][${stepName}] responseBody=${body.slice(0, 2000)}`);
  if (code !== 200) {
    throw new Error(`scenario_1 step ${stepNo} HTTP status not 200: ${code}, body=${body.slice(0, 500)}`);
  }
}

function debugWebhookVars(stepNo, eventType) {
  console.log(`[scenario_1][webhook step ${stepNo}] eventType=${eventType}`);
  [
    "phone",
    "merchantId",
    "preferredCurrency",
    "eventId",
    "dpuMerchantAccountId",
    "dpuLimitApplicationId",
    "dpuApplicationId",
    "lenderApprovedOfferId",
    "underwrittenOriginalRequestId",
    "approvedOriginalRequestId",
    "underwrittenAmount",
    "approvedAmount",
    "signedAmount"
  ].forEach((key) => console.log(`[scenario_1][webhook step ${stepNo}] ${key}=${getVar(key)}`));
}
```

## 1. 发送注册短信 - 前置脚本

```javascript
// paste common helper first

const prefixes = [
  "130", "131", "132", "133", "135", "136", "137", "138", "139",
  "150", "151", "152", "155", "156", "157", "158", "159",
  "166", "171", "172", "173", "175", "176", "177", "178",
  "180", "181", "182", "183", "184", "185", "186", "187", "188", "189",
  "191", "193", "195", "196", "198", "199"
];

const prefix = prefixes[Math.floor(Math.random() * prefixes.length)];
const suffix = String(Math.floor(Math.random() * 100000000)).padStart(8, "0");
const phoneNumber = prefix + suffix;

setVar("phoneNumber", phoneNumber);
setVar("phone", phoneNumber);

console.log(`===== 生成固定手机号: ${phoneNumber} =====`);
```

## 2. 发送注册短信 - 后置脚本

```javascript
// paste common helper first

if (pm.response.code >= 200 && pm.response.code < 300) {
  const phone = getVar("phone") || getVar("phoneNumber");
  if (!phone) throw new Error("未找到手机号变量，已尝试 phone 和 phoneNumber");
  setVar("phone", phone);
  console.log(`接口成功，保存手机号 phone=${phone}`);
} else {
  console.warn(`接口失败，不保存手机号，响应: ${pm.response.text()}`);
}

assertHttp200AndLog(1, "发送注册短信");
```

## 3. 验证码调用验证生成一次 token - 前置操作

先加数据库操作，结果提取到 `smsPlaceholders`：

```sql
SELECT placeholders
FROM dpu_seller_center.dpu_sms_record
WHERE phone_number = '{{phone}}'
ORDER BY COALESCE(send_time, create_time) DESC, id DESC
LIMIT 1;
```

再加自定义脚本：

```javascript
// paste common helper first

const placeholders = getVar("smsPlaceholders");
const match = String(placeholders || "").match(/(?<!\d)(\d{6})(?!\d)/);
const verificationCode = match ? match[1] : "";

setVar("verificationCode", verificationCode);

console.log(`smsPlaceholders=${placeholders}`);
console.log(`提取到验证码 verificationCode=${verificationCode}`);
```

## 4. 验证码调用验证生成一次 token - 后置脚本

```javascript
// paste common helper first
assertHttp200AndLog(2, "验证码调用验证生成一次token");
```

## 5. 用户注册 - 后置脚本

MeterSphere 原来用 JSONPath 提取 `$.data.token`，Apifox 可用后置“提取变量”，也可以直接用 JS：

```javascript
// paste common helper first

let token = "";
try {
  token = pm.response.json()?.data?.token || "";
} catch (e) {
  token = "";
}

setVar("token", token);
console.log(`token=${token}`);

assertHttp200AndLog(3, "用户注册");
```

## 6. 生成 state 做 SP - 前置脚本

MeterSphere 原来用 `SELECT UUID() AS state;`。Apifox 可直接用 JS 生成：

```javascript
// paste common helper first

const state = uuidv4();
setVar("state", state);
console.log(`state=${state}`);
```

后置脚本：

```javascript
// paste common helper first
assertHttp200AndLog(6, "生成state做sp");
```

## 7. 进行 SP 授权 - 前置脚本

MeterSphere 原来用 SQL 生成 `selling_partner_id`，Apifox 可直接用 JS 生成 32 位大写 hex：

```javascript
// paste common helper first

const sellingPartnerId = randomHex(32);
setVar("selling_partner_id", sellingPartnerId);
console.log(`selling_partner_id=${sellingPartnerId}`);
```

后置脚本：

```javascript
// paste common helper first
assertHttp200AndLog(7, "进行SP授权");
```

## 8. sp-updateOffer 成功 - 前置操作

数据库操作，提取 `idempotency_key`、`platform_offer_id`：

```sql
select idempotency_key, platform_offer_id
from dpu_manual_offer
where platform_seller_id = '{{selling_partner_id}}'
order by created_at desc
limit 1;
```

后置脚本：

```javascript
// paste common helper first
assertHttp200AndLog(8, "sp-updateOffer(成功)");
```

## 9. 亚马逊 3PL 授权 - 前置操作

先加数据库操作，提取到 `platformOfferId`：

```sql
select platform_offer_id
from dpu_manual_offer
where platform_seller_id = '{{selling_partner_id}}'
order by created_at desc
limit 1;
```

再加自定义脚本清洗变量：

```javascript
// paste common helper first

const platformOfferIdRaw = getVar("platformOfferId");
const platformOfferId = extractValue(platformOfferIdRaw);

setVar("platformOfferId", platformOfferId);

console.log(`platformOfferId(raw)=${platformOfferIdRaw}`);
console.log(`platformOfferId(clean)=${platformOfferId}`);
```

后置脚本：

```javascript
// paste common helper first
assertHttp200AndLog(9, "亚马逊3PL授权");
```

## 10. 3PL AUTH 授权 - 前置操作

数据库操作，提取 `platform_offer_id`：

```sql
select platform_offer_id
from dpu_manual_offer
where platform_seller_id = '{{selling_partner_id}}'
order by created_at desc
limit 1;
```

后置脚本：

```javascript
// paste common helper first
assertHttp200AndLog(10, "3PL AUTH授权");
```

## 11. 创建申请单 / 邓白氏 / offer / FP 任务 - 通用后置脚本

这些步骤在 `scenario_1.ms` 里主要是重复打印响应并断言 HTTP 200：

```javascript
// paste common helper first
assertHttp200AndLog(STEP_NO, "STEP_NAME");
```

按下面替换：

| 步骤 | STEP_NO | STEP_NAME |
|---|---:|---|
| 创建申请单 | 11 | 创建申请单 |
| 邓白氏提交企业信息 | 12 | 邓白氏提交企业信息 |
| file-scan-result-front | 14 | file-scan-result-front |
| file-scan-result-back | 15 | file-scan-result-back |
| 邓白氏提交股东信息 | 13 | 邓白氏提交股东信息 |
| 选择offer额度-500k | 14 | 选择offer额度 |
| 激活offer额度报价 | 16 | 激活offer额度报价 |
| 关联SP和3PL店铺 | 17 | 关联SP和3PL店铺 |
| 手动触发FP sanction任务 | 18 | 手动触发FP sanction任务 |
| 手动触发FP首次信用模型任务 | 19 | 手动触发FP首次信用模型任务 |
| 手动触发FP首次申请启动任务 | 20 | 手动触发FP首次申请启动任务 |

## 12. file-scan-result-front - 前置脚本

```javascript
// paste common helper first

setVar("director1_id", uuidv4());
setVar("director1_front_doc_name", "20251123-190026.jpg");
setVar("director1_back_doc_name", "20251123-190026.jpg");
setVar("director1_front_file_url", "uploads/default/default/default/file_20260402062831_fc58bdd81df3.jpg");
setVar("director1_back_file_url", "uploads/default/default/default/file_20260402063050_c40c747f1286.jpg");

console.log(`director1_id=${getVar("director1_id")}`);
console.log(`director1_front_file_url=${getVar("director1_front_file_url")}`);
console.log(`director1_back_file_url=${getVar("director1_back_file_url")}`);
```

## 13. 邓白氏提交股东信息 - 后置 SQL + JS

先保留响应断言：

```javascript
// paste common helper first
assertHttp200AndLog(13, "邓白氏提交股东信息");
```

再加数据库操作，修复 `VIRUS_SCAN` 依赖：

```sql
UPDATE dpu_seller_center.dpu_notify_event_dependency d
JOIN dpu_seller_center.dpu_notify_event e
  ON e.id = d.event_id
 AND e.event_type = d.event_type
 AND e.biz_id = d.biz_id
SET d.dependency_status = 'READY',
    d.dependency_finish_time = NOW(),
    d.update_time = NOW()
WHERE e.biz_id = (SELECT app_id FROM (
  SELECT a.application_unique_id AS app_id
  FROM dpu_seller_center.dpu_application a
  JOIN dpu_seller_center.dpu_users u ON u.merchant_id = a.merchant_id
  WHERE u.phone_number = '{{phone}}'
  ORDER BY a.created_at DESC
  LIMIT 1
) latest_app)
  AND d.dependency_type = 'VIRUS_SCAN'
  AND d.dependency_status <> 'READY';
```

再加数据库操作，提取 `virusScanPendingCount`：

```sql
SELECT COUNT(*) AS pending_count
FROM dpu_seller_center.dpu_notify_event_dependency d
JOIN dpu_seller_center.dpu_notify_event e
  ON e.id = d.event_id
 AND e.event_type = d.event_type
 AND e.biz_id = d.biz_id
WHERE e.biz_id = (SELECT app_id FROM (
  SELECT a.application_unique_id AS app_id
  FROM dpu_seller_center.dpu_application a
  JOIN dpu_seller_center.dpu_users u ON u.merchant_id = a.merchant_id
  WHERE u.phone_number = '{{phone}}'
  ORDER BY a.created_at DESC
  LIMIT 1
) latest_app)
  AND d.dependency_type = 'VIRUS_SCAN'
  AND d.dependency_status <> 'READY';
```

最后加自定义脚本：

```javascript
// paste common helper first

const raw = getVar("virusScanPendingCount");
const match = String(raw || "").match(/(-?\d+)/);
const pending = match ? parseInt(match[1], 10) : 0;

console.log(`[scenario_1][virus-scan] pending_count=${pending}, raw=${raw}`);
if (pending !== 0) {
  throw new Error(`VIRUS_SCAN dependency is still pending after SQL repair: ${raw}`);
}
```

## 14. SUBMITTED 轮询接口 - 后置脚本

```javascript
// paste common helper first

const body = pm.response.text();
const match = body.match(/"status"\s*:\s*"([^"]*)"/);
const status = match ? match[1].trim() : "";

setVar("credit_offer_status", status);

const pollCount = getVar("poll_count", "0") || "0";
console.log(`[scenario_1][poll] status=${status}, poll_count=${pollCount}, body=${body}`);

if (!status) {
  throw new Error(`credit_offer_status missing from response body: ${body}`);
}

assertHttp200AndLog("22.1", "SUBMITTED轮询");
```

如果 Apifox 场景里需要替代 MeterSphere 的 while Groovy 条件，可以用这个脚本把是否继续轮询写入变量：

```javascript
// paste common helper first

const c = parseInt(getVar("poll_count", "0") || "0", 10);
const status = getVar("credit_offer_status");
const keep = status !== "SUBMITTED" && c < 30;

if (keep) {
  setVar("poll_count", String(c + 1));
}

setVar("continue_poll_offer_status", keep ? "true" : "false");
console.log(`[scenario_1][poll-condition] keep=${keep}, status=${status}, poll_count=${c}`);
```

## 15. approved-offer - 前置 SQL

按顺序添加数据库操作：

```sql
SELECT merchant_id
FROM dpu_seller_center.dpu_users
WHERE phone_number = '{{phone}}'
ORDER BY created_at DESC
LIMIT 1;
```

提取到 `merchantId`。

```sql
SELECT COALESCE(prefer_finance_product_currency, 'USD')
FROM dpu_seller_center.dpu_users
WHERE phone_number = '{{phone}}'
ORDER BY created_at DESC
LIMIT 1;
```

提取到 `preferredCurrency`。

```sql
SELECT limit_application_unique_id
FROM dpu_seller_center.dpu_limit_application
WHERE merchant_id = '{{merchantId}}'
ORDER BY created_at DESC
LIMIT 1;
```

提取到 `dpuLimitApplicationId`。

```sql
SELECT authorization_id
FROM dpu_seller_center.dpu_auth_token
WHERE merchant_id = '{{merchantId}}'
  AND authorization_party = 'SP'
  AND status = 'ACTIVE'
  AND authorization_id IS NOT NULL
ORDER BY created_at DESC
LIMIT 1;
```

提取到 `dpuMerchantAccountId`。

```sql
SELECT application_unique_id
FROM dpu_seller_center.dpu_application
WHERE merchant_id = '{{merchantId}}'
ORDER BY created_at DESC
LIMIT 1;
```

提取到 `dpuApplicationId`。

## 16. approved-offer - 前置脚本

```javascript
// paste common helper first

console.log("scenario_1: preparing merchant/limit/account context before approved-offer; manual underwritten webhook is disabled because reg auto-generates it.");
console.log(`underwritten phone=${getVar("phone")}`);

const merchantId = extractValue(getVar("merchantId"));
const preferredCurrency = extractValue(getVar("preferredCurrency")) || "USD";
const dpuMerchantAccountId = extractValue(getVar("dpuMerchantAccountId"));
const dpuLimitApplicationId = extractValue(getVar("dpuLimitApplicationId"));
const dpuApplicationId = extractValue(getVar("dpuApplicationId"));

setVar("merchantId", merchantId);
setVar("preferredCurrency", preferredCurrency);
setVar("dpuMerchantAccountId", dpuMerchantAccountId);
setVar("dpuLimitApplicationId", dpuLimitApplicationId);
setVar("dpuApplicationId", dpuApplicationId);

console.log(`merchantId(clean)=${merchantId}`);
console.log(`preferredCurrency(clean)=${preferredCurrency}`);
console.log(`dpuMerchantAccountId(clean)=${dpuMerchantAccountId}`);
console.log(`dpuLimitApplicationId(clean)=${dpuLimitApplicationId}`);
console.log(`dpuApplicationId(clean)=${dpuApplicationId}`);

if (!dpuApplicationId) throw new Error("缺少 dpuApplicationId");

// disabled underwritten step 的上下文默认值，保留给后续 body/日志复用。
let eventId = uuidv4();
setVar("eventId", eventId);
setVar("underwrittenOriginalRequestId", `req_${eventId.replace(/-/g, "")}`);
setVar("datetime_utc", utcTime());
setVar("lastUpdatedOn", localDateTime());
setVar("chargeBases", preferredCurrency === "CNY" ? "Fixed" : "Float");

const suffix = dpuLimitApplicationId || eventId.replace(/-/g, "");
setVar("lenderCreditId", `lcredit_${suffix}`);
setVar("lenderLoanId", `lloan_${suffix}`);
setVar("lenderRepaymentScheduled", `lrs_${suffix}`);
setVar("lenderRepaymentId", `lrepay_${suffix}`);

if (!getVar("underwrittenAmount")) setVar("underwrittenAmount", "500000");
debugWebhookVars(24, "underwrittenLimit.completed");

// approved-offer 本接口自己的上下文。
let approvedAmount = getVar("approvedAmount") || "500000";
eventId = uuidv4();

setVar("approvedAmount", approvedAmount);
setVar("eventId", eventId);
setVar("approvedOriginalRequestId", `req_${eventId.replace(/-/g, "")}`);
setVar("datetime_utc", utcTime());
setVar("offerStartDate", dateOnly(0));
setVar("offerEndDate", dateOnly(90));
setVar("chargeBases", preferredCurrency === "CNY" ? "Fixed" : "Float");
setVar("lenderApprovedOfferId", `lender-${dpuApplicationId}`);

console.log(`merchantId=${getVar("merchantId")}`);
console.log(`preferredCurrency=${preferredCurrency}`);
console.log(`dpuApplicationId=${dpuApplicationId}`);
console.log(`approvedAmount=${approvedAmount}`);
console.log(`lenderApprovedOfferId=${getVar("lenderApprovedOfferId")}`);

debugWebhookVars(25, "approvedoffer.completed");
```

approved-offer 后置脚本：

```javascript
// paste common helper first
assertHttp200AndLog(25, "approved-offer");
```

## 17. psp-start / psp-completed - 前置 SQL

两个 PSP webhook 步骤都先查询并提取 `lenderApprovedOfferId`：

```sql
SELECT lender_approved_offer_id
FROM dpu_seller_center.dpu_credit_offer
WHERE merchant_id = '{{merchantId}}'
ORDER BY created_at DESC
LIMIT 1;
```

## 18. psp-start - 前置脚本

```javascript
// paste common helper first

const lenderApprovedOfferId = extractValue(getVar("lenderApprovedOfferId"));
const merchantAccountId = String(getVar("dpuMerchantAccountId") || "");

if (!lenderApprovedOfferId) {
  throw new Error("Missing lenderApprovedOfferId before PSP webhook; check approved-offer SQL/result first");
}
if (!merchantAccountId) {
  throw new Error("Missing dpuMerchantAccountId before PSP webhook; check SP auth SQL/result first");
}

setVar("lenderApprovedOfferId", lenderApprovedOfferId);
setVar("eventId", uuidv4());
setVar("datetime_utc", utcTime());
setVar("lastUpdatedOn", localDateTime());

console.log(`merchantId=${getVar("merchantId")}`);
console.log(`dpuMerchantAccountId=${merchantAccountId}`);
console.log(`lenderApprovedOfferId=${lenderApprovedOfferId}`);

debugWebhookVars(26, "psp.verification.started");
```

后置脚本：

```javascript
// paste common helper first
assertHttp200AndLog(26, "psp-start");
```

## 19. psp-completed - 前置脚本

```javascript
// paste common helper first

const lenderApprovedOfferId = extractValue(getVar("lenderApprovedOfferId"));
const merchantAccountId = String(getVar("dpuMerchantAccountId") || "");

if (!lenderApprovedOfferId) {
  throw new Error("Missing lenderApprovedOfferId before PSP webhook; check approved-offer SQL/result first");
}
if (!merchantAccountId) {
  throw new Error("Missing dpuMerchantAccountId before PSP webhook; check SP auth SQL/result first");
}

setVar("lenderApprovedOfferId", lenderApprovedOfferId);
setVar("eventId", uuidv4());
setVar("datetime_utc", utcTime());
setVar("lastUpdatedOn", localDateTime());

console.log(`merchantId=${getVar("merchantId")}`);
console.log(`dpuMerchantAccountId=${merchantAccountId}`);
console.log(`lenderApprovedOfferId=${lenderApprovedOfferId}`);

debugWebhookVars(27, "psp.verification.completed");
```

后置脚本：

```javascript
// paste common helper first
assertHttp200AndLog(27, "psp-completed");
```

## 20. esign - 前置 SQL

```sql
SELECT lender_approved_offer_id
FROM dpu_seller_center.dpu_credit_offer
WHERE merchant_id = '{{merchantId}}'
ORDER BY created_at DESC
LIMIT 1;
```

提取到 `lenderApprovedOfferId`。

## 21. esign - 前置脚本

```javascript
// paste common helper first

const lenderApprovedOfferId = extractValue(getVar("lenderApprovedOfferId"));
const preferredCurrency = String(getVar("preferredCurrency") || "USD");

if (!lenderApprovedOfferId) {
  throw new Error("Missing lenderApprovedOfferId before eSign webhook; check approved-offer SQL/result first");
}

const signedAmount = getVar("signedAmount") || "500000";

setVar("lenderApprovedOfferId", lenderApprovedOfferId);
setVar("signedAmount", signedAmount);
setVar("eventId", uuidv4());
setVar("datetime_utc", utcTime());
setVar("lastUpdatedOn", localDateTime());

console.log(`merchantId=${getVar("merchantId")}`);
console.log(`preferredCurrency=${preferredCurrency}`);
console.log(`lenderApprovedOfferId=${lenderApprovedOfferId}`);
console.log(`signedAmount=${signedAmount}`);

debugWebhookVars(28, "esign.completed");
```

## 22. esign - 后置脚本 + DB 断言

先加响应断言：

```javascript
// paste common helper first
assertHttp200AndLog(28, "esign");
```

然后加数据库操作，提取 `finalCreditOfferRow`：

```sql
SELECT lender_approved_offer_id, status, approved_limit_amount, approved_limit_currency, signed_limit_amount, signed_limit_currency, e_sign_status
FROM dpu_seller_center.dpu_credit_offer
WHERE merchant_id = '{{merchantId}}'
ORDER BY created_at DESC
LIMIT 1;
```

再加数据库操作，提取 `finalWebhookEventCount`：

```sql
SELECT COUNT(*) AS event_count
FROM dpu_seller_center.dpu_lender_event
WHERE merchant_id = '{{merchantId}}'
  AND event_type IN ('underwrittenLimit.completed', 'approvedoffer.completed', 'psp.verification.started', 'psp.verification.completed', 'esign.completed');
```

最后加 JS 断言：

```javascript
// paste common helper first

function firstInt(value) {
  const match = String(value || "").match(/(-?\d+)/);
  return match ? parseInt(match[1], 10) : 0;
}

const row = String(getVar("finalCreditOfferRow") || "").trim();
const eventCountRaw = String(getVar("finalWebhookEventCount") || "").trim();
const lenderApprovedOfferId = String(getVar("lenderApprovedOfferId") || "").trim();
const expectedAmount = String(getVar("signedAmount") || getVar("approvedAmount") || "500000").trim();

if (!row || row === "None" || row === "[]") {
  throw new Error(`Final dpu_credit_offer SQL returned empty result for merchantId=${getVar("merchantId")}`);
}
if (!lenderApprovedOfferId) {
  throw new Error("lenderApprovedOfferId is empty before final DB assertion");
}
if (!row.includes(lenderApprovedOfferId)) {
  throw new Error(`Final dpu_credit_offer row does not contain lenderApprovedOfferId=${lenderApprovedOfferId}; row=${row}`);
}
if (expectedAmount && !row.includes(expectedAmount)) {
  throw new Error(`Final dpu_credit_offer row does not contain expected amount=${expectedAmount}; row=${row}`);
}
if (!row.includes("SUCCESS")) {
  throw new Error(`Final dpu_credit_offer row does not show e_sign_status SUCCESS; row=${row}`);
}

const eventCount = firstInt(eventCountRaw);
if (eventCount < 4) {
  throw new Error(`Expected at least 4 lender events after eSign, got ${eventCount}; raw=${eventCountRaw}`);
}

setVar("finalCreditOfferRow", row);
setVar("finalWebhookEventCount", String(eventCount));
console.log(`[scenario_1][final-db] finalCreditOfferRow=${row}`);
console.log(`[scenario_1][final-db] finalWebhookEventCount=${eventCount}`);
```

## 23. disabled underwritten 步骤

`scenario_1.ms` 里 `underwritten` 是禁用步骤。它的上下文准备逻辑已经合并进 `approved-offer` 前置脚本；如果你在 Apifox 里单独启用 underwritten，可以复用 `approved-offer` 前置脚本里“disabled underwritten step 的上下文默认值”那一段，并把后置脚本设为：

```javascript
// paste common helper first
assertHttp200AndLog(24, "underwritten");
```

