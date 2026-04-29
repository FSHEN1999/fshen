# 项目总览与主入口

先定位核心脚本族、Web 接入层、数据库辅助层和长文档来源。

## 适合问这些问题
- 这个仓库的主入口和辅助层分别是什么
- CLI、Web、数据库、UI 自动化分别落在哪些文件

## 核心入口文件
- `AGENTS.md`: # AGENTS.md | ## Project Overview | ## Environment Setup | ### Python Environment
- `config.py`: 配置管理模块 - 从.env文件加载配置，支持环境变量覆盖 | symbols: DatabaseConfig, UIConfig, FileConfig, PollingConfig, Config, _ensure_config
- `db_helper.py`: 数据库助手模块 - 集中管理所有数据库查询，使用参数化查询防止SQL注入 | symbols: DatabaseHelper
- `dpu_rag_mvp/__init__.py`: DPU local RAG MVP package.
- `dpu_rag_mvp/__main__.py`: Python module
- `dpu_rag_mvp/cli.py`: symbols: cmd_build, cmd_status, cmd_search, cmd_catalog, cmd_suggest, cmd_topics
- `dpu_rag_mvp/config.py`: symbols: _default_project_root
- `dpu_rag_mvp/core.py`: symbols: SearchHit, AutomationSuggestion, utc_now_iso, ensure_data_dir, get_connection, init_db
- `dpu_rag_mvp/mcp_server.py`: Return local RAG index status for the current DPU test project. | symbols: rag_status, rag_build_index, rag_search, rag_automation_catalog, rag_suggest_automation, rag_topic_portals
- `dpu_rag_mvp/topic_portals.py`: symbols: TopicDefinition, TopicPortalInfo, _extract_wordprocessingml_text, _read_path_text, _extract_python_symbols, _extract_leading_doc_line
- `locators.py`: 页面元素定位器 - Page Object Model 组织，按页面分类管理元素定位 | symbols: RegistrationPage, PasswordSetupPage, CompanyInfoPage, DirectorInfoPage, BankAccountPage, ContactInfoPage
- `mock_sit.py`: DPU状态模拟工具 | symbols: ColorFormatter, generate_uuid37, validate_phone_number, get_current_time, get_utc_time, validate_numeric_input
- `mock_uat.py`: DPU状态模拟工具 | symbols: ColorFormatter, generate_uuid37, validate_phone_number, get_current_time, get_utc_time, validate_numeric_input
- `mockapi/AGENTS.md`: # AGENTS.md | ## Project Overview | ## Environment Setup | ### Python Environment
- `mockapi/web/app.py`: FastAPI 应用入口 | symbols: lifespan
- `webhook_service.py`: Webhook服务模块 - 统一管理所有webhook请求，支持参数化调用减少重复代码 | symbols: EventType, WebhookService

## 快速检索命令
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "项目主入口是什么"`
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "mock_uat mockapi db_helper 关系"`
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "先看哪些文件能快速理解 DPU 项目"`

## 推荐问法
- 项目主入口是什么
- mock_uat mockapi db_helper 关系
- 先看哪些文件能快速理解 DPU 项目

## 关联主题
- `10-mock-core-flow`
- `20-metersphere-mockapi`
