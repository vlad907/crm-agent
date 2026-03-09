"""convert workspace profile industries to json array

Revision ID: 0005_profile_industries
Revises: 0004_workspace_profile_pages
Create Date: 2026-03-09 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0005_profile_industries"
down_revision = "0004_workspace_profile_pages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "workspace_profile",
        "industries_served",
        existing_type=sa.Text(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        postgresql_using=(
            "CASE "
            "WHEN industries_served IS NULL OR btrim(industries_served) = '' THEN '[]'::jsonb "
            "ELSE to_jsonb(regexp_split_to_array(industries_served, '\\s*,\\s*')) "
            "END"
        ),
    )
    op.alter_column(
        "workspace_profile",
        "industries_served",
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    )


def downgrade() -> None:
    op.alter_column(
        "workspace_profile",
        "industries_served",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.Text(),
        postgresql_using="industries_served::text",
    )
    op.alter_column(
        "workspace_profile",
        "industries_served",
        nullable=True,
        server_default=None,
    )
