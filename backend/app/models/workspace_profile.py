from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class WorkspaceProfile(TimestampMixin, Base):
    __tablename__ = "workspace_profile"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    business_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    industries_served: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    service_specialties: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    service_area: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferred_tone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    outreach_style: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred_cta: Mapped[str | None] = mapped_column(Text, nullable=True)
    do_not_mention: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sender_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    workspace: Mapped["Workspace"] = relationship(back_populates="profile")
