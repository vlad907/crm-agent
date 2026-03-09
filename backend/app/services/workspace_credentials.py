from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.workspace_setting import WorkspaceSetting


def resolve_openai_api_key(db: Session, workspace_id: UUID) -> tuple[str | None, str]:
    workspace_settings = db.get(WorkspaceSetting, workspace_id)
    if workspace_settings and workspace_settings.openai_api_key and workspace_settings.openai_api_key.strip():
        return workspace_settings.openai_api_key.strip(), "workspace_settings"
    if settings.openai_api_key and settings.openai_api_key.strip():
        return settings.openai_api_key.strip(), "environment"
    return None, "missing"


def resolve_google_places_api_key(db: Session, workspace_id: UUID) -> tuple[str | None, str]:
    workspace_settings = db.get(WorkspaceSetting, workspace_id)
    if workspace_settings and workspace_settings.google_places_api_key and workspace_settings.google_places_api_key.strip():
        return workspace_settings.google_places_api_key.strip(), "workspace_settings"
    if settings.google_places_api_key and settings.google_places_api_key.strip():
        return settings.google_places_api_key.strip(), "environment"
    return None, "missing"
