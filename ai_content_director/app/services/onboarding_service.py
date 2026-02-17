"""Onboarding service: create tenant + brand profile."""
import json
from typing import Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models import Tenant, BrandProfile
from app.schemas.onboarding import OnboardingRequest

logger = get_logger(__name__)


async def create_tenant_and_profile(
    db: AsyncSession,
    payload: OnboardingRequest,
) -> Tuple[Tenant, BrandProfile]:
    """
    Create a tenant and its brand profile. Caller must commit session.

    Returns:
        Tuple of (Tenant, BrandProfile).
    """
    tenant = Tenant(
        name=payload.tenant_name,
        industry=payload.industry,
    )
    db.add(tenant)
    await db.flush()

    main_services_str = json.dumps(payload.main_services, ensure_ascii=False) if payload.main_services else None
    profile = BrandProfile(
        tenant_id=tenant.id,
        brand_tone=payload.brand_tone or None,
        main_services=main_services_str,
        target_customer=payload.target_customer or None,
        cta_style=payload.cta_style or None,
    )
    db.add(profile)
    await db.flush()
    await db.refresh(tenant)
    await db.refresh(profile)
    logger.info(
        "onboarding.created",
        tenant_id=str(tenant.id),
        brand_profile_id=str(profile.id),
    )
    return tenant, profile
