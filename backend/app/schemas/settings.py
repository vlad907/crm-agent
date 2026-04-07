from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WorkspaceSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workspace_id: UUID
    openai_api_key: str | None = None
    google_places_api_key: str | None = None
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    gmail_oauth_redirect_uri: str | None = None
    gmail_connected: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkspaceSettingsUpdate(BaseModel):
    openai_api_key: str | None = None
    google_places_api_key: str | None = None
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    gmail_oauth_redirect_uri: str | None = None
    gmail_connected: bool | None = None
