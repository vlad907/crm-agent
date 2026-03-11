from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.lead_status import DEFAULT_LEAD_STATUS, LEAD_STATUS_VALUES
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.email_draft import EmailDraft
    from app.models.website_page import WebsitePage
    from app.models.workspace import Workspace
    from app.models.website_snapshot import WebsiteSnapshot


class Lead(TimestampMixin, Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(*LEAD_STATUS_VALUES, name="lead_status"),
        nullable=False,
        default=DEFAULT_LEAD_STATUS,
        server_default=text(f"'{DEFAULT_LEAD_STATUS}'"),
        index=True,
    )

    workspace: Mapped["Workspace"] = relationship(back_populates="leads")
    snapshots: Mapped[list["WebsiteSnapshot"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    drafts: Mapped[list["EmailDraft"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    website_pages: Mapped[list["WebsitePage"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
