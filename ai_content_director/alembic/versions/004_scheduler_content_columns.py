"""Scheduler columns on content_items

Revision ID: 004
Revises: 003
Create Date: 2025-02-17

- scheduled_at, schedule_status, publish_attempts, last_publish_error, last_publish_at
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "content_items",
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "content_items",
        sa.Column("schedule_status", sa.String(32), nullable=True),
    )
    op.add_column(
        "content_items",
        sa.Column("publish_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "content_items",
        sa.Column("last_publish_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "content_items",
        sa.Column("last_publish_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("content_items", "last_publish_at")
    op.drop_column("content_items", "last_publish_error")
    op.drop_column("content_items", "publish_attempts")
    op.drop_column("content_items", "schedule_status")
    op.drop_column("content_items", "scheduled_at")
