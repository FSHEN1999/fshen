"""SQLAlchemy models for the treehole app."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    display_name = Column(String(64), nullable=True)
    password_hash = Column(String(256), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    entries = relationship("Entry", back_populates="user")
    conversations = relationship("Conversation", back_populates="user")
    sessions = relationship("AuthSession", back_populates="user", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    visitor_id = Column(String(96), nullable=True, index=True)
    status = Column(String(16), default="active", nullable=False, index=True)
    closed_reason = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    closed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="conversations")
    entries = relationship("Entry", back_populates="conversation")


class Entry(Base):
    __tablename__ = "entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(64), ForeignKey("conversations.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    visitor_id = Column(String(96), nullable=True, index=True)
    mood = Column(String(32), nullable=False)
    content = Column(Text, nullable=False)
    ai_reply = Column(Text, nullable=False)
    summary = Column(String(160), nullable=False)
    emotion_label = Column(String(64), nullable=False)
    analysis_source = Column(String(24), default="fallback", nullable=False, index=True)
    risk_level = Column(String(16), default="low", nullable=False, index=True)
    risk_flags = Column(Text, default="[]", nullable=False)
    status = Column(String(24), default="visible", nullable=False, index=True)
    is_farewell = Column(Boolean, default=False, nullable=False)
    manual_reply = Column(Text, nullable=True)
    admin_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="entries")
    conversation = relationship("Conversation", back_populates="entries")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    role = Column(String(16), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    user = relationship("User", back_populates="sessions")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_role = Column(String(16), nullable=False)
    actor_id = Column(Integer, nullable=True)
    action = Column(String(64), nullable=False)
    target_type = Column(String(32), nullable=True)
    target_id = Column(Integer, nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
