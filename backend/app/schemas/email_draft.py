from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmailDraftBase(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    agent1_output: dict[str, Any] | None = None
    agent3_verdict: dict[str, Any] | None = None
    decision: str = Field(default="draft", min_length=1, max_length=20)


class EmailDraftCreate(EmailDraftBase):
    pass


class EmailDraftRead(EmailDraftBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    created_at: datetime
    updated_at: datetime
