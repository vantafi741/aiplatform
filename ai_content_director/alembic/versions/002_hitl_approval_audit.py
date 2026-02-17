"""HITL approval workflow + audit log

Revision ID: 002
Revises: 001
Create Date: 2025-02-17

- approval_events table (audit log)
- content_items: review_state, approved_at, rejected_at
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # content_items: thêm cột review_state, approved_at, rejected_at
    op.add_column(
        "content_items",
        sa.Column("review_state", sa.String(32), nullable=True),
    )
    op.add_column(
        "content_items",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "content_items",
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Bảng audit: approval_events
    op.create_table(
        "approval_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(32), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_id"], ["content_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("approval_events")
    op.drop_column("content_items", "rejected_at")
    op.drop_column("content_items", "approved_at")
    op.drop_column("content_items", "review_state")
