"""Schema cho Media Analyze API dùng content_assets."""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MediaAnalyzeRequest(BaseModel):
    """Body cho POST /api/media/analyze."""

    tenant_id: UUID = Field(..., description="Tenant UUID")
    asset_id: UUID = Field(..., description="content_assets.id")


class MediaAnalyzeResponse(BaseModel):
    """Response package cho phân tích media."""

    tenant_id: UUID
    asset_id: UUID
    summary_id: UUID
    summary: str
    confidence_score: float = Field(0.0, description="Độ tự tin 0..1")
    suggested_angle: str = ""
    suggested_tone: str = ""
    insights_json: Dict[str, Any] = Field(default_factory=dict)
    cached: bool = False
    created_at: Optional[datetime] = None
