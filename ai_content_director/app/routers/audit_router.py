"""Audit log API: liệt kê events (GENERATE_PLAN, GENERATE_CONTENT, APPROVED, ...)."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.audit import AuditEventOut, AuditEventsResponse
from app.services.approval_service import list_audit_events

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events", response_model=AuditEventsResponse)
async def get_audit_events(
    tenant_id: UUID = Query(..., description="Tenant UUID"),
    limit: int = Query(50, ge=1, le=200, description="Số dòng tối đa"),
    db: AsyncSession = Depends(get_db),
) -> AuditEventsResponse:
    """Lấy audit log của tenant (mới nhất trước)."""
    events = await list_audit_events(db, tenant_id=tenant_id, limit=limit)
    out = [
        AuditEventOut(
            id=ev.id,
            tenant_id=ev.tenant_id,
            content_id=ev.content_id,
            event_type=ev.event_type,
            actor=ev.actor,
            metadata=ev.metadata_,
            created_at=ev.created_at,
        )
        for ev in events
    ]
    return AuditEventsResponse(tenant_id=tenant_id, events=out)
