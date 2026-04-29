# -*- coding: utf-8 -*-
"""Pydantic请求/响应模型"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator
import re


# ========== 通用响应 ==========

class ApiResponse(BaseModel):
    code: int = 0
    message: str = "成功"
    data: Optional[dict] = None


# ========== 认证相关 ==========

class SmsCodeRequest(BaseModel):
    phone: str = Field(..., description="手机号")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确，需为11位国内手机号")
        return v


class SmsLoginRequest(BaseModel):
    phone: str
    code: str = Field(..., min_length=6, max_length=6)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v


class PasswordLoginRequest(BaseModel):
    phone: str
    password: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v


class RegisterRequest(BaseModel):
    phone: str
    code: str = Field(..., min_length=6, max_length=6)
    password: str = Field(..., min_length=8, max_length=16)
    confirm_password: str
    email: Optional[str] = None
    invite_code: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if not re.search(r"[a-zA-Z]", v) or not re.search(r"\d", v):
            raise ValueError("密码必须包含字母和数字")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if v and not re.match(r"^[\w.+-]+@[\w-]+\.[\w.]+$", v):
            raise ValueError("邮箱格式不正确")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # 秒


# ========== 用户信息 ==========

class UserProfileRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="姓名")
    id_card: str = Field(..., min_length=18, max_length=18, description="身份证号")
    gender: str = Field(..., description="性别")
    age: Optional[int] = Field(None, ge=18, le=120)
    income_range: str = Field(..., description="收入范围")
    income_source: str = Field(..., description="收入来源")
    address: str = Field(..., description="常用居住地址")
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    occupation: Optional[str] = None

    @field_validator("id_card")
    @classmethod
    def validate_id_card(cls, v):
        if not re.match(r"^\d{17}[\dXx]$", v):
            raise ValueError("身份证号格式不正确")
        return v


class UserProfileResponse(BaseModel):
    name: Optional[str] = None
    id_card: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    income_range: Optional[str] = None
    income_source: Optional[str] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    occupation: Optional[str] = None
    is_complete: bool = False

    class Config:
        from_attributes = True


# ========== 股东信息 ==========

class ShareholderItem(BaseModel):
    name: str = Field(..., description="股东姓名")
    id_card: str = Field(..., min_length=18, max_length=18, description="身份证号")
    share_ratio: float = Field(..., gt=0, le=100, description="持股比例")
    investment_type: str = Field(..., description="出资方式")
    investment_amount: float = Field(..., gt=0, description="出资额")
    phone: Optional[str] = None
    position: Optional[str] = None
    investment_date: Optional[str] = None

    @field_validator("id_card")
    @classmethod
    def validate_id_card(cls, v):
        if not re.match(r"^\d{17}[\dXx]$", v):
            raise ValueError("股东身份证号格式不正确")
        return v


class ShareholderRequest(BaseModel):
    shareholders: list[ShareholderItem] = Field(..., min_length=1)

    @field_validator("shareholders")
    @classmethod
    def validate_total_ratio(cls, v):
        total = sum(s.share_ratio for s in v)
        if abs(total - 100) > 0.01:
            raise ValueError(f"所有股东持股比例之和必须为100%，当前为{total}%")
        return v


# ========== 额度评估 ==========

class QuotaResponse(BaseModel):
    estimated_quota: float = Field(..., description="预估借款额度")
    suggested_period: int = Field(..., description="建议还款周期（月）")
    interest_rate: float = Field(..., description="借款利率")
    risk_level: str = Field(..., description="风险等级")
    risk_note: Optional[str] = None
    valid_until: str = Field(..., description="额度有效期")
    assessment_basis: str = "基于您提交的信息测算"


class LoanApplyRequest(BaseModel):
    loan_amount: float = Field(..., gt=0, description="申请借款金额")
    loan_purpose: str = Field(..., description="借款用途")


# ========== 审批 ==========

class ApprovalStatusResponse(BaseModel):
    status: str = Field(..., description="审批状态")
    status_label: str = Field(..., description="状态显示文本")
    progress_note: Optional[str] = None
    reject_reason: Optional[str] = None
    estimated_quota: Optional[float] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
