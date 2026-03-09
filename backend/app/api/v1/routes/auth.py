from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps.request_context import RequestContext, get_request_context
from app.db.session import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.auth import DevLoginRequest, DevLoginResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=DevLoginResponse, status_code=status.HTTP_200_OK)
def dev_login_or_create_user(
    payload: DevLoginRequest,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> DevLoginResponse:
    workspace = db.get(Workspace, ctx.workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    normalized_email = payload.email.strip().lower()
    normalized_name = payload.name.strip() if payload.name else None
    if not normalized_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")

    existing_user = db.scalar(select(User).where(User.email == normalized_email).limit(1))
    created = False

    if existing_user is None:
        user = User(
            workspace_id=workspace.id,
            email=normalized_email,
            name=normalized_name,
            role="member",
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
            existing_user = user
            created = True
        except IntegrityError:
            db.rollback()
            existing_user = db.scalar(select(User).where(User.email == normalized_email).limit(1))

    if existing_user is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to login user")

    return DevLoginResponse(
        workspace_id=existing_user.workspace_id,
        user_id=existing_user.id,
        email=existing_user.email,
        name=existing_user.name,
        created=created,
    )
