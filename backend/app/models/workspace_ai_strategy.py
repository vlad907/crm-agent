from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class WorkspaceAIStrategy(TimestampMixin, Base):
    __tablename__ = "workspace_ai_strategy"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    generated_strategy: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    selected_target_categories: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    selected_priority_pain_points: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    selected_service_angles: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    selected_cta_style: Mapped[str | None] = mapped_column(String(100), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    last_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped["Workspace"] = relationship(back_populates="ai_strategy")
