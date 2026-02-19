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
    plan_id: Optional[UUID] = None
    created: int
    items: List[PlanItemOut]
    used_ai: bool = False
    used_fallback: bool = False
    model: Optional[str] = None


class PlanMaterializeRequest(BaseModel):
    """Body cho POST /api/plans/{plan_id}/materialize."""

    tenant_id: UUID = Field(..., description="Tenant UUID")
    timezone: str = Field("Asia/Ho_Chi_Minh", description="Timezone cho scheduled_at")
    posting_hours: List[str] = Field(
        default_factory=lambda: ["09:00", "19:30"],
        description="Giờ đăng mỗi ngày (round-robin), format HH:MM",
    )
    start_date: str = Field(..., description="Ngày bắt đầu YYYY-MM-DD")
    channel: str = Field("facebook", description="Kênh đăng")
    default_status: str = Field("draft", description="status mặc định: draft | approved")


class PlanMaterializeResponse(BaseModel):
    """Response sau materialize."""

    plan_id: UUID
    count_created: int
    content_item_ids: List[UUID]


class PlanDetailItemOut(BaseModel):
    """Một content item đã materialize (trong GET /api/plans/{plan_id})."""

    id: UUID
    title: Optional[str] = None
    caption: Optional[str] = None
    status: str
    scheduled_at: Optional[str] = None
    channel: Optional[str] = None
    content_type: Optional[str] = None


class PlanDetailResponse(BaseModel):
    """Response GET /api/plans/{plan_id}: plan + list items đã materialize."""

    id: UUID
    tenant_id: UUID
    title: Optional[str] = None
    objective: Optional[str] = None
    tone: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    items: List[PlanDetailItemOut]

