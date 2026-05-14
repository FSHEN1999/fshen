"""Request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


EntryStatus = Literal["visible", "pending_review", "hidden", "deleted"]
RiskLevel = Literal["low", "medium", "high"]
ConversationStatus = Literal["active", "closed"]


class UserPublic(BaseModel):
    id: int
    username: str
    display_name: str | None = None


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=72)
    display_name: str | None = Field(None, max_length=64)

    @field_validator("username")
    @classmethod
    def clean_username(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("用户名不能为空")
        return value


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=72)


class AuthResponse(BaseModel):
    token: str
    role: Literal["user", "admin"]
    user: UserPublic | None = None


class EntryCreateRequest(BaseModel):
    conversation_id: str | None = Field(None, max_length=64)
    visitor_id: str | None = Field(None, max_length=96)
    mood: str = Field(..., min_length=1, max_length=32)
    content: str = Field(..., min_length=2, max_length=2000)

    @field_validator("content", "mood")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("内容不能为空")
        return value


class EntryResponse(BaseModel):
    id: int
    conversation_id: str
    conversation_status: ConversationStatus
    visitor_id: str | None
    mood: str
    content: str
    ai_reply: str
    summary: str
    emotion_label: str
    analysis_source: str
    risk_level: RiskLevel
    risk_flags: list[str]
    status: EntryStatus
    is_farewell: bool
    manual_reply: str | None
    created_at: datetime
    updated_at: datetime


class ConversationResponse(BaseModel):
    id: str
    status: ConversationStatus
    closed_reason: str | None = None
    visitor_id: str | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    messages: list[EntryResponse] = Field(default_factory=list)


class ConversationCloseRequest(BaseModel):
    visitor_id: str | None = Field(None, max_length=96)


class RecentEntryResponse(BaseModel):
    id: int
    mood: str
    summary: str
    emotion_label: str
    analysis_source: str
    created_at: datetime


class AdminEntryResponse(EntryResponse):
    username: str | None = None
    admin_note: str | None = None
    deleted_at: datetime | None = None


class AdminEntryPatchRequest(BaseModel):
    status: EntryStatus | None = None
    manual_reply: str | None = Field(None, max_length=2000)
    admin_note: str | None = Field(None, max_length=2000)

    @field_validator("manual_reply", "admin_note")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None
