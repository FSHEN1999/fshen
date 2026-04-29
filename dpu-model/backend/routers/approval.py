# -*- coding: utf-8 -*-
"""审批流程路由"""

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from database import get_db
from models import User, Application, AuditLog
from schemas import ApiResponse

router = APIRouter(prefix="/api/approval", tags=["审批"])

STATUS_LABELS = {
    "draft": "草稿",
    "info_submitted": "信息已提交",
    "shareholder_submitted": "股东信息已提交",
    "assessing": "审批中",
    "approved": "审批通过",
    "rejected": "审批驳回",
    "pending_material": "待补充材料",
}

PROGRESS_NOTES = {
    "draft": "请完善个人信息",
    "info_submitted": "请补充股东信息",
    "shareholder_submitted": "请查看预估额度并提交借款申请",
    "assessing": "当前处于初审阶段，请耐心等待",
    "approved": "审批已通过，可进行借款操作",
    "rejected": "审批未通过，请查看原因",
    "pending_material": "请补充所需材料后重新提交",
}


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


@router.get("/status", response_model=ApiResponse)
def get_approval_status(request: Request, db: Session = Depends(get_db)):
    """查询审批状态"""
    try:
        user = _get_user_from_token(request, db)
    except ValueError as e:
        return ApiResponse(code=401, message=str(e))

    app = db.query(Application).filter(
        Application.user_id == user.id
    ).order_by(Application.updated_at.desc()).first()

    if not app:
        return ApiResponse(code=404, message="暂无借款申请")

    data = {
        "application_id": app.id,
        "status": app.status,
        "status_label": STATUS_LABELS.get(app.status, app.status),
        "progress_note": PROGRESS_NOTES.get(app.status, ""),
        "reject_reason": app.reject_reason,
        "estimated_quota": app.estimated_quota,
        "loan_amount": app.loan_amount,
        "created_at": app.created_at.strftime("%Y-%m-%d %H:%M") if app.created_at else None,
        "updated_at": app.updated_at.strftime("%Y-%m-%d %H:%M") if app.updated_at else None,
    }
    return ApiResponse(code=0, data=data)


@router.post("/cancel", response_model=ApiResponse)
def cancel_approval(request: Request, db: Session = Depends(get_db)):
    """取消审批"""
    try:
        user = _get_user_from_token(request, db)
    except ValueError as e:
        return ApiResponse(code=401, message=str(e))

    app = db.query(Application).filter(
        Application.user_id == user.id,
        Application.status == "assessing",
    ).first()
    if not app:
        return ApiResponse(code=400, message="没有可取消的审批")

    app.status = "draft"
    db.add(AuditLog(user_id=user.id, action="cancel_approval", detail=f"取消申请{app.id}"))
    db.commit()

    return ApiResponse(code=0, message="审批已取消")


@router.post("/mock-approve/{application_id}", response_model=ApiResponse)
def mock_approve(application_id: int, approve: bool = True, reason: str = "", db: Session = Depends(get_db)):
    """模拟审批操作（开发调试用）"""
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        return ApiResponse(code=404, message="申请不存在")

    if approve:
        app.status = "approved"
    else:
        app.status = "rejected"
        app.reject_reason = reason or "资质审核不通过"

    db.add(AuditLog(user_id=app.user_id, action="mock_approve", detail=f"模拟审批：{'通过' if approve else '驳回'}"))
    db.commit()

    return ApiResponse(code=0, message=f"审批{'通过' if approve else '驳回'}")
