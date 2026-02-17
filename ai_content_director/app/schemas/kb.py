"""KB (Knowledge Base) request/response schemas."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class KbItemCreate(BaseModel):
    """Body cho POST /kb/items (tạo một mục)."""

    tenant_id: UUID = Field(..., description="Tenant UUID")
    title: str = Field(..., min_length=1, max_length=2000)
    content: str = Field(..., min_length=1)
    tags: List[str] = Field(default_factory=list, max_length=50)


class KbItemOut(BaseModel):
    """Một mục KB trả về API."""

    id: UUID
    tenant_id: UUID
    title: str
    content: str
    tags: Optional[List[str]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class KbBulkItem(BaseModel):
    """Một mục trong bulk ingest."""

    title: str = Field(..., min_length=1, max_length=2000)
    content: str = Field(..., min_length=1)
    tags: List[str] = Field(default_factory=list, max_length=50)


class KbBulkRequest(BaseModel):
    """Body cho POST /kb/items/bulk."""

    tenant_id: UUID = Field(..., description="Tenant UUID")
    items: List[KbBulkItem] = Field(..., min_length=1, max_length=500)


class KbBulkResponse(BaseModel):
    """Response sau bulk ingest."""

    tenant_id: UUID
    created: int
    ids: List[UUID]


class KbQueryRequest(BaseModel):
    """Body cho POST /kb/query (ILIKE search)."""

    tenant_id: UUID = Field(..., description="Tenant UUID")
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(10, ge=1, le=50, description="Số kết quả tối đa")


class KbQueryItem(BaseModel):
    """Một mục trong kết quả query."""

    id: UUID
    title: str
    content: str
    tags: Optional[List[str]] = None


class KbQueryResponse(BaseModel):
    """Response POST /kb/query."""

    tenant_id: UUID
    query: str
    items: List[KbQueryItem]
    total: int
