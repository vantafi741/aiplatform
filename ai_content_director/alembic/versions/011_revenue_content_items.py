# Revenue MVP Module 2: content items from generated_plan (plan -> content)
# Revision ID: 011  Revises: 010
# Table revenue_content_items (plan_id FK -> generated_plans)

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "revenue_content_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day", sa.Integer(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("content_angle", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(32), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("hashtags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("approval_status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["generated_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_revenue_content_items_tenant_id", "revenue_content_items", ["tenant_id"], unique=False)
    op.create_index("ix_revenue_content_items_plan_id", "revenue_content_items", ["plan_id"], unique=False)
    op.create_index(
        "ix_revenue_content_items_tenant_plan",
        "revenue_content_items",
        ["tenant_id", "plan_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_revenue_content_items_tenant_plan", table_name="revenue_content_items")
    op.drop_index("ix_revenue_content_items_plan_id", table_name="revenue_content_items")
    op.drop_index("ix_revenue_content_items_tenant_id", table_name="revenue_content_items")
    op.drop_table("revenue_content_items")
