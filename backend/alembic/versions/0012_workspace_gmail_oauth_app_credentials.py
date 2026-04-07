"""workspace_settings: Gmail OAuth app credentials

Revision ID: 0012_workspace_gmail_oauth
Revises: 0011_user_password
Create Date: 2026-03-24 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012_workspace_gmail_oauth"
down_revision = "0011_user_password"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workspace_settings", sa.Column("google_oauth_client_id", sa.Text(), nullable=True))
    op.add_column("workspace_settings", sa.Column("google_oauth_client_secret", sa.Text(), nullable=True))
    op.add_column("workspace_settings", sa.Column("gmail_oauth_redirect_uri", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("workspace_settings", "gmail_oauth_redirect_uri")
    op.drop_column("workspace_settings", "google_oauth_client_secret")
    op.drop_column("workspace_settings", "google_oauth_client_id")
