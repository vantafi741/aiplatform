"""Onboarding API: create tenant + brand profile."""
import json
from typing import Any, Dict

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.onboarding import (
    OnboardingRequest,
    OnboardingResponse,
    TenantOut,
    BrandProfileOut,
)
from app.services.onboarding_service import create_tenant_and_profile

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _brand_profile_to_out(profile: Any) -> Dict[str, Any]:
    """Build BrandProfileOut dict; parse main_services JSON."""
    main_services = None
    if profile.main_services:
        try:
            main_services = json.loads(profile.main_services)
        except Exception:
            main_services = []
    return {
        "id": profile.id,
        "tenant_id": profile.tenant_id,
        "brand_tone": profile.brand_tone,
        "main_services": main_services,
        "target_customer": profile.target_customer,
        "cta_style": profile.cta_style,
        "created_at": profile.created_at,
    }


@router.post(
    "",
    response_model=OnboardingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_onboarding(
    payload: OnboardingRequest,
    db: AsyncSession = Depends(get_db),
) -> OnboardingResponse:
    """
    Create a new tenant and its brand profile.
    Returns tenant and brand_profile (201).
    """
    tenant, profile = await create_tenant_and_profile(db, payload)
    tenant_out = TenantOut.model_validate(tenant)
    profile_out = BrandProfileOut(**_brand_profile_to_out(profile))
    return OnboardingResponse(tenant=tenant_out, brand_profile=profile_out)
