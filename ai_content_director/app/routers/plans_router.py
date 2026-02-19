"""API plans: generate 30 ngày, materialize thành content_items, GET plan by id."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import ContentItem, ContentPlan
from app.schemas.planner import (
    PlanDetailItemOut,
    PlanDetailResponse,
    PlanMaterializeRequest,
    PlanMaterializeResponse,
    PlannerGenerateRequest,
    PlannerGenerateResponse,
    PlanItemOut,
)
from app.services.plan_materialize_service import materialize_plan
from app.services.planner_service import generate_30_day_plan

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.post(
    "/generate",
    response_model=PlannerGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_plans_generate(
    payload: PlannerGenerateRequest,
    db: AsyncSession = Depends(get_db),
    force: bool = Query(False, description="Replace existing plan"),
    ai: bool = Query(True, description="Use OpenAI when true"),
) -> PlannerGenerateResponse:
    """
    Tạo plan 30 ngày (1 content_plan với plan_json). Chuẩn hóa output đủ 30 ngày.
    Giữ nguyên behavior so với POST /planner/generate.
    """
    try:
        created, items, used_ai, used_fallback, model, plan_id = await generate_30_day_plan(
            db, payload, force=force, use_ai=ai
        )
    except ValueError as e:
        if str(e) == "tenant_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        if str(e) == "plan_exists":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Plan đã tồn tại. Dùng force=true để thay thế.",
            )
        if str(e) == "days_exceeded":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="days tối đa 30")
        raise
    return PlannerGenerateResponse(
        tenant_id=payload.tenant_id,
        plan_id=plan_id,
        created=created,
        items=items,
        used_ai=used_ai,
        used_fallback=used_fallback,
        model=model,
    )


@router.post("/{plan_id}/materialize", response_model=PlanMaterializeResponse)
async def post_plan_materialize(
    plan_id: UUID,
    payload: PlanMaterializeRequest,
    db: AsyncSession = Depends(get_db),
) -> PlanMaterializeResponse:
    """
    Materialize plan thành 30 content_items: scheduled_at, caption, channel, content_type, require_media.
    Idempotent: gọi lần 2 với cùng plan_id trả về count_created=0 và danh sách item ids hiện có.
    """
    try:
        start = date.fromisoformat(payload.start_date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date phải là YYYY-MM-DD",
        )
    try:
        count_created, content_item_ids = await materialize_plan(
            db,
            plan_id=plan_id,
            tenant_id=payload.tenant_id,
            timezone_str=payload.timezone,
            posting_hours=payload.posting_hours,
            start_date=start,
            channel=payload.channel,
            default_status=payload.default_status,
        )
    except ValueError as e:
        if str(e) == "plan_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
        if str(e) == "plan_has_no_plan_json":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Plan không có plan_json (plan cũ chưa hỗ trợ materialize)",
            )
        if str(e) == "plan_json_insufficient_entries":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="plan_json cần ít nhất 30 entries",
            )
        raise
    return PlanMaterializeResponse(
        plan_id=plan_id,
        count_created=count_created,
        content_item_ids=content_item_ids,
    )


@router.get("/{plan_id}", response_model=PlanDetailResponse)
async def get_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> PlanDetailResponse:
    """Lấy plan theo id kèm danh sách content_items đã materialize (plan_id = plan_id)."""
    r = await db.execute(select(ContentPlan).where(ContentPlan.id == plan_id))
    plan = r.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    r2 = await db.execute(
        select(ContentItem)
        .where(ContentItem.plan_id == plan_id)
        .order_by(ContentItem.scheduled_at)
    )
    items = list(r2.scalars().all())

    return PlanDetailResponse(
        id=plan.id,
        tenant_id=plan.tenant_id,
        title=plan.title,
        objective=plan.objective,
        tone=plan.tone,
        status=plan.status,
        created_at=plan.created_at.isoformat() if plan.created_at else None,
        items=[
            PlanDetailItemOut(
                id=it.id,
                title=it.title,
                caption=it.caption,
                status=it.status,
                scheduled_at=it.scheduled_at.isoformat() if it.scheduled_at else None,
                channel=it.channel,
                content_type=it.content_type,
            )
            for it in items
        ],
    )
