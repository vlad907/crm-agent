from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.agent3 import FinalEmailRead


class Agent1RunResponse(BaseModel):
    lead_id: UUID
    snapshot_id: UUID
    agent1_output: dict[str, Any]


class LatestContextSnapshot(BaseModel):
    id: UUID
    url: str = Field(min_length=1, max_length=500)
    fetched_at: datetime
    raw_text: str = Field(min_length=1)


class LatestContextResponse(BaseModel):
    lead_id: UUID
    snapshot: LatestContextSnapshot
    agent1_output: dict[str, Any] | None = None
    agent3_decision: str | None = None
    agent3_issues: list[str] | None = None
    final_email: FinalEmailRead | None = None
