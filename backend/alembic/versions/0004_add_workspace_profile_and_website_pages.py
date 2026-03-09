"""add workspace profile and website pages

Revision ID: 0004_workspace_profile_pages
Revises: 0003_prospects_settings
Create Date: 2026-03-09 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0004_workspace_profile_pages"
down_revision = "0003_prospects_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspace_settings",
        sa.Column("gmail_connected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "workspace_profile",
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("business_name", sa.String(length=255), nullable=True),
        sa.Column("business_description", sa.Text(), nullable=True),
        sa.Column("industries_served", sa.Text(), nullable=True),
        sa.Column("service_specialties", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("service_area", sa.String(length=255), nullable=True),
        sa.Column("preferred_tone", sa.String(length=100), nullable=True),
        sa.Column("outreach_style", sa.String(length=100), nullable=True),
        sa.Column("preferred_cta", sa.Text(), nullable=True),
        sa.Column("do_not_mention", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "website_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("page_type", sa.String(length=20), nullable=False, server_default=sa.text("'other'")),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("extracted_emails", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("extracted_phones", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_website_pages_workspace_id", "website_pages", ["workspace_id"])
    op.create_index("ix_website_pages_lead_id", "website_pages", ["lead_id"])
    op.create_index("ix_website_pages_page_type", "website_pages", ["page_type"])


def downgrade() -> None:
    op.drop_index("ix_website_pages_page_type", table_name="website_pages")
    op.drop_index("ix_website_pages_lead_id", table_name="website_pages")
    op.drop_index("ix_website_pages_workspace_id", table_name="website_pages")
    op.drop_table("website_pages")

    op.drop_table("workspace_profile")

    op.drop_column("workspace_settings", "gmail_connected")
