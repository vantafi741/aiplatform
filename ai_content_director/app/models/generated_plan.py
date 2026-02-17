"""Generated plan model: 30-day plan with plan_json JSONB (Revenue MVP Module 1)."""
import uuid
from datetime import date, datetime
from typing import Any, Dict

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class GeneratedPlan(Base):
    """
    One generated 30-day content plan per row.
    plan_json: JSONB with schema { "days": [ { "day": 1, "topic": "...", "content_angle": "..." }, ... ] }.
    approval_status: APPROVED | DRAFT | ESCALATE (HITL).
    """

    __tablename__ = "generated_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    plan_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    tenant = relationship("Tenant", back_populates="generated_plans")
    revenue_content_items = relationship(
        "RevenueContentItem",
        back_populates="plan",
        cascade="all, delete-orphan",
    )
