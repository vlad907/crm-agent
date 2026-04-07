from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps.request_context import RequestContext, get_request_context
from app.db.session import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.workspace import UserCreate, UserRead, WorkspaceCreate, WorkspaceRead

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
def create_workspace(payload: WorkspaceCreate, db: Session = Depends(get_db)) -> Workspace:
    workspace = Workspace(name=payload.name)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


@router.post("/{workspace_id}/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_workspace_user(
    workspace_id: UUID,
    payload: UserCreate,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> User:
    if workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    workspace = db.scalar(select(Workspace).where(Workspace.id == workspace_id).limit(1))
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    user = User(
        workspace_id=workspace_id,
        email=payload.email,
        name=payload.name,
        role=payload.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists in this workspace",
        ) from exc

    db.refresh(user)
    return user
