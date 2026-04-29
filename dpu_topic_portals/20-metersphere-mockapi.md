# MeterSphere 与 mockapi 接入

聚焦 FastAPI 接入层、会话模型、接口清单与 MeterSphere 变量设计。

## 适合问这些问题
- MeterSphere 最佳主入口为什么是 mockapi/web/app.py
- session_id、phone_number 这些变量应该怎样传递

## 核心入口文件
- `mockapi/INTEGRATION_GUIDE.md`: # 代码优化集成指南 | ## 📚 概述 | ## 📦 已创建的模块 | ### 1. **db_helper.py** - 数据库辅助层
- `mockapi/METERSPHERE_INTEGRATION_DESIGN.md`: # MeterSphere 接入设计文档 | ## 1. 一句话结论 | ## 2. 背景与目标 | ## 3. 为什么选 `mockapi/web/app.py`
- `mockapi/web/app.py`: FastAPI 应用入口 | symbols: lifespan
- `mockapi/web/models/__init__.py`: Python module
- `mockapi/web/models/requests.py`: Pydantic 请求模型定义 | symbols: ConnectRequest, RegisterRequest, MockBaseRequest, LinkSp3plRequest, UnderwrittenRequest, ApprovedOfferRequest
- `mockapi/web/models/responses.py`: 统一响应模型定义 | symbols: ApiResponse, ConnectResponse, RegisterResponse, EnumsResponse
- `mockapi/web/routes/__init__.py`: Python module
- `mockapi/web/routes/mock_routes.py`: Mock 操作路由：15 个 Mock 端点 | symbols: _get_service, mock_link_sp_3pl, mock_underwritten, mock_approved_offer, mock_psp_start, mock_psp_completed
- `mockapi/web/routes/register_routes.py`: 注册相关路由 | symbols: register_account
- `mockapi/web/routes/system_routes.py`: 系统路由：环境列表、连接/断开、健康检查、枚举查询 | symbols: health_check, list_environments, list_enums, connect, disconnect, list_sessions
- `mockapi/web/routes/ws_routes.py`: WebSocket 路由：实时日志推送 | symbols: websocket_logs
- `mockapi/web/services/__init__.py`: Python module
- `mockapi/web/services/log_capture.py`: 日志捕获器：拦截 Python logging 输出并通过 WebSocket 推送到前端 | symbols: WebSocketLogHandler
- `mockapi/web/services/mock_adapter.py`: Web 适配器：将 DPUMockService 的 input() 调用改为参数传入，返回结构化结果 | symbols: WebDPUMockService
- `mockapi/web/services/session_manager.py`: 会话管理器：管理数据库连接和 DDPUMockService 实例的生命周期 | symbols: SessionContext, SessionManager

## 快速检索命令
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "metersphere session_id scene variable"`
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "mockapi web app 路由和服务层怎么分"`
- `& '.\.venv\Scripts\python.exe' -m dpu_rag_mvp search "MeterSphere 应该怎么接 mockapi"`

## 推荐问法
- metersphere session_id scene variable
- mockapi web app 路由和服务层怎么分
- MeterSphere 应该怎么接 mockapi

## 关联主题
- `10-mock-core-flow`
- `70-governance-and-planning`
