from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class WorkspaceAutomationSetting(TimestampMixin, Base):
    __tablename__ = "workspace_automation_settings"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    automation_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    require_manual_review_before_send: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_create_gmail_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_send_approved_emails: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pause_pipeline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    inbox_reply_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="suggest_only")

    workspace: Mapped["Workspace"] = relationship(back_populates="automation_settings")
