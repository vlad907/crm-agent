from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps.request_context import RequestContext, get_request_context
from app.db.session import get_db
from app.models.workspace_profile import WorkspaceProfile
from app.schemas.workspace_profile import WorkspaceProfileRead, WorkspaceProfileUpdate

router = APIRouter(prefix="/workspace-profile", tags=["Workspace Profile"])


@router.get("", response_model=WorkspaceProfileRead)
def get_workspace_profile(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> WorkspaceProfileRead:
    profile = db.get(WorkspaceProfile, ctx.workspace_id)
    if profile is None:
        return WorkspaceProfileRead(
            workspace_id=ctx.workspace_id,
            industries_served=[],
            service_specialties=[],
            do_not_mention=[],
            created_at=None,
            updated_at=None,
        )
    return WorkspaceProfileRead.model_validate(profile)


@router.patch("", response_model=WorkspaceProfileRead)
def patch_workspace_profile(
    payload: WorkspaceProfileUpdate,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> WorkspaceProfileRead:
    profile = db.get(WorkspaceProfile, ctx.workspace_id)
    if profile is None:
        profile = WorkspaceProfile(workspace_id=ctx.workspace_id)
        db.add(profile)

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if field in {"industries_served", "service_specialties", "do_not_mention"}:
            normalized_list: list[str] = []
            if value:
                normalized_list = [item.strip() for item in value if isinstance(item, str) and item.strip()]
            setattr(profile, field, normalized_list)
            continue

        if isinstance(value, str):
            normalized = value.strip()
            setattr(profile, field, normalized or None)
        else:
            setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return WorkspaceProfileRead.model_validate(profile)
