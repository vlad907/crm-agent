"""add lead status pipeline enum

Revision ID: 0007_lead_status_pipeline
Revises: 0006_workspace_ai_strategy
Create Date: 2026-03-09 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0007_lead_status_pipeline"
down_revision = "0006_workspace_ai_strategy"
branch_labels = None
depends_on = None


LEAD_STATUS_VALUES = (
    "discovered",
    "imported",
    "researching",
    "researched",
    "drafting",
    "draft_ready",
    "needs_review",
    "approved",
    "sent",
    "replied",
    "converted",
    "archived",
)

lead_status_enum = postgresql.ENUM(*LEAD_STATUS_VALUES, name="lead_status")


def upgrade() -> None:
    bind = op.get_bind()
    lead_status_enum.create(bind, checkfirst=True)

    op.execute(
        """
        UPDATE leads
        SET status = CASE
            WHEN status IS NULL OR btrim(status) = '' THEN 'imported'
            WHEN lower(status) = 'new' THEN 'imported'
            WHEN lower(status) IN ('ingested', 'enriched', 'agent1') THEN 'researched'
            WHEN lower(status) IN ('agent2', 'agent3', 'verified', 'draft', 'drafted') THEN 'draft_ready'
            WHEN lower(status) = 'hold' THEN 'needs_review'
            WHEN lower(status) IN ('ready', 'ready_to_send', 'send') THEN 'approved'
            WHEN lower(status) IN ('discovered', 'imported', 'researching', 'researched', 'drafting', 'draft_ready', 'needs_review', 'approved', 'sent', 'replied', 'converted', 'archived') THEN lower(status)
            ELSE 'imported'
        END
        """
    )

    op.alter_column(
        "leads",
        "status",
        existing_type=sa.String(length=50),
        server_default=None,
        existing_nullable=False,
    )

    op.alter_column(
        "leads",
        "status",
        existing_type=sa.String(length=50),
        type_=lead_status_enum,
        existing_nullable=False,
        server_default=sa.text("'imported'::lead_status"),
        postgresql_using="status::lead_status",
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE leads
        SET status = CASE
            WHEN status IN ('discovered', 'imported') THEN 'new'
            WHEN status IN ('researching', 'researched') THEN 'ingested'
            WHEN status IN ('drafting', 'draft_ready') THEN 'draft'
            WHEN status = 'needs_review' THEN 'hold'
            WHEN status = 'approved' THEN 'send'
            ELSE status::text
        END
        """
    )

    op.alter_column(
        "leads",
        "status",
        existing_type=lead_status_enum,
        type_=sa.String(length=50),
        existing_nullable=False,
        server_default=sa.text("'new'"),
        postgresql_using="status::text",
    )

    bind = op.get_bind()
    lead_status_enum.drop(bind, checkfirst=True)
