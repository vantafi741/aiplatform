"""Brand profile model."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class BrandProfile(Base):
    """Brand profile per tenant."""

    __tablename__ = "brand_profiles"

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
    brand_tone: Mapped[str] = mapped_column(Text, nullable=True)
    main_services: Mapped[str] = mapped_column(Text, nullable=True)
    target_customer: Mapped[str] = mapped_column(Text, nullable=True)
    cta_style: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    tenant = relationship("Tenant", back_populates="brand_profiles")
