from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

JobStatus = Literal["proposed", "approved", "scheduled", "in_progress", "completed", "cancelled"]
JobType = Literal["service", "estimate", "onsite_visit", "meeting"]


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    job_type: JobType = "service"
    source_thread_id: UUID | None = None
    source_entity_type: str | None = None
    source_entity_id: UUID | None = None
    scheduled_at: datetime | None = None


class JobUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: JobStatus | None = None
    scheduled_at: datetime | None = None
    metadata_json: dict[str, Any] | None = None


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    title: str
    description: str | None
    job_type: str
    status: str
    source_thread_id: UUID | None
    source_entity_type: str | None
    source_entity_id: UUID | None
    scheduled_at: datetime | None
    metadata_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    items: list[JobRead]
    total: int
