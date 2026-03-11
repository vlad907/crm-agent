"""add automation settings and gmail draft metadata

Revision ID: 0008_automation_gmail
Revises: 0007_lead_status_pipeline
Create Date: 2026-03-10 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0008_automation_gmail"
down_revision = "0007_lead_status_pipeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_automation_settings",
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("automation_mode", sa.String(length=20), nullable=False, server_default=sa.text("'manual'")),
        sa.Column(
            "require_manual_review_before_send",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("auto_create_gmail_draft", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("auto_send_approved_emails", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("pause_pipeline", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.add_column(
        "email_drafts",
        sa.Column("review_status", sa.String(length=30), nullable=False, server_default=sa.text("'draft'")),
    )
    op.add_column("email_drafts", sa.Column("review_notes", sa.Text(), nullable=True))
    op.add_column("email_drafts", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("email_drafts", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("email_drafts", sa.Column("gmail_draft_id", sa.String(length=255), nullable=True))
    op.add_column("email_drafts", sa.Column("gmail_message_id", sa.String(length=255), nullable=True))
    op.add_column("email_drafts", sa.Column("gmail_thread_id", sa.String(length=255), nullable=True))
    op.add_column("email_drafts", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_email_drafts_review_status", "email_drafts", ["review_status"])
    op.create_index("ix_email_drafts_gmail_draft_id", "email_drafts", ["gmail_draft_id"])


def downgrade() -> None:
    op.drop_index("ix_email_drafts_gmail_draft_id", table_name="email_drafts")
    op.drop_index("ix_email_drafts_review_status", table_name="email_drafts")

    op.drop_column("email_drafts", "sent_at")
    op.drop_column("email_drafts", "gmail_thread_id")
    op.drop_column("email_drafts", "gmail_message_id")
    op.drop_column("email_drafts", "gmail_draft_id")
    op.drop_column("email_drafts", "rejected_at")
    op.drop_column("email_drafts", "approved_at")
    op.drop_column("email_drafts", "review_notes")
    op.drop_column("email_drafts", "review_status")

    op.drop_table("workspace_automation_settings")
