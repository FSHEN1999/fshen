# -*- coding: utf-8 -*-
"""用户信息路由：个人信息填写、股东信息填写"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserProfile, Shareholder, Application, AuditLog
from schemas import (
    UserProfileRequest, UserProfileResponse, ShareholderRequest,
    ApiResponse,
)
from services.validation import (
    validate_id_card, validate_phone, validate_income_range,
    extract_age_from_id_card, extract_gender_from_id_card,
)

router = APIRouter(prefix="/api/user", tags=["用户信息"])


def _get_user_from_token(request: Request, db: Session = Depends(get_db)) -> User:
    """从请求头中提取用户（简化版JWT解析）"""
    from jose import jwt, JWTError
    from config import JWT_SECRET_KEY, JWT_ALGORITHM

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise ValueError("未登录")
    token = auth[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise ValueError("登录已过期")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("用户不存在")
    return user


@router.get("/profile", response_model=ApiResponse)
def get_profile(request: Request, db: Session = Depends(get_db)):
    """获取个人信息"""
    try:
        user = _get_user_from_token(request, db)
    except ValueError as e:
        return ApiResponse(code=401, message=str(e))

    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    if not profile:
        return ApiResponse(code=0, data={"is_complete": False})

    data = {
        "name": profile.name,
        "id_card": profile.id_card,
        "gender": profile.gender,
        "age": profile.age,
        "income_range": profile.income_range,
        "income_source": profile.income_source,
        "address": profile.address,
        "phone": user.phone,
        "email": user.email,
        "emergency_contact_name": profile.emergency_contact_name,
        "emergency_contact_phone": profile.emergency_contact_phone,
        "occupation": profile.occupation,
        "is_complete": profile.is_complete,
    }
    return ApiResponse(code=0, data=data)


@router.post("/profile", response_model=ApiResponse)
def submit_profile(req: UserProfileRequest, request: Request, db: Session = Depends(get_db)):
    """提交个人信息"""
    try:
        user = _get_user_from_token(request, db)
    except ValueError as e:
        return ApiResponse(code=401, message=str(e))

    # 校验身份证号
    ok, msg = validate_id_card(req.id_card)
    if not ok:
        return ApiResponse(code=400, message=msg)

    # 校验收入范围
    ok, msg = validate_income_range(req.income_range)
    if not ok:
        return ApiResponse(code=400, message=msg)

    # 校验紧急联系人手机号
    if req.emergency_contact_phone:
        ok, msg = validate_phone(req.emergency_contact_phone)
        if not ok:
            return ApiResponse(code=400, message=f"紧急联系人{msg}")

    # 自动提取性别和年龄
    gender = extract_gender_from_id_card(req.id_card)
    age = extract_age_from_id_card(req.id_card)

    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    if not profile:
        profile = UserProfile(user_id=user.id)
        db.add(profile)

    profile.name = req.name
    profile.id_card = req.id_card
    profile.gender = gender
    profile.age = age
    profile.income_range = req.income_range
    profile.income_source = req.income_source
    profile.address = req.address
    profile.emergency_contact_name = req.emergency_contact_name
    profile.emergency_contact_phone = req.emergency_contact_phone
    profile.occupation = req.occupation
    profile.is_complete = True

    db.add(AuditLog(user_id=user.id, action="submit_profile", detail="提交个人信息"))
    db.commit()

    return ApiResponse(code=0, message="个人信息提交成功")


@router.post("/shareholder", response_model=ApiResponse)
def submit_shareholder(req: ShareholderRequest, request: Request, db: Session = Depends(get_db)):
    """提交公司股东信息"""
    try:
        user = _get_user_from_token(request, db)
    except ValueError as e:
        return ApiResponse(code=401, message=str(e))

    # 检查个人信息是否已填写
    profile = db.query(UserProfile).filter(
        UserProfile.user_id == user.id, UserProfile.is_complete == True
    ).first()
    if not profile:
        return ApiResponse(code=400, message="请先完成个人信息填写")

    # 校验每位股东身份证号
    for sh in req.shareholders:
        ok, msg = validate_id_card(sh.id_card)
        if not ok:
            return ApiResponse(code=400, message=f"股东{sh.name}的{msg}")

    # 获取或创建申请
    app = db.query(Application).filter(
        Application.user_id == user.id,
        Application.status.in_(["draft", "info_submitted"]),
    ).first()
    if not app:
        app = Application(user_id=user.id, status="info_submitted")
        db.add(app)
        db.flush()

    # 删除旧的股东记录，重新写入
    db.query(Shareholder).filter(Shareholder.application_id == app.id).delete()
    for sh in req.shareholders:
        db.add(Shareholder(
            application_id=app.id,
            name=sh.name,
            id_card=sh.id_card,
            share_ratio=sh.share_ratio,
            investment_type=sh.investment_type,
            investment_amount=sh.investment_amount,
            phone=sh.phone,
            position=sh.position,
            investment_date=sh.investment_date,
        ))

    app.status = "shareholder_submitted"
    db.add(AuditLog(user_id=user.id, action="submit_shareholder", detail=f"提交{len(req.shareholders)}位股东信息"))
    db.commit()

    return ApiResponse(code=0, message="股东信息提交成功", data={"application_id": app.id})
