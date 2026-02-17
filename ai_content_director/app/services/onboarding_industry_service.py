"""Onboarding industry_profile: create or update industry_profile for tenant_id (Module 1)."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IndustryProfile, Tenant

from app.schemas.revenue_mv1 import OnboardingIndustryRequest


async def upsert_industry_profile(
    db: AsyncSession,
    payload: OnboardingIndustryRequest,
) -> IndustryProfile:
    """
    Create or update industry_profile for the given tenant_id.
    If a profile exists for tenant_id, update it; otherwise create one.
    """
    result = await db.execute(
        select(IndustryProfile).where(IndustryProfile.tenant_id == payload.tenant_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.name = payload.name
        existing.description = payload.description
        await db.flush()
        await db.refresh(existing)
        return existing

    # Verify tenant exists
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == payload.tenant_id))
    if tenant_result.scalar_one_or_none() is None:
        raise ValueError("tenant_not_found")

    profile = IndustryProfile(
        tenant_id=payload.tenant_id,
        name=payload.name,
        description=payload.description,
    )
    db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return profile


async def get_industry_profile_by_tenant(
    db: AsyncSession,
    tenant_id: UUID,
) -> IndustryProfile | None:
    """Get industry_profile for tenant_id (first if multiple)."""
    result = await db.execute(
        select(IndustryProfile).where(IndustryProfile.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()
