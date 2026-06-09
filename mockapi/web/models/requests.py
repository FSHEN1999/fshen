# -*- coding: utf-8 -*-
"""Pydantic request models."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ConnectRequest(BaseModel):
    env: Literal["sit", "uat", "dev", "preprod", "reg", "local"]
    phone_number: str = Field(..., pattern=r"^\d{8}$|^\d{11}$")
    username: Optional[str] = None


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=1, max_length=200)


class ContactIssueCreateRequest(BaseModel):
    created_by: Optional[str] = None
    issue: str = Field(..., min_length=1)
    env: Optional[str] = None
    phone_number: Optional[str] = None
    session_id: Optional[str] = None
    merchant_id: Optional[str] = None


class ContactIssueReplyRequest(BaseModel):
    reply: str = Field(..., min_length=1)
    replied_by: Optional[str] = None


class RegisterRequest(BaseModel):
    env: Literal["sit", "uat", "dev", "preprod", "reg", "local"]
    journey: Literal["200K", "500K", "2000K"] = "500K"
    currency: Literal["CNY", "USD"] = "USD"
    offline: bool = False
    funder_resource: Literal["FUNDPARK", "HSBC", "DOWSURE"] = "FUNDPARK"
    username: Optional[str] = None
    operation_name: Optional[str] = None


class RegisterAndRunMultiShopRequest(RegisterRequest):
    sp_status: Literal["SUCCESS", "FAIL"] = "SUCCESS"


class MockBaseRequest(BaseModel):
    session_id: str
    application_unique_id: Optional[str] = None
    username: Optional[str] = None
    operation_name: Optional[str] = None


class LinkSp3plRequest(MockBaseRequest):
    pass


class UnderwrittenRequest(MockBaseRequest):
    amount: int = Field(..., gt=0)
    status: Literal["APPROVED", "REJECTED"]


class DowsureMerchantAccountLimit(BaseModel):
    merchantAccountId: str = Field(..., min_length=1)
    merchantAccountLimit: Optional[float] = Field(None, ge=0)


class UnderwrittenDowsureRequest(MockBaseRequest):
    status: Literal["APPROVED", "REJECTED"]
    merchant_accounts: list[DowsureMerchantAccountLimit] = Field(default_factory=list)


class DowsureCreditResultRequest(MockBaseRequest):
    application_code: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)


class DowsureEsignDrawdownResultRequest(MockBaseRequest):
    application_code: Optional[str] = None
    credit_contract_no: Optional[str] = None
    amount: float = Field(..., gt=0)
    processing_fee: float = Field(..., ge=0)


class DowsureRepaymentResultRequest(MockBaseRequest):
    application_code: Optional[str] = None
    loan_code: Optional[str] = None
    payment_principal: float = Field(..., ge=0)
    payment_interest: float = Field(..., ge=0)
    payment_overdue_interest: float = Field(..., ge=0)
    deal_amount: float = Field(..., ge=0)
    surplus_principal: float = Field(..., ge=0)


class DowsureRetryCallbackRequest(MockBaseRequest):
    pass


class ApprovedOfferRequest(MockBaseRequest):
    amount: int = Field(..., gt=0)
    status: Literal["APPROVED", "RETURNED", "REJECTED"]
    rejection_reason: Optional[Literal["fraud", "others"]] = None
    failure_reason_index: Optional[int] = Field(None, ge=1, le=7)


class PspStartRequest(MockBaseRequest):
    status: Literal["PROCESSING", "FAIL", "INITIAL"]
    merchant_account_id: Optional[str] = None


class PspCompletedRequest(MockBaseRequest):
    status: Literal["SUCCESS", "FAIL", "INITIAL"]
    merchant_account_id: Optional[str] = None


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


class CreateApplicationContextRequest(MockBaseRequest):
    journey: Optional[Literal["200K", "500K", "2000K"]] = None
    currency: Optional[Literal["CNY", "USD"]] = None
    funder_resource: Optional[Literal["FUNDPARK", "HSBC", "DOWSURE"]] = None
    tier_code: Optional[int] = Field(None, ge=1)
    offer_id: Optional[str] = None


class FpApplicationStepRequest(MockBaseRequest):
    journey: Optional[Literal["200K", "500K", "2000K"]] = None
    currency: Optional[Literal["CNY", "USD"]] = None
    funder_resource: Optional[Literal["FUNDPARK", "HSBC", "DOWSURE"]] = None
    nameCn: Optional[str] = None
    addressDetail: Optional[str] = None


class ShopPerformanceUpdateRequest(MockBaseRequest):
    offer_id: Optional[str] = None


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
    merchant_account_id: Optional[str] = None


class PspHsbcCompletedRequest(MockBaseRequest):
    result: Literal["SUCCESS", "FAIL"]
    merchant_account_id: Optional[str] = None


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
