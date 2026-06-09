# -*- coding: utf-8 -*-
"""Request guards for user-attributed write operations."""

from fastapi import HTTPException

from web.services.audit_store import audit_store


def require_valid_username(username: str | None) -> str:
    username = (username or "").strip()
    if not username:
        raise HTTPException(status_code=403, detail="请先登录账号再继续操作")
    if not audit_store.user_exists(username):
        raise HTTPException(status_code=403, detail="登录账号无效，请重新登录")
    return username
