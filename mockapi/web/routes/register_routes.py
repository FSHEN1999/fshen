# -*- coding: utf-8 -*-
"""Registration routes."""
import asyncio
import json
import logging

from fastapi import APIRouter

from web.models.requests import RegisterAndRunMultiShopRequest, RegisterRequest
from web.models.responses import ApiResponse
from web.routes.auth_guard import require_valid_username
from web.services.audit_store import audit_store
from web.services.mock_adapter import WebDPUMockService

router = APIRouter(prefix="/api", tags=["Registration"])
log = logging.getLogger(__name__)


@router.post("/register", response_model=ApiResponse)
async def register_account(req: RegisterRequest):
    username = require_valid_username(req.username)
    result = await asyncio.to_thread(
        WebDPUMockService.register_new_account_web,
        env=req.env,
        journey=req.journey,
        currency=req.currency,
        offline=req.offline,
        funder_resource=req.funder_resource,
    )
    if result.get("success"):
        response = ApiResponse(success=True, message="registration succeeded", data=result)
    else:
        response = ApiResponse(success=False, message=result.get("error", "registration failed"), data=result)
    try:
        await asyncio.to_thread(
            audit_store.record_operation,
            username=username,
            session_data=None,
            operation_name=(req.operation_name or "RegisterAccount").strip(),
            request_payload=req.model_dump(),
            response_payload=response.model_dump(),
            success=response.success,
        )
    except Exception:
        log.exception("Failed to record register audit")
    return response


@router.post("/register-and-run-multishop", response_model=ApiResponse)
async def register_and_run_multishop(req: RegisterAndRunMultiShopRequest):
    username = require_valid_username(req.username)
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
            "register and multishop flow completed: %s",
            json.dumps(log_payload, ensure_ascii=False, default=str),
        )
        response = ApiResponse(success=True, message="register and multishop flow succeeded", data=result)
        success = True
    else:
        log.error(
            "register and multishop flow failed: %s",
            json.dumps(log_payload, ensure_ascii=False, default=str),
        )
        response = ApiResponse(
            success=False,
            message=result.get("error", "register and multishop flow failed"),
            data=result,
        )
        success = False
    try:
        await asyncio.to_thread(
            audit_store.record_operation,
            username=username,
            session_data=result.get("session"),
            operation_name=(req.operation_name or "RegisterAndRunMultiShop").strip(),
            request_payload=req.model_dump(),
            response_payload=response.model_dump(),
            success=success,
        )
    except Exception:
        log.exception("Failed to record multishop register audit")
    return response
