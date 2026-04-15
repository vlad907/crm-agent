"""partner_candidates, email_threads, email_messages tables

Revision ID: 0013_partnerships_inbox
Revises: 0012_workspace_gmail_oauth
Create Date: 2026-04-11 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "0013_partnerships_inbox"
down_revision = "0012_workspace_gmail_oauth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "partner_candidates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("company_name", sa.String(255), nullable=False, index=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("industry", sa.String(255), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("partnership_type", sa.String(100), nullable=True),
        sa.Column("fit_score", sa.Float, nullable=True),
        sa.Column("extracted_signals", JSONB, nullable=True),
        sa.Column("recommended_outreach_angle", sa.Text, nullable=True),
        sa.Column("contact_emails", ARRAY(sa.String), nullable=True),
        sa.Column("contact_form_url", sa.String(500), nullable=True),
        sa.Column("source", sa.String(100), nullable=False, server_default="crawler"),
        sa.Column("status", sa.String(30), nullable=False, server_default="new", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "email_threads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("gmail_thread_id", sa.String(255), nullable=False, index=True),
        sa.Column("related_entity_type", sa.String(50), nullable=True),
        sa.Column("related_entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="active", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "email_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("thread_id", UUID(as_uuid=True), sa.ForeignKey("email_threads.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("sender", sa.String(255), nullable=True),
        sa.Column("recipients", JSONB, nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("classification", sa.String(50), nullable=True, index=True),
        sa.Column("suggested_response", JSONB, nullable=True),
        sa.Column("gmail_message_id", sa.String(255), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("email_messages")
    op.drop_table("email_threads")
    op.drop_table("partner_candidates")
