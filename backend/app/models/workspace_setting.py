from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Text
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class WorkspaceSetting(TimestampMixin, Base):
    __tablename__ = "workspace_settings"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    openai_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_places_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_oauth_client_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_oauth_client_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    gmail_oauth_redirect_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    gmail_connected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    gmail_send_as_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    gmail_send_as_display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    anthropic_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_ai_provider: Mapped[str | None] = mapped_column(Text, nullable=True)

    workspace: Mapped["Workspace"] = relationship(back_populates="settings")
