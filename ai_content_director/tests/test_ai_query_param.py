"""
Test query param ai=false reliably disables LLM calls.
- ensure_bool_query: "false" -> False, "true" -> True.
- POST /planner/generate?ai=false: used_ai=False, OpenAI generate_planner not called.
- POST /content/generate-samples?ai=false: used_ai=False, OpenAI generate_sample_posts not called.
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_factory
from app.models import Tenant
from app.utils.query_params import ensure_bool_query


def test_ensure_bool_query_false_strings() -> None:
    """ai=false (string) must be False so that LLM is not called."""
    assert ensure_bool_query("false") is False
    assert ensure_bool_query("False") is False
    assert ensure_bool_query("FALSE") is False
    assert ensure_bool_query("0") is False
    assert ensure_bool_query("no") is False
    assert ensure_bool_query("") is False
    assert ensure_bool_query(None) is False


def test_ensure_bool_query_true_strings() -> None:
    """ai=true (string) -> True."""
    assert ensure_bool_query("true") is True
    assert ensure_bool_query("True") is True
    assert ensure_bool_query("1") is True
    assert ensure_bool_query("yes") is True


def test_ensure_bool_query_native_bool() -> None:
    """Native bool unchanged."""
    assert ensure_bool_query(True) is True
    assert ensure_bool_query(False) is False


@pytest.mark.asyncio
async def test_planner_ai_false_openai_not_called() -> None:
    """
    POST /planner/generate?ai=false: used_ai must be False and LLMService.generate_planner must not be called.
    """
    async with async_session_factory() as session:
        tenant = Tenant(
            id=uuid.uuid4(),
            name="AI False Test",
            industry="Test",
        )
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
        tenant_id = tenant.id

    from app.main import app

    with patch(
        "app.services.planner_service.LLMService",
        autospec=True,
    ) as mock_llm_class:
        mock_llm_class.return_value.generate_planner = AsyncMock(side_effect=AssertionError("LLM should not be called"))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/planner/generate",
                json={"tenant_id": str(tenant_id), "days": 7},
                params={"ai": "false"},
            )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data.get("used_ai") is False, "ai=false must set used_ai=False"
        mock_llm_class.return_value.generate_planner.assert_not_called()


@pytest.mark.asyncio
async def test_content_ai_false_openai_not_called() -> None:
    """
    POST /content/generate-samples?ai=false: used_ai must be False and LLMService.generate_sample_posts must not be called.
    """
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

    with patch(
        "app.services.content_service.LLMService",
        autospec=True,
    ) as mock_llm_class:
        mock_llm_class.return_value.generate_sample_posts = AsyncMock(
            side_effect=AssertionError("LLM should not be called")
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/content/generate-samples",
                json={"tenant_id": str(tenant_id), "count": 2},
                params={"ai": "false"},
            )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data.get("used_ai") is False, "ai=false must set used_ai=False"
        mock_llm_class.return_value.generate_sample_posts.assert_not_called()
