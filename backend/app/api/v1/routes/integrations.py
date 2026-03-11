from __future__ import annotations

from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps.request_context import RequestContext, get_request_context
from app.core.config import settings
from app.db.session import get_db
from app.models.workspace import Workspace
from app.models.workspace_setting import WorkspaceSetting
from app.schemas.gmail_integration import GmailCallbackResponse, GmailConnectUrlResponse, GmailStatusResponse
from app.services.gmail_service import (
    GmailApiError,
    GmailConfigurationError,
    GmailOAuthExchangeError,
    GmailOAuthState,
    GmailOAuthStateError,
    attach_gmail_profile,
    build_gmail_connect_url,
    decode_oauth_state,
    exchange_code_for_tokens,
    get_gmail_connection_status,
    save_oauth_tokens,
    set_gmail_integration_error,
)

router = APIRouter(prefix="/integrations", tags=["Integrations"])


def _frontend_automation_redirect(*, oauth_status: str, message: str | None = None) -> RedirectResponse:
    base = settings.frontend_base_url.rstrip("/")
    params: dict[str, str] = {"gmail_oauth": oauth_status}
    if message:
        params["message"] = message
    return RedirectResponse(url=f"{base}/automation?{urlencode(params)}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


def _set_workspace_gmail_connected(db: Session, *, workspace_id: UUID, connected: bool) -> None:
    workspace_settings = db.get(WorkspaceSetting, workspace_id)
    if workspace_settings is None:
        workspace_settings = WorkspaceSetting(workspace_id=workspace_id)
        db.add(workspace_settings)
    workspace_settings.gmail_connected = bool(connected)


def _require_workspace_exists(db: Session, workspace_id: UUID) -> None:
    if db.get(Workspace, workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")


@router.get("/gmail/connect-url", response_model=GmailConnectUrlResponse)
def get_gmail_connect_url(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> GmailConnectUrlResponse:
    _require_workspace_exists(db, ctx.workspace_id)
    try:
        url = build_gmail_connect_url(workspace_id=ctx.workspace_id, user_id=ctx.user_id)
    except GmailConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return GmailConnectUrlResponse(connect_url=url)


@router.get("/gmail/status", response_model=GmailStatusResponse)
def get_gmail_status(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> GmailStatusResponse:
    _require_workspace_exists(db, ctx.workspace_id)
    status_payload = get_gmail_connection_status(db, workspace_id=ctx.workspace_id)
    return GmailStatusResponse(
        workspace_id=str(ctx.workspace_id),
        connected=status_payload.connected,
        connected_email=status_payload.connected_email,
        integration_status=status_payload.integration_status,
        last_error=status_payload.last_error,
    )


@router.get("/gmail/callback", response_model=GmailCallbackResponse)
def gmail_oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    response_mode: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> GmailCallbackResponse | RedirectResponse:
    parsed_state: GmailOAuthState | None = None
    if state:
        try:
            parsed_state = decode_oauth_state(state)
        except GmailOAuthStateError:
            parsed_state = None

    if error:
        if parsed_state:
            set_gmail_integration_error(db, workspace_id=parsed_state.workspace_id, error_message=f"Gmail OAuth failed: {error}")
            _set_workspace_gmail_connected(db, workspace_id=parsed_state.workspace_id, connected=False)
            db.commit()
        if response_mode == "json":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Gmail OAuth failed: {error}")
        return _frontend_automation_redirect(oauth_status="error", message=f"Gmail OAuth failed: {error}")

    if not code or not state:
        message = "Missing OAuth callback code/state."
        if parsed_state:
            set_gmail_integration_error(db, workspace_id=parsed_state.workspace_id, error_message=message)
            _set_workspace_gmail_connected(db, workspace_id=parsed_state.workspace_id, connected=False)
            db.commit()
        if response_mode == "json":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
        return _frontend_automation_redirect(oauth_status="error", message=message)

    try:
        if parsed_state is None:
            parsed_state = decode_oauth_state(state)
        _require_workspace_exists(db, parsed_state.workspace_id)
        token_payload = exchange_code_for_tokens(code=code)
        save_oauth_tokens(db, workspace_id=parsed_state.workspace_id, token_payload=token_payload)
        access_token = str(token_payload.get("access_token") or "").strip()
        account = attach_gmail_profile(db, workspace_id=parsed_state.workspace_id, access_token=access_token)
        _set_workspace_gmail_connected(db, workspace_id=parsed_state.workspace_id, connected=True)
    except GmailOAuthStateError as exc:
        if response_mode == "json":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return _frontend_automation_redirect(oauth_status="error", message=str(exc))
    except GmailConfigurationError as exc:
        if parsed_state:
            set_gmail_integration_error(db, workspace_id=parsed_state.workspace_id, error_message=str(exc))
            _set_workspace_gmail_connected(db, workspace_id=parsed_state.workspace_id, connected=False)
            db.commit()
        if response_mode == "json":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return _frontend_automation_redirect(oauth_status="error", message=str(exc))
    except GmailOAuthExchangeError as exc:
        if parsed_state:
            set_gmail_integration_error(db, workspace_id=parsed_state.workspace_id, error_message=str(exc))
            _set_workspace_gmail_connected(db, workspace_id=parsed_state.workspace_id, connected=False)
            db.commit()
        if response_mode == "json":
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        return _frontend_automation_redirect(oauth_status="error", message=str(exc))
    except GmailApiError as exc:
        if parsed_state:
            set_gmail_integration_error(db, workspace_id=parsed_state.workspace_id, error_message=str(exc))
            _set_workspace_gmail_connected(db, workspace_id=parsed_state.workspace_id, connected=False)
            db.commit()
        if response_mode == "json":
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        return _frontend_automation_redirect(oauth_status="error", message=str(exc))
    except Exception as exc:  # pragma: no cover - defensive catch for OAuth callback path
        if parsed_state:
            set_gmail_integration_error(db, workspace_id=parsed_state.workspace_id, error_message=f"Unexpected Gmail error: {exc}")
            _set_workspace_gmail_connected(db, workspace_id=parsed_state.workspace_id, connected=False)
            db.commit()
        if response_mode == "json":
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Unexpected Gmail error: {exc}") from exc
        return _frontend_automation_redirect(oauth_status="error", message=f"Unexpected Gmail error: {exc}")

    db.commit()
    connected_email = account.display_name
    if response_mode == "json":
        return GmailCallbackResponse(
            workspace_id=str(parsed_state.workspace_id),
            connected=True,
            connected_email=connected_email,
            integration_status="connected",
            last_error=None,
        )
    return _frontend_automation_redirect(oauth_status="success", message=connected_email or "Gmail connected")
