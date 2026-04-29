# -*- coding: utf-8 -*-
"""注册相关路由"""
import asyncio
from fastapi import APIRouter

from web.models.requests import RegisterRequest
from web.models.responses import ApiResponse
from web.services.mock_adapter import WebDPUMockService

router = APIRouter(prefix="/api", tags=["注册"])


@router.post("/register", response_model=ApiResponse)
async def register_account(req: RegisterRequest):
    """注册新账号"""
    result = await asyncio.to_thread(
        WebDPUMockService.register_new_account_web,
        env=req.env,
        journey=req.journey,
        currency=req.currency,
        offline=req.offline,
    )
    if result.get("success"):
        return ApiResponse(success=True, message="注册成功", data=result)
    return ApiResponse(success=False, message=result.get("error", "注册失败"), data=result)
