from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.integration_account import IntegrationAccount
from app.models.oauth_token import OAuthToken
from app.models.workspace_setting import WorkspaceSetting

GMAIL_PROVIDER = "gmail"
GOOGLE_OAUTH_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_ROOT = "https://gmail.googleapis.com/gmail/v1/users/me"
GMAIL_PROFILE_URL = f"{GMAIL_API_ROOT}/profile"
STATE_MAX_AGE_SECONDS = 15 * 60


class GmailIntegrationError(RuntimeError):
    pass


class GmailConfigurationError(GmailIntegrationError):
    pass


class GmailOAuthStateError(GmailIntegrationError):
    pass


class GmailOAuthExchangeError(GmailIntegrationError):
    pass


class GmailApiError(GmailIntegrationError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class GmailOAuthState:
    workspace_id: UUID
    user_id: UUID
    issued_at: int


@dataclass(frozen=True)
class GmailConnectionStatus:
    workspace_id: UUID
    connected: bool
    connected_email: str | None
    integration_status: str
    last_error: str | None


# ── Google login state (no workspace_id needed — used before authentication) ──

GOOGLE_LOGIN_SCOPES = "openid email profile"


def encode_google_login_state() -> str:
    payload = {"intent": "google_login", "iat": int(time.time())}
    payload_segment = _urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature_segment = _state_signature(payload_segment)
    return f"{payload_segment}.{signature_segment}"


def decode_google_login_state(raw_state: str) -> None:
    """Validate signature + expiry; raises GmailOAuthStateError on failure."""
    parts = (raw_state or "").split(".", 1)
    if len(parts) != 2:
        raise GmailOAuthStateError("Invalid login state.")
    payload_segment, signature_segment = parts
    if not hmac.compare_digest(signature_segment, _state_signature(payload_segment)):
        raise GmailOAuthStateError("Login state signature mismatch.")
    try:
        payload = json.loads(_urlsafe_b64decode(payload_segment).decode("utf-8"))
        issued_at = int(payload["iat"])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise GmailOAuthStateError("Login state payload is invalid.") from exc
    if int(time.time()) - issued_at > STATE_MAX_AGE_SECONDS:
        raise GmailOAuthStateError("Login state expired. Try signing in again.")


def resolve_google_login_oauth_config(db: Session) -> tuple[str, str, str]:
    """
    Resolve client_id/secret/redirect_uri for the Google login flow.
    Prefers env vars, then falls back to the first workspace that has credentials configured.
    """
    client_id = (settings.google_oauth_client_id or "").strip()
    client_secret = (settings.google_oauth_client_secret or "").strip()
    redirect_uri = settings.google_login_redirect_uri.strip()

    if not client_id or not client_secret:
        # Fall back to any workspace that has them stored
        from sqlalchemy import select as _select
        from app.models.workspace_setting import WorkspaceSetting as _WS
        row = db.scalar(_select(_WS).where(_WS.google_oauth_client_id.isnot(None)).limit(1))
        if row:
            if not client_id:
                client_id = (row.google_oauth_client_id or "").strip()
            if not client_secret:
                client_secret = (row.google_oauth_client_secret or "").strip()

    if not client_id:
        raise GmailConfigurationError(
            "Google OAuth client ID is not configured. Add it under Settings → Integrations."
        )
    if not client_secret:
        raise GmailConfigurationError(
            "Google OAuth client secret is not configured. Add it under Settings → Integrations."
        )
    return client_id, client_secret, redirect_uri


def build_google_login_url(db: Session) -> str:
    client_id, _, redirect_uri = resolve_google_login_oauth_config(db)
    state = encode_google_login_state()
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_LOGIN_SCOPES,
        "access_type": "offline",
        "prompt": "select_account",
        "state": state,
    }
    return f"{GOOGLE_OAUTH_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_google_login_code(db: Session, code: str) -> dict[str, Any]:
    """Exchange auth code for tokens using the login redirect URI."""
    client_id, client_secret, redirect_uri = resolve_google_login_oauth_config(db)
    payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    with httpx.Client(timeout=20.0) as client:
        response = client.post(GOOGLE_OAUTH_TOKEN_URL, data=payload)
    try:
        resp_json = response.json()
    except Exception:
        resp_json = {}
    if response.status_code >= 400 or "access_token" not in resp_json:
        try:
            google_error = resp_json.get("error", "")
            google_desc = resp_json.get("error_description", "")
            if google_error == "invalid_client":
                detail = (
                    "Google rejected the OAuth credentials — the Client Secret appears to be wrong or expired. "
                    "Go to Google Cloud Console → Credentials, regenerate the secret, and update it in Settings."
                )
            elif google_desc:
                detail = google_desc
            elif google_error:
                detail = google_error
            else:
                detail = response.text.strip() or "Token exchange failed"
        except Exception:
            detail = response.text.strip() or "Token exchange failed"
        raise GmailOAuthExchangeError(detail)
    return resp_json


