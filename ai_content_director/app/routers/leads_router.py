"""
API lead signals: GET /api/leads (list theo tenant, filter status).
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.leads import LeadListResponse
from app.services.lead_service import list_leads

router = APIRouter(prefix="/api", tags=["leads"])


@router.get("/leads", response_model=LeadListResponse)
async def get_leads(
    tenant_id: UUID = Query(..., description="Tenant UUID"),
    status: str | None = Query(None, description="Lọc theo status (vd: new_auto, new_draft)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> LeadListResponse:
    """Danh sách lead signals của tenant, mới nhất trước."""
    return await list_leads(db, tenant_id=tenant_id, status=status, limit=limit, offset=offset)
