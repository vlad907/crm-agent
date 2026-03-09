from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workspace_id: UUID
    business_name: str | None = None
    business_description: str | None = None
    industries_served: list[str] = Field(default_factory=list)
    service_specialties: list[str] = Field(default_factory=list)
    service_area: str | None = None
    preferred_tone: str | None = None
    outreach_style: str | None = None
    preferred_cta: str | None = None
    do_not_mention: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkspaceProfileUpdate(BaseModel):
    business_name: str | None = Field(default=None, max_length=255)
    business_description: str | None = None
    industries_served: list[str] | None = None
    service_specialties: list[str] | None = None
    service_area: str | None = Field(default=None, max_length=255)
    preferred_tone: str | None = Field(default=None, max_length=100)
    outreach_style: str | None = Field(default=None, max_length=100)
    preferred_cta: str | None = None
    do_not_mention: list[str] | None = None
