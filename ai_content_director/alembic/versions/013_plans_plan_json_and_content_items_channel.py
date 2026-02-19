# Planner 30 ngày: content_plans thêm title, objective, tone, plan_json; content_items thêm channel, content_type
# Revision ID: 013  Revises: 012

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # content_plans: thêm title, objective, tone, plan_json (1 row = 1 plan 30 ngày)
    op.add_column("content_plans", sa.Column("title", sa.String(512), nullable=True))
    op.add_column("content_plans", sa.Column("objective", sa.Text(), nullable=True))
    op.add_column("content_plans", sa.Column("tone", sa.String(64), nullable=True))
    op.add_column(
        "content_plans",
        sa.Column("plan_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    # Cho phép nullable để tương thích dữ liệu cũ (giữ nguyên day_number, topic, content_angle)
    op.alter_column(
        "content_plans",
        "day_number",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.alter_column(
        "content_plans",
        "topic",
        existing_type=sa.String(512),
        nullable=True,
    )
    op.alter_column(
        "content_plans",
        "content_angle",
        existing_type=sa.Text(),
        nullable=True,
    )

    # content_items: thêm channel, content_type (image/video/text)
    op.add_column("content_items", sa.Column("channel", sa.String(32), nullable=True))
    op.add_column("content_items", sa.Column("content_type", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("content_items", "content_type")
    op.drop_column("content_items", "channel")

    op.alter_column(
        "content_plans",
        "content_angle",
        existing_type=sa.Text(),
        nullable=False,
    )
    op.alter_column(
        "content_plans",
        "topic",
        existing_type=sa.String(512),
        nullable=False,
    )
    op.alter_column(
        "content_plans",
        "day_number",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_column("content_plans", "plan_json")
    op.drop_column("content_plans", "tone")
    op.drop_column("content_plans", "objective")
    op.drop_column("content_plans", "title")
