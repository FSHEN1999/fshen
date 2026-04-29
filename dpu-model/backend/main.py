# -*- coding: utf-8 -*-
"""FastAPI应用入口"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from routers import auth, user, assessment, approval

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DPU模型版本 - 借款平台API",
    description="提交信息即可完成贷款借款的线上平台核心API",
    version="1.0.0",
)

# 跨域配置（开发环境）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(assessment.router)
app.include_router(approval.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "dpu-model"}
