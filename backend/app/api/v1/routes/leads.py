from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import HttpUrl, TypeAdapter, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.email_draft import EmailDraft
from app.models.lead import Lead
from app.models.website_snapshot import WebsiteSnapshot
from app.schemas.agent1 import Agent1RunResponse, LatestContextResponse, LatestContextSnapshot
from app.schemas.agent3 import FinalEmailRead
from app.schemas.email_draft import EmailDraftRead
from app.schemas.lead import LeadCreate, LeadListResponse, LeadRead, LeadUpdate
from app.schemas.website_snapshot import WebsiteSnapshotIngestRead
from app.services.openai_client import OpenAIClientError, OpenAIRateLimitError, run_agent1, run_agent2
from app.services.scrape import WebsiteFetchError, extract_text, fetch_html

router = APIRouter(prefix="/leads", tags=["Leads"])
logger = logging.getLogger(__name__)
http_url_adapter = TypeAdapter(HttpUrl)


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def create_lead(payload: LeadCreate, db: Session = Depends(get_db)) -> Lead:
    lead = Lead(**payload.model_dump())
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


@router.get("", response_model=LeadListResponse)
def list_leads(
    db: Session = Depends(get_db),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    query: str | None = Query(default=None, alias="q", min_length=1),
) -> LeadListResponse:
    filters = []

    if status_filter:
        filters.append(Lead.status == status_filter)
    if query:
        filters.append(Lead.company.ilike(f"%{query}%"))

    list_stmt = select(Lead).order_by(Lead.created_at.desc()).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(Lead)

    if filters:
        list_stmt = list_stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    items = db.scalars(list_stmt).all()
    total = db.scalar(count_stmt) or 0
    return LeadListResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/{lead_id}", response_model=LeadRead)
def get_lead(lead_id: UUID, db: Session = Depends(get_db)) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


@router.patch("/{lead_id}", response_model=LeadRead)
def update_lead(lead_id: UUID, payload: LeadUpdate, db: Session = Depends(get_db)) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(lead, field, value)

    db.commit()
    db.refresh(lead)
    return lead


