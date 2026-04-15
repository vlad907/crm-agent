"""Phase 4-9: next_action, reply_review, inbox_reply_mode, partner outreach, jobs table

Revision ID: 0014_phase4_to_9
Revises: 0013_partnerships_inbox
Create Date: 2026-04-11 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0014_phase4_to_9"
down_revision = "0013_partnerships_inbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Phase 4 + 7: thread next_action, reply review status
    op.add_column("email_threads", sa.Column("next_action", sa.String(50), nullable=True))
    op.add_column("email_threads", sa.Column("next_action_detail", JSONB, nullable=True))
    op.add_column("email_threads", sa.Column("reply_review_status", sa.String(30), nullable=True))

    # Phase 4: inbox reply automation mode
    op.add_column(
        "workspace_automation_settings",
        sa.Column("inbox_reply_mode", sa.String(20), nullable=False, server_default="suggest_only"),
    )

    # Phase 6: partner outreach fields
    op.add_column("partner_candidates", sa.Column("outreach_subject", sa.String(500), nullable=True))
    op.add_column("partner_candidates", sa.Column("outreach_body", sa.Text, nullable=True))
    op.add_column("partner_candidates", sa.Column("outreach_status", sa.String(30), nullable=True))

    # Phase 9: jobs table
    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("job_type", sa.String(50), nullable=False, server_default="service"),
        sa.Column("status", sa.String(30), nullable=False, server_default="proposed", index=True),
        sa.Column("source_thread_id", UUID(as_uuid=True), sa.ForeignKey("email_threads.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_entity_type", sa.String(50), nullable=True),
        sa.Column("source_entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_column("partner_candidates", "outreach_status")
    op.drop_column("partner_candidates", "outreach_body")
    op.drop_column("partner_candidates", "outreach_subject")
    op.drop_column("workspace_automation_settings", "inbox_reply_mode")
    op.drop_column("email_threads", "reply_review_status")
    op.drop_column("email_threads", "next_action_detail")
    op.drop_column("email_threads", "next_action")
