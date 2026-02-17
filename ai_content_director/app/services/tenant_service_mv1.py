"""Tenant service for Revenue MVP Module 1: create tenant."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant

from app.schemas.revenue_mv1 import TenantCreate


async def create_tenant(db: AsyncSession, payload: TenantCreate) -> Tenant:
    """
    Create a new tenant. Returns the created Tenant.
    """
    tenant = Tenant(
        name=payload.name,
        industry=payload.industry,
    )
    db.add(tenant)
    await db.flush()
    await db.refresh(tenant)
    return tenant
