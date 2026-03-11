from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.request_context import RequestContext, get_request_context
from app.api.deps.scoping import require_scoped_lead
from app.db.session import get_db
from app.models.email_draft import EmailDraft
from app.models.lead_status import LEAD_STATUS_APPROVED, LEAD_STATUS_NEEDS_REVIEW
from app.models.workspace_ai_strategy import WorkspaceAIStrategy
from app.models.website_snapshot import WebsiteSnapshot
from app.schemas.agent3 import Agent3RunResponse, FinalEmailRead
from app.services.agent3_verifier import (
    Agent3ConfigurationError,
    Agent3RateLimitError,
    Agent3VerifierError,
    verify_email_with_agent3,
)
from app.services.workspace_credentials import resolve_openai_api_key
from app.services.workspace_ai_strategy import build_strategy_context

router = APIRouter(prefix="/leads/{lead_id}", tags=["Agent 3"])
logger = logging.getLogger(__name__)


@router.post("/run-agent3", response_model=Agent3RunResponse, status_code=status.HTTP_200_OK)
def run_agent3_for_lead(
    lead_id: UUID,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> Agent3RunResponse:
    logger.info("Agent3 run requested workspace_id=%s lead_id=%s", ctx.workspace_id, lead_id)
    lead = require_scoped_lead(db=db, lead_id=lead_id, workspace_id=ctx.workspace_id)

    latest_snapshot = db.scalar(
        select(WebsiteSnapshot)
        .where(WebsiteSnapshot.lead_id == lead_id, WebsiteSnapshot.workspace_id == ctx.workspace_id)
        .order_by(WebsiteSnapshot.fetched_at.desc(), WebsiteSnapshot.created_at.desc())
        .limit(1)
    )
    if latest_snapshot is None:
        logger.warning("Agent3 missing dependency workspace_id=%s lead_id=%s dependency=latest_snapshot", ctx.workspace_id, lead_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No website snapshots found for lead. Run /ingest-website first.",
        )

    recent_drafts = db.scalars(
        select(EmailDraft)
        .where(EmailDraft.lead_id == lead_id, EmailDraft.workspace_id == ctx.workspace_id)
        .order_by(EmailDraft.created_at.desc())
        .limit(25)
    ).all()
    latest_draft: EmailDraft | None = None
    for draft in recent_drafts:
        verdict = draft.agent3_verdict
        if isinstance(verdict, dict) and verdict.get("source") == "agent2":
            latest_draft = draft
            break
    if latest_draft is None:
        for draft in recent_drafts:
            verdict = draft.agent3_verdict
            if (
                isinstance(verdict, dict)
                and draft.decision in {"send", "hold"}
                and isinstance(verdict.get("final_email"), dict)
            ):
                latest_draft = draft
                break
    if latest_draft is None:
        logger.warning("Agent3 missing dependency workspace_id=%s lead_id=%s dependency=agent2_draft", ctx.workspace_id, lead_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No agent2 draft found for lead. Run /run-agent2 first.",
        )

    latest_agent1_draft = db.scalar(
        select(EmailDraft)
        .where(
            EmailDraft.lead_id == lead_id,
            EmailDraft.workspace_id == ctx.workspace_id,
            EmailDraft.agent1_output.is_not(None),
        )
        .order_by(EmailDraft.created_at.desc())
        .limit(1)
    )
    if latest_agent1_draft is None or latest_agent1_draft.agent1_output is None:
        logger.warning("Agent3 missing dependency workspace_id=%s lead_id=%s dependency=agent1_output", ctx.workspace_id, lead_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No agent1 output found for lead. Run /run-agent1 first.",
        )
    logger.info(
        "Agent3 dependencies workspace_id=%s lead_id=%s snapshot_id=%s agent2_draft_id=%s agent1_draft_id=%s",
        ctx.workspace_id,
        lead_id,
        latest_snapshot.id,
        latest_draft.id,
        latest_agent1_draft.id,
    )

    openai_api_key, key_source = resolve_openai_api_key(db=db, workspace_id=ctx.workspace_id)
    logger.info(
        "Agent3 OpenAI key resolution workspace_id=%s lead_id=%s key_source=%s",
        ctx.workspace_id,
        lead_id,
        key_source,
    )

    logger.info("Agent3 run start lead_id=%s draft_id=%s", lead_id, latest_draft.id)
    strategy_context = build_strategy_context(db.get(WorkspaceAIStrategy, ctx.workspace_id))
    try:
        verdict = verify_email_with_agent3(
            lead_name=lead.name,
            company=lead.company,
            website_url=lead.website_url,
            snapshot_text=latest_snapshot.raw_text,
            agent1_output=latest_agent1_draft.agent1_output,
            draft_subject=latest_draft.subject,
            draft_body=latest_draft.body,
            strategy_context=strategy_context,
            api_key=openai_api_key,
        )
    except Agent3ConfigurationError as exc:
        logger.warning("Agent3 configuration error workspace_id=%s lead_id=%s error=%s", ctx.workspace_id, lead_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenAI API key is missing. Configure workspace settings at /api/v1/settings or set OPENAI_API_KEY.",
        ) from exc
    except Agent3RateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Agent3 failed: {exc}") from exc
    except Agent3VerifierError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Agent3 failed: {exc}") from exc

    final_email = verdict["final_email"]
    latest_draft.agent3_verdict = verdict
    latest_draft.decision = verdict["decision"]
    latest_draft.subject = final_email["subject"][:255]
    latest_draft.body = final_email["email_body"]
    decision = str(verdict.get("decision") or "").strip().lower()
    if decision in {"send", "approved"}:
        lead.status = LEAD_STATUS_APPROVED
    else:
        lead.status = LEAD_STATUS_NEEDS_REVIEW
    latest_draft.review_status = "pending_review"
    latest_draft.approved_at = None
    latest_draft.rejected_at = None

    db.commit()
    db.refresh(latest_draft)
    logger.info(
        "Agent3 run end lead_id=%s draft_id=%s decision=%s",
        lead_id,
        latest_draft.id,
        latest_draft.decision,
    )

    return Agent3RunResponse(
        lead_id=lead_id,
        draft_id=latest_draft.id,
        decision=verdict["decision"],
        issues=verdict.get("issues", []),
        final_email=FinalEmailRead(
            subject=final_email["subject"],
            email_body=final_email["email_body"],
        ),
    )
