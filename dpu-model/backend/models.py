# -*- coding: utf-8 -*-
"""SQLAlchemy数据模型"""

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, Enum, ForeignKey, Boolean
)
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String(11), unique=True, nullable=False, index=True, comment="手机号")
    password_hash = Column(String(128), nullable=False, comment="密码哈希")
    email = Column(String(128), nullable=True, comment="邮箱")
    invite_code = Column(String(32), nullable=True, comment="邀请码")
    is_active = Column(Boolean, default=True, comment="是否激活")
    login_failures = Column(Integer, default=0, comment="连续登录失败次数")
    locked_until = Column(DateTime, nullable=True, comment="锁定截止时间")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    profile = relationship("UserProfile", back_populates="user", uselist=False)
    applications = relationship("Application", back_populates="user")


class UserProfile(Base):
    """用户个人信息表"""
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    name = Column(String(64), nullable=True, comment="姓名")
    id_card = Column(String(18), nullable=True, comment="身份证号")
    gender = Column(String(4), nullable=True, comment="性别")
    age = Column(Integer, nullable=True, comment="年龄")
    income_range = Column(String(32), nullable=True, comment="收入范围")
    income_source = Column(String(64), nullable=True, comment="收入来源")
    address = Column(String(256), nullable=True, comment="常用居住地址")
    emergency_contact_name = Column(String(64), nullable=True, comment="紧急联系人姓名")
    emergency_contact_phone = Column(String(11), nullable=True, comment="紧急联系人手机号")
    occupation = Column(String(64), nullable=True, comment="职业信息")
    is_complete = Column(Boolean, default=False, comment="信息是否填写完整")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="profile")


class Shareholder(Base):
    """股东信息表"""
    __tablename__ = "shareholders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    name = Column(String(64), nullable=False, comment="股东姓名")
    id_card = Column(String(18), nullable=False, comment="股东身份证号")
    share_ratio = Column(Float, nullable=False, comment="持股比例")
    investment_type = Column(String(32), nullable=False, comment="出资方式")
    investment_amount = Column(Float, nullable=False, comment="出资额")
    phone = Column(String(11), nullable=True, comment="股东联系电话")
    position = Column(String(32), nullable=True, comment="任职情况")
    investment_date = Column(String(32), nullable=True, comment="出资日期")
    created_at = Column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="shareholders")


class Application(Base):
    """借款申请表"""
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    loan_amount = Column(Float, nullable=True, comment="申请借款金额")
    loan_purpose = Column(String(128), nullable=True, comment="借款用途")
    estimated_quota = Column(Float, nullable=True, comment="预估额度")
    suggested_period = Column(Integer, nullable=True, comment="建议还款周期（月）")
    interest_rate = Column(Float, nullable=True, comment="借款利率")
    risk_level = Column(String(10), nullable=True, comment="风险等级：高/中/低")
    risk_note = Column(Text, nullable=True, comment="风险提示")
    quota_valid_until = Column(DateTime, nullable=True, comment="额度有效期")
    status = Column(
        String(20), default="draft",
        comment="状态：draft/info_submitted/shareholder_submitted/assessing/approved/rejected/pending_material"
    )
    reject_reason = Column(Text, nullable=True, comment="驳回原因")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="applications")
    shareholders = relationship("Shareholder", back_populates="application", cascade="all, delete-orphan")


class AuditLog(Base):
    """审计日志表"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True)
    action = Column(String(64), nullable=False, comment="操作类型")
    detail = Column(Text, nullable=True, comment="操作详情")
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
