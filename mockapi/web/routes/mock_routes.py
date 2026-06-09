# -*- coding: utf-8 -*-
"""Mock operation routes."""
import asyncio
from fastapi import APIRouter, HTTPException

from web.models.requests import (
    LinkSp3plRequest, UnderwrittenRequest, ApprovedOfferRequest,
    UnderwrittenDowsureRequest,
    DowsureCreditResultRequest, DowsureEsignDrawdownResultRequest,
    DowsureRepaymentResultRequest, DowsureRetryCallbackRequest,
    PspStartRequest, PspCompletedRequest, EsignRequest, DrawdownRequest,
    RepaymentStartRequest, RepaymentRequest,
    MultiShopBindingRequest, SpStatusUpdateRequest, MultiShop3plRedirectRequest,
    SystemEventRequest, PspHsbcStartRequest, PspHsbcCompletedRequest,
    ApplicationAbandonRequest,
    CreateApplicationContextRequest, FpApplicationStepRequest,
    ShopPerformanceUpdateRequest,
)
from web.models.responses import ApiResponse
from web.routes.auth_guard import require_valid_username
from web.services.audit_store import audit_store
from web.services.session_manager import session_manager

router = APIRouter(prefix="/api/mock", tags=["Mock"])


def _get_service(session_id: str, application_unique_id: str | None = None, username: str | None = None):
    """Get the service instance from a live session."""
    if username is not None:
        require_valid_username(username)
    ctx = session_manager.get_session(session_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="session not found or expired")
    if application_unique_id:
        try:
            ctx = session_manager.select_application(session_id, application_unique_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="session not found or expired") from exc
    return ctx.service


def _get_context(session_id: str):
    """Get a live session context for read-only refresh endpoints."""
    ctx = session_manager.get_session(session_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="session not found or expired")
    return ctx


def _serialize_context(session_id: str) -> dict | None:
    ctx = session_manager.get_session(session_id)
    if not ctx:
        return None
    return session_manager.serialize_session(ctx)


def _operation_response(req, operation_name: str, result: dict, message: str) -> ApiResponse:
    username = require_valid_username(getattr(req, "username", None))
    audit_operation_name = (getattr(req, "operation_name", None) or operation_name).strip()
    success = result.get("success", False)
    response = ApiResponse(success=success, message=message, data=result)
    try:
        audit_store.record_operation(
            username=username,
            session_data=_serialize_context(req.session_id),
            operation_name=audit_operation_name,
            request_payload=req.model_dump(),
            response_payload=response.model_dump(),
            success=success,
        )
    except Exception:
        # Audit persistence should not block a mock operation result.
        import logging
        logging.getLogger(__name__).exception("Failed to record mock operation audit")
    return response


