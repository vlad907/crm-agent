"""add prospects and workspace settings

Revision ID: 0003_prospects_settings
Revises: 0002_multitenant_core
Create Date: 2026-03-09 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0003_prospects_settings"
down_revision = "0002_multitenant_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("phone", sa.String(length=50), nullable=True))

    op.create_table(
        "workspace_settings",
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("openai_api_key", sa.Text(), nullable=True),
        sa.Column("google_places_api_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "prospects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("website_url", sa.String(length=500), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("raw_source_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("import_status", sa.String(length=20), nullable=False, server_default=sa.text("'new'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_prospects_workspace_id", "prospects", ["workspace_id"])
    op.create_index("ix_prospects_source", "prospects", ["source"])
    op.create_index("ix_prospects_company_name", "prospects", ["company_name"])
    op.create_index("ix_prospects_category", "prospects", ["category"])
    op.create_index("ix_prospects_import_status", "prospects", ["import_status"])
    op.create_index(
        "uq_prospects_workspace_source_external_id",
        "prospects",
        ["workspace_id", "source", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_prospects_workspace_source_external_id", table_name="prospects")
    op.drop_index("ix_prospects_import_status", table_name="prospects")
    op.drop_index("ix_prospects_category", table_name="prospects")
    op.drop_index("ix_prospects_company_name", table_name="prospects")
    op.drop_index("ix_prospects_source", table_name="prospects")
    op.drop_index("ix_prospects_workspace_id", table_name="prospects")
    op.drop_table("prospects")

    op.drop_table("workspace_settings")
    op.drop_column("leads", "phone")
