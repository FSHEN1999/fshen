"""Admin routes for moderation."""

from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import AuditLog, Entry, utcnow
from app.realtime import conversation_connections
from app.schemas import AdminEntryPatchRequest, AdminEntryResponse, AuthResponse
from app.schemas import LoginRequest
from app.security import create_session, require_admin_session


router = APIRouter(prefix="/api/admin", tags=["admin"])


def _admin_entry_response(entry: Entry) -> AdminEntryResponse:
    try:
        risk_flags = json.loads(entry.risk_flags or "[]")
    except json.JSONDecodeError:
        risk_flags = []
    return AdminEntryResponse(
        id=entry.id,
        conversation_id=entry.conversation_id or "",
        conversation_status=entry.conversation.status if entry.conversation else "active",
        visitor_id=entry.visitor_id,
        mood=entry.mood,
        content=entry.content,
        ai_reply=entry.manual_reply or entry.ai_reply,
        summary=entry.summary,
        emotion_label=entry.emotion_label,
        analysis_source=entry.analysis_source,
        risk_level=entry.risk_level,
        risk_flags=risk_flags if isinstance(risk_flags, list) else [],
        status=entry.status,
        is_farewell=bool(entry.is_farewell),
        manual_reply=entry.manual_reply,
        admin_note=entry.admin_note,
        username=entry.user.username if entry.user else None,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        deleted_at=entry.deleted_at,
    )


@router.post("/login", response_model=AuthResponse)
def admin_login(request: LoginRequest, db: Session = Depends(get_db)):
    if request.username != settings.admin_username or request.password != settings.admin_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员账号或密码错误")
    token = create_session(db, "admin")
    db.add(AuditLog(actor_role="admin", actor_id=None, action="admin_login"))
    db.commit()
    return AuthResponse(token=token, role="admin", user=None)


@router.get("/entries", response_model=list[AdminEntryResponse])
def admin_entries(
    _session=Depends(require_admin_session),
    db: Session = Depends(get_db),
    status_filter: str | None = Query(None, alias="status"),
    risk_level: str | None = Query(None),
    q: str | None = Query(None, max_length=120),
):
    query = db.query(Entry)
    if status_filter:
        query = query.filter(Entry.status == status_filter)
    if risk_level:
        query = query.filter(Entry.risk_level == risk_level)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Entry.content.like(like), Entry.summary.like(like), Entry.emotion_label.like(like)))
    entries = query.order_by(Entry.created_at.desc()).limit(200).all()
    return [_admin_entry_response(entry) for entry in entries]


@router.patch("/entries/{entry_id}", response_model=AdminEntryResponse)
def patch_admin_entry(
    entry_id: int,
    patch: AdminEntryPatchRequest,
    background_tasks: BackgroundTasks,
    _session=Depends(require_admin_session),
    db: Session = Depends(get_db),
):
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记录不存在")

    changes: list[str] = []
    if patch.status is not None and patch.status != entry.status:
        entry.status = patch.status
        changes.append(f"status={patch.status}")
        if patch.status == "deleted":
            entry.deleted_at = utcnow()
        elif entry.deleted_at is not None:
            entry.deleted_at = None
    should_broadcast_reply = False
    if patch.manual_reply is not None:
        should_broadcast_reply = patch.manual_reply != entry.manual_reply and bool(patch.manual_reply)
        entry.manual_reply = patch.manual_reply
        changes.append("manual_reply")
    if patch.admin_note is not None:
        entry.admin_note = patch.admin_note
        changes.append("admin_note")

    entry.updated_at = utcnow()
    db.add(
        AuditLog(
            actor_role="admin",
            actor_id=None,
            action="patch_entry",
            target_type="entry",
            target_id=entry.id,
            detail=",".join(changes) or "no_change",
        )
    )
    db.commit()
    db.refresh(entry)
    if should_broadcast_reply and entry.conversation_id:
        background_tasks.add_task(
            conversation_connections.broadcast,
            entry.conversation_id,
            {
                "type": "admin_reply",
                "conversation_id": entry.conversation_id,
                "entry_id": entry.id,
                "manual_reply": entry.manual_reply,
                "updated_at": entry.updated_at.isoformat(),
            },
        )
    return _admin_entry_response(entry)
