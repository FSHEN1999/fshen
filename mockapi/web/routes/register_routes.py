# -*- coding: utf-8 -*-
"""注册相关路由。"""
import asyncio
import json
import logging

from fastapi import APIRouter

from web.models.requests import RegisterAndRunMultiShopRequest, RegisterRequest
from web.models.responses import ApiResponse
from web.services.mock_adapter import WebDPUMockService

router = APIRouter(prefix="/api", tags=["注册"])
log = logging.getLogger(__name__)


@router.post("/register", response_model=ApiResponse)
async def register_account(req: RegisterRequest):
    """注册新账号。"""
    result = await asyncio.to_thread(
        WebDPUMockService.register_new_account_web,
        env=req.env,
        journey=req.journey,
        currency=req.currency,
        offline=req.offline,
        funder_resource=req.funder_resource,
    )
    if result.get("success"):
        return ApiResponse(success=True, message="注册成功", data=result)
    return ApiResponse(success=False, message=result.get("error", "注册失败"), data=result)


@router.post("/register-and-run-multishop", response_model=ApiResponse)
async def register_and_run_multishop(req: RegisterAndRunMultiShopRequest):
    result = await asyncio.to_thread(
        WebDPUMockService.register_and_run_multishop_flow_web,
        env=req.env,
        journey=req.journey,
        currency=req.currency,
        offline=req.offline,
        funder_resource=req.funder_resource,
        sp_status=req.sp_status,
    )
    log_payload = {
        "request": req.model_dump(),
        "result": result,
    }
    if result.get("success"):
        log.info(
            "注册并完成绑店流程完成: %s",
            json.dumps(log_payload, ensure_ascii=False, default=str),
        )
        return ApiResponse(success=True, message="注册并完成绑店流程成功", data=result)
    log.error(
        "注册并完成绑店流程失败: %s",
        json.dumps(log_payload, ensure_ascii=False, default=str),
    )
    return ApiResponse(
        success=False,
        message=result.get("error", "注册并完成绑店流程失败"),
        data=result,
    )
