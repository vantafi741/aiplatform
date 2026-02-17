"""Planner request/response schemas."""
from typing import List, Optional
from uuid import UUID


from pydantic import BaseModel, Field


class PlannerGenerateRequest(BaseModel):
    """Request body for POST /planner/generate."""

    tenant_id: UUID = Field(..., description="Tenant UUID")
    days: int = Field(30, ge=1, le=30, description="Number of days (1-30)")


class PlanItemOut(BaseModel):
    """Single content plan item in response."""

    day_number: int
    topic: str
    content_angle: Optional[str] = None
    status: str


class PlannerGenerateResponse(BaseModel):
    """Response for POST /planner/generate (201)."""

    tenant_id: UUID
    created: int
    items: List[PlanItemOut]
    used_ai: bool = False
    used_fallback: bool = False
    model: Optional[str] = None

