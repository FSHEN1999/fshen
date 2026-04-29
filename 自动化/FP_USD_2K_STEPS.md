# FP-USD 2k 生成与验证步骤

## 本次修改

1. 去掉了固定验证码方案
2. 恢复为数据库查询验证码
3. 在场景文件里补上完整的 `approved / esign / disbursement` webhook
4. 把轮询逻辑改回更符合脚本的两段式：
   - `credit-offer/status`
   - `drawdown/status`
5. 增加 `FUNDPARK + currency=USD` 的资方切换步骤

## 我做了什么

1. 重新梳理了 `线下自动化.py` 里 `2k` 分支的真实顺序。
2. 更新了 `generate_fp_usd_2k_ms.py`，重新生成 `scenario_2_fp_usd_2k.ms`。
3. 确认第 2 步使用 SQL 从 `dpu_sms_record` 提取验证码。
4. 确认场景里已经存在以下关键步骤：
   - `approved-offer`
   - `esign`
   - `disbursement-completed`
   - `轮询credit offer状态`
   - `轮询drawdown状态`
5. 新写了验证脚本，分成两部分：
   - 场景结构验证
   - UAT 实跑验证

## 本次验证范围

### 结构验证

结构验证确认了以下内容都已经在生成后的 `.ms` 文件中落地：

- 验证码步骤使用 SQL 查询 `dpu_sms_record`
- 注册步骤使用 `${verificationCode}`
- `approved-offer` 默认额度是 `2000`
- `esign` 默认额度是 `2000`
- `disbursement-completed` 已经存在
- `disbursement-completed` 前置 SQL 会查询 `loan_id`
- 场景中同时存在 `credit-offer` 和 `drawdown` 两段轮询

### UAT 实跑验证

UAT 实跑验证确认了以下内容：

- 验证码确实来自 UAT 数据库查询
- 注册链路可跑通
- `FUNDPARK + currency=USD` 资方切换可跑通
- SP / 3PL / 建单 / 企业信息 / 董事信息 / 2k 额度选择 / 激活 / 店铺关联 / 三个任务触发都可跑通
- 业务态断言成立：
  - `application-status.status = SUBMITTED`
  - `applicationFlow = drawdownDetails`
  - 至少一个店铺 `threePlShopStatus = ACTIVE`
  - `marketing-quota.preApprovedLimit = 2000`
  - `product-tier = L1 / 2K-200K`
  - `drawdown.status = INIT`

## 本次 UAT 观察

在当前这条纯接口 UAT 路径里，前置链路已经能稳定跑通，但 UAT 库里没有自动生成：

- `dpu_limit_application`
- `dpu_credit_offer`
- `dpu_drawdown`

这意味着本机当前无法把 `approved / esign / disbursement` 在 UAT 上继续实跑到成功返回。  
不过这三个 webhook 步骤已经按脚本真实逻辑补进场景文件，并且关键 SQL 变量链也已经做了结构校验。

## 最终文件

- `D:\data\project\dpu\自动化\scenario_2_fp_usd_2k.ms`
- `D:\data\project\dpu\自动化\generate_fp_usd_2k_ms.py`
- `D:\data\project\dpu\自动化\validate_fp_usd_2k_direct_flow.py`
- `D:\data\project\dpu\自动化\fp_usd_2k_validation_result.json`
- `D:\data\project\dpu\自动化\FP_USD_2K_MS_SCENARIO.md`
- `D:\data\project\dpu\自动化\FP_USD_2K_STEPS.md`
