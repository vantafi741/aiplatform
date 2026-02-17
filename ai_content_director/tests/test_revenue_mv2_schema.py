"""
Tests for Revenue MVP Module 2 schema validation.
Day bounds 1..30, hashtags 5..30, approval_status_from_confidence.
No OpenAI network calls.
"""
import pytest
from pydantic import ValidationError

from app.schemas.revenue_mv2 import (
    ContentGenerateRequest,
    ContentItemOut,
    ContentTypeEnum,
    ApprovalStatusEnum,
)
from app.services.content_service_mv2 import approval_status_from_confidence


def test_content_generate_request_day_bounds() -> None:
    """ContentGenerateRequest accepts day 1..30."""
    req = ContentGenerateRequest(
        tenant_id="11111111-1111-1111-1111-111111111111",
        plan_id="22222222-2222-2222-2222-222222222222",
        day=1,
    )
    assert req.day == 1
    req30 = ContentGenerateRequest(
        tenant_id="11111111-1111-1111-1111-111111111111",
        plan_id="22222222-2222-2222-2222-222222222222",
        day=30,
    )
    assert req30.day == 30


def test_content_generate_request_day_invalid() -> None:
    """ContentGenerateRequest rejects day < 1 or > 30."""
    with pytest.raises(ValidationError):
        ContentGenerateRequest(
            tenant_id="11111111-1111-1111-1111-111111111111",
            plan_id="22222222-2222-2222-2222-222222222222",
            day=0,
        )
    with pytest.raises(ValidationError):
        ContentGenerateRequest(
            tenant_id="11111111-1111-1111-1111-111111111111",
            plan_id="22222222-2222-2222-2222-222222222222",
            day=31,
        )


def test_content_item_out_hashtags_bounds() -> None:
    """ContentItemOut hashtags: 5..30 items."""
    from datetime import datetime, timezone
    from uuid import uuid4

    uid = uuid4()
    now = datetime.now(timezone.utc)
    valid_hashtags = ["#a", "#b", "#c", "#d", "#e"]
    item = ContentItemOut(
        id=uid,
        tenant_id=uid,
        plan_id=uid,
        day=1,
        topic="T",
        content_angle="A",
        content_type="POST",
        title="Title",
        caption="Cap",
        hashtags=valid_hashtags,
        confidence_score=0.8,
        approval_status="DRAFT",
        created_at=now,
        updated_at=now,
    )
    assert len(item.hashtags) == 5


def test_content_item_out_hashtags_too_few() -> None:
    """ContentItemOut rejects hashtags with < 5 items."""
    from datetime import datetime, timezone
    from uuid import uuid4

    uid = uuid4()
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        ContentItemOut(
            id=uid,
            tenant_id=uid,
            plan_id=uid,
            day=1,
            topic="T",
            content_angle="A",
            content_type="POST",
            title="Title",
            caption="Cap",
            hashtags=["#a", "#b"],
            confidence_score=0.8,
            approval_status="DRAFT",
            created_at=now,
            updated_at=now,
        )


def test_content_item_out_hashtags_too_many() -> None:
    """ContentItemOut rejects hashtags with > 30 items."""
    from datetime import datetime, timezone
    from uuid import uuid4

    uid = uuid4()
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        ContentItemOut(
            id=uid,
            tenant_id=uid,
            plan_id=uid,
            day=1,
            topic="T",
            content_angle="A",
            content_type="POST",
            title="Title",
            caption="Cap",
            hashtags=["#x"] * 31,
            confidence_score=0.8,
            approval_status="DRAFT",
            created_at=now,
            updated_at=now,
        )


def test_approval_status_from_confidence_approved() -> None:
    """confidence >= 0.85 => APPROVED."""
    assert approval_status_from_confidence(0.85) == "APPROVED"
    assert approval_status_from_confidence(0.9) == "APPROVED"
    assert approval_status_from_confidence(1.0) == "APPROVED"


def test_approval_status_from_confidence_draft() -> None:
    """0.70 <= confidence < 0.85 => DRAFT."""
    assert approval_status_from_confidence(0.70) == "DRAFT"
    assert approval_status_from_confidence(0.80) == "DRAFT"
    assert approval_status_from_confidence(0.84) == "DRAFT"


def test_approval_status_from_confidence_escalate() -> None:
    """confidence < 0.70 => ESCALATE."""
    assert approval_status_from_confidence(0.69) == "ESCALATE"
    assert approval_status_from_confidence(0.0) == "ESCALATE"


def test_content_type_enum() -> None:
    """ContentTypeEnum values."""
    assert ContentTypeEnum.POST.value == "POST"
    assert ContentTypeEnum.REEL.value == "REEL"
    assert ContentTypeEnum.CAROUSEL.value == "CAROUSEL"


def test_approval_status_enum() -> None:
    """ApprovalStatusEnum values."""
    assert ApprovalStatusEnum.APPROVED.value == "APPROVED"
    assert ApprovalStatusEnum.DRAFT.value == "DRAFT"
    assert ApprovalStatusEnum.ESCALATE.value == "ESCALATE"
