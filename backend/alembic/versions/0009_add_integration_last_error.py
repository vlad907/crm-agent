"""add integration account last_error

Revision ID: 0009_integration_last_error
Revises: 0008_automation_gmail
Create Date: 2026-03-10 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0009_integration_last_error"
down_revision = "0008_automation_gmail"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("integration_accounts", sa.Column("last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("integration_accounts", "last_error")
