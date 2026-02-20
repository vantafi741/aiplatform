"""Lead signal model – sự kiện lead từ comment/inbox/call/form cho B2B KPI."""
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class LeadSignal(Base):
    """
    Bảng lưu lead events: comment, inbox, call, form.
    Dùng cho dashboard: đếm theo status/intent, top content dẫn lead, follow-up.
    """

    __tablename__ = "lead_signals"

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
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_subtype: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    content_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    publish_log_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("publish_logs.id", ondelete="SET NULL"),
        nullable=True,
    )
    external_post_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    external_thread_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    external_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    author_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intent_label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    priority: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    assignee: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    follow_up_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_contact_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    tenant = relationship("Tenant", back_populates="lead_signals")
    content_item = relationship("ContentItem", back_populates="lead_signals")
    publish_log = relationship("PublishLog", back_populates="lead_signals")
