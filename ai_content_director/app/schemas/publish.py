"""Publish request/response và publish log output."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PublishFacebookRequest(BaseModel):
    """Body cho POST /publish/facebook."""

    tenant_id: UUID = Field(..., description="Tenant UUID")
    content_id: UUID = Field(..., description="Content item UUID (phải đã approved)")
    use_latest_asset: bool = Field(
        False,
        description="Nếu true và content require_media: dùng asset unattached mới nhất của tenant khi không có asset gắn content",
    )


class PublishFacebookResponse(BaseModel):
    """Response sau khi gửi đăng Facebook."""

    tenant_id: UUID
    content_id: UUID
    log_id: UUID
    status: str  # queued | success | fail
    post_id: Optional[str] = None
    error_message: Optional[str] = None


class PublishLogOut(BaseModel):
    """Một dòng publish log."""

    id: UUID
    content_id: UUID
    platform: str
    post_id: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    published_at: Optional[datetime] = None
    created_at: datetime


class PublishLogsResponse(BaseModel):
    """Response cho GET /publish/logs."""

    tenant_id: UUID
    logs: List[PublishLogOut]
