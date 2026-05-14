# MeterSphere 接入设计文档

## 1. 一句话结论

推荐方案不是让 MeterSphere 直接驱动 `mock_sit.py` 的 CLI，也不是让它直接接管 `线上自动化.py`。

最佳接入方式是：

- 以 `mockapi/web/app.py` 提供的 FastAPI 作为 MeterSphere 的统一接入层
- 以 `mockapi/mock_sit.py` 作为统一底层业务执行器
- 以 `线上自动化.py` 仅作为少量 UI 冒烟补充，不作为主回归入口

## 2. 背景与目标

当前仓库已经具备三类能力：

- Web API 接入层：`mockapi/web/app.py`
- DPU 状态模拟能力：`mockapi/mock_sit.py`
- UI 自动化能力：`线上自动化.py`

MeterSphere 最擅长的是：

- 编排 HTTP 接口场景
- 维护环境变量和测试数据
- 做前后置步骤、断言、参数传递、报告汇总

因此本次接入目标不是“把所有脚本塞进 MeterSphere”，而是建立一套更稳定的分层：

1. MeterSphere 负责场景编排、变量管理、断言和报告。
2. FastAPI 负责将 HTTP 请求转换为仓库现有 mock 能力调用。
3. mock 服务负责真正执行 DPU 状态流转。
4. UI 自动化只承担页面级补充验证。

## 3. 为什么选 `mockapi/web/app.py`

`mockapi/web/app.py` 已具备 MeterSphere 所需的核心特征：

- 基于 FastAPI，天然适合被 MeterSphere 作为 HTTP 接口调用
- 已拆分出系统、注册、mock 操作等路由，边界清晰
- 通过 `session_id` 维持上下文，适合一条业务链路串联多个步骤
- `web/services/mock_adapter.py` 已把 CLI 型 `DPUMockService` 适配成结构化返回结果
- 返回体统一为 `success`、`message`、`data`，方便 MeterSphere 写统一断言

反过来看，另外两个入口都不适合作为主接入面：

- `mock_sit.py`
  - 优点是能力完整
  - 缺点是以脚本/交互式流程为主，不适合 MeterSphere 直接调用和变量编排
- `线上自动化.py`
  - 优点是能覆盖真实 UI 流程
  - 缺点是执行慢、对环境依赖重、稳定性低于接口层，不适合作为主回归链路

## 4. 总体架构

```text
MeterSphere
  -> 调用 FastAPI 接口
  -> 管理环境变量 / 场景变量 / 断言 / 报告

FastAPI: mockapi/web/app.py
  -> system_routes: 健康检查、环境枚举、会话管理
  -> register_routes: 注册账号
  -> mock_routes: 核保/审批/PSP/签约/放款/还款/多店铺等操作

Adapter: web/services/mock_adapter.py
  -> 将 Web 请求转换为 WebDPUMockService 方法调用

Execution Layer
  -> mockapi/mock_sit.py

Supplement
  -> 线上自动化.py 只做少量 UI smoke
```

## 5. 推荐接入范围

### 5.1 MeterSphere 主入口

主入口使用以下接口：

- `GET /api/health`
- `GET /api/environments`
- `GET /api/enums`
- `POST /api/register`
- `POST /api/connect`
- `POST /api/disconnect`
- `POST /api/mock/*`

### 5.2 UI 自动化保留范围

`线上自动化.py` 仅建议保留以下用途：

- 每日或每版本 1 到 3 条 UI 冒烟
- 校验关键页面流程仍可打开和提交
- 校验少量高风险前端交互

不建议将其作为全量回归主链路，因为：

- 浏览器依赖重
- 页面元素容易波动
- 执行速度远慢于接口编排
- 报错定位成本高于接口调用

## 6. FastAPI 接口设计映射

以下内容适合直接映射为 MeterSphere 的接口定义。

### 6.1 系统类接口

#### `GET /api/health`

用途：

- 服务健康检查
- 场景执行前的网关可用性校验

基础断言：

- HTTP 状态码 = 200
- `$.status == "ok"`

#### `GET /api/environments`

用途：

- 获取支持环境列表
- 供 MeterSphere 环境校验或调试使用

基础断言：

- HTTP 状态码 = 200
- `$.success == true`

