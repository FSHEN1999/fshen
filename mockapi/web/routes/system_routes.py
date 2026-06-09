# -*- coding: utf-8 -*-
"""System routes for health, enums, sessions, and logs."""
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from web.models.requests import ConnectRequest
from web.models.responses import ApiResponse, ConnectResponse, EnumsResponse
from web.routes.auth_guard import require_valid_username
from web.services.ai_service import available_ai_sql_data_sources
from web.services.audit_store import audit_store
from web.services.log_capture import ws_log_handler
from web.services.session_manager import session_manager

router = APIRouter(prefix="/api", tags=["System"])
log = logging.getLogger(__name__)


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/environments", response_model=ApiResponse)
async def list_environments():
    envs = ["sit", "uat", "dev", "preprod", "reg", "local"]
    return ApiResponse(success=True, message="environments loaded", data=envs)


@router.get("/enums", response_model=ApiResponse)
async def list_enums():
    data = EnumsResponse(
        environments=["sit", "uat", "dev", "preprod", "reg", "local"],
        ai_sql_data_sources=list(available_ai_sql_data_sources()),
        journeys=["200K", "500K", "2000K"],
        currencies=["USD", "CNY"],
        funder_resources=["FUNDPARK", "HSBC", "DOWSURE"],
        underwritten_statuses=["APPROVED", "REJECTED"],
        approved_offer_statuses=["APPROVED", "RETURNED", "REJECTED"],
        esign_statuses=["SUCCESS", "FAIL"],
        drawdown_statuses=["APPROVED", "REJECTED"],
        psp_start_statuses=["PROCESSING", "FAIL", "INITIAL"],
        psp_completed_statuses=["SUCCESS", "FAIL", "INITIAL"],
        repayment_statuses=["Success", "Failure"],
        system_event_types=[
            "EXCEPTION-APPLICATION-CREATION",
            "INDICATIVE-OFFER",
            "IN-PROCESS",
            "ERROR",
            "ETB-customer",
        ],
        returned_failure_reasons=[
            {"index": 1, "label": "incorrect BRN"},
            {"index": 2, "label": "unable to retrieve customer ID number"},
            {"index": 3, "label": "ID number does not match CR record"},
            {"index": 4, "label": "company structure validation failed"},
            {"index": 5, "label": "manual AML review required"},
            {"index": 6, "label": "incorrect unified social credit code"},
            {"index": 7, "label": "ID number does not match company registration data"},
        ],
        approved_rejection_reasons=[
            {"value": "fraud", "label": "fraud"},
            {"value": "others", "label": "others"},
        ],
        drawdown_failure_reasons=[
            {"index": 1, "code": "ER001", "label": "no valid bank account"},
            {"index": 2, "code": "ER002", "label": "available limit is lower than drawdown amount"},
            {"index": 3, "code": "ER003", "label": "unknown error"},
            {"index": 4, "code": "ER004", "label": "bank or payment service provider rejected"},
            {"index": 5, "code": "ER005", "label": "overdue"},
        ],
        repayment_failure_reasons=[
            {"index": 1, "code": "ER001", "label": "bank slip amount does not match repayment amount"},
            {"index": 2, "code": "ER002", "label": "operation rejected"},
        ],
        sp_update_failure_reasons=[
            {"index": 1, "label": "The lender country doesn't match with the Seller reporting country"},
            {"index": 2, "label": "Active credit approval exists"},
            {"index": 3, "label": "An offer already exists for the seller for the same partner product combination"},
            {"index": 4, "label": "others"},
        ],
        application_abandon_reasons=[
            {"value": "SellerCancelled", "label": "seller cancelled"},
            {"value": "OfferExpired", "label": "offer expired"},
            {"value": "ApplicationInfoNotSubmitted", "label": "application info not submitted"},
            {"value": "LenderOfferNotReturned", "label": "lender offer not returned"},
        ],
    )
    return ApiResponse(success=True, message="enums loaded", data=data.model_dump())


@router.post("/connect", response_model=ApiResponse)
async def connect(req: ConnectRequest):
    username = require_valid_username(req.username)
    try:
        ctx = await asyncio.to_thread(session_manager.create_session, req.env, req.phone_number)
        session_data = await asyncio.to_thread(session_manager.serialize_session, ctx)
        resp = ConnectResponse(
            session_id=session_data["session_id"],
            env=session_data["env"],
            phone_number=session_data["phone_number"],
            merchant_id=session_data.get("merchant_id"),
            preferred_currency=session_data.get("preferred_currency") or "USD",
            application_unique_id=session_data.get("application_unique_id"),
            selected_application_unique_id=session_data.get("selected_application_unique_id"),
            applications=session_data.get("applications") or [],
            finance_product_currency=session_data.get("finance_product_currency"),
            lender_code=session_data.get("lender_code"),
            application_status=session_data.get("application_status"),
        )
        try:
            await asyncio.to_thread(audit_store.record_session, username, resp.model_dump())
            await asyncio.to_thread(
                audit_store.record_operation,
                username=username,
                session_data=resp.model_dump(),
                operation_name="ConnectSession",
                request_payload=req.model_dump(),
                response_payload=ApiResponse(success=True, message="connected", data=resp.model_dump()).model_dump(),
                success=True,
            )
            log.info("Connect audit recorded | username=%s | session_id=%s", username, resp.session_id)
        except Exception:
            log.exception("Connect audit failed | username=%s | session_id=%s", username, resp.session_id)
        return ApiResponse(success=True, message="connected", data=resp.model_dump())
    except HTTPException:
        raise
    except LookupError:
        raise HTTPException(status_code=404, detail="PHONE_NOT_FOUND")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"connect failed: {exc}") from exc


@router.post("/disconnect", response_model=ApiResponse)
async def disconnect(session_id: str):
    destroyed = session_manager.destroy_session(session_id)
    if destroyed:
        try:
            await asyncio.to_thread(audit_store.mark_session_disconnected, session_id)
        except Exception:
            pass
        return ApiResponse(success=True, message="session disconnected")
    raise HTTPException(status_code=404, detail="session not found")


@router.get("/sessions", response_model=ApiResponse)
async def list_sessions(session_id: Optional[str] = None):
    if session_id:
        sessions = await asyncio.to_thread(session_manager.list_session, session_id)
    else:
        sessions = await asyncio.to_thread(session_manager.list_sessions)
    return ApiResponse(success=True, message=f"{len(sessions)} active sessions", data=sessions)


@router.get("/logs", response_model=ApiResponse)
async def query_logs(
    keyword: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 500,
):
    logs = await asyncio.to_thread(
        ws_log_handler.query_logs,
        keyword=keyword,
        start_time=start_time,
        end_time=end_time,
        session_id=session_id,
        limit=limit,
    )
    return ApiResponse(success=True, message=f"{len(logs)} matching logs", data=logs)
