# Asset summaries + integrate into revenue_content_items
# Revision ID: 015  Revises: 014

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "asset_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("detected_text", sa.Text(), nullable=True),
        sa.Column("objects_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("insights_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("suggested_angle", sa.Text(), nullable=True),
        sa.Column("suggested_tone", sa.String(length=64), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["content_assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_asset_summaries_tenant_id", "asset_summaries", ["tenant_id"], unique=False)
    op.create_index("ix_asset_summaries_asset_id", "asset_summaries", ["asset_id"], unique=False)
    op.create_index("ix_asset_summaries_created_at", "asset_summaries", ["created_at"], unique=False)
    op.create_index(
        "ux_asset_summaries_tenant_asset",
        "asset_summaries",
        ["tenant_id", "asset_id"],
        unique=True,
    )

    op.add_column(
        "revenue_content_items",
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "revenue_content_items",
        sa.Column("summary_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "revenue_content_items",
        sa.Column("summary_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_foreign_key(
        "fk_revenue_content_items_asset_id",
        "revenue_content_items",
        "content_assets",
        ["asset_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_revenue_content_items_summary_id",
        "revenue_content_items",
        "asset_summaries",
        ["summary_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_revenue_content_items_asset_id",
        "revenue_content_items",
        ["asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_revenue_content_items_summary_id",
        "revenue_content_items",
        ["summary_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_revenue_content_items_summary_id", table_name="revenue_content_items")
    op.drop_index("ix_revenue_content_items_asset_id", table_name="revenue_content_items")
    op.drop_constraint("fk_revenue_content_items_summary_id", "revenue_content_items", type_="foreignkey")
    op.drop_constraint("fk_revenue_content_items_asset_id", "revenue_content_items", type_="foreignkey")
    op.drop_column("revenue_content_items", "summary_snapshot_json")
    op.drop_column("revenue_content_items", "summary_id")
    op.drop_column("revenue_content_items", "asset_id")

    op.drop_index("ux_asset_summaries_tenant_asset", table_name="asset_summaries")
    op.drop_index("ix_asset_summaries_created_at", table_name="asset_summaries")
    op.drop_index("ix_asset_summaries_asset_id", table_name="asset_summaries")
    op.drop_index("ix_asset_summaries_tenant_id", table_name="asset_summaries")
    op.drop_table("asset_summaries")
