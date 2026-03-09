from __future__ import annotations

import logging
import uuid
from typing import Tuple

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.email_draft import EmailDraft  # noqa: F401
from app.models.integration_account import IntegrationAccount  # noqa: F401
from app.models.lead import Lead  # noqa: F401
from app.models.oauth_token import OAuthToken  # noqa: F401
from app.models.user import User
from app.models.website_snapshot import WebsiteSnapshot  # noqa: F401
from app.models.workspace import Workspace

logger = logging.getLogger(__name__)

HEADER_WORKSPACE_ID = "X-Workspace-Id"
HEADER_USER_ID = "X-User-Id"
DEFAULT_WORKSPACE_NAME = "Default Workspace"
DEFAULT_USER_EMAIL = "dev@local"
DEFAULT_USER_NAME = "Development Owner"

_runtime_default_identity: tuple[uuid.UUID, uuid.UUID] | None = None


class DevIdentityError(ValueError):
    """Raised when development identity headers/defaults are invalid or missing."""


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise DevIdentityError(f"{field_name} must be a valid UUID") from exc


def set_runtime_default_identity(workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    global _runtime_default_identity
    _runtime_default_identity = (workspace_id, user_id)


def get_runtime_default_identity() -> tuple[uuid.UUID, uuid.UUID] | None:
    return _runtime_default_identity


def resolve_request_identity(
    workspace_header_value: str | None,
    user_header_value: str | None,
) -> tuple[uuid.UUID, uuid.UUID]:
    runtime_defaults = get_runtime_default_identity()

    default_workspace_id: uuid.UUID | None = None
    if settings.default_workspace_id:
        default_workspace_id = _parse_uuid(settings.default_workspace_id, "DEFAULT_WORKSPACE_ID")
    elif runtime_defaults is not None:
        default_workspace_id = runtime_defaults[0]

    default_user_id: uuid.UUID | None = None
    if settings.default_user_id:
        default_user_id = _parse_uuid(settings.default_user_id, "DEFAULT_USER_ID")
    elif runtime_defaults is not None:
        default_user_id = runtime_defaults[1]

    workspace_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None

    if workspace_header_value:
        workspace_id = _parse_uuid(workspace_header_value, HEADER_WORKSPACE_ID)
    elif default_workspace_id is not None:
        workspace_id = default_workspace_id

    if user_header_value:
        user_id = _parse_uuid(user_header_value, HEADER_USER_ID)
    elif default_user_id is not None:
        user_id = default_user_id

    if workspace_id is None or user_id is None:
        raise DevIdentityError(
            "Missing request identity. Set X-Workspace-Id/X-User-Id headers or configure DEFAULT_WORKSPACE_ID/DEFAULT_USER_ID."
        )

    return workspace_id, user_id


def _is_email_taken(email: str, db_user_id: uuid.UUID | None = None) -> bool:
    with SessionLocal() as db:
        stmt = select(User).where(User.email == email)
        existing = db.scalar(stmt)
        if existing is None:
            return False
        if db_user_id is not None and existing.id == db_user_id:
            return False
        return True


def _build_available_dev_email(user_id: uuid.UUID | None = None) -> str:
    if user_id and not _is_email_taken(DEFAULT_USER_EMAIL, db_user_id=user_id):
        return DEFAULT_USER_EMAIL
    if not _is_email_taken(DEFAULT_USER_EMAIL):
        return DEFAULT_USER_EMAIL

    suffix = user_id.hex[:8] if user_id else uuid.uuid4().hex[:8]
    return f"dev+{suffix}@local"


def initialize_default_identity_for_dev() -> tuple[uuid.UUID, uuid.UUID] | None:
    """
    Create or reuse a default workspace/user in development and expose their IDs at runtime.

    This is a dev helper, not authentication.
    """

    if settings.environment.lower() not in {"development", "dev", "local", "test"}:
        return None

    try:
        with SessionLocal() as db:
            configured_workspace_id: uuid.UUID | None = None
            if settings.default_workspace_id:
                configured_workspace_id = _parse_uuid(settings.default_workspace_id, "DEFAULT_WORKSPACE_ID")

            configured_user_id: uuid.UUID | None = None
            if settings.default_user_id:
                configured_user_id = _parse_uuid(settings.default_user_id, "DEFAULT_USER_ID")

            workspace: Workspace | None = None
            if configured_workspace_id:
                workspace = db.get(Workspace, configured_workspace_id)
                if workspace is None:
                    workspace = Workspace(id=configured_workspace_id, name=DEFAULT_WORKSPACE_NAME)
                    db.add(workspace)
                    db.flush()
            else:
                workspace = db.scalar(select(Workspace).order_by(Workspace.created_at.asc()).limit(1))
                if workspace is None:
                    workspace = Workspace(name=DEFAULT_WORKSPACE_NAME)
                    db.add(workspace)
                    db.flush()

            user: User | None = None
            if configured_user_id:
                user = db.get(User, configured_user_id)
                if user is None:
                    user = User(
                        id=configured_user_id,
                        workspace_id=workspace.id,
                        email=_build_available_dev_email(configured_user_id),
                        name=DEFAULT_USER_NAME,
                        role="owner",
                    )
                    db.add(user)
                elif user.workspace_id != workspace.id:
                    user.workspace_id = workspace.id
            else:
                user = db.scalar(
                    select(User)
                    .where(User.workspace_id == workspace.id)
                    .order_by(User.created_at.asc())
                    .limit(1)
                )
                if user is None:
                    user = User(
                        workspace_id=workspace.id,
                        email=_build_available_dev_email(),
                        name=DEFAULT_USER_NAME,
                        role="owner",
                    )
                    db.add(user)

            db.commit()
            db.refresh(workspace)
            db.refresh(user)

            set_runtime_default_identity(workspace.id, user.id)
            logger.info(
                "Dev identity ready workspace_id=%s user_id=%s",
                workspace.id,
                user.id,
            )
            if not settings.default_workspace_id or not settings.default_user_id:
                logger.info(
                    "Set DEFAULT_WORKSPACE_ID=%s and DEFAULT_USER_ID=%s in .env to make defaults explicit.",
                    workspace.id,
                    user.id,
                )
            return workspace.id, user.id
    except DevIdentityError:
        raise
    except (ProgrammingError, OperationalError, SQLAlchemyError) as exc:
        logger.warning("Skipping dev identity bootstrap (database not ready): %s", exc)
        return None
