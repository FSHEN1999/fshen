# -*- coding: utf-8 -*-
"""Contact issue routes backed by PostgreSQL."""
from fastapi import APIRouter, HTTPException

from web.models.requests import ContactIssueCreateRequest, ContactIssueReplyRequest
from web.models.responses import ApiResponse
from web.routes.auth_guard import require_valid_username
from web.services.audit_store import audit_store

router = APIRouter(prefix="/api/contact-issues", tags=["联系我们"])


@router.get("", response_model=ApiResponse)
async def list_contact_issues():
    try:
        issues = audit_store.list_contact_issues()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查询问题失败: {exc}") from exc
    return ApiResponse(success=True, message=f"共 {len(issues)} 条问题", data=issues)


@router.post("", response_model=ApiResponse)
async def create_contact_issue(req: ContactIssueCreateRequest):
    require_valid_username(req.created_by)
    try:
        issue = audit_store.create_contact_issue(req.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"提交问题失败: {exc}") from exc
    return ApiResponse(success=True, message="问题已提交", data=issue)


@router.post("/{issue_id}/reply", response_model=ApiResponse)
async def reply_contact_issue(issue_id: int, req: ContactIssueReplyRequest):
    require_valid_username(req.replied_by)
    try:
        issue = audit_store.reply_contact_issue(issue_id, req.reply, req.replied_by)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"回复问题失败: {exc}") from exc
    if not issue:
        raise HTTPException(status_code=404, detail="问题不存在")
    return ApiResponse(success=True, message="问题已回复", data=issue)


@router.delete("/{issue_id}", response_model=ApiResponse)
async def delete_contact_issue(issue_id: int):
    try:
        deleted = audit_store.delete_contact_issue(issue_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"删除问题失败: {exc}") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="问题不存在")
    return ApiResponse(success=True, message="问题已删除", data={"id": str(issue_id)})
