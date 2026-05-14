"""User authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog, User
from app.schemas import AuthResponse, LoginRequest, RegisterRequest, UserPublic
from app.security import create_session, hash_password, verify_password


router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_public(user: User) -> UserPublic:
    return UserPublic(id=user.id, username=user.username, display_name=user.display_name)


@router.post("/register", response_model=AuthResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")

    user = User(
        username=request.username,
        display_name=request.display_name or request.username,
        password_hash=hash_password(request.password),
    )
    db.add(user)
    db.flush()
    db.add(AuditLog(actor_role="user", actor_id=user.id, action="register", target_type="user", target_id=user.id))
    db.commit()
    db.refresh(user)

    token = create_session(db, "user", user.id)
    return AuthResponse(token=token, role="user", user=_user_public(user))


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username, User.is_active.is_(True)).first()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    db.add(AuditLog(actor_role="user", actor_id=user.id, action="login", target_type="user", target_id=user.id))
    db.commit()
    token = create_session(db, "user", user.id)
    return AuthResponse(token=token, role="user", user=_user_public(user))
