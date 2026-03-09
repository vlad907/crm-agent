"""add multitenancy workspace/user/integrations

Revision ID: 0002_multitenant_core
Revises: 0001_create_core_tables
Create Date: 2026-02-18 00:00:00.000000

"""
from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0002_multitenant_core"
down_revision = "0001_create_core_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False, server_default=sa.text("'owner'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_users_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_workspace_id", "users", ["workspace_id"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "integration_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("external_account_id", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'disconnected'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_integration_accounts_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_integration_accounts_workspace_id", "integration_accounts", ["workspace_id"])
    op.create_index("ix_integration_accounts_provider", "integration_accounts", ["provider"])
    op.create_index("ix_integration_accounts_status", "integration_accounts", ["status"])

    op.create_table(
        "oauth_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("integration_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["integration_account_id"],
            ["integration_accounts.id"],
            name="fk_oauth_tokens_integration_account_id_integration_accounts",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_oauth_tokens_integration_account_id", "oauth_tokens", ["integration_account_id"])

    op.add_column("leads", sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("website_snapshots", sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("email_drafts", sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True))

    op.create_foreign_key(
        "fk_leads_workspace_id_workspaces",
        "leads",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_website_snapshots_workspace_id_workspaces",
        "website_snapshots",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_email_drafts_workspace_id_workspaces",
        "email_drafts",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )

    default_workspace_id = uuid.uuid4()
    default_user_id = uuid.uuid4()
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            INSERT INTO workspaces (id, name, created_at, updated_at)
            VALUES (:workspace_id, :name, now(), now())
            """
        ),
        {"workspace_id": default_workspace_id, "name": "Default Workspace"},
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO users (id, workspace_id, email, name, role, created_at, updated_at)
            VALUES (:user_id, :workspace_id, :email, :name, 'owner', now(), now())
            """
        ),
        {
            "user_id": default_user_id,
            "workspace_id": default_workspace_id,
            "email": "dev@local",
            "name": "Development Owner",
        },
    )

    conn.execute(
        sa.text("UPDATE leads SET workspace_id = :workspace_id WHERE workspace_id IS NULL"),
        {"workspace_id": default_workspace_id},
    )
    conn.execute(
        sa.text("UPDATE website_snapshots SET workspace_id = :workspace_id WHERE workspace_id IS NULL"),
        {"workspace_id": default_workspace_id},
    )
    conn.execute(
        sa.text("UPDATE email_drafts SET workspace_id = :workspace_id WHERE workspace_id IS NULL"),
        {"workspace_id": default_workspace_id},
    )

    op.alter_column("leads", "workspace_id", nullable=False)
    op.alter_column("website_snapshots", "workspace_id", nullable=False)
    op.alter_column("email_drafts", "workspace_id", nullable=False)

    op.create_index("ix_leads_workspace_id", "leads", ["workspace_id"])
    op.create_index("ix_website_snapshots_workspace_id", "website_snapshots", ["workspace_id"])
    op.create_index("ix_email_drafts_workspace_id", "email_drafts", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_email_drafts_workspace_id", table_name="email_drafts")
    op.drop_index("ix_website_snapshots_workspace_id", table_name="website_snapshots")
    op.drop_index("ix_leads_workspace_id", table_name="leads")

    op.alter_column("email_drafts", "workspace_id", nullable=True)
    op.alter_column("website_snapshots", "workspace_id", nullable=True)
    op.alter_column("leads", "workspace_id", nullable=True)

    op.drop_constraint("fk_email_drafts_workspace_id_workspaces", "email_drafts", type_="foreignkey")
    op.drop_constraint("fk_website_snapshots_workspace_id_workspaces", "website_snapshots", type_="foreignkey")
    op.drop_constraint("fk_leads_workspace_id_workspaces", "leads", type_="foreignkey")

    op.drop_column("email_drafts", "workspace_id")
    op.drop_column("website_snapshots", "workspace_id")
    op.drop_column("leads", "workspace_id")

    op.drop_index("ix_oauth_tokens_integration_account_id", table_name="oauth_tokens")
    op.drop_table("oauth_tokens")

    op.drop_index("ix_integration_accounts_status", table_name="integration_accounts")
    op.drop_index("ix_integration_accounts_provider", table_name="integration_accounts")
    op.drop_index("ix_integration_accounts_workspace_id", table_name="integration_accounts")
    op.drop_table("integration_accounts")

    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_workspace_id", table_name="users")
    op.drop_table("users")

    op.drop_table("workspaces")
