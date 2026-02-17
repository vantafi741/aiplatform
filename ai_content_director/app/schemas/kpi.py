"""KPI summary và fetch-now request/response."""
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class KpiFetchNowRequest(BaseModel):
    """Body cho POST /kpi/fetch-now."""

    tenant_id: UUID = Field(..., description="Tenant UUID")
    days: int = Field(7, ge=1, le=30, description="Lấy bài đăng trong N ngày gần đây (tối đa 30)")
    limit: int = Field(20, ge=1, le=50, description="Số bài tối đa (tối đa 50)")


class KpiFetchNowResponse(BaseModel):
    """Response sau khi gọi POST /kpi/fetch-now."""

    tenant_id: UUID
    fetched: int = Field(..., description="Số bài đã gọi fetch")
    success: int = Field(..., description="Số lần lấy metrics thành công")
    fail: int = Field(..., description="Số lần lỗi")


class KpiPostSummary(BaseModel):
    """Một post trong KPI summary."""

    post_id: Optional[str] = None
    fetched_at: Optional[str] = None
    reach: Optional[int] = None
    impressions: Optional[int] = None
    reactions: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None


class KpiTotals(BaseModel):
    """Tổng reach, impressions, reactions, comments, shares."""

    reach: int = 0
    impressions: int = 0
    reactions: int = 0
    comments: int = 0
    shares: int = 0


class KpiSummaryResponse(BaseModel):
    """GET /kpi/summary."""

    tenant_id: UUID
    range_days: int
    totals: KpiTotals
    posts: List[KpiPostSummary]
