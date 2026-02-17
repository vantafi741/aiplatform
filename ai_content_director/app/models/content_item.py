"""Content item model."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ContentItem(Base):
    """
    Content item (post/caption).
    status: draft | approved | published (publish lifecycle).
    review_state: auto_approved | needs_review | escalate_required | approved | rejected (HITL).
    """

    __tablename__ = "content_items"

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
    plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=True)
    hashtags: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    review_state: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Scheduler: none | scheduled | publishing | published | failed
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    schedule_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    publish_attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    last_publish_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_publish_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    tenant = relationship("Tenant", back_populates="content_items")
    plan = relationship("ContentPlan", back_populates="content_items")
    publish_logs = relationship("PublishLog", back_populates="content_item")
    approval_events = relationship("ApprovalEvent", back_populates="content_item")
    post_metrics = relationship("PostMetrics", back_populates="content_item")
