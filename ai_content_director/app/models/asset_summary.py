"""Asset summary model - lưu tóm tắt media từ content_assets."""
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AssetSummary(Base):
    """
    Cache summary theo (tenant_id, asset_id) để tránh gọi GPT lặp lại.
    asset_id trỏ tới content_assets.id.
    """

    __tablename__ = "asset_summaries"

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
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detected_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    objects_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    insights_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    suggested_angle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_tone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
