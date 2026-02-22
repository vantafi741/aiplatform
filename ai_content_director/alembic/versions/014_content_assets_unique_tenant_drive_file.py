# UNIQUE (tenant_id, drive_file_id) cho content_assets – ingest idempotent
# Revision ID: 014  Revises: 013

from typing import Sequence, Union

from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent ingest: mỗi (tenant_id, drive_file_id) chỉ một row
    op.create_index(
        "ux_content_assets_tenant_drive_file",
        "content_assets",
        ["tenant_id", "drive_file_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_content_assets_tenant_drive_file", table_name="content_assets")
