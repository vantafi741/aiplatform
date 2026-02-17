"""Content request/response schemas."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ContentGenerateSamplesRequest(BaseModel):
    """Request body for POST /content/generate-samples (cost guard: max 20)."""

    tenant_id: UUID = Field(..., description="Tenant UUID")
    count: int = Field(10, ge=1, le=20, description="Number of sample posts (1-20)")


class ContentItemOut(BaseModel):
    """Single content item (HITL + scheduler fields)."""

    id: UUID
    title: str
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    status: str
    confidence_score: Optional[float] = None
    review_state: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    schedule_status: Optional[str] = None
    publish_attempts: Optional[int] = None
    last_publish_error: Optional[str] = None
    last_publish_at: Optional[datetime] = None


class ContentGenerateSamplesResponse(BaseModel):
    """Response for POST /content/generate-samples (201)."""

    tenant_id: UUID
    created: int
    items: List[ContentItemOut]
    used_ai: bool = False
    used_fallback: bool = False
    model: Optional[str] = None


# --- HITL Approval ---


class ContentListResponse(BaseModel):
    """Response for GET /content/list."""

    tenant_id: UUID
    items: List[ContentItemOut]


class ApproveRequest(BaseModel):
    """Body for POST /content/{content_id}/approve."""

    tenant_id: UUID = Field(..., description="Tenant UUID")
    actor: str = Field("HUMAN", description="HUMAN | SYSTEM")


class RejectRequest(BaseModel):
    """Body for POST /content/{content_id}/reject."""

    tenant_id: UUID = Field(..., description="Tenant UUID")
    actor: str = Field("HUMAN", description="HUMAN | SYSTEM")
    reason: str = Field(..., min_length=1, description="Lý do từ chối")


# --- Scheduler ---


class ScheduleRequest(BaseModel):
    """Body for POST /content/{content_id}/schedule."""

    tenant_id: UUID = Field(..., description="Tenant UUID")
    scheduled_at: datetime = Field(..., description="ISO datetime (UTC hoặc Asia/Ho_Chi_Minh)")


class ScheduleResponse(BaseModel):
    """Response after scheduling."""

    content_id: UUID
    schedule_status: str
    scheduled_at: Optional[datetime] = None


class UnscheduleRequest(BaseModel):
    """Body for POST /content/{content_id}/unschedule."""

    tenant_id: UUID = Field(..., description="Tenant UUID")


class UnscheduleResponse(BaseModel):
    """Response after unschedule."""

    content_id: UUID
    schedule_status: str = "none"