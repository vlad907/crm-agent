from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.email_draft import EmailDraft
from app.models.lead import Lead
from app.models.website_snapshot import WebsiteSnapshot
from app.schemas.agent3 import Agent3RunResponse, FinalEmailRead
from app.services.agent3_verifier import Agent3RateLimitError, Agent3VerifierError, verify_email_with_agent3

router = APIRouter(prefix="/leads/{lead_id}", tags=["Agent 3"])
logger = logging.getLogger(__name__)


@router.post("/run-agent3", response_model=Agent3RunResponse, status_code=status.HTTP_200_OK)
def run_agent3_for_lead(lead_id: UUID, db: Session = Depends(get_db)) -> Agent3RunResponse:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    latest_snapshot = db.scalar(
        select(WebsiteSnapshot)
        .where(WebsiteSnapshot.lead_id == lead_id)
        .order_by(WebsiteSnapshot.fetched_at.desc(), WebsiteSnapshot.created_at.desc())
        .limit(1)
    )
    if latest_snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No website snapshots found for lead")

    recent_drafts = db.scalars(
        select(EmailDraft)
        .where(EmailDraft.lead_id == lead_id)
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No agent2 draft found for lead")

    latest_agent1_draft = db.scalar(
        select(EmailDraft)
        .where(EmailDraft.lead_id == lead_id, EmailDraft.agent1_output.is_not(None))
        .order_by(EmailDraft.created_at.desc())
        .limit(1)
    )
    if latest_agent1_draft is None or latest_agent1_draft.agent1_output is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No agent1 output found for lead")

    logger.info("Agent3 run start lead_id=%s draft_id=%s", lead_id, latest_draft.id)
    try:
        verdict = verify_email_with_agent3(
            lead_name=lead.name,
            company=lead.company,
            website_url=lead.website_url,
            snapshot_text=latest_snapshot.raw_text,
            agent1_output=latest_agent1_draft.agent1_output,
            draft_subject=latest_draft.subject,
            draft_body=latest_draft.body,
        )
    except Agent3RateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Agent3 failed: {exc}") from exc
    except Agent3VerifierError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Agent3 failed: {exc}") from exc

    final_email = verdict["final_email"]
    latest_draft.agent3_verdict = verdict
    latest_draft.decision = verdict["decision"]
    latest_draft.subject = final_email["subject"][:255]
    latest_draft.body = final_email["email_body"]

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
