# -*- coding: utf-8 -*-
"""Pydantic 请求模型定义"""
from typing import Optional, Literal

from pydantic import BaseModel, Field


class ConnectRequest(BaseModel):
    """连接请求：选择环境 + 输入手机号"""
    env: Literal["sit", "uat", "dev", "preprod", "reg", "local"]
    phone_number: str = Field(..., pattern=r"^\d{8}$|^\d{11}$", description="8位或11位数字手机号")


class RegisterRequest(BaseModel):
    """注册新账号请求"""
    env: Literal["sit", "uat", "dev", "preprod", "reg", "local"]
    journey: Literal["200K", "500K", "2000K"] = "500K"
    currency: Literal["CNY", "USD"] = "USD"
    offline: bool = False


# ---- Mock 操作请求（全部携带 session_id） ----

class MockBaseRequest(BaseModel):
    """Mock 操作基类"""
    session_id: str


class LinkSp3plRequest(MockBaseRequest):
    """SP-3PL 关联（无额外参数）"""
    pass


class UnderwrittenRequest(MockBaseRequest):
    """核保状态"""
    amount: int = Field(..., gt=0, description="评估额度")
    status: Literal["APPROVED", "REJECTED"]


class ApprovedOfferRequest(MockBaseRequest):
    """审批状态"""
    amount: int = Field(..., gt=0, description="授信额度")
    status: Literal["APPROVED", "RETURNED", "REJECTED"]
    failure_reason_index: Optional[int] = Field(None, ge=1, le=5, description="退回原因编号(1-5)，RETURNED时必填")


class PspStartRequest(MockBaseRequest):
    """PSP 开始"""
    status: Literal["PROCESSING", "FAIL", "INITIAL"]


class PspCompletedRequest(MockBaseRequest):
    """PSP 完成"""
    status: Literal["SUCCESS", "FAIL", "INITIAL"]


class EsignRequest(MockBaseRequest):
    """电子签"""
    signed_amount: int = Field(..., gt=0, description="签约额度")
    status: Literal["SUCCESS", "FAIL"]


class DrawdownRequest(MockBaseRequest):
    """放款"""
    amount: float = Field(..., gt=0, description="放款额度")
    status: Literal["APPROVED", "REJECTED"]
    failure_reason_index: Optional[int] = Field(None, ge=1, le=5, description="放款失败原因编号(1-5)，REJECTED时必填")


class RepaymentStartRequest(MockBaseRequest):
    """还款开始"""
    principal_amount: float = Field(..., gt=0, description="还款本金")
    outstanding_amount: float = Field(..., ge=0, description="未结清金额")


class RepaymentRequest(MockBaseRequest):
    """还款"""
    principal_amount: float = Field(..., gt=0, description="还款本金")
    outstanding_amount: float = Field(..., ge=0, description="未结清金额")
    status: Literal["Success", "Failure"]
    failure_reason_index: Optional[int] = Field(None, ge=1, le=2, description="失败原因编号(1-2)，Failure时必填")


class MultiShopBindingRequest(MockBaseRequest):
    """多店铺 SP 绑定"""
    state: str = Field(..., min_length=1, description="state 值")


class SpStatusUpdateRequest(MockBaseRequest):
    """SP 状态更新"""
    platform_seller_id: Optional[str] = Field(None, description="platform_seller_id，为空时使用已生成的")
    status: Literal["SUCCESS", "FAIL"]
    failure_reason_index: Optional[int] = Field(None, ge=1, le=3, description="失败原因编号(1-3)，FAIL时必填")


class MultiShop3plRedirectRequest(MockBaseRequest):
    """3PL 重定向（无额外参数）"""
    pass


class SystemEventRequest(MockBaseRequest):
    """系统事件通知"""
    event_type: Literal[
        "EXCEPTION-APPLICATION-CREATION",
        "INDICATIVE-OFFER",
        "IN-PROCESS",
        "ERROR",
        "ETB-customer"
    ]
    application_unique_id: Optional[str] = None
    error_code: Optional[Literal["B-6003", "B-6005"]] = None


class PspHsbcStartRequest(MockBaseRequest):
    """PSP 开始（HSBC）（无额外参数）"""
    pass


class PspHsbcCompletedRequest(MockBaseRequest):
    """PSP 完成（HSBC）"""
    result: Literal["SUCCESS", "FAIL"]
