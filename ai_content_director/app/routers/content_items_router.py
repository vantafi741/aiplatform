"""API content_items: approve, reject, list (HITL + scheduler)."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.content import (
    ContentItemApiOut,
    ContentItemApproveRequest,
    ContentItemApproveResponse,
    ContentItemPatchRequest,
    ContentItemPatchResponse,
    ContentItemRejectRequest,
    ContentItemRejectResponse,
    ContentItemsListResponse,
)
from app.services.approval_service import approve_content, reject_content
from app.services.content_service import list_content_items, update_content_item_scheduled

router = APIRouter(prefix="/api/content_items", tags=["content_items"])


@router.post("/{item_id}/approve", response_model=ContentItemApproveResponse)
async def post_content_item_approve(
    item_id: UUID,
    payload: ContentItemApproveRequest,
    db: AsyncSession = Depends(get_db),
) -> ContentItemApproveResponse:
    """Duyệt item: set status=approved, approved_at=now, approved_by."""
    try:
        item = await approve_content(
            db,
            tenant_id=payload.tenant_id,
            content_id=item_id,
            actor="HUMAN",
            approved_by=payload.approved_by,
        )
    except ValueError as e:
        if str(e) == "content_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content item not found")
        if str(e) == "already_approved":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already approved")
        if str(e) == "cannot_approve_rejected":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot approve rejected content")
        raise
    return ContentItemApproveResponse(
        item_id=item.id,
        status=item.status,
        approved_at=item.approved_at,
    )


@router.post("/{item_id}/reject", response_model=ContentItemRejectResponse)
async def post_content_item_reject(
    item_id: UUID,
    payload: ContentItemRejectRequest,
    db: AsyncSession = Depends(get_db),
) -> ContentItemRejectResponse:
    """Từ chối item: set status=rejected, rejection_reason, rejected_by."""
    try:
        item = await reject_content(
            db,
            tenant_id=payload.tenant_id,
            content_id=item_id,
            reason=payload.reason,
            actor="HUMAN",
            rejected_by=payload.rejected_by,
        )
    except ValueError as e:
        if str(e) == "content_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content item not found")
        raise
    return ContentItemRejectResponse(item_id=item.id, status=item.status)


@router.patch("/{item_id}", response_model=ContentItemPatchResponse)
async def patch_content_item(
    item_id: UUID,
    payload: ContentItemPatchRequest,
    db: AsyncSession = Depends(get_db),
) -> ContentItemPatchResponse:
    """Cập nhật scheduled_at (cho smoke test / runbook). Chỉ cập nhật khi payload.scheduled_at có giá trị."""
    try:
        item = await update_content_item_scheduled(
            db,
            tenant_id=payload.tenant_id,
            item_id=item_id,
            scheduled_at=payload.scheduled_at,
        )
    except ValueError as e:
        if str(e) == "content_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content item not found")
        raise
    return ContentItemPatchResponse(item_id=item.id, scheduled_at=item.scheduled_at)


@router.get("", response_model=ContentItemsListResponse)
async def get_content_items(
    tenant_id: UUID = Query(..., description="Tenant UUID"),
    status: str | None = Query(None, description="draft | approved | rejected | published | publish_failed"),
    channel: str | None = Query(None, description="facebook | ..."),
    from_: datetime | None = Query(None, alias="from", description="scheduled_at >= from (ISO)"),
    to: datetime | None = Query(None, description="scheduled_at <= to (ISO)"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> ContentItemsListResponse:
    """Liệt kê content_items với filter: tenant_id, status, channel, from, to."""
    items = await list_content_items(
        db,
        tenant_id=tenant_id,
        status=status,
        channel=channel,
        from_date=from_,
        to_date=to,
        limit=limit,
    )
    return ContentItemsListResponse(
        items=[
            ContentItemApiOut(
                id=it.id,
                tenant_id=it.tenant_id,
                plan_id=it.plan_id,
                title=it.title,
                caption=it.caption,
                status=it.status,
                approved_at=it.approved_at,
                approved_by=getattr(it, "approved_by", None),
                rejected_at=it.rejected_at,
                rejection_reason=getattr(it, "rejection_reason", None),
                rejected_by=getattr(it, "rejected_by", None),
                scheduled_at=it.scheduled_at,
                schedule_status=it.schedule_status,
                channel=it.channel,
                content_type=it.content_type,
                publish_attempts=it.publish_attempts,
                last_publish_attempt_at=getattr(it, "last_publish_attempt_at", None),
                last_publish_error=it.last_publish_error,
                external_post_id=getattr(it, "external_post_id", None),
                created_at=it.created_at,
            )
            for it in items
        ],
    )
