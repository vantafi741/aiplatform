"""Schema cho Google Drive ingest và content assets."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class GdriveIngestRequest(BaseModel):
    """Body cho POST /api/gdrive/ingest."""

    tenant_id: UUID = Field(..., description="Tenant UUID")


class GdriveIngestResponse(BaseModel):
    """Response sau khi ingest."""

    tenant_id: UUID
    count_ingested: int = Field(..., description="Số asset đã tải và ghi READY")
    count_invalid: int = Field(..., description="Số file invalid (đã chuyển REJECTED)")


class ContentAssetOut(BaseModel):
    """Một dòng content asset (GET /api/assets)."""

    id: UUID
    tenant_id: UUID
    content_id: Optional[UUID] = None
    drive_file_id: str
    drive_parent_folder: Optional[str] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    asset_type: str
    local_path: Optional[str] = None
    status: str
    error_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AssetsListResponse(BaseModel):
    """Response cho GET /api/assets."""

    tenant_id: UUID
    assets: List[ContentAssetOut]