@router.post(
    "/{lead_id}/ingest-website",
    response_model=WebsiteSnapshotIngestRead,
    status_code=status.HTTP_201_CREATED,
)
def ingest_website(lead_id: UUID, db: Session = Depends(get_db)) -> WebsiteSnapshotIngestRead:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    if not lead.website_url or not lead.website_url.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lead website_url is missing")

    url = lead.website_url.strip()
    try:
        normalized_url = str(http_url_adapter.validate_python(url))
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid website_url") from exc

    try:
        html = fetch_html(normalized_url)
    except WebsiteFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Website fetch failed: {exc}",
        ) from exc

    raw_text = extract_text(html)
    if not raw_text:
        raw_text = "[no readable text extracted]"
    logger.info("Website text extracted lead_id=%s length=%s", lead_id, len(raw_text))

    snapshot = WebsiteSnapshot(
        lead_id=lead.id,
        url=normalized_url,
        raw_text=raw_text,
        fetched_at=datetime.now(timezone.utc),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    return WebsiteSnapshotIngestRead(
        id=snapshot.id,
        fetched_at=snapshot.fetched_at,
        raw_text_length=len(snapshot.raw_text),
    )


@router.post(
    "/{lead_id}/run-agent1",
    response_model=Agent1RunResponse,
    status_code=status.HTTP_201_CREATED,
)
def run_agent1_for_lead(lead_id: UUID, db: Session = Depends(get_db)) -> Agent1RunResponse:
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

    logger.info("Agent1 run start lead_id=%s snapshot_id=%s", lead_id, latest_snapshot.id)
    try:
        agent1_output = run_agent1(latest_snapshot.raw_text)
    except OpenAIRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Agent1 failed: {exc}") from exc
    except OpenAIClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Agent1 failed: {exc}") from exc

    draft = EmailDraft(
        lead_id=lead_id,
        subject=f"Agent1 draft for {lead.company}",
        body=f"Auto-generated Agent1 analysis from website snapshot {latest_snapshot.id}.",
        agent1_output=agent1_output,
        decision="draft",
    )
    db.add(draft)
    db.commit()

    logger.info("Agent1 run end lead_id=%s snapshot_id=%s", lead_id, latest_snapshot.id)
    return Agent1RunResponse(
        lead_id=lead_id,
        snapshot_id=latest_snapshot.id,
        agent1_output=agent1_output,
    )


@router.post(
    "/{lead_id}/run-agent2",
    response_model=EmailDraftRead,
    status_code=status.HTTP_201_CREATED,
)
def run_agent2_for_lead(lead_id: UUID, db: Session = Depends(get_db)) -> EmailDraft:
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

    latest_agent1_draft = db.scalar(
        select(EmailDraft)
        .where(EmailDraft.lead_id == lead_id, EmailDraft.agent1_output.is_not(None))
        .order_by(EmailDraft.created_at.desc())
        .limit(1)
    )
    if latest_agent1_draft is None or latest_agent1_draft.agent1_output is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No agent1 output found for lead")

    logger.info("Agent2 run start lead_id=%s snapshot_id=%s", lead_id, latest_snapshot.id)
    try:
        agent2_output = run_agent2(
            lead_name=lead.name,
            company=lead.company,
            website_url=lead.website_url,
            snapshot_text=latest_snapshot.raw_text,
            agent1_output=latest_agent1_draft.agent1_output,
        )
    except OpenAIRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Agent2 failed: {exc}") from exc
    except OpenAIClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Agent2 failed: {exc}") from exc

    draft = EmailDraft(
        lead_id=lead_id,
        subject=agent2_output["subject"][:255],
        body=agent2_output["email_body"],
        agent1_output=latest_agent1_draft.agent1_output,
        agent3_verdict={"used_signal": agent2_output["used_signal"], "source": "agent2"},
        decision="draft",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    logger.info("Agent2 run end lead_id=%s draft_id=%s", lead_id, draft.id)
    return draft


@router.get("/{lead_id}/latest-context", response_model=LatestContextResponse)
def get_latest_context(lead_id: UUID, db: Session = Depends(get_db)) -> LatestContextResponse:
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

    latest_agent1_draft = db.scalar(
        select(EmailDraft)
        .where(EmailDraft.lead_id == lead_id, EmailDraft.agent1_output.is_not(None))
        .order_by(EmailDraft.created_at.desc())
        .limit(1)
    )
    latest_agent3_draft = db.scalar(
        select(EmailDraft)
        .where(
            EmailDraft.lead_id == lead_id,
            EmailDraft.agent3_verdict.is_not(None),
            EmailDraft.decision.in_(["send", "hold"]),
        )
        .order_by(EmailDraft.created_at.desc())
        .limit(1)
    )

    agent3_decision: str | None = None
    agent3_issues: list[str] | None = None
    final_email: FinalEmailRead | None = None
    if latest_agent3_draft and isinstance(latest_agent3_draft.agent3_verdict, dict):
        verdict = latest_agent3_draft.agent3_verdict
        raw_decision = verdict.get("decision")
        if isinstance(raw_decision, str):
            agent3_decision = raw_decision
        raw_issues = verdict.get("issues")
        if isinstance(raw_issues, list) and all(isinstance(item, str) for item in raw_issues):
            agent3_issues = raw_issues
        raw_final_email = verdict.get("final_email")
        if isinstance(raw_final_email, dict):
            subject = raw_final_email.get("subject")
            email_body = raw_final_email.get("email_body")
            if isinstance(subject, str) and isinstance(email_body, str) and subject.strip() and email_body.strip():
                final_email = FinalEmailRead(subject=subject, email_body=email_body)

    return LatestContextResponse(
        lead_id=lead_id,
        snapshot=LatestContextSnapshot(
            id=latest_snapshot.id,
            url=latest_snapshot.url,
            fetched_at=latest_snapshot.fetched_at,
            raw_text=latest_snapshot.raw_text,
        ),
        agent1_output=latest_agent1_draft.agent1_output if latest_agent1_draft else None,
        agent3_decision=agent3_decision,
        agent3_issues=agent3_issues,
        final_email=final_email,
    )