#### `GET /api/enums`

用途：

- 获取状态枚举、失败原因、币种、journey 等
- 可以作为 MeterSphere 的数据字典参考源

建议用途：

- 不一定每次场景都调用
- 更适合在联调阶段验证入参合法性

### 6.2 注册接口

#### `POST /api/register`

用途：

- 生成并注册新的测试账号
- 返回手机号、邮箱、offerId、redirectUrl 等数据

请求体：

```json
{
  "env": "uat",
  "journey": "500K",
  "currency": "USD",
  "offline": false
}
```

核心响应字段：

- `$.success`
- `$.data.phone_number`
- `$.data.email`
- `$.data.offer_id`
- `$.data.redirect_url`

MeterSphere 建议保存变量：

- `phone_number`
- `email`
- `offer_id`
- `redirect_url`
- `env`
- `currency`
- `journey`

基础断言：

- HTTP 状态码 = 200
- `$.success == true`
- `$.data.phone_number` 非空
- `$.data.redirect_url` 非空

### 6.3 会话接口

#### `POST /api/connect`

用途：

- 通过 `env + phone_number` 建立会话
- 获取后续 mock 操作需要的 `session_id`

请求体：

```json
{
  "env": "uat",
  "phone_number": "${phone_number}"
}
```

核心响应字段：

- `$.data.session_id`
- `$.data.merchant_id`
- `$.data.preferred_currency`

MeterSphere 建议保存变量：

- `session_id`
- `merchant_id`
- `preferred_currency`

基础断言：

- HTTP 状态码 = 200
- `$.success == true`
- `$.data.session_id` 非空

#### `POST /api/disconnect`

用途：

- 场景结束后回收会话

建议：

- 放在场景最后一步
- 即使中间步骤失败，也建议配置为收尾动作

## 7. Mock 接口清单

`mockapi/web/routes/mock_routes.py` 已暴露以下主要操作。

### 7.1 SP / 3PL / 多店铺

- `POST /api/mock/link-sp-3pl`
- `POST /api/mock/multi-shop-binding`
- `POST /api/mock/sp-status-update`
- `POST /api/mock/multi-shop-3pl-redirect`

### 7.2 DPU 主流程

- `POST /api/mock/underwritten`
- `POST /api/mock/approved-offer`
- `POST /api/mock/psp-start`
- `POST /api/mock/psp-completed`
- `POST /api/mock/esign`
- `POST /api/mock/drawdown`
- `POST /api/mock/repayment-start`
- `POST /api/mock/repayment`

### 7.3 系统事件 / HSBC PSP

- `POST /api/mock/system-event`
- `POST /api/mock/psp-hsbc-start`
- `POST /api/mock/psp-hsbc-completed`

## 8. MeterSphere 用例分层建议

推荐在 MeterSphere 按三层组织。

### 8.1 第一层：公共原子接口

每个 FastAPI 接口单独维护为原子接口用例：

- register
- connect
- underwritten
- approved-offer
- psp-start
- psp-completed
- esign
- drawdown
- repayment-start
- repayment
- disconnect

这层的价值是：

- 便于调试单步失败
- 便于后续被多个场景复用
- 接口变更时影响面最小

### 8.2 第二层：业务场景链路

按真实业务流编排场景用例，例如：

1. 注册并创建会话
2. 核保通过
3. 审批通过
4. PSP 开始
5. PSP 完成
6. 电子签约成功
7. 放款成功
8. 收尾断开会话

### 8.3 第三层：版本回归集合

按业务线和回归目的归档，例如：

- UAT-USD-500K 主流程回归
- UAT-CNY-500K 主流程回归
- 拒绝类异常回归
- RETURNED 类审批回归
- 多店铺链路回归
- 系统事件通知回归
- UI smoke 回归

## 9. 场景编排建议

### 9.1 场景 A：标准主流程 Happy Path

适用：

- 最核心回归链路
- 版本发布前必跑

步骤：

1. `POST /api/register`
2. `POST /api/connect`
3. `POST /api/mock/underwritten`
4. `POST /api/mock/approved-offer`
5. `POST /api/mock/psp-start`
6. `POST /api/mock/psp-completed`
7. `POST /api/mock/esign`
8. `POST /api/mock/drawdown`
9. `POST /api/disconnect`

