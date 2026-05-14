"""Password and token helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import AuthSession, User, utcnow


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 180000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, salt, expected = stored_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 180000)
    return hmac.compare_digest(digest.hex(), expected)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, role: str, user_id: int | None = None) -> str:
    token = secrets.token_urlsafe(36)
    session = AuthSession(
        token_hash=hash_token(token),
        role=role,
        user_id=user_id,
        expires_at=utcnow() + timedelta(hours=settings.session_hours),
    )
    db.add(session)
    db.commit()
    return token


def _bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:].strip()
    return token or None


def get_session(
    request: Request,
    db: Session,
    *,
    required: bool = False,
    role: str | None = None,
) -> AuthSession | None:
    token = _bearer_token(request)
    if not token:
        if required:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
        return None

    session = db.query(AuthSession).filter(AuthSession.token_hash == hash_token(token)).first()
    if not session or session.expires_at <= utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期")
    if role and session.role != role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    return session


def get_optional_user(request: Request, db: Session) -> User | None:
    session = get_session(request, db, required=False, role=None)
    if not session:
        return None
    if session.role != "user" or not session.user_id:
        return None
    user = db.query(User).filter(User.id == session.user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


def get_user_by_token_value(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    session = db.query(AuthSession).filter(AuthSession.token_hash == hash_token(token)).first()
    if not session or session.expires_at <= utcnow() or session.role != "user" or not session.user_id:
        return None
    return db.query(User).filter(User.id == session.user_id, User.is_active.is_(True)).first()


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    session = get_session(request, db, required=True, role="user")
    user = db.query(User).filter(User.id == session.user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


def require_admin_session(request: Request, db: Session = Depends(get_db)) -> AuthSession:
    return get_session(request, db, required=True, role="admin")
