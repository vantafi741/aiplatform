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


class ContentItemApproveRequest(BaseModel):
    """Body cho POST /api/content_items/{item_id}/approve."""

    tenant_id: UUID = Field(..., description="Tenant UUID")
    approved_by: str = Field(..., description="manual:<email_or_name>")


class ContentItemApproveResponse(BaseModel):
    """Response sau approve."""

    item_id: UUID
    status: str
    approved_at: Optional[datetime] = None


class ContentItemRejectRequest(BaseModel):
    """Body cho POST /api/content_items/{item_id}/reject."""

    tenant_id: UUID = Field(..., description="Tenant UUID")
    rejected_by: str = Field(..., description="manual:<email_or_name>")
    reason: str = Field(..., min_length=1, description="Lý do từ chối")


class ContentItemRejectResponse(BaseModel):
    """Response sau reject."""

    item_id: UUID
    status: str


class ContentItemApiOut(BaseModel):
    """Một item trong GET /api/content_items."""

    id: UUID
    tenant_id: UUID
    plan_id: Optional[UUID] = None
    title: str
    caption: Optional[str] = None
    status: str
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    rejected_by: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    schedule_status: Optional[str] = None
    channel: Optional[str] = None
    content_type: Optional[str] = None
    publish_attempts: Optional[int] = None
    last_publish_attempt_at: Optional[datetime] = None
    last_publish_error: Optional[str] = None
    external_post_id: Optional[str] = None
    created_at: Optional[datetime] = None


class ContentItemsListResponse(BaseModel):
    """Response cho GET /api/content_items."""

    items: List[ContentItemApiOut]


class ContentItemPatchRequest(BaseModel):
    """Body cho PATCH /api/content_items/{item_id} (cập nhật scheduled_at, dùng cho smoke test / runbook)."""

    tenant_id: UUID = Field(..., description="Tenant UUID")
    scheduled_at: Optional[datetime] = Field(None, description="Thời điểm hẹn đăng (ISO); null = giữ nguyên")


class ContentItemPatchResponse(BaseModel):
    """Response sau PATCH."""

    item_id: UUID
    scheduled_at: Optional[datetime] = None