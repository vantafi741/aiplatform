# Lead Signals: B2B mechanical KPI tracking (comments/inbox/calls/forms)
# Revision ID: 012  Revises: 011
# Table public.lead_signals + indexes + updated_at trigger

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Bảng lead_signals: sự kiện lead từ comment/inbox/call/form
    op.create_table(
        "lead_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_subtype", sa.String(64), nullable=True),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("publish_log_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("external_post_id", sa.String(255), nullable=True),
        sa.Column("external_thread_id", sa.String(255), nullable=True),
        sa.Column("external_message_id", sa.String(255), nullable=True),
        sa.Column("author_name", sa.String(255), nullable=True),
        sa.Column("author_id", sa.String(255), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("intent_label", sa.String(64), nullable=True),
        sa.Column("priority", sa.String(32), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("assignee", sa.String(255), nullable=True),
        sa.Column("follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_contact_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_id"], ["content_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["publish_log_id"], ["publish_logs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes cho dashboard: tenant + time, status, intent, content, publish_log
    op.create_index(
        "ix_lead_signals_tenant_created",
        "lead_signals",
        ["tenant_id", "created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index("ix_lead_signals_tenant_status", "lead_signals", ["tenant_id", "status"], unique=False)
    op.create_index("ix_lead_signals_tenant_intent", "lead_signals", ["tenant_id", "intent_label"], unique=False)
    op.create_index("ix_lead_signals_content_id", "lead_signals", ["content_id"], unique=False)
    op.create_index("ix_lead_signals_publish_log_id", "lead_signals", ["publish_log_id"], unique=False)

    # Unique partial: tránh trùng message theo tenant + platform khi có external_message_id
    op.create_index(
        "uq_lead_signals_tenant_platform_message",
        "lead_signals",
        ["tenant_id", "platform", "external_message_id"],
        unique=True,
        postgresql_where=sa.text("external_message_id IS NOT NULL"),
    )

    # Hàm + trigger: tự cập nhật updated_at khi UPDATE (chỉ cho lead_signals)
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
        CREATE TRIGGER lead_signals_set_updated_at
        BEFORE UPDATE ON lead_signals
        FOR EACH ROW
        EXECUTE PROCEDURE set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS lead_signals_set_updated_at ON lead_signals;")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")

    op.drop_index("uq_lead_signals_tenant_platform_message", table_name="lead_signals")
    op.drop_index("ix_lead_signals_publish_log_id", table_name="lead_signals")
    op.drop_index("ix_lead_signals_content_id", table_name="lead_signals")
    op.drop_index("ix_lead_signals_tenant_intent", table_name="lead_signals")
    op.drop_index("ix_lead_signals_tenant_status", table_name="lead_signals")
    op.drop_index("ix_lead_signals_tenant_created", table_name="lead_signals")
    op.drop_table("lead_signals")
