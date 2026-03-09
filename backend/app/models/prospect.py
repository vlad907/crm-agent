from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class Prospect(TimestampMixin, Base):
    __tablename__ = "prospects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rating: Mapped[float | None] = mapped_column(nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_source_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    import_status: Mapped[str] = mapped_column(String(20), nullable=False, default="new", index=True)

    workspace: Mapped["Workspace"] = relationship(back_populates="prospects")
