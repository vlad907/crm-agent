from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps.request_context import RequestContext, get_request_context
from app.db.session import get_db
from app.models.workspace_setting import WorkspaceSetting
from app.schemas.settings import WorkspaceSettingsRead, WorkspaceSettingsUpdate

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("", response_model=WorkspaceSettingsRead)
def get_workspace_settings(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> WorkspaceSettingsRead:
    settings = db.get(WorkspaceSetting, ctx.workspace_id)
    if settings is None:
        return WorkspaceSettingsRead(
            workspace_id=ctx.workspace_id,
            openai_api_key=None,
            google_places_api_key=None,
            gmail_connected=False,
            created_at=None,
            updated_at=None,
        )
    return WorkspaceSettingsRead.model_validate(settings)


@router.patch("", response_model=WorkspaceSettingsRead)
def patch_workspace_settings(
    payload: WorkspaceSettingsUpdate,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> WorkspaceSettingsRead:
    settings = db.get(WorkspaceSetting, ctx.workspace_id)
    if settings is None:
        settings = WorkspaceSetting(workspace_id=ctx.workspace_id)
        db.add(settings)

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if field == "gmail_connected":
            if value is None:
                continue
            setattr(settings, field, bool(value))
            continue
        if isinstance(value, str):
            normalized = value.strip()
            setattr(settings, field, normalized or None)
        else:
            setattr(settings, field, value)

    db.commit()
    db.refresh(settings)
    return WorkspaceSettingsRead.model_validate(settings)
