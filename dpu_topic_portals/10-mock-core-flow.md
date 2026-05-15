# 核心 Mock 状态流

聚焦注册、核保、审批、PSP、电子签、放款、还款等主流程。

## 适合问这些问题
- 主流程里关键 ID 是怎么从数据库取出来的
- 核保到放款之间的状态更新入口在哪里

## 核心入口文件
- `config.py`: 配置管理模块 - 从.env文件加载配置，支持环境变量覆盖 | symbols: DatabaseConfig, UIConfig, FileConfig, PollingConfig, Config, _ensure_config
- `db_helper.py`: 数据库助手模块 - 集中管理所有数据库查询，使用参数化查询防止SQL注入 | symbols: DatabaseHelper
- `mock_sit.py`: DPU状态模拟工具 | symbols: ColorFormatter, generate_uuid37, validate_phone_number, get_current_time, get_utc_time, validate_numeric_input
- `mockapi/web/services/mock_adapter.py`: Web 适配器：将 DPUMockService 的 input() 调用改为参数传入，返回结构化结果 | symbols: WebDPUMockService
- `webhook_service.py`: Webhook服务模块 - 统一管理所有webhook请求，支持参数化调用减少重复代码 | symbols: EventType, WebhookService

## 快速检索命令
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "underwritten approved psp esign drawdown repayment 流程"`
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "merchant_id application_unique_id 是怎么串起来的"`
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "mock_uat 里主流程方法有哪些"`

## 推荐问法
- underwritten approved psp esign drawdown repayment 流程
- merchant_id application_unique_id 是怎么串起来的
- mock_uat 里主流程方法有哪些

## 关联主题
- `20-metersphere-mockapi`
- `40-multi-shop-psp`