def fetch_google_userinfo(*, access_token: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=20.0) as client:
        response = client.get("https://www.googleapis.com/oauth2/v3/userinfo", headers=headers)
    if response.status_code >= 400:
        raise GmailApiError("Failed to fetch Google user info.", status_code=502)
    return response.json()


def _urlsafe_b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * ((4 - (len(value) % 4)) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("utf-8"))


def _state_signature(payload_segment: str) -> str:
    digest = hmac.new(
        settings.oauth_state_signing_secret.encode("utf-8"),
        payload_segment.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _urlsafe_b64encode(digest)


def encode_oauth_state(*, workspace_id: UUID, user_id: UUID) -> str:
    payload = {
        "workspace_id": str(workspace_id),
        "user_id": str(user_id),
        "iat": int(time.time()),
    }
    payload_segment = _urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature_segment = _state_signature(payload_segment)
    return f"{payload_segment}.{signature_segment}"


def decode_oauth_state(raw_state: str) -> GmailOAuthState:
    parts = (raw_state or "").split(".", 1)
    if len(parts) != 2:
        raise GmailOAuthStateError("Invalid OAuth state.")
    payload_segment, signature_segment = parts
    expected_signature = _state_signature(payload_segment)
    if not hmac.compare_digest(signature_segment, expected_signature):
        raise GmailOAuthStateError("OAuth state signature mismatch.")

    try:
        payload = json.loads(_urlsafe_b64decode(payload_segment).decode("utf-8"))
        workspace_id = UUID(str(payload["workspace_id"]))
        user_id = UUID(str(payload["user_id"]))
        issued_at = int(payload["iat"])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise GmailOAuthStateError("OAuth state payload is invalid.") from exc

    if int(time.time()) - issued_at > STATE_MAX_AGE_SECONDS:
        raise GmailOAuthStateError("OAuth state expired. Start Gmail connect again.")

    return GmailOAuthState(workspace_id=workspace_id, user_id=user_id, issued_at=issued_at)


def resolve_gmail_oauth_config(db: Session, workspace_id: UUID) -> tuple[str, str, str]:
    """
    OAuth app credentials: workspace_settings override, else server environment.
    """
    ws = db.get(WorkspaceSetting, workspace_id)
    client_id = (ws.google_oauth_client_id or "").strip() if ws else ""
    client_secret = (ws.google_oauth_client_secret or "").strip() if ws else ""
    redirect_uri = (ws.gmail_oauth_redirect_uri or "").strip() if ws else ""
    if not client_id:
        client_id = (settings.google_oauth_client_id or "").strip()
    if not client_secret:
        client_secret = (settings.google_oauth_client_secret or "").strip()
    if not redirect_uri:
        redirect_uri = (settings.gmail_oauth_redirect_uri or "").strip()
    if not client_id:
        raise GmailConfigurationError(
            "GOOGLE_OAUTH_CLIENT_ID is missing. Add it under Settings → Integrations or set GOOGLE_OAUTH_CLIENT_ID on the server."
        )
    if not client_secret:
        raise GmailConfigurationError(
            "GOOGLE_OAUTH_CLIENT_SECRET is missing. Add it under Settings → Integrations or set GOOGLE_OAUTH_CLIENT_SECRET on the server."
        )
    if not redirect_uri:
        raise GmailConfigurationError("GMAIL_OAUTH_REDIRECT_URI is missing.")
    return client_id, client_secret, redirect_uri


def _scopes_list() -> list[str]:
    raw = (settings.gmail_oauth_scopes or "").strip()
    if not raw:
        return [
            "https://www.googleapis.com/auth/gmail.compose",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.modify",
        ]
    return [part.strip() for part in raw.split() if part.strip()]


def build_gmail_connect_url(*, db: Session, workspace_id: UUID, user_id: UUID) -> str:
    client_id, _, redirect_uri = resolve_gmail_oauth_config(db, workspace_id)
    state = encode_oauth_state(workspace_id=workspace_id, user_id=user_id)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(_scopes_list()),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_OAUTH_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_tokens(*, db: Session, workspace_id: UUID, code: str) -> dict[str, Any]:
    client_id, client_secret, redirect_uri = resolve_gmail_oauth_config(db, workspace_id)
    payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    with httpx.Client(timeout=20.0) as client:
        response = client.post(GOOGLE_OAUTH_TOKEN_URL, data=payload)
    if response.status_code >= 400:
        raw = response.text.strip() or "unknown error"
        # Try to extract a human-readable message from Google's JSON error response
        try:
            err_body = response.json()
            google_error = err_body.get("error", "")
            google_desc = err_body.get("error_description", "")
            if google_error == "invalid_client":
                detail = (
                    "Google rejected the OAuth credentials — the Client Secret appears to be wrong or expired. "
                    "Go to Google Cloud Console → Credentials, regenerate the secret, and update it in Settings."
                )
            elif google_error == "redirect_uri_mismatch":
                detail = (
                    "Redirect URI mismatch. Make sure "
                    "http://localhost:8000/api/v1/integrations/gmail/callback "
                    "is listed under Authorized redirect URIs in your Google Cloud Console OAuth client."
                )
            elif google_desc:
                detail = google_desc
            elif google_error:
                detail = google_error
            else:
                detail = raw
        except Exception:
            detail = raw
        raise GmailOAuthExchangeError(detail)
    data = response.json()
    if not isinstance(data, dict) or not isinstance(data.get("access_token"), str):
        raise GmailOAuthExchangeError("OAuth response missing access_token.")
    return data


def _calculate_expiry(data: dict[str, Any]) -> datetime | None:
    expires_in = data.get("expires_in")
    if isinstance(expires_in, int) and expires_in > 0:
        return datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    if isinstance(expires_in, str) and expires_in.isdigit():
        return datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
    return None


def _normalize_scopes(data: dict[str, Any]) -> list[str]:
    scopes_value = data.get("scope")
    if isinstance(scopes_value, str):
        return [item.strip() for item in scopes_value.split() if item.strip()]
    scopes = data.get("scopes")
    if isinstance(scopes, list):
        return [item.strip() for item in scopes if isinstance(item, str) and item.strip()]
    return _scopes_list()


def get_gmail_account(db: Session, workspace_id: UUID) -> IntegrationAccount | None:
    return db.scalar(
        select(IntegrationAccount)
        .where(
            IntegrationAccount.workspace_id == workspace_id,
            IntegrationAccount.provider == GMAIL_PROVIDER,
        )
        .order_by(IntegrationAccount.created_at.desc())
        .limit(1)
    )


def _get_or_create_gmail_account(db: Session, workspace_id: UUID) -> IntegrationAccount:
    account = get_gmail_account(db, workspace_id)
    if account is None:
        account = IntegrationAccount(
            workspace_id=workspace_id,
            provider=GMAIL_PROVIDER,
            status="connected",
        )
        db.add(account)
        db.flush()
    return account


def set_gmail_integration_error(db: Session, *, workspace_id: UUID, error_message: str) -> IntegrationAccount:
    account = get_gmail_account(db, workspace_id)
    if account is None:
        account = IntegrationAccount(
            workspace_id=workspace_id,
            provider=GMAIL_PROVIDER,
            status="error",
        )
        db.add(account)
    account.status = "error"
    account.last_error = error_message.strip()[:2000]
    db.flush()
    return account


def save_oauth_tokens(db: Session, *, workspace_id: UUID, token_payload: dict[str, Any]) -> OAuthToken:
    account = _get_or_create_gmail_account(db, workspace_id)
    account.status = "connected"
    account.last_error = None

    refresh_token = token_payload.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token.strip():
        previous_refresh = db.scalar(
            select(OAuthToken.refresh_token)
            .where(OAuthToken.integration_account_id == account.id, OAuthToken.refresh_token.is_not(None))
            .order_by(OAuthToken.created_at.desc())
            .limit(1)
        )
        refresh_token = previous_refresh

    access_token = str(token_payload.get("access_token") or "").strip()
    if not access_token:
        raise GmailOAuthExchangeError("OAuth response did not include an access token.")

    token = OAuthToken(
        integration_account_id=account.id,
        access_token=access_token,
        refresh_token=refresh_token.strip() if isinstance(refresh_token, str) and refresh_token.strip() else None,
        expires_at=_calculate_expiry(token_payload),
        scopes=_normalize_scopes(token_payload),
    )
    db.add(token)
    db.flush()
    return token


def _refresh_access_token(db: Session, *, account: IntegrationAccount, refresh_token: str) -> OAuthToken:
    client_id, client_secret, _ = resolve_gmail_oauth_config(db, account.workspace_id)
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    with httpx.Client(timeout=20.0) as client:
        response = client.post(GOOGLE_OAUTH_TOKEN_URL, data=payload)
    if response.status_code >= 400:
        detail = response.text.strip() or "unknown error"
        account.status = "error"
        account.last_error = f"Failed to refresh Gmail token: {detail}"[:2000]
        raise GmailApiError(f"Failed to refresh Gmail OAuth token: {detail}", status_code=502)

    data = response.json()
    access_token = str(data.get("access_token") or "").strip()
    if not access_token:
        raise GmailApiError("Refresh token response missing access_token.", status_code=502)

    token = OAuthToken(
        integration_account_id=account.id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=_calculate_expiry(data),
        scopes=_normalize_scopes(data),
    )
    db.add(token)
    account.status = "connected"
    account.last_error = None
    db.flush()
    return token


def get_active_token(db: Session, workspace_id: UUID) -> tuple[IntegrationAccount, OAuthToken]:
    account = get_gmail_account(db, workspace_id)
    if account is None:
        raise GmailApiError("Gmail is not connected for this workspace.", status_code=400)

    token = db.scalar(
        select(OAuthToken)
        .where(OAuthToken.integration_account_id == account.id)
        .order_by(OAuthToken.created_at.desc())
        .limit(1)
    )
    if token is None:
        account.status = "disconnected"
        account.last_error = "No Gmail OAuth token found for this workspace."
        raise GmailApiError("No Gmail OAuth token found for this workspace.", status_code=400)

    now = datetime.now(timezone.utc)
    if token.expires_at and token.expires_at <= now + timedelta(seconds=60):
        if not token.refresh_token:
            account.status = "error"
            account.last_error = "Gmail token expired and no refresh token is available."
            raise GmailApiError("Gmail token expired and no refresh token is available.", status_code=400)
        token = _refresh_access_token(db, account=account, refresh_token=token.refresh_token)

    account.status = "connected"
    account.last_error = None
    return account, token


def fetch_gmail_profile(*, access_token: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=20.0) as client:
        response = client.get(GMAIL_PROFILE_URL, headers=headers)
    if response.status_code >= 400:
        detail = response.text.strip() or "unknown Gmail API error"
        raise GmailApiError(f"Gmail profile request failed: {detail}", status_code=502)
    data = response.json()
    if not isinstance(data, dict):
        raise GmailApiError("Gmail profile response is invalid.", status_code=502)
    return data


def attach_gmail_profile(
    db: Session,
    *,
    workspace_id: UUID,
    access_token: str,
) -> IntegrationAccount:
    account = _get_or_create_gmail_account(db, workspace_id)
    profile = fetch_gmail_profile(access_token=access_token)
    email_address = profile.get("emailAddress")
    email_value = email_address.strip() if isinstance(email_address, str) and email_address.strip() else None
    if email_value:
        account.display_name = email_value
        account.external_account_id = email_value
    account.status = "connected"
    account.last_error = None
    db.flush()
    return account


def get_gmail_connection_status(db: Session, *, workspace_id: UUID) -> GmailConnectionStatus:
    config_error: str | None = None
    try:
        resolve_gmail_oauth_config(db, workspace_id)
    except GmailConfigurationError as exc:
        config_error = str(exc)

    account = get_gmail_account(db, workspace_id)
    if account is None:
        return GmailConnectionStatus(
            workspace_id=workspace_id,
            connected=False,
            connected_email=None,
            integration_status="disconnected",
            last_error=config_error,
        )

    token = db.scalar(
        select(OAuthToken.id)
        .where(OAuthToken.integration_account_id == account.id)
        .order_by(OAuthToken.created_at.desc())
        .limit(1)
    )
    connected = account.status == "connected" and token is not None
    last_error = (account.last_error or "").strip() or None
    if not connected and not last_error:
        if token is None:
            last_error = "No OAuth token stored."
    if config_error and not last_error:
        last_error = config_error

    return GmailConnectionStatus(
        workspace_id=workspace_id,
        connected=bool(connected),
        connected_email=account.display_name,
        integration_status=account.status,
        last_error=last_error,
    )


def _gmail_api_post(
    *,
    db: Session,
    workspace_id: UUID,
    path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    account, token = get_active_token(db, workspace_id)
    url = f"{GMAIL_API_ROOT}{path}"

    def _request(access_token: str) -> httpx.Response:
        headers = {"Authorization": f"Bearer {access_token}"}
        with httpx.Client(timeout=25.0) as client:
            return client.post(url, headers=headers, json=payload)

    response = _request(token.access_token)
    if response.status_code == 401 and token.refresh_token:
        refreshed = _refresh_access_token(db, account=account, refresh_token=token.refresh_token)
        response = _request(refreshed.access_token)

    if response.status_code >= 400:
        detail = response.text.strip() or "unknown Gmail API error"
        account.status = "error"
        account.last_error = f"Gmail API request failed: {detail}"[:2000]
        raise GmailApiError(f"Gmail API request failed: {detail}", status_code=502)

    data = response.json()
    if not isinstance(data, dict):
        account.status = "error"
        account.last_error = "Gmail API returned invalid JSON payload."
        raise GmailApiError("Gmail API returned invalid JSON payload.", status_code=502)
    account.status = "connected"
    account.last_error = None
    return data


def _build_raw_message(
    *,
    to_email: str,
    subject: str,
    body: str,
    from_email: str | None = None,
    from_name: str | None = None,
) -> str:
    message = EmailMessage()
    message["To"] = to_email
    message["Subject"] = subject
    if from_email:
        if from_name:
            message["From"] = f"{from_name} <{from_email}>"
        else:
            message["From"] = from_email
    message.set_content(body)
    return _urlsafe_b64encode(message.as_bytes())


def _get_send_as_config(db: Session, workspace_id: UUID) -> tuple[str | None, str | None]:
    """Return (send_as_email, send_as_display_name) from workspace settings, or (None, None)."""
    ws = db.get(WorkspaceSetting, workspace_id)
    if ws is None:
        return None, None
    return ws.gmail_send_as_email, ws.gmail_send_as_display_name


def create_gmail_draft(
    *,
    db: Session,
    workspace_id: UUID,
    to_email: str,
    subject: str,
    body: str,
) -> dict[str, Any]:
    from_email, from_name = _get_send_as_config(db, workspace_id)
    raw = _build_raw_message(
        to_email=to_email,
        subject=subject,
        body=body,
        from_email=from_email,
        from_name=from_name,
    )
    payload = {"message": {"raw": raw}}
    return _gmail_api_post(db=db, workspace_id=workspace_id, path="/drafts", payload=payload)


def fetch_send_as_aliases(db: Session, workspace_id: UUID) -> list[dict[str, Any]]:
    """Return the list of send-as addresses for the connected Gmail account."""
    account, token = get_active_token(db, workspace_id)
    url = f"{GMAIL_API_ROOT}/settings/sendAs"
    headers = {"Authorization": f"Bearer {token.access_token}"}
    with httpx.Client(timeout=20.0) as client:
        response = client.get(url, headers=headers)
    if response.status_code == 401 and token.refresh_token:
        refreshed = _refresh_access_token(db, account=account, refresh_token=token.refresh_token)
        headers = {"Authorization": f"Bearer {refreshed.access_token}"}
        with httpx.Client(timeout=20.0) as client:
            response = client.get(url, headers=headers)
    if response.status_code >= 400:
        detail = response.text.strip() or "unknown Gmail API error"
        raise GmailApiError(f"Failed to fetch send-as aliases: {detail}", status_code=502)
    data = response.json()
    return data.get("sendAs", [])


def disconnect_gmail(db: Session, workspace_id: UUID) -> None:
    """Revoke tokens, mark account disconnected, clear workspace gmail_connected flag."""
    account = get_gmail_account(db, workspace_id)
    if account is not None:
        # Best-effort token revocation
        token = db.scalar(
            select(OAuthToken)
            .where(OAuthToken.integration_account_id == account.id)
            .order_by(OAuthToken.created_at.desc())
            .limit(1)
        )
        if token:
            try:
                with httpx.Client(timeout=10.0) as client:
                    client.post(
                        "https://oauth2.googleapis.com/revoke",
                        params={"token": token.access_token},
                    )
            except Exception:  # pragma: no cover
                pass
        # Delete all tokens for this account
        all_tokens = db.scalars(
            select(OAuthToken).where(OAuthToken.integration_account_id == account.id)
        ).all()
        for t in all_tokens:
            db.delete(t)
        account.status = "disconnected"
        account.last_error = None
        db.flush()

    ws = db.get(WorkspaceSetting, workspace_id)
    if ws is not None:
        ws.gmail_connected = False
        ws.gmail_send_as_email = None
        ws.gmail_send_as_display_name = None
        db.flush()


def send_gmail_draft(*, db: Session, workspace_id: UUID, gmail_draft_id: str) -> dict[str, Any]:
    payload = {"id": gmail_draft_id}
    return _gmail_api_post(db=db, workspace_id=workspace_id, path="/drafts/send", payload=payload)
