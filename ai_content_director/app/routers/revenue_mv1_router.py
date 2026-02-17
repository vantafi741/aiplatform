"""Revenue MVP Module 1: POST /api/tenants, /api/onboarding, /api/plans/generate, GET /api/plans/{id}, /api/industry_profile/{tenant_id}."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.revenue_mv1 import (
    TenantCreate,
    TenantOut,
    OnboardingIndustryRequest,
    IndustryProfileOut,
    PlanGenerateRequest,
    PlanGenerateResponse,
    PlanOut,
)
from app.services.tenant_service_mv1 import create_tenant
from app.services.onboarding_industry_service import (
    upsert_industry_profile,
    get_industry_profile_by_tenant,
)
from app.services.plan_service_mv1 import generate_plan, get_plan_by_id

router = APIRouter(prefix="/api", tags=["revenue_mv1"])


@router.post("/tenants", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
async def post_tenant(
    payload: TenantCreate,
    db: AsyncSession = Depends(get_db),
) -> TenantOut:
    """Create a new tenant."""
    tenant = await create_tenant(db, payload)
    return TenantOut.model_validate(tenant)


@router.post(
    "/onboarding",
    response_model=IndustryProfileOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_onboarding_industry(
    payload: OnboardingIndustryRequest,
    db: AsyncSession = Depends(get_db),
) -> IndustryProfileOut:
    """Create or update industry_profile for tenant_id."""
    try:
        profile = await upsert_industry_profile(db, payload)
        return IndustryProfileOut.model_validate(profile)
    except ValueError as e:
        if str(e) == "tenant_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found",
            ) from e
        raise


@router.get(
    "/industry_profile/{tenant_id}",
    response_model=IndustryProfileOut,
)
async def get_industry_profile(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> IndustryProfileOut:
    """Get industry_profile for tenant_id."""
    profile = await get_industry_profile_by_tenant(db, tenant_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Industry profile not found for tenant",
        )
    return IndustryProfileOut.model_validate(profile)


@router.post(
    "/plans/generate",
    response_model=PlanGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_plans_generate(
    payload: PlanGenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> PlanGenerateResponse:
    """Generate 30-day plan for tenant. Strict JSON schema. HITL sets approval_status. Logs usage."""
    try:
        plan = await generate_plan(
            db,
            tenant_id=payload.tenant_id,
            start_date=payload.start_date,
        )
        return PlanGenerateResponse(plan=PlanOut.model_validate(plan))
    except ValueError as e:
        if str(e) == "tenant_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found",
            ) from e
        raise


@router.get("/plans/{plan_id}", response_model=PlanOut)
async def get_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> PlanOut:
    """Get generated plan by id."""
    plan = await get_plan_by_id(db, plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )
    return PlanOut.model_validate(plan)
