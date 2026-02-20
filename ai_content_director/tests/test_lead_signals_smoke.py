"""
Smoke test cho bảng lead_signals và AI Lead System.
- test_lead_signals_insert_count_and_join: insert 1 row, count + join content_items.
- test_webhook_facebook_and_get_leads: POST /webhooks/facebook -> GET /api/leads; assert intent/priority/confidence/status.
- test_webhook_dedup: POST 2 lần cùng payload; lần 2 created=0, lead count không tăng.
Cần DB đã chạy migration 012 (alembic upgrade head).
Chạy: pytest tests/test_lead_signals_smoke.py -v
"""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_factory
from app.models import ContentItem, LeadSignal, Tenant


async def _get_or_create_tenant_and_content(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Lấy hoặc tạo 1 tenant + 1 content_item để gắn lead_signal."""
    r = await session.execute(select(ContentItem).limit(1))
    existing = r.scalar_one_or_none()
    if existing:
        return existing.tenant_id, existing.id
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Smoke Tenant",
        industry="Test",
    )
    session.add(tenant)
    item = ContentItem(
        tenant_id=tenant.id,
        title="Smoke content",
        caption="For lead_signal smoke test",
        status="draft",
    )
    session.add(item)
    await session.flush()
    return tenant.id, item.id


@pytest.mark.asyncio
async def test_lead_signals_insert_count_and_join() -> None:
    """
    Insert 1 lead_signal trỏ tới content_item có sẵn (hoặc tạo tenant+content).
    Kiểm tra: SELECT count(*) và join lead_signals với content_items.
    """
    async with async_session_factory() as session:
        tenant_id, content_id = await _get_or_create_tenant_and_content(session)

        lead = LeadSignal(
            tenant_id=tenant_id,
            platform="facebook",
            source_type="comment",
            source_subtype="post_comment",
            content_id=content_id,
            author_name="Smoke User",
            content_text="I want to know more",
            intent_label="inquiry",
            status="new",
            priority="medium",
            confidence_score=0.9,
        )
        session.add(lead)
        await session.commit()
        lead_id = lead.id

    async with async_session_factory() as session:
        r = await session.execute(
            select(func.count(LeadSignal.id)).where(LeadSignal.tenant_id == tenant_id)
        )
        count = r.scalar_one_or_none()
        assert count is not None and count >= 1, "lead_signals count phải >= 1"

        r2 = await session.execute(
            select(LeadSignal, ContentItem.title)
            .join(ContentItem, ContentItem.id == LeadSignal.content_id)
            .where(LeadSignal.id == lead_id)
        )
        row = r2.one_or_none()
        assert row is not None, "Join lead_signals với content_items phải trả về 1 row"
        ls, title = row
        assert ls.content_id == content_id
        assert title == "Smoke content"


@pytest.mark.asyncio
async def test_webhook_facebook_and_get_leads() -> None:
    """
    Smoke test AI Lead System: tenant -> POST /webhooks/facebook (mock payload)
    -> GET /api/leads; assert intent_label, priority, confidence_score, status (new_auto|new_draft|new_escalate).
    """
    async with async_session_factory() as session:
        r = await session.execute(select(Tenant).limit(1))
        tenant = r.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                id=uuid.uuid4(),
                name="Webhook Smoke Tenant",
                industry="Test",
            )
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
        tenant_id = tenant.id

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "object": "page",
            "tenant_id": str(tenant_id),
            "entry": [
                {
                    "message": "Cho tôi báo giá gói Enterprise",
                    "sender_name": "Smoke Webhook User",
                    "sender_id": "sw1",
                    "post_id": "sp1",
                    "comment_id": "smoke-webhook-c1",
                }
            ],
        }
        resp = await client.post("/webhooks/facebook", json=payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("created", 0) >= 1
        assert len(data.get("lead_ids", [])) >= 1

        list_resp = await client.get(f"/api/leads?tenant_id={tenant_id}&limit=5")
        assert list_resp.status_code == 200, list_resp.text
        list_data = list_resp.json()
        assert "leads" in list_data
        assert list_data.get("total", 0) >= 1
        leads = list_data["leads"]
        assert len(leads) >= 1
        first = leads[0]
        assert "intent_label" in first
        assert "priority" in first
        assert "confidence_score" in first
        assert "status" in first
        assert first.get("status") in ("new_auto", "new_draft", "new_escalate"), (
            f"status phải là new_auto|new_draft|new_escalate, got {first.get('status')}"
        )
        assert first.get("platform") == "facebook"
        assert first.get("content_text") or first.get("author_name")


@pytest.mark.asyncio
async def test_webhook_dedup() -> None:
    """
    Dedup theo external_message_id: gọi POST /webhooks/facebook 2 lần với cùng tenant_id và comment_id.
    Lần 2 phải trả về created=0 (hoặc lead count không tăng).
    """
    async with async_session_factory() as session:
        r = await session.execute(select(Tenant).limit(1))
        tenant = r.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                id=uuid.uuid4(),
                name="Dedup Smoke Tenant",
                industry="Test",
            )
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
        tenant_id = tenant.id

    from app.main import app

    payload = {
        "object": "page",
        "tenant_id": str(tenant_id),
        "entry": [
            {
                "message": "Tôi cần tư vấn",
                "sender_name": "Dedup User",
                "sender_id": "du1",
                "post_id": "dp1",
                "comment_id": "dedup-unique-cid-001",
            }
        ],
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp1 = await client.post("/webhooks/facebook", json=payload)
        assert resp1.status_code == 200, resp1.text
        data1 = resp1.json()
        assert data1.get("ok") is True
        created1 = data1.get("created", 0)
        assert created1 >= 1, "Lần 1 phải tạo ít nhất 1 lead"

        list1 = await client.get(f"/api/leads?tenant_id={tenant_id}&limit=100")
        assert list1.status_code == 200
        total1 = list1.json().get("total", 0)

        # Gửi lại cùng payload (cùng comment_id)
        resp2 = await client.post("/webhooks/facebook", json=payload)
        assert resp2.status_code == 200, resp2.text
        data2 = resp2.json()
        assert data2.get("ok") is True
        created2 = data2.get("created", 0)
        assert created2 == 0, f"Dedup: lần 2 phải created=0, got {created2}"

        list2 = await client.get(f"/api/leads?tenant_id={tenant_id}&limit=100")
        assert list2.status_code == 200
        total2 = list2.json().get("total", 0)
        assert total2 == total1, f"Dedup: total lead không được tăng sau lần 2: {total1} -> {total2}"
