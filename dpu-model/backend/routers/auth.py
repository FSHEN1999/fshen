# -*- coding: utf-8 -*-
"""认证路由：登录、注册、验证码"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt

from database import get_db
from models import User, UserProfile, AuditLog
from schemas import (
    SmsCodeRequest, SmsLoginRequest, PasswordLoginRequest,
    RegisterRequest, TokenResponse, ApiResponse,
)
from config import (
    JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_DAYS,
    LOGIN_MAX_FAILURES, LOGIN_LOCK_MINUTES,
)
from services.sms import sms_service

router = APIRouter(prefix="/api/auth", tags=["认证"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_token(user_id: int) -> tuple[str, int]:
    """生成JWT令牌"""
    expire_seconds = JWT_EXPIRE_DAYS * 86400
    expire = datetime.utcnow() + timedelta(seconds=expire_seconds)
    payload = {"sub": str(user_id), "exp": expire}
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token, expire_seconds


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(lambda: None),  # 占位，实际由中间件处理
) -> User:
    """从JWT提取当前用户（由依赖注入使用）"""
    pass


@router.post("/sms-code", response_model=ApiResponse)
def send_sms_code(req: SmsCodeRequest):
    """发送短信验证码"""
    ok, msg = sms_service.send_code(req.phone)
    if not ok:
        return ApiResponse(code=400, message=msg)
    # 开发环境将验证码返回给前端方便调试
    return ApiResponse(code=0, message="验证码已发送", data={"code": msg})


@router.post("/login/sms", response_model=ApiResponse)
def login_by_sms(req: SmsLoginRequest, db: Session = Depends(get_db)):
    """手机号+验证码登录"""
    # 验证码校验
    ok, msg = sms_service.verify_code(req.phone, req.code)
    if not ok:
        return ApiResponse(code=400, message=msg)

    user = db.query(User).filter(User.phone == req.phone).first()
    if not user:
        return ApiResponse(code=404, message="手机号未注册")

    # 清除失败计数
    user.login_failures = 0
    user.locked_until = None
    db.commit()

    token, expires_in = create_token(user.id)
    db.add(AuditLog(user_id=user.id, action="login_sms", detail="短信验证码登录"))
    db.commit()
    return ApiResponse(
        code=0, message="登录成功",
        data={"access_token": token, "token_type": "bearer", "expires_in": expires_in}
    )


@router.post("/login/password", response_model=ApiResponse)
def login_by_password(req: PasswordLoginRequest, db: Session = Depends(get_db)):
    """密码登录"""
    user = db.query(User).filter(User.phone == req.phone).first()
    if not user:
        return ApiResponse(code=404, message="手机号未注册")

    # 锁定检查
    now = datetime.utcnow()
    if user.locked_until and now < user.locked_until:
        remaining = int((user.locked_until - now).total_seconds() / 60)
        return ApiResponse(code=423, message=f"账号已锁定，请{remaining}分钟后重试")

    # 锁定到期后重置失败计数
    if user.locked_until and now >= user.locked_until:
        user.login_failures = 0
        user.locked_until = None

    # 密码校验
    if not pwd_context.verify(req.password, user.password_hash):
        user.login_failures += 1
        if user.login_failures >= LOGIN_MAX_FAILURES:
            user.locked_until = now + timedelta(minutes=LOGIN_LOCK_MINUTES)
            db.commit()
            return ApiResponse(code=423, message=f"连续{LOGIN_MAX_FAILURES}次密码错误，账号已锁定{LOGIN_LOCK_MINUTES}分钟")
        db.commit()
        return ApiResponse(code=401, message=f"密码错误，还剩{LOGIN_MAX_FAILURES - user.login_failures}次机会")

    # 登录成功
    user.login_failures = 0
    user.locked_until = None
    db.commit()

    token, expires_in = create_token(user.id)
    db.add(AuditLog(user_id=user.id, action="login_password", detail="密码登录"))
    db.commit()
    return ApiResponse(
        code=0, message="登录成功",
        data={"access_token": token, "token_type": "bearer", "expires_in": expires_in}
    )


@router.post("/register", response_model=ApiResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """用户注册"""
    # 密码确认
    if req.password != req.confirm_password:
        return ApiResponse(code=400, message="两次输入的密码不一致")

    # 先检查手机号是否已注册（避免消耗验证码）
    existing = db.query(User).filter(User.phone == req.phone).first()
    if existing:
        return ApiResponse(code=409, message="该手机号已注册")

    # 验证码校验
    ok, msg = sms_service.verify_code(req.phone, req.code)
    if not ok:
        return ApiResponse(code=400, message=msg)

    # 创建用户
    user = User(
        phone=req.phone,
        password_hash=pwd_context.hash(req.password),
        email=req.email,
        invite_code=req.invite_code,
    )
    db.add(user)
    db.flush()

    # 创建空的个人信息记录
    profile = UserProfile(user_id=user.id)
    db.add(profile)

    db.add(AuditLog(user_id=user.id, action="register", detail=f"注册手机号{req.phone}"))
    db.commit()

    # 注册成功后清除冷却时间，方便立即发送新验证码登录
    sms_service.clear_cooldown(req.phone)

    return ApiResponse(code=0, message="注册成功，请登录")
