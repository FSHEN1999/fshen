"""Conversation WebSocket connection manager."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConversationConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, conversation_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[conversation_id].add(websocket)

    def disconnect(self, conversation_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(conversation_id)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(conversation_id, None)

    async def broadcast(self, conversation_id: str, payload: dict[str, Any]) -> None:
        connections = list(self._connections.get(conversation_id, set()))
        for websocket in connections:
            try:
                await websocket.send_json(payload)
            except Exception:
                self.disconnect(conversation_id, websocket)


conversation_connections = ConversationConnectionManager()
