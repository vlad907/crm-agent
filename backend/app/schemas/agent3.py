from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class FinalEmailRead(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    email_body: str = Field(min_length=1)


class Agent3RunResponse(BaseModel):
    lead_id: UUID
    draft_id: UUID
    decision: Literal["send", "hold"]
    issues: list[str] = Field(default_factory=list)
    final_email: FinalEmailRead
