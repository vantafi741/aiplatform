"""Schemas cho pipeline Drive -> Facebook."""
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field


class DriveToFacebookRunRequest(BaseModel):
    """Body cho POST /api/pipelines/drive_to_facebook/run."""

    tenant_id: UUID = Field(..., description="Tenant UUID")


class DriveToFacebookRunResponse(BaseModel):
    """Kết quả chạy pipeline Drive -> Facebook."""

    ok: bool = True
    processed: int = 0
    skipped: int = 0
    errors: List[str] = Field(default_factory=list)

