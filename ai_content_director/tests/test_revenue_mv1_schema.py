"""
Minimal tests for Revenue MVP Module 1 schema validation.
PlanJsonSchema: strict JSON schema for 30-day plan (days[].day, topic, content_angle).
HITL: approval_status_from_confidence.
"""
import pytest
from pydantic import ValidationError

from app.schemas.revenue_mv1 import PlanJsonSchema, PlanDayItem
from app.services.plan_service_mv1 import approval_status_from_confidence


def test_plan_day_item_valid() -> None:
    """PlanDayItem accepts day 1-30, topic, optional content_angle."""
    item = PlanDayItem(day=1, topic="Topic A", content_angle="Angle A")
    assert item.day == 1
    assert item.topic == "Topic A"
    assert item.content_angle == "Angle A"

    item2 = PlanDayItem(day=30, topic="Topic B")
    assert item2.content_angle is None


def test_plan_day_item_invalid_day() -> None:
    """PlanDayItem rejects day < 1 or > 30."""
    with pytest.raises(ValidationError):
        PlanDayItem(day=0, topic="x", content_angle=None)
    with pytest.raises(ValidationError):
        PlanDayItem(day=31, topic="x", content_angle=None)


def test_plan_json_schema_valid() -> None:
    """PlanJsonSchema accepts 1-30 days."""
    data = {
        "days": [
            {"day": d, "topic": f"Topic {d}", "content_angle": f"Angle {d}"}
            for d in range(1, 31)
        ]
    }
    schema = PlanJsonSchema.model_validate(data)
    assert len(schema.days) == 30
    assert schema.days[0].day == 1
    assert schema.days[29].day == 30


def test_plan_json_schema_empty_days_fails() -> None:
    """PlanJsonSchema requires at least one day."""
    with pytest.raises(ValidationError):
        PlanJsonSchema.model_validate({"days": []})


def test_plan_json_schema_more_than_30_days_fails() -> None:
    """PlanJsonSchema rejects more than 30 days."""
    data = {
        "days": [
            {"day": d, "topic": f"T{d}", "content_angle": None}
            for d in range(1, 32)
        ]
    }
    with pytest.raises(ValidationError):
        PlanJsonSchema.model_validate(data)


def test_hitl_approved() -> None:
    """confidence >= 0.85 => APPROVED."""
    assert approval_status_from_confidence(0.85) == "APPROVED"
    assert approval_status_from_confidence(0.90) == "APPROVED"
    assert approval_status_from_confidence(1.0) == "APPROVED"


def test_hitl_draft() -> None:
    """0.70 <= confidence < 0.85 => DRAFT."""
    assert approval_status_from_confidence(0.70) == "DRAFT"
    assert approval_status_from_confidence(0.80) == "DRAFT"
    assert approval_status_from_confidence(0.84) == "DRAFT"


def test_hitl_escalate() -> None:
    """confidence < 0.70 => ESCALATE."""
    assert approval_status_from_confidence(0.69) == "ESCALATE"
    assert approval_status_from_confidence(0.0) == "ESCALATE"
