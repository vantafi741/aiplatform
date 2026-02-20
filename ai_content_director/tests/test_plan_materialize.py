"""
Test POST /api/plans/{plan_id}/materialize: plan from generated_plans is found and materialized.
- Create tenant -> POST /api/plans/generate -> POST /api/plans/{plan_id}/materialize -> assert 200 and content_items count.
"""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_factory
from app.models import ContentItem, GeneratedPlan, Tenant


@pytest.mark.asyncio
async def test_plan_generate_then_materialize() -> None:
    """
    Create tenant, generate plan (POST /api/plans/generate), then materialize (POST /api/plans/{plan_id}/materialize).
    Assert 200 and content_items_created matches number of days in plan (e.g. 30).
    """
    async with async_session_factory() as session:
        tenant = Tenant(
            id=uuid.uuid4(),
            name="Materialize Test Tenant",
            industry="Test",
        )
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
        tenant_id = tenant.id

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1) Generate plan
        gen_resp = await client.post(
            "/api/plans/generate",
            json={"tenant_id": str(tenant_id)},
        )
        assert gen_resp.status_code == 201, gen_resp.text
        gen_data = gen_resp.json()
        assert "plan" in gen_data
        plan_id = gen_data["plan"]["id"]
        plan_json = gen_data["plan"].get("plan_json") or {}
        days = plan_json.get("days") or []
        expected_count = len(days)
        assert expected_count >= 1, "plan should have at least one day"

        # 2) Materialize
        mat_resp = await client.post(
            f"/api/plans/{plan_id}/materialize",
            json={"tenant_id": str(tenant_id)},
        )
        assert mat_resp.status_code == 200, mat_resp.text
        mat_data = mat_resp.json()
        assert mat_data.get("plan_id") == plan_id
        assert "content_items_created" in mat_data
        assert "content_plans_created" in mat_data
        assert mat_data["content_items_created"] == expected_count, (
            f"content_items_created should equal days length: {mat_data['content_items_created']} != {expected_count}"
        )
        assert mat_data["content_plans_created"] == expected_count

    # 3) Verify DB: content_items for this tenant count
    async with async_session_factory() as session:
        r = await session.execute(
            select(ContentItem).where(ContentItem.tenant_id == tenant_id)
        )
        items = list(r.scalars().all())
        assert len(items) >= expected_count


@pytest.mark.asyncio
async def test_plan_materialize_404_when_plan_not_found() -> None:
    """POST /api/plans/{plan_id}/materialize with non-existent plan_id returns 404."""
    async with async_session_factory() as session:
        r = await session.execute(select(Tenant).limit(1))
        tenant = r.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(id=uuid.uuid4(), name="T", industry="T")
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
        tenant_id = tenant.id

    from app.main import app

    fake_plan_id = uuid.uuid4()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/plans/{fake_plan_id}/materialize",
            json={"tenant_id": str(tenant_id)},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json().get("detail", "").lower()
