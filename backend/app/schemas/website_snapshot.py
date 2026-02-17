from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WebsiteSnapshotBase(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    raw_text: str = Field(min_length=1)


class WebsiteSnapshotCreate(WebsiteSnapshotBase):
    fetched_at: datetime | None = None


class WebsiteSnapshotRead(WebsiteSnapshotBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    fetched_at: datetime
    created_at: datetime
    updated_at: datetime


class WebsiteSnapshotIngestRead(BaseModel):
    id: UUID
    fetched_at: datetime
    raw_text_length: int = Field(ge=0)
