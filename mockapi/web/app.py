# -*- coding: utf-8 -*-
"""FastAPI 应用入口"""
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from web.routes import system_routes, register_routes, mock_routes, ws_routes, ai_routes, auth_routes, contact_routes
from web.services.audit_store import audit_store
from web.services.log_capture import ws_log_handler
from web.services.session_manager import session_manager

# 确保项目根目录在 sys.path 中
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时：注册 WebSocket 日志处理器到 mock_sit 模块的 logger
    root_logger = logging.getLogger()
    mock_logger = logging.getLogger("mock_sit")

    # 添加 WebSocket 日志处理器（全局广播）
    if ws_log_handler not in root_logger.handlers:
        root_logger.addHandler(ws_log_handler)
    if ws_log_handler in mock_logger.handlers:
        mock_logger.removeHandler(ws_log_handler)

    audit_store.init_schema()
    logging.getLogger(__name__).info("DPU Mock Web 应用已启动")
    yield

    # 关闭时：清理所有会话
    for sid in list(session_manager._sessions.keys()):
        session_manager.destroy_session(sid)
    logging.getLogger(__name__).info("DPU Mock Web 应用已关闭")


app = FastAPI(
    title="DPU Mock 工具",
    description="DPU 状态模拟工具 Web 版 - 支持注册、核保、审批、PSP、电子签、放款、还款等操作",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.getLogger(__name__).exception("Unhandled API error")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": f"{type(exc).__name__}: {exc}",
            "data": {
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
                "error_message": f"{type(exc).__name__}: {exc}",
                "request_info": {
                    "method": request.method,
                    "url": str(request.url),
                    "headers": dict(request.headers),
                },
                "response_info": None,
            },
        },
    )


@app.middleware("http")
async def add_utf8_charset(request, call_next):
    response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    text_types = (
        "text/html",
        "text/css",
        "application/javascript",
        "text/javascript",
        "application/json",
    )
    if content_type and "charset=" not in content_type.lower() and content_type.startswith(text_types):
        response.headers["content-type"] = f"{content_type}; charset=utf-8"
    return response

# CORS 配置（开发期间允许 Vite dev server 跨域）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"https://.*\.ngrok-free\.(dev|app|free\.dev)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(system_routes.router)
app.include_router(auth_routes.router)
app.include_router(contact_routes.router)
app.include_router(register_routes.router)
app.include_router(mock_routes.router)
app.include_router(ws_routes.router)
app.include_router(ai_routes.router)

# 静态文件（前端构建产物，部署时启用）
_static_dir = Path(__file__).parent / "static"
_static_index = _static_dir / "index.html"
if _static_index.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
