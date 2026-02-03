from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.lead import Lead


class EmailDraft(TimestampMixin, Base):
    __tablename__ = "email_drafts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    agent1_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    agent3_verdict: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    decision: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")

    lead: Mapped["Lead"] = relationship(back_populates="drafts")

