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


def resolve_anthropic_api_key(db: Session, workspace_id: UUID) -> tuple[str | None, str]:
    workspace_settings = db.get(WorkspaceSetting, workspace_id)
    if workspace_settings and workspace_settings.anthropic_api_key and workspace_settings.anthropic_api_key.strip():
        return workspace_settings.anthropic_api_key.strip(), "workspace_settings"
    if settings.anthropic_api_key and settings.anthropic_api_key.strip():
        return settings.anthropic_api_key.strip(), "environment"
    return None, "missing"


def resolve_email_generation_provider(
    db: Session, workspace_id: UUID
) -> tuple[str, str | None]:
    """Return (provider, api_key) for email generation.

    Respects workspace preferred_ai_provider setting:
    - 'anthropic': force Claude (requires Anthropic key)
    - 'openai': force GPT (requires OpenAI key)
    - 'auto' or None: prefers Anthropic if configured, falls back to OpenAI
    Returns ('none', None) when no key is available.
    """
    workspace_settings = db.get(WorkspaceSetting, workspace_id)
    preference = (workspace_settings.preferred_ai_provider if workspace_settings else None) or "auto"

    anthropic_key, _ = resolve_anthropic_api_key(db, workspace_id)
    openai_key, _ = resolve_openai_api_key(db, workspace_id)

    if preference == "anthropic":
        return ("anthropic", anthropic_key) if anthropic_key else ("none", None)
    if preference == "openai":
        return ("openai", openai_key) if openai_key else ("none", None)

    # auto: prefer anthropic
    if anthropic_key:
        return "anthropic", anthropic_key
    if openai_key:
        return "openai", openai_key
    return "none", None


def resolve_google_places_api_key(db: Session, workspace_id: UUID) -> tuple[str | None, str]:
    workspace_settings = db.get(WorkspaceSetting, workspace_id)
    if workspace_settings and workspace_settings.google_places_api_key and workspace_settings.google_places_api_key.strip():
        return workspace_settings.google_places_api_key.strip(), "workspace_settings"
    if settings.google_places_api_key and settings.google_places_api_key.strip():
        return settings.google_places_api_key.strip(), "environment"
    return None, "missing"
