from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps.request_context import RequestContext, get_request_context
from app.db.session import get_db
from app.models.workspace_ai_strategy import WorkspaceAIStrategy
from app.models.workspace_profile import WorkspaceProfile
from app.schemas.workspace_ai_strategy import WorkspaceAIStrategyRead, WorkspaceAIStrategyUpdate
from app.services.openai_client import (
    OpenAIClientError,
    OpenAIConfigurationError,
    OpenAIRateLimitError,
)
from app.services.workspace_ai_strategy import (
    generate_workspace_outreach_strategy,
    normalize_string_list,
)
from app.services.workspace_credentials import resolve_openai_api_key

router = APIRouter(prefix="/workspace-ai-strategy", tags=["Workspace AI Strategy"])
logger = logging.getLogger(__name__)


def _as_read(strategy: WorkspaceAIStrategy | None, workspace_id: UUID) -> WorkspaceAIStrategyRead:
    if strategy is None:
        return WorkspaceAIStrategyRead(
            workspace_id=workspace_id,
            generated_strategy=None,
            selected_target_categories=[],
            selected_priority_pain_points=[],
            selected_service_angles=[],
            selected_cta_style=None,
            version=1,
            last_generated_at=None,
            created_at=None,
            updated_at=None,
        )
    return WorkspaceAIStrategyRead.model_validate(strategy)


@router.get("", response_model=WorkspaceAIStrategyRead)
def get_workspace_ai_strategy(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> WorkspaceAIStrategyRead:
    strategy = db.get(WorkspaceAIStrategy, ctx.workspace_id)
    return _as_read(strategy, ctx.workspace_id)


@router.patch("", response_model=WorkspaceAIStrategyRead)
def patch_workspace_ai_strategy(
    payload: WorkspaceAIStrategyUpdate,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> WorkspaceAIStrategyRead:
    strategy = db.get(WorkspaceAIStrategy, ctx.workspace_id)
    if strategy is None:
        strategy = WorkspaceAIStrategy(workspace_id=ctx.workspace_id)
        db.add(strategy)

    updates = payload.model_dump(exclude_unset=True)
    if "selected_target_categories" in updates:
        strategy.selected_target_categories = normalize_string_list(updates["selected_target_categories"])
    if "selected_priority_pain_points" in updates:
        strategy.selected_priority_pain_points = normalize_string_list(updates["selected_priority_pain_points"])
    if "selected_service_angles" in updates:
        strategy.selected_service_angles = normalize_string_list(updates["selected_service_angles"])
    if "selected_cta_style" in updates:
        cta_style = updates["selected_cta_style"]
        strategy.selected_cta_style = cta_style.strip() if isinstance(cta_style, str) and cta_style.strip() else None

    db.commit()
    db.refresh(strategy)
    return WorkspaceAIStrategyRead.model_validate(strategy)


@router.post("/generate", response_model=WorkspaceAIStrategyRead)
def generate_workspace_ai_strategy(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> WorkspaceAIStrategyRead:
    workspace_profile = db.get(WorkspaceProfile, ctx.workspace_id)
    openai_api_key, key_source = resolve_openai_api_key(db=db, workspace_id=ctx.workspace_id)
    logger.info("Workspace AI strategy generate requested workspace_id=%s key_source=%s", ctx.workspace_id, key_source)

    try:
        generated_strategy = generate_workspace_outreach_strategy(
            workspace_profile=workspace_profile,
            api_key=openai_api_key,
        )
    except OpenAIConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenAI API key is missing. Configure workspace settings at /api/v1/settings or set OPENAI_API_KEY.",
        ) from exc
    except OpenAIRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Strategy generation failed: {exc}") from exc
    except OpenAIClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Strategy generation failed: {exc}") from exc

    strategy = db.get(WorkspaceAIStrategy, ctx.workspace_id)
    if strategy is None:
        strategy = WorkspaceAIStrategy(workspace_id=ctx.workspace_id)
        db.add(strategy)
    else:
        previous_version = max(1, int(strategy.version or 1))
        strategy.version = previous_version + 1 if strategy.generated_strategy is not None else previous_version

    strategy.generated_strategy = generated_strategy
    strategy.last_generated_at = datetime.now(timezone.utc)
    strategy.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(strategy)
    return WorkspaceAIStrategyRead.model_validate(strategy)
