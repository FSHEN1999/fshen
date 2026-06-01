# -*- coding: utf-8 -*-
"""Mock 操作路由：15 个 Mock 端点"""
import asyncio
from fastapi import APIRouter, HTTPException

from web.models.requests import (
    LinkSp3plRequest, UnderwrittenRequest, ApprovedOfferRequest,
    UnderwrittenDowsureRequest,
    PspStartRequest, PspCompletedRequest, EsignRequest, DrawdownRequest,
    RepaymentStartRequest, RepaymentRequest,
    MultiShopBindingRequest, SpStatusUpdateRequest, MultiShop3plRedirectRequest,
    SystemEventRequest, PspHsbcStartRequest, PspHsbcCompletedRequest,
    ApplicationAbandonRequest,
)
from web.models.responses import ApiResponse
from web.services.session_manager import session_manager

router = APIRouter(prefix="/api/mock", tags=["Mock操作"])


def _get_service(session_id: str):
    """获取会话中的 service 实例"""
    ctx = session_manager.get_session(session_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="会话不存在或已过期，请重新连接")
    return ctx.service


# 1. SP-3PL 关联
@router.post("/link-sp-3pl", response_model=ApiResponse)
async def mock_link_sp_3pl(req: LinkSp3plRequest):
    service = _get_service(req.session_id)
    result = await asyncio.to_thread(service.mock_link_sp_3pl_shop)
    return ApiResponse(success=result.get("success", False), message="SP-3PL关联完成", data=result)


# 2. 核保
@router.post("/underwritten", response_model=ApiResponse)
async def mock_underwritten(req: UnderwrittenRequest):
    service = _get_service(req.session_id)
    result = await asyncio.to_thread(service.mock_underwritten_status, amount=req.amount, status=req.status)
    msg = f"核保状态更新{'成功' if result.get('success') else '失败'}"
    return ApiResponse(success=result.get("success", False), message=msg, data=result)


# 3. 审批
@router.post("/approved-offer", response_model=ApiResponse)
async def mock_approved_offer(req: ApprovedOfferRequest):
    service = _get_service(req.session_id)
    result = await asyncio.to_thread(
        service.mock_approved_offer_status,
        amount=req.amount, status=req.status,
        failure_reason_index=req.failure_reason_index,
        rejection_reason=req.rejection_reason,
    )
    msg = f"审批状态更新{'成功' if result.get('success') else '失败'}"
    return ApiResponse(success=result.get("success", False), message=msg, data=result)


# 4. PSP 开始
@router.post("/psp-start", response_model=ApiResponse)
async def mock_psp_start(req: PspStartRequest):
    service = _get_service(req.session_id)
    result = await asyncio.to_thread(service.mock_psp_start_status, status=req.status)
    msg = f"PSP开始状态更新{'成功' if result.get('success') else '失败'}"
    return ApiResponse(success=result.get("success", False), message=msg, data=result)


# 5. PSP 完成
@router.post("/psp-completed", response_model=ApiResponse)
async def mock_psp_completed(req: PspCompletedRequest):
    service = _get_service(req.session_id)
    result = await asyncio.to_thread(service.mock_psp_completed_status, status=req.status)
    msg = f"PSP完成状态更新{'成功' if result.get('success') else '失败'}"
    return ApiResponse(success=result.get("success", False), message=msg, data=result)


# 6. 电子签
@router.post("/esign", response_model=ApiResponse)
async def mock_esign(req: EsignRequest):
    service = _get_service(req.session_id)
    result = await asyncio.to_thread(
        service.mock_esign_status, signed_amount=req.signed_amount, status=req.status
    )
    msg = f"电子签状态更新{'成功' if result.get('success') else '失败'}"
    return ApiResponse(success=result.get("success", False), message=msg, data=result)


# 7. 放款
@router.post("/drawdown", response_model=ApiResponse)
async def mock_drawdown(req: DrawdownRequest):
    service = _get_service(req.session_id)
    result = await asyncio.to_thread(
        service.mock_drawdown_status,
        amount=req.amount, status=req.status,
        failure_reason_index=req.failure_reason_index
    )
    msg = f"放款状态更新{'成功' if result.get('success') else '失败'}"
    return ApiResponse(success=result.get("success", False), message=msg, data=result)


# 8. 还款开始
@router.post("/repayment-start", response_model=ApiResponse)
async def mock_repayment_start(req: RepaymentStartRequest):
    service = _get_service(req.session_id)
    result = await asyncio.to_thread(
        service.mock_repayment_start_status,
        principal_amount=req.principal_amount,
        outstanding_amount=req.outstanding_amount
    )
    msg = f"还款开始请求{'成功' if result.get('success') else '失败'}"
    return ApiResponse(success=result.get("success", False), message=msg, data=result)


