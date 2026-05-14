# -*- coding: utf-8 -*-
"""AI assistant routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from web.models.requests import AiChatRequest
from web.models.responses import ApiResponse
from web.services.ai_service import DPUAIService, build_ai_context

router = APIRouter(prefix="/api/ai", tags=["AI助手"])
ai_service = DPUAIService()


@router.post("/chat", response_model=ApiResponse)
async def chat_with_ai(req: AiChatRequest):
    try:
        context = build_ai_context(req.context.model_dump())
        result = ai_service.chat(
            message=req.message,
            history=[item.model_dump() for item in req.history],
            context=context,
        )
        return ApiResponse(success=result.get("success", False), message="ok", data=result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

