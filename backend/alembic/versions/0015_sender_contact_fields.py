"""Add sender contact fields to workspace_profile."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015_sender_contact"
down_revision = "0014_phase4_to_9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workspace_profile", sa.Column("sender_name", sa.String(255), nullable=True))
    op.add_column("workspace_profile", sa.Column("sender_title", sa.String(255), nullable=True))
    op.add_column("workspace_profile", sa.Column("sender_phone", sa.String(50), nullable=True))
    op.add_column("workspace_profile", sa.Column("sender_email", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("workspace_profile", "sender_email")
    op.drop_column("workspace_profile", "sender_phone")
    op.drop_column("workspace_profile", "sender_title")
    op.drop_column("workspace_profile", "sender_name")
