from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    name: str | None = Field(default=None, max_length=255)
    role: str = Field(default="owner", min_length=1, max_length=20)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    email: str
    name: str | None = None
    role: str
    created_at: datetime
    updated_at: datetime


class MeResponse(BaseModel):
    workspace_id: UUID
    user_id: UUID
    workspace: WorkspaceRead | None = None
    user: UserRead | None = None
