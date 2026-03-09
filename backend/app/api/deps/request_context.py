from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, Request, status


@dataclass(frozen=True)
class RequestContext:
    workspace_id: UUID
    user_id: UUID


def get_request_context(request: Request) -> RequestContext:
    workspace_id = getattr(request.state, "workspace_id", None)
    user_id = getattr(request.state, "user_id", None)

    if not isinstance(workspace_id, UUID) or not isinstance(user_id, UUID):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Request context is not initialized",
        )

    return RequestContext(workspace_id=workspace_id, user_id=user_id)
