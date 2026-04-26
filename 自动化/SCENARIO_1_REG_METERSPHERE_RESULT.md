# scenario_1 reg 实跑结果与 MeterSphere 对照结论

## 结论

- 场景：`线下FP-USD-500k`
- MeterSphere 文件：`D:/data/project/dpu/自动化/scenario_1.ms`
- 验证脚本：`D:/data/project/dpu/自动化/validate_scenario_1_direct_flow.py`
- 结果文件：`D:/data/project/dpu/自动化/scenario_1_validation_result.json`
- 验证时间：`2026-04-25 20:08:31`
- 环境：`reg`
- Base URL：`https://dpu-gateway-reg.dowsure.com`
- 结果：`PASS`

本次 reg 实跑链路已通过：注册、SP/3PL、申请资料、任务推进、`SUBMITTED` 轮询、`approved-offer`、`psp-start`、`psp-completed`、`esign` 均完成。最终 DB 结果为 `dpu_credit_offer.status=ACCEPTED`，`e_sign_status=SUCCESS`。

## 本次测试数据

| 字段 | 值 |
| --- | --- |
| phone | `19106226872` |
| merchant_id | `47b2ed220c8f40b0900800cf94b26496` |
| platform_offer_id | `amzn1.lending.offer.us.t8hCHX289RpDAvmi61afWYSTESTOFFER` |
| dpu_limit_application_id | `EFAL17771188309534238` |
| dpu_application_id | `EFA17771188197256616` |
| lender_approved_offer_id | `lender-EFA17771188197256616` |
| currency | `USD` |
| amount | `500000` |

## MeterSphere 步骤对照

| 阶段 | 本次结果 | 对照点 |
| --- | --- | --- |
| 注册短信 | 已完成 | step 4 获取验证码，验证码写入结果文件 |
| 校验短信 | 已完成 | step 5 HTTP 业务成功 |
| Signup | 已完成 | step 6 生成 token，结果文件保留 token 前缀 |
| SP 授权 URL | 已完成 | step 7 生成 state |
| SP 授权 | 已完成 | step 8 生成 selling_partner_id |
| updateOffer | 已完成 | step 9 拿到 platform_offer_id |
| 3PL redirect | 已完成 | step 10 GET、step 11 POST 均通过 |
| 申请资料提交 | 已完成 | step 12-22 均通过 |
| 文件扫描依赖 | 已处理 | step 14/15 查询为 PENDING；step 16 后将本次 application 的 2 条扫描依赖置为可继续推进 |
| credit offer 轮询 | 已完成 | 第 17 次轮询达到 `SUBMITTED` |
| underwritten | 手工 webhook 禁用 | 当前 reg 链路通过任务推进进入后续申请状态，未手工发送 `underwrittenLimit.completed` |
| approved-offer | 已完成 | step 27 返回 HTTP 200，响应 `{"data":{}}` |
| psp-start | 已完成 | step 28 返回 HTTP 200，响应 `{"data":{}}` |
| psp-completed | 已完成 | step 29 返回 HTTP 200，响应 `{"data":{}}` |
| esign | 已完成 | step 30 返回 HTTP 200，响应 `{"data":{}}` |

## Webhook 断言结果

| Step | eventType | eventId | 核心断言 |
| --- | --- | --- | --- |
| 27 | `approvedoffer.completed` | `63644585-ec34-4550-bb63-586d62d387f7` | eventType、eventId、merchantId、dpuApplicationId、lenderApprovedOfferId、originalRequestId、amount、currency 均通过 |
| 28 | `psp.verification.started` | `4fdf5555-0294-4667-a6a1-8133ef78dd22` | eventType、eventId、merchantId、merchantAccountId、lenderApprovedOfferId、result=`PROCESSING` 均通过 |
| 29 | `psp.verification.completed` | `6f9d3589-f86a-4b2d-ae9a-6da55267d99a` | eventType、eventId、merchantId、merchantAccountId、lenderApprovedOfferId、result=`SUCCESS` 均通过 |
| 30 | `esign.completed` | `b069f136-ba27-45f1-9909-f2cefc169998` | eventType、eventId、merchantId、lenderApprovedOfferId、signedLimit.amount、signedLimit.currency、result=`SUCCESS` 均通过 |

所有已发送 webhook 的 `unresolved_values` 均为空，说明请求体内没有未替换的 MeterSphere 变量。

## 最终 DB 断言

`scenario_1_validation_result.json` 中最终 `dpu_credit_offer` 行：

| lender_approved_offer_id | status | approved_limit_amount | e_sign_status |
| --- | --- | --- | --- |
| `lender-EFA17771188197256616` | `ACCEPTED` | `500000.0` | `SUCCESS` |

本次 merchant 下已记录的 lender event 计数为 `4`，对应本次实际手工发送并成功落库的后半段事件：`approvedoffer.completed`、`psp.verification.started`、`psp.verification.completed`、`esign.completed`。

## 结果文件说明

- `scenario_1_validation_result.json` 是最终 PASS 证据，已经修正为可被 `ConvertFrom-Json` 直接解析。
- `validate_scenario_1_direct_flow.py` 需要本机环境变量 `DPU_REG_DB_PASSWORD` 才能重新执行数据库校验，避免把数据库密码提交到 Git。
- `output/scenario_1_latest_run.txt` 仍指向 19:15 那次失败日志，不能作为最终通过依据。
- 最终通过依据应以 `自动化/scenario_1_validation_result.json` 和当前 `自动化/scenario_1.ms` 为准。

## 改动摘要

- `scenario_1.ms`：补齐 FP-USD 500k 链路需要的动态变量、SQL 前置提取、webhook 请求体、HTTP 200/`data={}` 断言，以及 approved-offer/PSP/eSign 后半段链路。
- `scenario_1.ms`：`file-scan-result-front/back` 为场景内自定义 HTTP 步骤，需保持 `CUSTOM_REQUEST` + `DIRECT` + `resourceId=null`，不能以 `COPY` + 空 `resourceId` 运行，否则 MeterSphere `/api/scenario/run` 会在运行前校验阶段报 400。
- `validate_scenario_1_direct_flow.py`：提供可重复的直连验证脚本，覆盖注册、SP/3PL、任务推进、SUBMITTED 轮询、webhook 请求体断言、最终 DB 断言，并将结果写入 JSON。
- `scenario_1_validation_result.json`：保存本次 PASS 的完整证据，包括步骤记录、webhook 请求体、响应、最终 DB 行。
