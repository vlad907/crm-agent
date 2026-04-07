"""multi-user: workspace email unique

Revision ID: 0010_multi_user
Revises: 0009_integration_last_error
Create Date: 2026-03-15 00:00:00.000000

"""
from __future__ import annotations

from alembic import op

revision = "0010_multi_user"
down_revision = "0009_integration_last_error"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.create_unique_constraint("uq_users_workspace_email", "users", ["workspace_id", "email"])


def downgrade() -> None:
    op.drop_constraint("uq_users_workspace_email", "users", type_="unique")
    op.create_unique_constraint("uq_users_email", "users", ["email"])
