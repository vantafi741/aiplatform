"""Onboarding request/response schemas."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class OnboardingRequest(BaseModel):
    """Request body for POST /onboarding."""

    tenant_name: str = Field(..., min_length=1, max_length=255)
    industry: str = Field(..., min_length=1, max_length=255)
    brand_tone: str = Field("", max_length=2000)
    main_services: List[str] = Field(default_factory=list, max_length=20)
    target_customer: str = Field("", max_length=2000)
    cta_style: str = Field("", max_length=500)


class TenantOut(BaseModel):
    """Tenant in API response."""

    id: UUID
    name: str
    industry: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BrandProfileOut(BaseModel):
    """Brand profile in API response."""

    id: UUID
    tenant_id: UUID
    brand_tone: Optional[str] = None
    main_services: Optional[list] = None
    target_customer: Optional[str] = None
    cta_style: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OnboardingResponse(BaseModel):
    """Response for POST /onboarding (201)."""

    tenant: TenantOut
    brand_profile: BrandProfileOut