# 1. SP-3PL 閸忓疇浠?
@router.post("/link-sp-3pl", response_model=ApiResponse)
async def mock_link_sp_3pl(req: LinkSp3plRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(service.mock_link_sp_3pl_shop)
    return _operation_response(req, req.__class__.__name__, result, "SP-3PL鍏宠仈瀹屾垚")


# 2. 閺嶉晲绻?
@router.post("/underwritten", response_model=ApiResponse)
async def mock_underwritten(req: UnderwrittenRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(service.mock_underwritten_status, amount=req.amount, status=req.status)
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 3. 鐎光剝澹?
@router.post("/approved-offer", response_model=ApiResponse)
async def mock_approved_offer(req: ApprovedOfferRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_approved_offer_status,
        amount=req.amount, status=req.status,
        failure_reason_index=req.failure_reason_index,
        rejection_reason=req.rejection_reason,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 4. PSP 瀵偓婵?
@router.post("/psp-start", response_model=ApiResponse)
async def mock_psp_start(req: PspStartRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_psp_start_status,
        status=req.status,
        merchant_account_id=req.merchant_account_id,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 5. PSP 鐎瑰本鍨?
@router.post("/psp-completed", response_model=ApiResponse)
async def mock_psp_completed(req: PspCompletedRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_psp_completed_status,
        status=req.status,
        merchant_account_id=req.merchant_account_id,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 6. 閻㈤潧鐡欑粵?
@router.post("/esign", response_model=ApiResponse)
async def mock_esign(req: EsignRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_esign_status, signed_amount=req.signed_amount, status=req.status
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 7. 閺€鐐儥
@router.post("/drawdown", response_model=ApiResponse)
async def mock_drawdown(req: DrawdownRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_drawdown_status,
        amount=req.amount, status=req.status,
        failure_reason_index=req.failure_reason_index
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 8. 鏉╂ɑ顑欏鈧慨?
@router.post("/repayment-start", response_model=ApiResponse)
async def mock_repayment_start(req: RepaymentStartRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_repayment_start_status,
        principal_amount=req.principal_amount,
        outstanding_amount=req.outstanding_amount
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 9. 鏉╂ɑ顑?
@router.post("/repayment", response_model=ApiResponse)
async def mock_repayment(req: RepaymentRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_repayment_status,
        principal_amount=req.principal_amount,
        outstanding_amount=req.outstanding_amount,
        status=req.status,
        failure_reason_index=req.failure_reason_index
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 10. 婢舵艾绨甸柧?SP 缂佹垵鐣?
@router.post("/multi-shop-binding", response_model=ApiResponse)
async def mock_multi_shop_binding(req: MultiShopBindingRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(service.mock_multi_shop_binding, state=req.state)
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 11. SP 閻樿埖鈧焦娲块弬?
@router.post("/sp-status-update", response_model=ApiResponse)
async def mock_sp_status_update(req: SpStatusUpdateRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_sp_status_update,
        platform_seller_id=req.platform_seller_id,
        status=req.status,
        failure_reason_index=req.failure_reason_index
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 12. 3PL 闁插秴鐣鹃崥?
@router.post("/multi-shop-3pl-redirect", response_model=ApiResponse)
async def mock_multi_shop_3pl_redirect(req: MultiShop3plRedirectRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(service.mock_multi_shop_3pl_redirect)
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)
@router.post("/create-application-context", response_model=ApiResponse)
async def create_application_context(req: CreateApplicationContextRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.ensure_application_context_web,
        req.journey,
        req.currency,
        req.funder_resource,
        req.tier_code,
        req.offer_id,
    )
    msg = "application context prepared" if result.get("success") else result.get("error", "application context prepare failed")
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/fp-business-profile", response_model=ApiResponse)
async def submit_fp_business_profile(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.submit_fp_business_profile_web,
        req.journey,
        req.currency,
        req.funder_resource,
    )
    msg = "business profile submitted" if result.get("success") else result.get("error", "business profile submit failed")
    return _operation_response(req, "SubmitFpBusinessProfile", result, msg)


@router.post("/fp-director-info", response_model=ApiResponse)
async def submit_fp_director_info(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.submit_fp_director_info_web,
        req.journey,
        req.currency,
        req.funder_resource,
        req.nameCn,
        req.addressDetail,
    )
    msg = "director info submitted" if result.get("success") else result.get("error", "director info submit failed")
    return _operation_response(req, "SubmitFpDirectorInfo", result, msg)


@router.post("/shop-performance-cny-boost", response_model=ApiResponse)
async def update_shop_performance_cny_boost(req: ShopPerformanceUpdateRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.update_shop_performance_cny_boost_web,
        req.offer_id,
    )
    msg = "shop performance updated" if result.get("success") else result.get("error", "shop performance update failed")
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/fp-start-reassessment", response_model=ApiResponse)
async def start_fp_reassessment(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.start_reassessment_web,
        req.journey,
        req.currency,
        req.funder_resource,
    )
    msg = "reassessment started" if result.get("success") else result.get("error", "reassessment start failed")
    return _operation_response(req, "StartFpReassessment", result, msg)


@router.post("/fp-offer-limit-select", response_model=ApiResponse)
async def select_fp_offer_limit(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(service.select_fp_offer_limit_web, req.journey)
    msg = "offer limit selected" if result.get("success") else result.get("error", "offer limit select failed")
    return _operation_response(req, "SelectFpOfferLimit", result, msg)


@router.post("/fp-offer-quote-activate", response_model=ApiResponse)
async def activate_fp_offer_quote(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(service.activate_fp_offer_quote_web, req.journey)
    msg = "offer quote activated" if result.get("success") else result.get("error", "offer quote activate failed")
    return _operation_response(req, "ActivateFpOfferQuote", result, msg)


@router.post("/fp-link-sp-3pl-shops", response_model=ApiResponse)
async def link_fp_sp_3pl_shops(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(service.link_fp_sp_3pl_shops_web, req.journey)
    msg = "sp and 3pl shops linked" if result.get("success") else result.get("error", "sp and 3pl shop link failed")
    return _operation_response(req, "LinkFpSp3plShops", result, msg)


@router.post("/fp-scheduled-submit", response_model=ApiResponse)
async def run_fp_scheduled_submit(req: FpApplicationStepRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(service.run_fp_scheduled_tasks_and_poll_submitted_web, req.journey)
    msg = "scheduled tasks completed" if result.get("success") else result.get("error", "scheduled tasks failed")
    return _operation_response(req, "RunFpScheduledSubmit", result, msg)


# 13. 缁崵绮烘禍瀣╂闁氨鐓?
@router.post("/system-event", response_model=ApiResponse)
async def mock_system_event(req: SystemEventRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_system_event_notification,
        event_type=req.event_type,
        application_unique_id=req.application_unique_id,
        error_code=req.error_code
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.get("/dowsure-merchant-accounts", response_model=ApiResponse)
async def list_dowsure_merchant_accounts(session_id: str):
    ctx = _get_context(session_id)
    session_manager._get_application_rows(ctx, force=True)
    session_manager._refresh_application_snapshot(ctx)
    service = ctx.service
    result = await asyncio.to_thread(service.get_dowsure_merchant_accounts)
    return ApiResponse(
        success=result.get("success", False),
        message="DOWSURE merchant accounts loaded" if result.get("success") else result.get("error", "DOWSURE merchant accounts load failed"),
        data=result,
    )


@router.get("/psp-authorization-rows", response_model=ApiResponse)
async def list_psp_authorization_rows(session_id: str):
    service = _get_service(session_id)
    result = await asyncio.to_thread(service.get_psp_authorization_rows)
    return ApiResponse(
        success=result.get("success", False),
        message="PSP authorization rows loaded" if result.get("success") else result.get("error", "PSP authorization rows load failed"),
        data=result,
    )


@router.post("/underwritten-dowsure", response_model=ApiResponse)
async def mock_underwritten_dowsure(req: UnderwrittenDowsureRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_underwritten_status_dowsure,
        status=req.status,
        merchant_accounts=[item.model_dump() for item in req.merchant_accounts],
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/dowsure-credit-result", response_model=ApiResponse)
async def send_dowsure_credit_result(req: DowsureCreditResultRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.send_dowsure_credit_result_web,
        application_code=req.application_code,
        amount=req.amount,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/dowsure-esign-drawdown-result", response_model=ApiResponse)
async def send_dowsure_esign_drawdown_result(req: DowsureEsignDrawdownResultRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.send_dowsure_esign_drawdown_result_web,
        application_code=req.application_code,
        credit_contract_no=req.credit_contract_no,
        amount=req.amount,
        processing_fee=req.processing_fee,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/dowsure-repayment-result", response_model=ApiResponse)
async def send_dowsure_repayment_result(req: DowsureRepaymentResultRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.send_dowsure_repayment_result_web,
        application_code=req.application_code,
        loan_code=req.loan_code,
        payment_principal=req.payment_principal,
        payment_interest=req.payment_interest,
        payment_overdue_interest=req.payment_overdue_interest,
        deal_amount=req.deal_amount,
        surplus_principal=req.surplus_principal,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


@router.post("/dowsure-retry-callback", response_model=ApiResponse)
async def retry_dowsure_callback(req: DowsureRetryCallbackRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(service.retry_dowsure_callback_web)
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 16. Abandon(application.status)
@router.post("/application-abandon", response_model=ApiResponse)
async def mock_application_abandon(req: ApplicationAbandonRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_application_abandon_status,
        abandon_reason=req.abandon_reason,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 14. PSP 瀵偓婵绱橦SBC閿?
@router.post("/psp-hsbc-start", response_model=ApiResponse)
async def mock_psp_hsbc_start(req: PspHsbcStartRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_psp_start_status_hsbc,
        merchant_account_id=req.merchant_account_id,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)


# 15. PSP 鐎瑰本鍨氶敍鍦歋BC閿?
@router.post("/psp-hsbc-completed", response_model=ApiResponse)
async def mock_psp_hsbc_completed(req: PspHsbcCompletedRequest):
    service = _get_service(req.session_id, req.application_unique_id, req.username)
    result = await asyncio.to_thread(
        service.mock_psp_completed_status_hsbc,
        result=req.result,
        merchant_account_id=req.merchant_account_id,
    )
    msg = "operation succeeded" if result.get("success") else "operation failed"
    return _operation_response(req, req.__class__.__name__, result, msg)
