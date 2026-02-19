"""Content plan model (30-day planner). Một row = một plan 30 ngày, plan_json chứa 30 entries."""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ContentPlan(Base):
    """
    Content plan: 1 row = 1 kế hoạch 30 ngày.
    plan_json: [{"day_number": 1, "topic": "...", "content_angle": "...", "caption": "..."}, ...]
    day_number, topic, content_angle nullable khi dùng plan_json (giữ cho tương thích).
    """

    __tablename__ = "content_plans"

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
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    objective: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    tone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    plan_json: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSONB(), nullable=True)
    day_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    topic: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    content_angle: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="planned", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    tenant = relationship("Tenant", back_populates="content_plans")
    content_items = relationship("ContentItem", back_populates="plan")
