from __future__ import annotations

from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.auth import DevLoginRequest, DevLoginResponse
from app.services.gmail_service import (
    GmailConfigurationError,
    GmailOAuthExchangeError,
    GmailOAuthStateError,
    build_google_login_url,
    decode_google_login_state,
    exchange_google_login_code,
    fetch_google_userinfo,
)

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


# ── Google OAuth sign-in ──────────────────────────────────────────────────────

def _frontend_login_redirect(*, google_auth: str, message: str | None = None, workspace_id: str | None = None, user_id: str | None = None, created: bool = False) -> RedirectResponse:
    base = settings.frontend_base_url.rstrip("/")
    params: dict[str, str] = {"google_auth": google_auth}
    if message:
        params["message"] = message
    if workspace_id:
        params["workspace_id"] = workspace_id
    if user_id:
        params["user_id"] = user_id
    if created:
        params["created"] = "1"
    return RedirectResponse(url=f"{base}/login?{urlencode(params)}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/google/connect-url", summary="Get Google OAuth URL for sign-in")
def get_google_login_url(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        url = build_google_login_url(db)
    except GmailConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"connect_url": url}


@router.get("/google/callback", summary="Google OAuth callback for sign-in")
def google_login_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if error:
        return _frontend_login_redirect(google_auth="error", message=f"Google sign-in failed: {error}")
    if not code or not state:
        return _frontend_login_redirect(google_auth="error", message="Missing OAuth code or state.")

    try:
        decode_google_login_state(state)
    except GmailOAuthStateError as exc:
        return _frontend_login_redirect(google_auth="error", message=str(exc))

    try:
        token_payload = exchange_google_login_code(db, code)
        access_token = token_payload.get("access_token", "")
        userinfo = fetch_google_userinfo(access_token=access_token)
    except (GmailOAuthExchangeError, GmailConfigurationError, Exception) as exc:
        return _frontend_login_redirect(google_auth="error", message=str(exc))

    google_email = (userinfo.get("email") or "").strip().lower()
    google_name = (userinfo.get("name") or "").strip() or None
    if not google_email:
        return _frontend_login_redirect(google_auth="error", message="Could not retrieve email from Google.")

    # Find or create workspace + user (same logic as dev_login_or_create_user)
    workspace = db.scalar(select(Workspace).order_by(Workspace.created_at.asc()).limit(1))
    if workspace is None:
        workspace = Workspace(name="Default Workspace")
        db.add(workspace)
        db.flush()

    existing_user = db.scalar(
        select(User).where(
            User.workspace_id == workspace.id,
            User.email == google_email,
        ).limit(1)
    )
    user_created = False
    if existing_user is None:
        user_created = True
        existing_user = User(
            workspace_id=workspace.id,
            email=google_email,
            name=google_name,
            role="owner",
        )
        db.add(existing_user)
        try:
            db.commit()
            db.refresh(existing_user)
        except IntegrityError:
            db.rollback()
            user_created = False
            existing_user = db.scalar(
                select(User).where(
                    User.workspace_id == workspace.id,
                    User.email == google_email,
                ).limit(1)
            )
    else:
        if google_name and not existing_user.name:
            existing_user.name = google_name
        db.commit()

    if existing_user is None:
        return _frontend_login_redirect(google_auth="error", message="Failed to create or find user account.")

    return _frontend_login_redirect(
        google_auth="success",
        workspace_id=str(existing_user.workspace_id),
        user_id=str(existing_user.id),
        created=user_created,
    )