推荐默认参数：

- `journey = 500K`
- `currency = USD`
- `underwritten.status = APPROVED`
- `approved-offer.status = APPROVED`
- `psp-start.status = PROCESSING`
- `psp-completed.status = SUCCESS`
- `esign.status = SUCCESS`
- `drawdown.status = APPROVED`

### 9.2 场景 B：核保拒绝

步骤：

1. register
2. connect
3. underwritten with `status=REJECTED`
4. disconnect

用途：

- 验证核保拒绝分支
- 验证下游步骤不再继续执行

### 9.3 场景 C：审批退回 RETURNED

步骤：

1. register
2. connect
3. underwritten with `APPROVED`
4. approved-offer with `status=RETURNED`
5. `failure_reason_index = 1..5`
6. disconnect

用途：

- 覆盖审批退回原因
- 适合作为参数化场景

### 9.4 场景 D：放款拒绝

步骤：

1. register
2. connect
3. underwritten approved
4. approved-offer approved
5. esign success
6. drawdown rejected
7. `failure_reason_index = 1..5`
8. disconnect

### 9.5 场景 E：还款链路

步骤：

1. 先执行完成一条可放款成功的主流程
2. `POST /api/mock/repayment-start`
3. `POST /api/mock/repayment`
4. disconnect

注意：

- `repayment-start` 和 `repayment` 依赖同一会话上下文
- 该链路与仓库中的还款 ID 缓存机制有关，不能拆成两个无关场景

### 9.6 场景 F：多店铺链路

步骤：

1. register
2. connect
3. `multi-shop-binding`
4. `sp-status-update`
5. `multi-shop-3pl-redirect`
6. disconnect

用途：

- 覆盖多店铺授权和跳转能力

### 9.7 场景 G：系统事件通知

步骤：

1. register
2. connect
3. `system-event`
4. disconnect

建议参数化事件：

- `EXCEPTION-APPLICATION-CREATION`
- `INDICATIVE-OFFER`
- `IN-PROCESS`
- `ERROR`
- `ETB-customer`

## 10. MeterSphere 变量设计

推荐按三类变量管理。

### 10.1 环境变量

这类变量由 MeterSphere 环境统一维护：

- `base_url`
- `env`
- 默认金额
- 默认币种
- 默认 journey

示例：

```text
base_url = http://<fastapi-host>:<port>
env = uat
default_currency = USD
default_journey = 500K
underwritten_amount = 500000
approved_amount = 500000
signed_amount = 500000
drawdown_amount = 2000
repayment_principal_amount = 1000
repayment_outstanding_amount = 0
```

### 10.2 场景变量

这类变量由前一步响应提取：

- `phone_number`
- `email`
- `offer_id`
- `redirect_url`
- `session_id`
- `merchant_id`
- `preferred_currency`

### 10.3 数据驱动变量

适合做 CSV 或参数化：

- `journey`
- `currency`
- `underwritten_status`
- `approved_offer_status`
- `approved_offer_failure_reason_index`
- `psp_start_status`
- `psp_completed_status`
- `esign_status`
- `drawdown_status`
- `drawdown_failure_reason_index`
- `repayment_status`
- `repayment_failure_reason_index`
- `system_event_type`

## 11. 断言设计建议

MeterSphere 不建议只断言 HTTP 200，还应做三层断言。

### 11.1 第一层：接口成功断言

每个接口统一断言：

- HTTP 状态码 = 200
- `$.success == true`
- `$.message` 非空

### 11.2 第二层：关键字段断言

针对不同接口补充断言。

示例：

- register
  - `$.data.phone_number` 非空
  - `$.data.redirect_url` 非空
- connect
  - `$.data.session_id` 非空
- approved-offer
  - `$.data.status == "APPROVED"` 或预期状态
- drawdown
  - `$.data.amount` 等于请求金额

### 11.3 第三层：业务语义断言

如果 MeterSphere 支持脚本断言，建议补充：

- 失败场景时，不允许继续执行后继步骤
- RETURNED 时必须带合法 `failure_reason_index`
- REJECTED 时必须携带对应失败原因
- 还款场景必须沿用同一 `session_id`

