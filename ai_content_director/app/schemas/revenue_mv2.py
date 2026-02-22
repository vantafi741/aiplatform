"""Schemas for Revenue MVP Module 2: Content Generator (plan -> content items)."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ContentTypeEnum(str, Enum):
    """Content type: POST | REEL | CAROUSEL."""

    POST = "POST"
    REEL = "REEL"
    CAROUSEL = "CAROUSEL"


class ApprovalStatusEnum(str, Enum):
    """HITL approval status."""

    APPROVED = "APPROVED"
    DRAFT = "DRAFT"
    ESCALATE = "ESCALATE"


# --- POST /api/content/generate ---
class ContentGenerateRequest(BaseModel):
    """Request body for POST /api/content/generate."""

    tenant_id: UUID = Field(..., description="Tenant UUID")
    plan_id: UUID = Field(..., description="Generated plan UUID")
    day: int = Field(..., ge=1, le=30, description="Day 1..30 in the plan")
    asset_id: Optional[UUID] = Field(default=None, description="Optional content_assets.id để bám media summary")

    model_config = {"extra": "forbid"}


class ContentItemOut(BaseModel):
    """Content item in API response. hashtags: list[str] length 5..30."""

    id: UUID
    tenant_id: UUID
    plan_id: UUID
    day: int
    topic: str
    content_angle: str
    content_type: str
    title: str
    caption: str
    hashtags: List[str]
    confidence_score: float
    approval_status: str
    asset_id: Optional[UUID] = None
    summary_id: Optional[UUID] = None
    summary_snapshot_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("hashtags")
    @classmethod
    def hashtags_bounds(cls, v: List[str]) -> List[str]:
        """Validate hashtags list length 5..30."""
        if not isinstance(v, list):
            raise ValueError("hashtags must be a list")
        if len(v) < 5 or len(v) > 30:
            raise ValueError("hashtags must have 5 to 30 items")
        return [str(x) for x in v]


class ContentGenerateResponse(BaseModel):
    """Response for POST /api/content/generate (201)."""

    content: ContentItemOut
