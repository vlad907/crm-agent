from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.email_draft import EmailDraft
    from app.models.integration_account import IntegrationAccount
    from app.models.lead import Lead
    from app.models.prospect import Prospect
    from app.models.user import User
    from app.models.website_page import WebsitePage
    from app.models.website_snapshot import WebsiteSnapshot
    from app.models.workspace_profile import WorkspaceProfile
    from app.models.workspace_setting import WorkspaceSetting


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="workspace", cascade="all, delete-orphan", passive_deletes=True)
    integration_accounts: Mapped[list["IntegrationAccount"]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    leads: Mapped[list["Lead"]] = relationship(back_populates="workspace", cascade="all, delete-orphan", passive_deletes=True)
    snapshots: Mapped[list["WebsiteSnapshot"]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    drafts: Mapped[list["EmailDraft"]] = relationship(back_populates="workspace", cascade="all, delete-orphan", passive_deletes=True)
    prospects: Mapped[list["Prospect"]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    settings: Mapped["WorkspaceSetting | None"] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    profile: Mapped["WorkspaceProfile | None"] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    website_pages: Mapped[list["WebsitePage"]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