## 12. 推荐的 MeterSphere 接口定义示例

### 12.1 注册

```http
POST {{base_url}}/api/register
Content-Type: application/json
```

```json
{
  "env": "{{env}}",
  "journey": "{{journey}}",
  "currency": "{{currency}}",
  "offline": false
}
```

### 12.2 建立会话

```http
POST {{base_url}}/api/connect
Content-Type: application/json
```

```json
{
  "env": "{{env}}",
  "phone_number": "{{phone_number}}"
}
```

### 12.3 核保

```http
POST {{base_url}}/api/mock/underwritten
Content-Type: application/json
```

```json
{
  "session_id": "{{session_id}}",
  "amount": {{underwritten_amount}},
  "status": "{{underwritten_status}}"
}
```

### 12.4 审批

```http
POST {{base_url}}/api/mock/approved-offer
Content-Type: application/json
```

```json
{
  "session_id": "{{session_id}}",
  "amount": {{approved_amount}},
  "status": "{{approved_offer_status}}",
  "failure_reason_index": {{approved_offer_failure_reason_index}}
}
```

### 12.5 放款

```http
POST {{base_url}}/api/mock/drawdown
Content-Type: application/json
```

```json
{
  "session_id": "{{session_id}}",
  "amount": {{drawdown_amount}},
  "status": "{{drawdown_status}}",
  "failure_reason_index": {{drawdown_failure_reason_index}}
}
```

## 13. 执行与部署建议

### 13.1 服务部署方式

建议先部署一套独立的 mockapi 服务，供 MeterSphere 调用：

- MeterSphere 不直接跑本地脚本
- MeterSphere 只访问一个稳定的 HTTP 地址

建议启动方式：

```bash
cd mockapi
uvicorn web.app:app --host 0.0.0.0 --port 8000
```

### 13.2 环境隔离

建议至少区分：

- SIT 接入地址
- UAT 接入地址
- PREPROD 接入地址

避免同一套 MeterSphere 场景误连错误环境。

### 13.3 并发控制

虽然接口层支持多会话，但仍建议：

- 单手机号不要并发复用
- 一个场景链路只使用一个 `session_id`
- 压测型并发和功能回归并发分开

## 14. 风险与注意事项

### 14.1 不建议直接调用 CLI

如果 MeterSphere 直接调 `mock_sit.py`：

- 输入输出不稳定
- 不利于参数提取
- 不利于失败重试和断言
- 不利于统一报告

### 14.2 UI 自动化不要主导回归

如果把 `线上自动化.py` 当主入口：

- 会让回归时间变长
- 环境问题会掩盖业务问题
- 定位成本高

### 14.3 会话生命周期要明确

所有 mock 操作依赖 `session_id`，因此必须保证：

- register/connect 在前
- disconnect 在后
- 中间不跨场景复用失效会话

### 14.4 数据污染要控制

如果多个环境共用或复用旧手机号，可能导致：

- 商户数据串场
- 状态前后不一致
- 数据断言失真

所以推荐每次通过 `register` 生成新账号，少用历史账号回归。

## 15. 推荐落地顺序

建议分三步推进。

### 第一步：先接 Happy Path

优先打通：

1. health
2. register
3. connect
4. underwritten
5. approved-offer
6. psp-start
7. psp-completed
8. esign
9. drawdown
10. disconnect

### 第二步：补异常流

补充：

- underwritten reject
- approved-offer returned
- drawdown rejected
- repayment failure
- system event error

### 第三步：补 UI smoke

最后再接：

- `线上自动化.py` 的 1 到 3 条关键冒烟

## 16. 最终建议

这套仓库已经具备较好的 MeterSphere 接入面，关键不是“能不能接”，而是“入口要选对”。

最终推荐结论如下：

- 主入口选 `mockapi/web/app.py`
- 底层执行依赖 `mockapi/mock_sit.py`
- `线上自动化.py` 只做补充冒烟，不做主回归入口
- MeterSphere 负责接口编排、变量提取、断言和回归报告

按这个分层推进，后续无论是做版本回归、异常分支覆盖，还是做管理层想看的回归统计，都会比直接接 UI 或 CLI 更稳、更容易扩展。
