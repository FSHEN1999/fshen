"""Public, personal, and realtime treehole conversation routes."""

from __future__ import annotations

import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import AuditLog, Conversation, Entry, User, utcnow
from app.qwen_client import qwen_analyzer
from app.realtime import conversation_connections
from app.schemas import (
    ConversationCloseRequest,
    ConversationResponse,
    EntryCreateRequest,
    EntryResponse,
    RecentEntryResponse,
)
from app.security import get_optional_user, get_user_by_token_value


router = APIRouter(prefix="/api", tags=["entries"])

FAREWELL_KEYWORDS = (
    "再见",
    "拜拜",
    "告别",
    "不聊了",
    "先这样",
    "就到这里",
    "今天先到这",
    "结束倾诉",
    "晚安",
    "goodbye",
    "bye",
)


def _risk_flags(entry: Entry) -> list[str]:
    try:
        parsed = json.loads(entry.risk_flags or "[]")
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _is_farewell(content: str) -> bool:
    lowered = content.lower()
    return any(keyword in lowered for keyword in FAREWELL_KEYWORDS)


def _entry_conversation_status(entry: Entry) -> str:
    if entry.conversation:
        return entry.conversation.status
    return "active"


def entry_response(entry: Entry) -> EntryResponse:
    return EntryResponse(
        id=entry.id,
        conversation_id=entry.conversation_id or "",
        conversation_status=_entry_conversation_status(entry),
        visitor_id=entry.visitor_id,
        mood=entry.mood,
        content=entry.content,
        ai_reply=entry.manual_reply or entry.ai_reply,
        summary=entry.summary,
        emotion_label=entry.emotion_label,
        analysis_source=entry.analysis_source,
        risk_level=entry.risk_level,
        risk_flags=_risk_flags(entry),
        status=entry.status,
        is_farewell=bool(entry.is_farewell),
        manual_reply=entry.manual_reply,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def _conversation_response(conversation: Conversation) -> ConversationResponse:
    messages = [entry_response(entry) for entry in conversation.entries if entry.status != "deleted"]
    messages.sort(key=lambda item: item.created_at)
    return ConversationResponse(
        id=conversation.id,
        status=conversation.status,
        closed_reason=conversation.closed_reason,
        visitor_id=conversation.visitor_id,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        closed_at=conversation.closed_at,
        messages=messages,
    )


def _can_access_conversation(conversation: Conversation, user: User | None, visitor_id: str | None) -> bool:
    if user and conversation.user_id == user.id:
        return True
    if visitor_id and conversation.visitor_id == visitor_id:
        return True
    return False


def _create_conversation(db: Session, user: User | None, visitor_id: str | None) -> Conversation:
    conversation = Conversation(
        id=str(uuid4()),
        user_id=user.id if user else None,
        visitor_id=visitor_id,
        status="active",
    )
    db.add(conversation)
    db.flush()
    return conversation


def _resolve_conversation(
    db: Session,
    *,
    conversation_id: str | None,
    user: User | None,
    visitor_id: str | None,
) -> Conversation:
    conversation = None
    if conversation_id:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conversation and not _can_access_conversation(conversation, user, visitor_id):
            conversation = None
        if conversation and conversation.status == "closed":
            conversation = None

    if not conversation:
        conversation = _create_conversation(db, user, visitor_id)
    elif user and conversation.user_id is None and conversation.visitor_id == visitor_id:
        conversation.user_id = user.id
        conversation.updated_at = utcnow()

    return conversation


def _close_conversation(conversation: Conversation, reason: str) -> None:
    if conversation.status == "closed":
        return
    conversation.status = "closed"
    conversation.closed_reason = reason
    conversation.closed_at = utcnow()
    conversation.updated_at = utcnow()


@router.post("/entries", response_model=EntryResponse)
def create_entry(request_data: EntryCreateRequest, request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    visitor_id = request_data.visitor_id or str(uuid4())
    conversation = _resolve_conversation(
        db,
        conversation_id=request_data.conversation_id,
        user=user,
        visitor_id=visitor_id,
    )

    analysis = qwen_analyzer.analyze(request_data.content, request_data.mood)
    status_value = "pending_review" if analysis.risk_level == "high" else "visible"
    is_farewell = _is_farewell(request_data.content)

    entry = Entry(
        conversation_id=conversation.id,
        user_id=user.id if user else None,
        visitor_id=visitor_id,
        mood=request_data.mood,
        content=request_data.content,
        ai_reply=analysis.ai_reply,
        summary=analysis.summary,
        emotion_label=analysis.emotion_label,
        analysis_source=analysis.analysis_source,
        risk_level=analysis.risk_level,
        risk_flags=json.dumps(analysis.risk_flags, ensure_ascii=False),
        status=status_value,
        is_farewell=is_farewell,
    )
    db.add(entry)
    if is_farewell:
        _close_conversation(conversation, "farewell_keyword")
    else:
        conversation.updated_at = utcnow()

    db.flush()
    db.add(
        AuditLog(
            actor_role="user" if user else "visitor",
            actor_id=user.id if user else None,
            action="create_entry",
            target_type="entry",
            target_id=entry.id,
            detail=f"conversation={conversation.id};risk={analysis.risk_level};status={status_value}",
        )
    )
    db.commit()
    db.refresh(entry)
    return entry_response(entry)


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: str,
    request: Request,
    visitor_id: str | None = Query(None, max_length=96),
    db: Session = Depends(get_db),
):
    user = get_optional_user(request, db)
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation or not _can_access_conversation(conversation, user, visitor_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return _conversation_response(conversation)


@router.post("/conversations/{conversation_id}/close", response_model=ConversationResponse)
def close_conversation(
    conversation_id: str,
    close_request: ConversationCloseRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_optional_user(request, db)
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation or not _can_access_conversation(conversation, user, close_request.visitor_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

    _close_conversation(conversation, "user_button")
    db.add(AuditLog(actor_role="user" if user else "visitor", action="close_conversation", target_type="conversation", target_id=None, detail=conversation.id))
    db.commit()
    db.refresh(conversation)
    return _conversation_response(conversation)


@router.get("/me/entries", response_model=list[EntryResponse])
def my_entries(
    request: Request,
    visitor_id: str | None = Query(None, max_length=96),
    db: Session = Depends(get_db),
):
    user = get_optional_user(request, db)
    query = db.query(Entry).filter(Entry.status != "deleted")
    if user:
        query = query.filter(Entry.user_id == user.id)
    elif visitor_id:
        query = query.filter(Entry.visitor_id == visitor_id)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少 visitor_id")

    entries = query.order_by(Entry.created_at.desc()).limit(50).all()
    return [entry_response(entry) for entry in entries]


@router.get("/entries/recent", response_model=list[RecentEntryResponse])
def recent_entries(limit: int = Query(8, ge=1, le=20), db: Session = Depends(get_db)):
    entries = (
        db.query(Entry)
        .filter(Entry.status == "visible", Entry.risk_level != "high")
        .order_by(Entry.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        RecentEntryResponse(
            id=entry.id,
            mood=entry.mood,
            summary=entry.summary,
            emotion_label=entry.emotion_label,
            analysis_source=entry.analysis_source,
            created_at=entry.created_at,
        )
        for entry in entries
    ]


@router.websocket("/ws/conversations/{conversation_id}")
async def conversation_websocket(
    websocket: WebSocket,
    conversation_id: str,
    visitor_id: str | None = Query(None),
    token: str | None = Query(None),
):
    db = SessionLocal()
    try:
        user = get_user_by_token_value(db, token)
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conversation or not _can_access_conversation(conversation, user, visitor_id):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    finally:
        db.close()

    await conversation_connections.connect(conversation_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        conversation_connections.disconnect(conversation_id, websocket)
