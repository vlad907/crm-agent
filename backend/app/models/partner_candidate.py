from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin

PARTNER_STATUS_VALUES = ("new", "reviewed", "contacted", "replied", "active_partner", "ignored", "converted")


class PartnerCandidate(TimestampMixin, Base):
    __tablename__ = "partner_candidates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    partnership_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fit_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    extracted_signals: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    recommended_outreach_angle: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_emails: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    contact_form_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="crawler")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="new", index=True)
    outreach_subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    outreach_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    outreach_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
