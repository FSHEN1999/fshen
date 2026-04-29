# -*- coding: utf-8 -*-
"""WebSocket 路由：实时日志推送"""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from web.services.log_capture import ws_log_handler

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/logs/{session_id}")
async def websocket_logs(websocket: WebSocket, session_id: str):
    """WebSocket 实时日志推送"""
    await websocket.accept()
    queue = ws_log_handler.register_session(session_id)
    try:
        while True:
            log_entry = await queue.get()
            await websocket.send_text(json.dumps(log_entry, ensure_ascii=False))
    except WebSocketDisconnect:
        pass
    finally:
        ws_log_handler.unregister_session(session_id)