# 9. 还款
@router.post("/repayment", response_model=ApiResponse)
async def mock_repayment(req: RepaymentRequest):
    service = _get_service(req.session_id)
    result = await asyncio.to_thread(
        service.mock_repayment_status,
        principal_amount=req.principal_amount,
        outstanding_amount=req.outstanding_amount,
        status=req.status,
        failure_reason_index=req.failure_reason_index
    )
    msg = f"还款请求{'成功' if result.get('success') else '失败'}"
    return ApiResponse(success=result.get("success", False), message=msg, data=result)


# 10. 多店铺 SP 绑定
@router.post("/multi-shop-binding", response_model=ApiResponse)
async def mock_multi_shop_binding(req: MultiShopBindingRequest):
    service = _get_service(req.session_id)
    result = await asyncio.to_thread(service.mock_multi_shop_binding, state=req.state)
    msg = f"SP店铺绑定{'成功' if result.get('success') else '失败'}"
    return ApiResponse(success=result.get("success", False), message=msg, data=result)


# 11. SP 状态更新
@router.post("/sp-status-update", response_model=ApiResponse)
async def mock_sp_status_update(req: SpStatusUpdateRequest):
    service = _get_service(req.session_id)
    result = await asyncio.to_thread(
        service.mock_sp_status_update,
        platform_seller_id=req.platform_seller_id,
        status=req.status,
        failure_reason_index=req.failure_reason_index
    )
    msg = f"SP状态更新{'成功' if result.get('success') else '失败'}"
    return ApiResponse(success=result.get("success", False), message=msg, data=result)


# 12. 3PL 重定向
@router.post("/multi-shop-3pl-redirect", response_model=ApiResponse)
async def mock_multi_shop_3pl_redirect(req: MultiShop3plRedirectRequest):
    service = _get_service(req.session_id)
    result = await asyncio.to_thread(service.mock_multi_shop_3pl_redirect)
    msg = f"3PL重定向{'成功' if result.get('success') else '失败'}"
    return ApiResponse(success=result.get("success", False), message=msg, data=result)


# 13. 系统事件通知
@router.post("/system-event", response_model=ApiResponse)
async def mock_system_event(req: SystemEventRequest):
    service = _get_service(req.session_id)
    result = await asyncio.to_thread(
        service.mock_system_event_notification,
        event_type=req.event_type,
        application_unique_id=req.application_unique_id,
        error_code=req.error_code
    )
    msg = f"系统事件通知{'成功' if result.get('success') else '失败'}"
    return ApiResponse(success=result.get("success", False), message=msg, data=result)


@router.get("/dowsure-merchant-accounts", response_model=ApiResponse)
async def list_dowsure_merchant_accounts(session_id: str):
    service = _get_service(session_id)
    result = await asyncio.to_thread(service.get_dowsure_merchant_accounts)
    return ApiResponse(
        success=result.get("success", False),
        message="DOWSURE店铺列表已加载" if result.get("success") else result.get("error", "DOWSURE店铺列表加载失败"),
        data=result,
    )


@router.post("/underwritten-dowsure", response_model=ApiResponse)
async def mock_underwritten_dowsure(req: UnderwrittenDowsureRequest):
    service = _get_service(req.session_id)
    result = await asyncio.to_thread(
        service.mock_underwritten_status_dowsure,
        amount=req.amount,
        status=req.status,
        merchant_accounts=[item.model_dump() for item in req.merchant_accounts],
    )
    msg = f"DOWSURE核保状态更新{'成功' if result.get('success') else '失败'}"
    return ApiResponse(success=result.get("success", False), message=msg, data=result)


# 16. Abandon(application.status)
@router.post("/application-abandon", response_model=ApiResponse)
async def mock_application_abandon(req: ApplicationAbandonRequest):
    service = _get_service(req.session_id)
    result = await asyncio.to_thread(
        service.mock_application_abandon_status,
        abandon_reason=req.abandon_reason,
    )
    msg = f"Abandon状态通知{'成功' if result.get('success') else '失败'}"
    return ApiResponse(success=result.get("success", False), message=msg, data=result)


# 14. PSP 开始（HSBC）
@router.post("/psp-hsbc-start", response_model=ApiResponse)
async def mock_psp_hsbc_start(req: PspHsbcStartRequest):
    service = _get_service(req.session_id)
    result = await asyncio.to_thread(service.mock_psp_start_status_hsbc)
    msg = f"PSP开始（HSBC）{'成功' if result.get('success') else '失败'}"
    return ApiResponse(success=result.get("success", False), message=msg, data=result)


# 15. PSP 完成（HSBC）
@router.post("/psp-hsbc-completed", response_model=ApiResponse)
async def mock_psp_hsbc_completed(req: PspHsbcCompletedRequest):
    service = _get_service(req.session_id)
    result = await asyncio.to_thread(service.mock_psp_completed_status_hsbc, result=req.result)
    msg = f"PSP完成（HSBC）{'成功' if result.get('success') else '失败'}"
    return ApiResponse(success=result.get("success", False), message=msg, data=result)
