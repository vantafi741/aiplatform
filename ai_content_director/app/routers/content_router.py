"""Content items API: generate samples, list, approve, reject (HITL)."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.content import (
    ContentGenerateSamplesRequest,
    ContentGenerateSamplesResponse,
    ContentListResponse,
    ContentItemOut,
    ApproveRequest,
    RejectRequest,
    ScheduleRequest,
    ScheduleResponse,
    UnscheduleRequest,
    UnscheduleResponse,
)
from app.services.content_service import generate_sample_posts, list_content, schedule_content, unschedule_content
from app.services.approval_service import approve_content, reject_content

router = APIRouter(prefix="/content", tags=["content"])


@router.post(
    "/generate-samples",
    response_model=ContentGenerateSamplesResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_content_generate_samples(
    payload: ContentGenerateSamplesRequest,
    db: AsyncSession = Depends(get_db),
    force: bool = Query(False, description="Allow generating when samples already exist"),
    ai: bool = Query(True, description="Use OpenAI when true; fallback to template if AI fails or key missing"),
) -> ContentGenerateSamplesResponse:
    """
    Generate sample content items (draft) for tenant. Max count=20 (cost guard).
    When ai=true uses OpenAI; on failure or missing OPENAI_API_KEY falls back to deterministic template.
    404 if tenant_id not found; 409 if already >= count items and force=false.
    """
    try:
        created, items, used_ai, used_fallback, model = await generate_sample_posts(
            db, payload, force=force, use_ai=ai
        )
    except ValueError as e:
        if str(e) == "tenant_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found",
            )
        if str(e) == "content_exists":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Sample content already exists. Use force=true to add more.",
            )
        if str(e) == "count_exceeded":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="count must be at most 20 (cost guard).",
            )
        raise
    return ContentGenerateSamplesResponse(
        tenant_id=payload.tenant_id,
        created=created,
        items=items,
        used_ai=used_ai,
        used_fallback=used_fallback,
        model=model,
    )


@router.get("/list", response_model=ContentListResponse)
async def get_content_list(
    tenant_id: UUID = Query(..., description="Tenant UUID"),
    status: str | None = Query(None, description="Lọc theo status: draft | approved | published"),
    db: AsyncSession = Depends(get_db),
) -> ContentListResponse:
    """Liệt kê content items của tenant. Có thể lọc theo status."""
    items = await list_content(db, tenant_id=tenant_id, status=status)
    return ContentListResponse(tenant_id=tenant_id, items=items)


@router.post("/{content_id}/approve")
async def post_content_approve(
    content_id: UUID,
    payload: ApproveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Duyệt nội dung (HITL). Set status=approved, review_state=approved."""
    try:
        item = await approve_content(
            db,
            tenant_id=payload.tenant_id,
            content_id=content_id,
            actor=payload.actor,
        )
    except ValueError as e:
        if str(e) == "content_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
        if str(e) == "already_approved":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already approved")
        if str(e) == "cannot_approve_rejected":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot approve rejected content")
        raise
    return ContentItemOut(
        id=item.id,
        title=item.title,
        caption=item.caption,
        hashtags=item.hashtags,
        status=item.status,
        confidence_score=item.confidence_score,
        review_state=item.review_state,
        approved_at=item.approved_at,
        rejected_at=item.rejected_at,
        scheduled_at=item.scheduled_at,
        schedule_status=item.schedule_status,
        publish_attempts=item.publish_attempts,
        last_publish_error=item.last_publish_error,
        last_publish_at=item.last_publish_at,
    )


@router.post("/{content_id}/schedule", response_model=ScheduleResponse)
async def post_content_schedule(
    content_id: UUID,
    payload: ScheduleRequest,
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    """Đặt lịch đăng (chỉ content đã approved). scheduled_at: ISO datetime."""
    try:
        item = await schedule_content(
            db,
            tenant_id=payload.tenant_id,
            content_id=content_id,
            scheduled_at=payload.scheduled_at,
            actor="HUMAN",
        )
    except ValueError as e:
        if str(e) == "content_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
        if str(e) == "content_not_approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ được lên lịch nội dung đã approved.",
            )
        raise
    return ScheduleResponse(
        content_id=item.id,
        schedule_status=item.schedule_status or "scheduled",
        scheduled_at=item.scheduled_at,
    )


@router.post("/{content_id}/unschedule", response_model=UnscheduleResponse)
async def post_content_unschedule(
    content_id: UUID,
    payload: UnscheduleRequest,
    db: AsyncSession = Depends(get_db),
) -> UnscheduleResponse:
    """Xóa lịch đăng."""
    try:
        item = await unschedule_content(
            db,
            tenant_id=payload.tenant_id,
            content_id=content_id,
            actor="HUMAN",
        )
    except ValueError as e:
        if str(e) == "content_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
        raise
    return UnscheduleResponse(content_id=item.id, schedule_status="none")


@router.post("/{content_id}/reject")
async def post_content_reject(
    content_id: UUID,
    payload: RejectRequest,
    db: AsyncSession = Depends(get_db),
):
    """Từ chối nội dung (HITL). Set review_state=rejected, rejected_at=now."""
    try:
        item = await reject_content(
            db,
            tenant_id=payload.tenant_id,
            content_id=content_id,
            reason=payload.reason,
            actor=payload.actor,
        )
    except ValueError as e:
        if str(e) == "content_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
        raise
    return ContentItemOut(
        id=item.id,
        title=item.title,
        caption=item.caption,
        hashtags=item.hashtags,
        status=item.status,
        confidence_score=item.confidence_score,
        review_state=item.review_state,
        approved_at=item.approved_at,
        rejected_at=item.rejected_at,
        scheduled_at=item.scheduled_at,
        schedule_status=item.schedule_status,
        publish_attempts=item.publish_attempts,
        last_publish_error=item.last_publish_error,
        last_publish_at=item.last_publish_at,
    )
