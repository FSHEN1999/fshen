# -*- coding: utf-8 -*-
"""Pydantic request models."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ConnectRequest(BaseModel):
    env: Literal["sit", "uat", "dev", "preprod", "reg", "local"]
    phone_number: str = Field(..., pattern=r"^\d{8}$|^\d{11}$")


class RegisterRequest(BaseModel):
    env: Literal["sit", "uat", "dev", "preprod", "reg", "local"]
    journey: Literal["200K", "500K", "2000K"] = "500K"
    currency: Literal["CNY", "USD"] = "USD"
    offline: bool = False
    funder_resource: Literal["FUNDPARK", "HSBC", "DOWSURE"] = "FUNDPARK"


class RegisterAndRunMultiShopRequest(RegisterRequest):
    sp_status: Literal["SUCCESS", "FAIL"] = "SUCCESS"


class MockBaseRequest(BaseModel):
    session_id: str


class LinkSp3plRequest(MockBaseRequest):
    pass


class UnderwrittenRequest(MockBaseRequest):
    amount: int = Field(..., gt=0)
    status: Literal["APPROVED", "REJECTED"]


class DowsureMerchantAccountLimit(BaseModel):
    merchantAccountId: str = Field(..., min_length=1)
    merchantAccountLimit: Optional[float] = Field(None, ge=0)


class UnderwrittenDowsureRequest(MockBaseRequest):
    amount: Optional[float] = Field(None, ge=0)
    status: Literal["APPROVED", "REJECTED"]
    merchant_accounts: list[DowsureMerchantAccountLimit] = Field(default_factory=list)


class ApprovedOfferRequest(MockBaseRequest):
    amount: int = Field(..., gt=0)
    status: Literal["APPROVED", "RETURNED", "REJECTED"]
    rejection_reason: Optional[Literal["fraud", "others"]] = None
    failure_reason_index: Optional[int] = Field(None, ge=1, le=7)


class PspStartRequest(MockBaseRequest):
    status: Literal["PROCESSING", "FAIL", "INITIAL"]


class PspCompletedRequest(MockBaseRequest):
    status: Literal["SUCCESS", "FAIL", "INITIAL"]


class EsignRequest(MockBaseRequest):
    signed_amount: int = Field(..., gt=0)
    status: Literal["SUCCESS", "FAIL"]


class DrawdownRequest(MockBaseRequest):
    amount: float = Field(..., gt=0)
    status: Literal["APPROVED", "REJECTED"]
    failure_reason_index: Optional[int] = Field(None, ge=1, le=5)


class RepaymentStartRequest(MockBaseRequest):
    principal_amount: float = Field(..., gt=0)
    outstanding_amount: float = Field(..., ge=0)


class RepaymentRequest(MockBaseRequest):
    principal_amount: float = Field(..., gt=0)
    outstanding_amount: float = Field(..., ge=0)
    status: Literal["Success", "Failure"]
    failure_reason_index: Optional[int] = Field(None, ge=1, le=2)


class MultiShopBindingRequest(MockBaseRequest):
    state: str = Field(..., min_length=1)


class SpStatusUpdateRequest(MockBaseRequest):
    platform_seller_id: Optional[str] = None
    status: Literal["SUCCESS", "FAIL"]
    failure_reason_index: Optional[int] = Field(None, ge=1, le=4)


class MultiShop3plRedirectRequest(MockBaseRequest):
    pass


class SystemEventRequest(MockBaseRequest):
    event_type: Literal[
        "EXCEPTION-APPLICATION-CREATION",
        "INDICATIVE-OFFER",
        "IN-PROCESS",
        "ERROR",
        "ETB-customer",
    ]
    application_unique_id: Optional[str] = None
    error_code: Optional[Literal["B-6003", "B-6005"]] = None


class ApplicationAbandonRequest(MockBaseRequest):
    abandon_reason: Literal[
        "SellerCancelled",
        "OfferExpired",
        "ApplicationInfoNotSubmitted",
        "LenderOfferNotReturned",
    ]


class PspHsbcStartRequest(MockBaseRequest):
    pass


class PspHsbcCompletedRequest(MockBaseRequest):
    result: Literal["SUCCESS", "FAIL"]


class AiChatMessage(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str


class AiChatContext(BaseModel):
    active_session_id: Optional[str] = None
    session: Optional[dict] = None
    selected_env: Optional[str] = None
    selected_register_env: Optional[str] = None
    selected_currency: Optional[str] = None
    preferred_currency: Optional[str] = None
    selected_journey: Optional[str] = None
    recent_logs: list[dict] = Field(default_factory=list)
    recent_activities: list[dict] = Field(default_factory=list)


class AiChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    history: list[AiChatMessage] = Field(default_factory=list)
    context: AiChatContext = Field(default_factory=AiChatContext)
