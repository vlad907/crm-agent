from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.request_context import RequestContext, get_request_context
from app.db.session import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.workspace import MeResponse, UserRead, WorkspaceRead

router = APIRouter(tags=["Identity"])


@router.get("/me", response_model=MeResponse)
def get_me(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> MeResponse:
    workspace = db.get(Workspace, ctx.workspace_id)
    user = db.scalar(select(User).where(User.id == ctx.user_id, User.workspace_id == ctx.workspace_id).limit(1))

    return MeResponse(
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        workspace=WorkspaceRead.model_validate(workspace) if workspace else None,
        user=UserRead.model_validate(user) if user else None,
    )
