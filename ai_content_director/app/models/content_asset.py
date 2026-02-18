"""Content asset model – ảnh/video từ Google Drive dropzone."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ContentAsset(Base):
    """
    Asset (image/video) từ Google Drive.
    status: READY | PROCESSED | REJECTED.
    content_id nullable: asset chưa gắn content (dùng use_latest_asset khi publish).
    """

    __tablename__ = "content_assets"

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
    content_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    drive_file_id: Mapped[str] = mapped_column(String(128), nullable=False)
    drive_parent_folder: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger(), nullable=True)
    asset_type: Mapped[str] = mapped_column(String(16), nullable=False)
    local_path: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="READY", nullable=False)
    error_reason: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    tenant = relationship("Tenant", back_populates="content_assets")
    content_item = relationship("ContentItem", back_populates="content_assets")
