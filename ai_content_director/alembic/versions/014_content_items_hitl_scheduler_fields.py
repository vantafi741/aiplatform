# HITL Approval + Scheduler: content_items thêm approved_by, rejection_reason, rejected_by, external_post_id
# Revision ID: 014  Revises: 013

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("content_items", sa.Column("approved_by", sa.String(255), nullable=True))
    op.add_column("content_items", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column("content_items", sa.Column("rejected_by", sa.String(255), nullable=True))
    op.add_column("content_items", sa.Column("external_post_id", sa.String(255), nullable=True))
    op.add_column("content_items", sa.Column("last_publish_attempt_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("content_items", "last_publish_attempt_at")
    op.drop_column("content_items", "external_post_id")
    op.drop_column("content_items", "rejected_by")
    op.drop_column("content_items", "rejection_reason")
    op.drop_column("content_items", "approved_by")
