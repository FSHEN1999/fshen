# 多店铺PSP绑定脚本 SOP

## 一、脚本概述

**脚本名称：** `migration_test_FP_json 多店铺绑定psp.py`

**功能说明：** 为HSBC DPU系统多店铺场景批量绑定PSP（Payment Service Provider）记录，并自动拆分分配额度。

**执行环境：** sit / uat / preprod / dev

---

## 二、执行前准备

### 2.1 环境配置

确认脚本中的环境配置正确（第19行）：

```python
ENV = "sit"  # 可选：sit, uat, preprod, dev
```

### 2.2 数据文件准备

**支持格式：** `.json` 或 `.csv`

**JSON格式示例：**
```json
{
  "application": {
    "mobile_phone": "13828806069"
  },
  "amzs": [
    {
      "amazon_seller_id": "A1N2J4H6809SGL",
      "psp_id": "acct_-ENCXBf7OBOSoHrQ8ZqxNg",
      "psp_name": "Airwallex"
    }
  ],
  "limit": {
    "underwritten_amount": "34595.99",
    "approved_limit": "35000.00",
    "signed_limit": "34595.99",
    "activate_limit": "51324.09"
  }
}
```

**CSV格式示例：**
```csv
phone_number,amazon_seller_id,psp_id,psp_name
13828806069,A1N2J4H6809SGL,acct_-ENCXBf7OBOSoHrQ8ZqxNg,Airwallex
```

---

## 三、执行步骤

### Step 1: 查询用户信息

- **操作：** 根据手机号查询 `dpu_users` 表
- **获取：** `merchant_id`
- **失败处理：** 未找到用户则跳过该条数据

---

### Step 2: 查询AMZ Token

- **操作：** 根据店铺的 `amazon_seller_id` 查询 `dpu_auth_token` 表
- **获取：** `merchant_account_id`
- **失败处理：** 未找到AMZ Token则跳过该店铺

---

### Step 3: 插入PSP记录

- **操作：** 向 `dpu_auth_token` 表插入PSP授权记录
- **前置检查：** 查询 `merchant_account_id` + `authorization_id(psp_id)` 是否已存在
  - 已存在 → 跳过插入
  - 不存在 → 执行插入
- **插入字段：**
  - `authorization_id` = psp_id
  - `authorization_party` = 'PSP'
  - `status` = 'ACTIVE'
  - `merchant_account_id` / `merchant_id`

---

### Step 4: 更新psp_status + 额度拆分

**重要：** 此步骤在所有店铺处理完成后统一执行一次

#### 4.1 查询记录

- 查询该 `merchant_id` 下所有 `dpu_merchant_account_limit` 记录
- 获取记录总数 `total_records`

#### 4.2 获取总额度

从JSON的 `limit` 对象读取：
- `underwritten_amount`
- `approved_limit`
- `signed_limit`
- `activate_limit`

**计算 available_limit：**
```python
available_limit = min(approved_limit, activate_limit)
```

#### 4.3 平均分配额度

```
每条记录的新额度 = 总额度 ÷ total_records
```

**示例：**
```
approved_limit: 35000.00, 2条记录 → 每条 17500.00
signed_limit: 34595.99, 2条记录 → 每条 17297.99
```

#### 4.4 更新记录

对所有 `merchant_account_limit` 记录执行UPDATE：
- 更新 `psp_status` = 'SUCCESS'
- 更新各额度字段为拆分后的值
- 无论原 `psp_status` 是否为SUCCESS，都会更新limit

---

### Step 5: 插入dpu_limit_application表

**当前状态：** 已注释，不执行

---

### Step 6: 插入dpu_limit_application_account表

- **操作：** 为每个店铺插入 `dpu_limit_application_account` 记录
- **前置检查：** 检查 `merchant_account_id` 是否已存在记录
  - 已存在 → 跳过插入
  - 不存在 → 执行插入
- **数据来源：**
  - `limit_application_id` / `limit_application_unique_id` 从 `dpu_limit_application` 表查询获取
  - `underwritten_limit` 从查询结果获取，如为空则从JSON获取
  - 其他limit值从JSON的 `limit` 对象获取

---

## 四、执行命令

### 基本命令

```bash
python "migration_test_FP_json 多店铺绑定psp.py" <数据文件路径>
```

### 示例

```bash
# 使用JSON文件
python "migration_test_FP_json 多店铺绑定psp.py" migration_data多店铺.json

# 使用CSV文件
python "migration_test_FP_json 多店铺绑定psp.py" data.csv

# 不指定文件（使用默认文件）
python "migration_test_FP_json 多店铺绑定psp.py"
# 默认使用：migration_data多店铺.json
```

---

## 五、注意事项

### 5.1 数据安全

1. **备份建议：** 执行前备份相关表数据
2. **测试环境：** 建议先在sit环境验证

### 5.2 重复执行

- **PSP记录：** 已存在会自动跳过，可安全重复执行
- **psp_status：** 已为SUCCESS的记录也会更新limit
- **limit_application_account：** 已存在会跳过

### 5.3 额度拆分逻辑

- 拆分基于 `merchant_account_limit` 表的记录总数
- 原额度从JSON文件读取，不是从数据库现有值累加
- `available_limit` = `min(approved_limit, activate_limit)`

### 5.4 异常处理

- 任何步骤失败会终止当前行数据的处理
- 错误信息会记录到日志
- 已执行的操作不会回滚

---

## 六、日志检查

### 正常执行日志示例

```
[INFO] 当前环境: sit
[INFO] ==================== 正在处理第 1 条数据 ====================

--- Step 4: 统一更新psp_status并执行额度拆分 ---
[INFO] Step 4: 检测到 2 条merchant_account_limit记录，额度将除以 2
[INFO] Step 4: 从JSON获取总额度并平均分配:
[INFO]   underwritten_amount: 34595.99 → 每条 17297.99
[INFO]   approved_limit: 35000.00 → 每条 17500.00
[INFO]   available_limit: 35000.00 → 每条 17500.00
[INFO] Step 4: 额度拆分完成，共更新 2 条记录

[INFO] ==================== 第 1 条数据处理完成 ====================
```

### 异常日志示例

```
[ERROR] SQL执行异常: (1054, "Unknown column 'None' in 'field list'")
[ERROR] Step 4: 更新Merchant Account Limit（psp_status + 额度拆分） 失败，终止当前行处理
```

---

## 七、常见问题

| 问题 | 原因 | 解决方案 |
|-----|------|---------|
| 未找到用户 | 手机号不存在于dpu_users表 | 检查手机号是否正确 |
| 未找到AMZ Token | amazon_seller_id未绑定 | 先完成店铺授权 |
| SQL执行异常 | 额度字段为None | 检查JSON数据完整性 |
| 额度拆分错误 | JSON缺少limit字段 | 检查JSON格式 |

---

## 八、数据库表关系

```
dpu_users (用户表)
    ↓ merchant_id
dpu_auth_token (授权记录表) - 存储AMZ和PSP授权
    ↓ merchant_account_id
dpu_merchant_account_limit (额度表) - 存储各店铺额度
    ↓ merchant_id
dpu_limit_application (额度申请表)
dpu_limit_application_account (店铺额度申请关联表)
```

---

## 九、更新记录

| 日期 | 版本 | 更改内容 |
|-----|------|---------|
| 2025-03-05 | v1.0 | 初始版本 |
