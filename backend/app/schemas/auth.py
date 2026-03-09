from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class DevLoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    name: str | None = Field(default=None, max_length=255)


class DevLoginResponse(BaseModel):
    workspace_id: UUID
    user_id: UUID
    email: str
    name: str | None = None
    created: bool
