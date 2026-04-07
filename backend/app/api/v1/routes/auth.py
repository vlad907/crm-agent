from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.auth import DevLoginRequest, DevLoginResponse

router = APIRouter(prefix="/auth", tags=["Auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _parse_workspace_id(value: str | None) -> UUID | None:
    if not value or not value.strip():
        return None
    try:
        return UUID(value.strip())
    except ValueError:
        return None


BCRYPT_MAX_PASSWORD_BYTES = 72


def _truncate_for_bcrypt(password: str) -> str:
    """Bcrypt limits passwords to 72 bytes; truncate to avoid ValueError."""
    encoded = password.encode("utf-8")
    if len(encoded) <= BCRYPT_MAX_PASSWORD_BYTES:
        return password
    return encoded[:BCRYPT_MAX_PASSWORD_BYTES].decode("utf-8", errors="replace")


def _hash_password(password: str) -> str:
    return pwd_context.hash(_truncate_for_bcrypt(password))


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_truncate_for_bcrypt(plain), hashed)


@router.post("/login", response_model=DevLoginResponse, status_code=status.HTTP_200_OK)
def dev_login_or_create_user(
    payload: DevLoginRequest,
    db: Session = Depends(get_db),
) -> DevLoginResponse:
    normalized_email = payload.email.strip().lower()
    normalized_name = (payload.name or payload.username or "").strip() or None
    normalized_username = (payload.username or "").strip() or None
    password = (payload.password or "").strip() or None

    if not normalized_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")

    workspace_id = _parse_workspace_id(payload.workspace_id)
    workspace: Workspace | None = None
    if workspace_id:
        workspace = db.get(Workspace, workspace_id)
        if workspace is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    else:
        workspace = db.scalar(select(Workspace).order_by(Workspace.created_at.asc()).limit(1))
        if workspace is None:
            workspace = Workspace(name="Default Workspace")
            db.add(workspace)
            db.flush()

    existing_user = db.scalar(
        select(User).where(
            User.workspace_id == workspace.id,
            User.email == normalized_email,
        ).limit(1)
    )
    created = False

    if existing_user is None:
        if not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is required for new accounts",
            )
        user = User(
            workspace_id=workspace.id,
            email=normalized_email,
            username=normalized_username,
            name=normalized_name,
            password_hash=_hash_password(password),
            role="owner" if not workspace_id else "member",
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
            existing_user = user
            created = True
        except IntegrityError:
            db.rollback()
            existing_user = db.scalar(
                select(User).where(
                    User.workspace_id == workspace.id,
                    User.email == normalized_email,
                ).limit(1)
            )

    if existing_user is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to login user")

    if existing_user.password_hash:
        if not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is required",
            )
        if not _verify_password(password, existing_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

    return DevLoginResponse(
        workspace_id=existing_user.workspace_id,
        user_id=existing_user.id,
        email=existing_user.email,
        name=existing_user.name,
        created=created,
    )
