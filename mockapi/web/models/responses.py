# -*- coding: utf-8 -*-
"""统一响应模型定义"""
import time
from typing import Any, Optional

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    """统一 API 响应"""
    success: bool
    message: str
    data: Optional[Any] = None
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))


class ConnectResponse(BaseModel):
    """连接成功响应"""
    session_id: str
    env: str
    phone_number: str
    merchant_id: Optional[str] = None
    preferred_currency: str = "USD"
    application_unique_id: Optional[str] = None
    selected_application_unique_id: Optional[str] = None
    applications: list[dict] = Field(default_factory=list)
    finance_product_currency: Optional[str] = None
    lender_code: Optional[str] = None
    application_status: Optional[str] = None


class RegisterResponse(BaseModel):
    """注册成功响应"""
    phone_number: str
    email: str
    offer_id: Optional[str] = None
    redirect_url: Optional[str] = None


class EnumsResponse(BaseModel):
    """枚举选项响应（供前端下拉框使用）"""
    environments: list[str]
    ai_sql_data_sources: list[str] = Field(default_factory=list)
    journeys: list[str]
    currencies: list[str]
    funder_resources: list[str]
    underwritten_statuses: list[str]
    approved_offer_statuses: list[str]
    esign_statuses: list[str]
    drawdown_statuses: list[str]
    psp_start_statuses: list[str]
    psp_completed_statuses: list[str]
    repayment_statuses: list[str]
    system_event_types: list[str]
    returned_failure_reasons: list[dict]
    approved_rejection_reasons: list[dict]
    drawdown_failure_reasons: list[dict]
    repayment_failure_reasons: list[dict]
    sp_update_failure_reasons: list[dict]
    application_abandon_reasons: list[dict]
