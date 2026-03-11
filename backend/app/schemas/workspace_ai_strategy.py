from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceAIStrategyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workspace_id: UUID
    generated_strategy: dict[str, Any] | None = None
    selected_target_categories: list[str] = Field(default_factory=list)
    selected_priority_pain_points: list[str] = Field(default_factory=list)
    selected_service_angles: list[str] = Field(default_factory=list)
    selected_cta_style: str | None = None
    version: int = 1
    last_generated_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkspaceAIStrategyUpdate(BaseModel):
    selected_target_categories: list[str] | None = None
    selected_priority_pain_points: list[str] | None = None
    selected_service_angles: list[str] | None = None
    selected_cta_style: str | None = None
