"""Audit event schemas."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    """Một dòng audit log."""

    id: UUID
    tenant_id: UUID
    content_id: Optional[UUID] = None
    event_type: str
    actor: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class AuditEventsResponse(BaseModel):
    """Response cho GET /audit/events."""

    tenant_id: UUID
    events: List[AuditEventOut]
