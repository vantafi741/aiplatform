"""Schemas for Revenue MVP Module 1: tenants, onboarding (industry_profile), plans."""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# --- POST /api/tenants ---
class TenantCreate(BaseModel):
    """Request body for POST /api/tenants."""

    name: str = Field(..., min_length=1, max_length=255)
    industry: str = Field(..., min_length=1, max_length=255)


class TenantOut(BaseModel):
    """Tenant in API response."""

    id: UUID
    name: str
    industry: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- POST /api/onboarding (create/update industry_profile) ---
class OnboardingIndustryRequest(BaseModel):
    """Request body for POST /api/onboarding: upsert industry_profile for tenant_id."""

    tenant_id: UUID = Field(..., description="Tenant UUID")
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)


class IndustryProfileOut(BaseModel):
    """Industry profile in API response."""

    id: UUID
    tenant_id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- POST /api/plans/generate, GET /api/plans/{plan_id} ---
class PlanGenerateRequest(BaseModel):
    """Request body for POST /api/plans/generate."""

    tenant_id: UUID = Field(..., description="Tenant UUID")
    start_date: Optional[date] = Field(None, description="Start date of 30-day plan; default today.")


class PlanDayItem(BaseModel):
    """One day in plan_json.days."""

    day: int = Field(..., ge=1, le=30)
    topic: str = Field(..., max_length=512)
    content_angle: Optional[str] = Field(None, max_length=2000)


class PlanJsonSchema(BaseModel):
    """Strict schema for plan_json (30-day plan)."""

    days: List[PlanDayItem] = Field(..., min_length=1, max_length=30)


class PlanOut(BaseModel):
    """Generated plan in API response."""

    id: UUID
    tenant_id: UUID
    start_date: date
    end_date: date
    plan_json: Dict[str, Any]
    confidence_score: float
    approval_status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlanGenerateResponse(BaseModel):
    """Response for POST /api/plans/generate (201)."""

    plan: PlanOut
