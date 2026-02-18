"""Tenant model."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Tenant(Base):
    """Tenant (SME account) table."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    brand_profiles = relationship("BrandProfile", back_populates="tenant")
    industry_profiles = relationship("IndustryProfile", back_populates="tenant")
    generated_plans = relationship("GeneratedPlan", back_populates="tenant")
    revenue_content_items = relationship(
        "RevenueContentItem",
        back_populates="tenant",
    )
    content_plans = relationship("ContentPlan", back_populates="tenant")
    content_items = relationship("ContentItem", back_populates="tenant")
    kb_items = relationship("KbItem", back_populates="tenant")
    ai_usage_logs = relationship("AiUsageLog", back_populates="tenant")
    approval_events = relationship("ApprovalEvent", back_populates="tenant")
    post_metrics = relationship("PostMetrics", back_populates="tenant")
    content_assets = relationship("ContentAsset", back_populates="tenant")
