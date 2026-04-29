# DPU 专题检索入口

这些入口文档会在构建本地 RAG 索引时自动刷新，用来承接 task.md、SOP、迁移脚本、mockapi 和自动化脚本等长上下文。

- [项目总览与主入口](00-project-map.md): 先定位核心脚本族、Web 接入层、数据库辅助层和长文档来源。 | files=16
- [核心 Mock 状态流](10-mock-core-flow.md): 聚焦注册、核保、审批、PSP、电子签、放款、还款等主流程。 | files=6
- [MeterSphere 与 mockapi 接入](20-metersphere-mockapi.md): 聚焦 FastAPI 接入层、会话模型、接口清单与 MeterSphere 变量设计。 | files=15
- [迁移脚本与 reg 生产回传](30-migration-reg-prod.md): 聚焦 batch1、batch3、多店铺 PSP 绑定、数据导出、回滚与 reg 环境。 | files=9
- [多店铺与 PSP 专题](40-multi-shop-psp.md): 聚焦多店铺绑定、3PL 跳转、PSP 记录插入与额度拆分。 | files=5
- [线上 UI 自动化](50-online-ui-automation.md): 聚焦 offerId 生成、线上注册、TIER 流程和浏览器自动化脚本。 | files=7
- [线下 UI 自动化](60-offline-ui-automation.md): 聚焦线下、DMF、手动输入版和暂停检查能力。 | files=5
- [治理规划与需求源文档](70-governance-and-planning.md): 聚焦短期计划、长期治理、AI 测试方案与需求设计源文件。 | files=5
