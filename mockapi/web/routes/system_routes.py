# -*- coding: utf-8 -*-
"""系统路由：环境列表、连接/断开、健康检查、枚举查询"""
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException

from web.models.requests import ConnectRequest
from web.models.responses import ApiResponse, ConnectResponse, EnumsResponse
from web.services.log_capture import ws_log_handler
from web.services.session_manager import session_manager

router = APIRouter(prefix="/api", tags=["系统"])


@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}


@router.get("/environments", response_model=ApiResponse)
async def list_environments():
    """获取支持的环境列表"""
    envs = ["sit", "uat", "dev", "preprod", "reg", "local"]
    return ApiResponse(success=True, message="获取环境列表成功", data=envs)


@router.get("/enums", response_model=ApiResponse)
async def list_enums():
    """获取所有枚举选项（供前端下拉框使用）"""
    data = EnumsResponse(
        environments=["sit", "uat", "dev", "preprod", "reg", "local"],
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
            "ETB-customer"
        ],
        returned_failure_reasons=[
            {"index": 1, "label": "不正确BRN"},
            {"index": 2, "label": "未能获取客户ID号码"},
            {"index": 3, "label": "ID 号码与 CR 记录不相符"},
            {"index": 4, "label": "未能通过公司结构校验"},
            {"index": 5, "label": "需要人工处理反洗钱验证"},
            {"index": 6, "label": "不正确统一社会信用代码"},
            {"index": 7, "label": "ID号码与公司登记资料不相符"},
        ],
        approved_rejection_reasons=[
            {"value": "fraud", "label": "fraud"},
            {"value": "others", "label": "others"},
        ],
        drawdown_failure_reasons=[
            {"index": 1, "code": "ER001", "label": "无有效银行账户"},
            {"index": 2, "code": "ER002", "label": "可用水位线 < 提款金额"},
            {"index": 3, "code": "ER003", "label": "未知错误"},
            {"index": 4, "code": "ER004", "label": "银行/支付服务提供商拒绝"},
            {"index": 5, "code": "ER005", "label": "逾期"},
        ],
        repayment_failure_reasons=[
            {"index": 1, "code": "ER001", "label": "银行汇票与实际还款金额不符"},
            {"index": 2, "code": "ER002", "label": "操作拒绝"},
        ],
        sp_update_failure_reasons=[
            {"index": 1, "label": "the seller location does not match the lender location"},
            {"index": 2, "label": "Active credit approval exists"},
            {"index": 3, "label": "offer already exists"},
            {"index": 4, "label": "others"},
        ],
        application_abandon_reasons=[
            {"value": "SellerCancelled", "label": "卖家取消"},
            {"value": "OfferExpired", "label": "报价过期"},
            {"value": "ApplicationInfoNotSubmitted", "label": "申请信息未提交"},
            {"value": "LenderOfferNotReturned", "label": "资方报价未返回"},
        ],
    )
    return ApiResponse(success=True, message="获取枚举成功", data=data.model_dump())


@router.post("/connect", response_model=ApiResponse)
async def connect(req: ConnectRequest):
    """连接数据库 + 创建会话"""
    try:
        ctx = await asyncio.to_thread(session_manager.create_session, req.env, req.phone_number)
        resp = ConnectResponse(
            session_id=ctx.session_id,
            env=ctx.env,
            phone_number=ctx.phone_number,
            merchant_id=ctx.merchant_id,
            preferred_currency=ctx.preferred_currency,
        )
        return ApiResponse(success=True, message="连接成功", data=resp.model_dump())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"连接失败: {str(e)}")


@router.post("/disconnect", response_model=ApiResponse)
async def disconnect(session_id: str):
    """断开会话"""
    destroyed = session_manager.destroy_session(session_id)
    if destroyed:
        return ApiResponse(success=True, message="会话已断开")
    raise HTTPException(status_code=404, detail="会话不存在")


@router.get("/sessions", response_model=ApiResponse)
async def list_sessions():
    """列出所有活跃会话"""
    sessions = session_manager.list_sessions()
    return ApiResponse(success=True, message=f"共 {len(sessions)} 个活跃会话", data=sessions)


@router.get("/logs", response_model=ApiResponse)
async def query_logs(
    keyword: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 500,
):
    logs = ws_log_handler.query_logs(
        keyword=keyword,
        start_time=start_time,
        end_time=end_time,
        session_id=session_id,
        limit=limit,
    )
    return ApiResponse(success=True, message=f"共 {len(logs)} 条匹配日志", data=logs)

