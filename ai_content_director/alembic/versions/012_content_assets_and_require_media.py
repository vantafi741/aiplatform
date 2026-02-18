# Google Drive Dropzone: content_assets + content_items require_media, primary_asset_type
# Revision ID: 012  Revises: 011

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("drive_file_id", sa.String(128), nullable=False),
        sa.Column("drive_parent_folder", sa.String(128), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("mime_type", sa.String(64), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("asset_type", sa.String(16), nullable=False),
        sa.Column("local_path", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), server_default="READY", nullable=False),
        sa.Column("error_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_id"], ["content_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_content_assets_tenant_id", "content_assets", ["tenant_id"], unique=False)
    op.create_index("ix_content_assets_content_id", "content_assets", ["content_id"], unique=False)
    op.create_index("ix_content_assets_tenant_status", "content_assets", ["tenant_id", "status"], unique=False)
    op.create_index("ix_content_assets_drive_file_id", "content_assets", ["drive_file_id"], unique=False)

    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.updated_at = now();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER content_assets_set_updated_at
        BEFORE UPDATE ON content_assets
        FOR EACH ROW
        EXECUTE PROCEDURE set_updated_at();
        """
    )

    op.add_column(
        "content_items",
        sa.Column("require_media", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "content_items",
        sa.Column("primary_asset_type", sa.String(16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("content_items", "primary_asset_type")
    op.drop_column("content_items", "require_media")

    op.execute("DROP TRIGGER IF EXISTS content_assets_set_updated_at ON content_assets;")

    op.drop_index("ix_content_assets_drive_file_id", table_name="content_assets")
    op.drop_index("ix_content_assets_tenant_status", table_name="content_assets")
    op.drop_index("ix_content_assets_content_id", table_name="content_assets")
    op.drop_index("ix_content_assets_tenant_id", table_name="content_assets")
    op.drop_table("content_assets")
