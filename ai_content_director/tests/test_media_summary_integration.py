"""Tests cho Media Summary API + tích hợp vào /api/content/generate."""
import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db import async_session_factory
from app.models import ContentAsset, GeneratedPlan, RevenueContentItem, Tenant


@pytest.mark.asyncio
async def test_media_analyze_cache_by_tenant_asset() -> None:
    """Gọi /api/media/analyze 2 lần cùng asset -> lần 2 cached=true."""
    async with async_session_factory() as db:
        tenant = Tenant(id=uuid.uuid4(), name="Media Summary Tenant", industry="Test")
        db.add(tenant)
        await db.flush()
        asset = ContentAsset(
            tenant_id=tenant.id,
            content_id=None,
            asset_type="image",
            drive_file_id=f"drive_{uuid.uuid4().hex[:8]}",
            file_name="demo.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
            storage_url="https://images.unsplash.com/photo-1518770660439-4636190af475",
            local_path=None,
            status="cached",
        )
        db.add(asset)
        await db.commit()
        tenant_id = tenant.id
        asset_id = asset.id

    fake_summary = {
        "summary": "Ảnh dây chuyền cơ khí với cụm máy chính.",
        "detected_text": "",
        "objects_json": {"objects": ["machine", "factory"]},
        "insights_json": {"key_points": ["môi trường sản xuất"]},
        "suggested_angle": "Nhấn mạnh năng lực vận hành.",
        "suggested_tone": "professional",
        "confidence_score": 0.86,
        "model": "gpt-4o-mini",
        "usage": {"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33},
    }
    mocked_openai = AsyncMock(return_value=fake_summary)

    from app.main import app

    with patch("app.services.asset_summary_service._generate_summary_with_openai", mocked_openai):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {"tenant_id": str(tenant_id), "asset_id": str(asset_id)}

            resp1 = await client.post("/api/media/analyze", json=payload)
            assert resp1.status_code == 200, resp1.text
            d1 = resp1.json()
            assert d1["cached"] is False
            assert d1["summary"]
            assert d1["summary_id"]

            resp2 = await client.post("/api/media/analyze", json=payload)
            assert resp2.status_code == 200, resp2.text
            d2 = resp2.json()
            assert d2["cached"] is True
            assert d2["summary_id"] == d1["summary_id"]

    assert mocked_openai.await_count == 1


@pytest.mark.asyncio
async def test_content_generate_with_asset_id_persists_summary_snapshot() -> None:
    """POST /api/content/generate với asset_id phải lưu asset_id/summary_id/snapshot."""
    async with async_session_factory() as db:
        tenant = Tenant(id=uuid.uuid4(), name="MV2 Tenant", industry="Cơ khí")
        db.add(tenant)
        await db.flush()

        plan = GeneratedPlan(
            tenant_id=tenant.id,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=29),
            plan_json={"days": [{"day": 1, "topic": "Gia công CNC", "content_angle": "Độ chính xác và vật liệu"}]},
            confidence_score=0.9,
            approval_status="APPROVED",
        )
        db.add(plan)
        await db.flush()

        asset = ContentAsset(
            tenant_id=tenant.id,
            content_id=None,
            asset_type="image",
            drive_file_id=f"drive_{uuid.uuid4().hex[:8]}",
            file_name="cnc.jpg",
            mime_type="image/jpeg",
            size_bytes=2048,
            storage_url="https://images.unsplash.com/photo-1518770660439-4636190af475",
            local_path=None,
            status="cached",
        )
        db.add(asset)
        await db.commit()
        tenant_id = tenant.id
        plan_id = plan.id
        asset_id = asset.id

    fake_summary = {
        "summary": "Ảnh máy CNC đang gia công chi tiết kim loại.",
        "detected_text": "",
        "objects_json": {"objects": ["cnc", "metal"]},
        "insights_json": {"key_points": ["năng lực gia công"]},
        "suggested_angle": "Nêu rõ độ chính xác và vật liệu.",
        "suggested_tone": "technical",
        "confidence_score": 0.9,
        "model": "gpt-4o-mini",
        "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
    }
    fake_content = (
        {
            "content_type": "POST",
            "title": "Gia công CNC chính xác cao",
            "caption": "Chi tiết cơ khí được gia công với dung sai ổn định.",
            "hashtags": ["#cnc", "#cokhi", "#gia-cong", "#sanxuat", "#b2b"],
            "confidence_score": 0.88,
        },
        {"prompt_tokens": 50, "completion_tokens": 60, "total_tokens": 110},
    )

    from app.main import app

    with (
        patch("app.services.asset_summary_service._generate_summary_with_openai", AsyncMock(return_value=fake_summary)),
        patch("app.services.llm_service.LLMService.generate_single_content", AsyncMock(return_value=fake_content)),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "tenant_id": str(tenant_id),
                "plan_id": str(plan_id),
                "day": 1,
                "asset_id": str(asset_id),
            }
            resp = await client.post("/api/content/generate", json=payload)
            assert resp.status_code == 201, resp.text
            data = resp.json()["content"]
            assert data["asset_id"] == str(asset_id)
            assert data["summary_id"] is not None
            assert data["summary_snapshot_json"] is not None

    async with async_session_factory() as db:
        q = await db.execute(
            select(RevenueContentItem).where(
                RevenueContentItem.tenant_id == tenant_id,
                RevenueContentItem.plan_id == plan_id,
                RevenueContentItem.day == 1,
            )
        )
        row = q.scalar_one_or_none()
        assert row is not None
        assert row.asset_id == asset_id
        assert row.summary_id is not None
        assert isinstance(row.summary_snapshot_json, dict)
