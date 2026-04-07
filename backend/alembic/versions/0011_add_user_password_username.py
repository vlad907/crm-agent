"""add user password_hash and username

Revision ID: 0011_user_password
Revises: 0010_multi_user
Create Date: 2026-03-15 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0011_user_password"
down_revision = "0010_multi_user"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
    op.drop_column("users", "username")
