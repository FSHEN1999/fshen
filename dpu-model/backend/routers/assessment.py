# -*- coding: utf-8 -*-
"""资质评估与额度测算路由"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserProfile, Application, AuditLog
from schemas import QuotaResponse, LoanApplyRequest, ApiResponse
from config import QUOTA_VALID_DAYS
from services.risk import assess_risk
from services.credit import calculate_quota
from services.validation import validate_id_card

router = APIRouter(prefix="/api/assessment", tags=["资质评估"])


def _get_user_from_token(request: Request, db: Session = Depends(get_db)) -> User:
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


@router.get("/quota", response_model=ApiResponse)
def get_quota(request: Request, db: Session = Depends(get_db)):
    """获取预估额度"""
    try:
        user = _get_user_from_token(request, db)
    except ValueError as e:
        return ApiResponse(code=401, message=str(e))

    profile = db.query(UserProfile).filter(
        UserProfile.user_id == user.id, UserProfile.is_complete == True
    ).first()
    if not profile:
        return ApiResponse(code=400, message="请先完成个人信息填写")

    # 已有有效额度直接返回
    app = db.query(Application).filter(
        Application.user_id == user.id,
        Application.estimated_quota.isnot(None),
        Application.quota_valid_until > datetime.utcnow(),
    ).first()
    if app:
        return ApiResponse(code=0, data={
            "estimated_quota": app.estimated_quota,
            "suggested_period": app.suggested_period,
            "interest_rate": app.interest_rate,
            "risk_level": app.risk_level,
            "risk_note": app.risk_note,
            "valid_until": app.quota_valid_until.strftime("%Y-%m-%d"),
            "assessment_basis": "基于您提交的信息测算",
        })

    # 风险评估
    id_card_valid, _ = validate_id_card(profile.id_card or "")
    risk_level, risk_note, risk_score = assess_risk(
        age=profile.age,
        income_range=profile.income_range or "",
        income_source=profile.income_source or "",
        id_card_valid=id_card_valid,
    )

    # 高风险拦截
    if risk_level == "高":
        db.add(AuditLog(user_id=user.id, action="risk_blocked", detail=risk_note))
        db.commit()
        return ApiResponse(code=403, message="暂时无法通过资质评估", data={
            "risk_level": risk_level,
            "risk_note": risk_note,
        })

    # 额度测算
    quota, period, rate = calculate_quota(
        income_range=profile.income_range or "",
        risk_level=risk_level,
        risk_score=risk_score,
        age=profile.age,
    )

    valid_until = datetime.utcnow() + timedelta(days=QUOTA_VALID_DAYS)

    # 保存到申请记录
    app = db.query(Application).filter(
        Application.user_id == user.id,
        Application.status.in_(["draft", "info_submitted", "shareholder_submitted"]),
    ).first()
    if not app:
        app = Application(user_id=user.id, status="info_submitted")
        db.add(app)

    app.estimated_quota = quota
    app.suggested_period = period
    app.interest_rate = rate
    app.risk_level = risk_level
    app.risk_note = risk_note
    app.quota_valid_until = valid_until

    db.add(AuditLog(user_id=user.id, action="quota_assessed", detail=f"额度{quota}，风险{risk_level}"))
    db.commit()

    return ApiResponse(code=0, data={
        "estimated_quota": quota,
        "suggested_period": period,
        "interest_rate": rate,
        "risk_level": risk_level,
        "risk_note": risk_note,
        "valid_until": valid_until.strftime("%Y-%m-%d"),
        "assessment_basis": "基于您提交的信息测算",
    })


@router.post("/apply", response_model=ApiResponse)
def apply_loan(req: LoanApplyRequest, request: Request, db: Session = Depends(get_db)):
    """提交借款申请"""
    try:
        user = _get_user_from_token(request, db)
    except ValueError as e:
        return ApiResponse(code=401, message=str(e))

    app = db.query(Application).filter(
        Application.user_id == user.id,
        Application.estimated_quota.isnot(None),
        Application.quota_valid_until > datetime.utcnow(),
    ).first()
    if not app:
        return ApiResponse(code=400, message="请先完成额度测算")

    if req.loan_amount > app.estimated_quota:
        return ApiResponse(code=400, message=f"申请金额不能超过预估额度{app.estimated_quota}元")

    app.loan_amount = req.loan_amount
    app.loan_purpose = req.loan_purpose
    app.status = "assessing"

    db.add(AuditLog(user_id=user.id, action="loan_apply", detail=f"申请{req.loan_amount}元"))
    db.commit()

    return ApiResponse(code=0, message="借款申请已提交，请等待审批", data={"application_id": app.id})
