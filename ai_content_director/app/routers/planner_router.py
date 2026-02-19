"""30-day content planner API."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.planner import PlannerGenerateRequest, PlannerGenerateResponse
from app.services.planner_service import generate_30_day_plan

router = APIRouter(prefix="/planner", tags=["planner"])


@router.post(
    "/generate",
    response_model=PlannerGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_planner_generate(
    payload: PlannerGenerateRequest,
    db: AsyncSession = Depends(get_db),
    force: bool = Query(False, description="Replace existing plan if already 30 days"),
    ai: bool = Query(True, description="Use OpenAI when true; fallback to template if AI fails or key missing"),
) -> PlannerGenerateResponse:
    """
    Generate 30-day (or custom days) content plan for tenant.
    When ai=true uses OpenAI; on failure or missing OPENAI_API_KEY falls back to deterministic template.
    404 if tenant_id not found; 409 if plan already exists and force=false.
    """
    try:
        created, items, used_ai, used_fallback, model, plan_id = await generate_30_day_plan(
            db, payload, force=force, use_ai=ai
        )
    except ValueError as e:
        if str(e) == "tenant_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found",
            )
        if str(e) == "plan_exists":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Content plan already exists (30 days). Use force=true to replace.",
            )
        if str(e) == "days_exceeded":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="days must be at most 30 (cost guard).",
            )
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
