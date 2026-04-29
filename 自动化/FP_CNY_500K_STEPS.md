# FP-CNY 500k 场景处理步骤

## 本次生成结果

- 新场景文件：`D:\data\project\dpu\自动化\scenario_fp_cny_500k.ms`
- 说明文档：`D:\data\project\dpu\自动化\FP_CNY_500K_STEPS.md`

## 我实际修改了什么

基于 `scenario_1.ms` 克隆生成了新的 `FP-CNY 500k` 场景，并保持流程顺序、循环控制器、停止点与原场景一致，只改以下关键字段：

1. 所有启用步骤的请求头 `product-currency` 从 `USD` 改为 `CNY`
2. 第 2 步继续保留数据库查询验证码：
   - 查询表：`dpu_seller_center.dpu_sms_record`
   - 数据源：`reg`
3. 第 3 步注册请求体新增：
   - `preferFinanceProductCurrency: "CNY"`
4. 第 4 步 `选择FUNDPARK流程` 改为启用，并改为：
   - `{"funderCode":"FUNDPARK","currency":"CNY"}`
   - 同时补齐 `Bearer ${token}` 和标准业务头
5. 第 11 步企业信息 `regNo` 改为：
   - `91330201MA2AFFT07Q`
6. 第 13 步 `limitSelection` 改为：
   - `1500000`
7. 第 23 步 `underwritten` 默认金额改为：
   - `1500000`
8. 第 24 步 `approved-offer` 默认金额改为：
   - `1500000`
9. 第 27 步 `esign` 默认金额改为：
   - `1500000`
10. 所有 SQL 前置处理器统一改成 `reg` 数据源，修正了原场景里 `sp-updateOffer(成功)` 仍指向 `sit数据库` 的问题

## 结构验证结果

我已经对生成后的 `.ms` 做了静态检查，确认以下内容成立：

- 第 2 步仍然走数据库查询验证码
- 第 3 步注册体已经带 `preferFinanceProductCurrency = CNY`
- 第 4 步已经启用，且请求体带 `currency = CNY`
- 第 11 步 `regNo = 91330201MA2AFFT07Q`
- 第 13 步 `limitSelection = 1500000`
- `underwritten / approved-offer / esign` 三步默认金额均已切到 `1500000`
- 停止点仍然与 `scenario_1` 一致，只做到 `esign`

## reg 实跑结论

我对 `reg` 做了真实链路验证，结论分两段：

### 已确认通过的部分

以下步骤在 `reg` 实跑通过：

- 发送注册短信
- 从数据库查询验证码并完成校验
- 用户注册，且注册后返回的 `preferFinanceProductCurrency = CNY`
- 切换 `FUNDPARK + CNY`
- 生成 SP state
- 执行 SP 授权接口
- 创建申请单
- 提交企业信息
- 提交股东信息
- 选择 CNY 高额度
- 查询 offer 页面
- 激活 offer
- 关联 SP 和 3PL 店铺
- 触发三个 FP 任务

### 当前阻塞点

`reg` 环境当前在 `sp-updateOffer / 3PL offer` 这条链路上被外部依赖阻塞，具体表现为：

- `dpu_manual_offer` 已落库
- 但 `platform_offer_id` 为 `NULL`
- `send_status = FAIL`
- `reason` 中的真实错误为：
  - `auto offer error!`
  - `500 Internal Server Error`
  - `POST https://lending-na-gamma.amazonservices.com/test/offers`
  - `{"message":"Invalid token format"}`

这意味着当前 `reg` 上即使是原始 USD 路径也会在这里失败，不是本次 CNY 改动单独造成的。

## 对当前验证状态的影响

由于 `platform_offer_id` 没有生成，后续与 `scenario_1` 同构的以下链路无法在当前 `reg` 完整实跑到成功：

- `sp-updateOffer(成功)`
- 基于 `platform_offer_id` 的亚马逊 3PL 授权
- 后续依赖完整额度申请落库的：
  - `underwritten`
  - `approved-offer`
  - `psp-start`
  - `psp-completed`
  - `esign`

换句话说：

- 场景文件本身已经按你的要求改完
- `reg` 上前半段 CNY 主链已经验证
- 但完整跑到 `esign` 目前被 `reg` 环境外部 Amazon token 问题阻断

## 当前最重要的事实

这次我没有把“实跑成功”写假。

真实情况是：

- 场景生成完成：是
- 结构检查通过：是
- `reg` 前半段实跑通过：是
- `reg` 全链路到 `esign`：当前环境阻塞，未完成

如果你后面要我继续把它跑到真正通过，我建议下一步先处理 `reg` 当前的 `Invalid token format` 外部依赖问题，然后我可以直接基于这份 `.ms` 再补一轮完整回归。
