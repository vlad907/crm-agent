from __future__ import annotations

from collections import defaultdict
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import HttpUrl, TypeAdapter, ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.deps.request_context import RequestContext, get_request_context
from app.api.deps.scoping import require_scoped_lead
from app.db.session import get_db
from app.models.email_draft import EmailDraft
from app.models.lead import Lead
from app.models.website_page import WebsitePage
from app.models.website_snapshot import WebsiteSnapshot
from app.schemas.agent1 import Agent1RunResponse, LatestContextResponse, LatestContextSnapshot
from app.schemas.agent3 import FinalEmailRead
from app.schemas.email_draft import EmailDraftRead
from app.schemas.lead import (
    LeadCreate,
    LeadImportDuplicate,
    LeadImportError,
    LeadImportRequest,
    LeadImportResponse,
    LeadListResponse,
    LeadPipelineSummary,
    LeadRead,
    LeadUpdate,
)
from app.schemas.website_snapshot import WebsiteSnapshotIngestRead
from app.services.lead_import import LeadImportCandidate, import_leads_for_workspace
from app.services.lead_context import build_prepared_lead_context
from app.services.openai_client import (
    OpenAIClientError,
    OpenAIConfigurationError,
    OpenAIRateLimitError,
    run_agent1,
    run_agent2,
)
from app.services.scrape import WebsiteFetchError
from app.services.website_ingestion import ingest_website_pages
from app.services.workspace_credentials import resolve_openai_api_key

router = APIRouter(prefix="/leads", tags=["Leads"])
logger = logging.getLogger(__name__)
http_url_adapter = TypeAdapter(HttpUrl)
AGENT1_SUBJECT_PREFIX = "Agent1 draft for "
AGENT1_BODY_PREFIX = "Auto-generated Agent1 analysis"


def _compute_stage(
    *,
    lead_status: str | None,
    has_snapshot: bool,
    has_agent1_output: bool,
    has_draft: bool,
    has_agent3_verdict: bool,
    final_decision: str | None,
) -> str:
    status_norm = (lead_status or "").strip().lower()
    if status_norm == "sent":
        return "sent"
    if final_decision == "send" or status_norm in {"send", "ready_to_send", "ready"}:
        return "ready"
    if final_decision == "hold" or status_norm == "hold":
        return "hold"
    if has_agent3_verdict:
        return "agent3"
    if has_draft:
        return "agent2"
    if has_agent1_output:
        return "agent1"
    if has_snapshot or status_norm == "ingested":
        return "ingested"
    return "new"


def _is_non_agent1_placeholder_draft(draft: EmailDraft) -> bool:
    subject = draft.subject or ""
    body = draft.body or ""
    return not (subject.startswith(AGENT1_SUBJECT_PREFIX) and body.startswith(AGENT1_BODY_PREFIX))


def _build_pipeline_summary_map(db: Session, workspace_id: UUID, leads: list[Lead]) -> dict[UUID, LeadPipelineSummary]:
    if not leads:
        return {}

    lead_ids = [lead.id for lead in leads]
    snapshot_lead_ids = set(
        db.scalars(
            select(WebsiteSnapshot.lead_id)
            .where(WebsiteSnapshot.workspace_id == workspace_id, WebsiteSnapshot.lead_id.in_(lead_ids))
            .distinct()
        ).all()
    )

    drafts = db.scalars(
        select(EmailDraft)
        .where(EmailDraft.workspace_id == workspace_id, EmailDraft.lead_id.in_(lead_ids))
        .order_by(EmailDraft.created_at.desc(), EmailDraft.updated_at.desc())
    ).all()
    drafts_by_lead: dict[UUID, list[EmailDraft]] = defaultdict(list)
    for draft in drafts:
        drafts_by_lead[draft.lead_id].append(draft)

    pipeline_map: dict[UUID, LeadPipelineSummary] = {}
    for lead in leads:
        has_snapshot = lead.id in snapshot_lead_ids
        has_agent1_output = False
        has_draft = False
        has_agent3_verdict = False
        final_decision: str | None = None

        for draft in drafts_by_lead.get(lead.id, []):
            verdict = draft.agent3_verdict if isinstance(draft.agent3_verdict, dict) else None
            verdict_source = (str(verdict.get("source", "")).strip().lower() if verdict else "")
            verdict_decision = verdict.get("decision") if verdict else None
            draft_decision = (draft.decision or "").strip().lower()

            if draft.agent1_output is not None:
                has_agent1_output = True

            if verdict_source == "agent2" or draft_decision in {"send", "hold"} or _is_non_agent1_placeholder_draft(draft):
                has_draft = True

            if isinstance(verdict_decision, str) and verdict_decision in {"send", "hold"}:
                has_agent3_verdict = True
                if final_decision is None:
                    final_decision = verdict_decision

            if draft_decision in {"send", "hold"}:
                if verdict is not None:
                    has_agent3_verdict = True
                if final_decision is None:
                    final_decision = draft_decision

        if final_decision is None:
            status_norm = (lead.status or "").strip().lower()
            if status_norm in {"send", "hold"}:
                final_decision = status_norm

        pipeline_map[lead.id] = LeadPipelineSummary(
            has_snapshot=has_snapshot,
            has_agent1_output=has_agent1_output,
            has_draft=has_draft,
            has_agent3_verdict=has_agent3_verdict,
            final_decision=final_decision,
            computed_stage=_compute_stage(
                lead_status=lead.status,
                has_snapshot=has_snapshot,
                has_agent1_output=has_agent1_output,
                has_draft=has_draft,
                has_agent3_verdict=has_agent3_verdict,
                final_decision=final_decision,
            ),
        )

    return pipeline_map


def _with_pipeline_summary(lead: Lead, summary: LeadPipelineSummary | None) -> LeadRead:
    payload = LeadRead.model_validate(lead, from_attributes=True)
    return payload.model_copy(update={"pipeline_summary": summary})


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def create_lead(
    payload: LeadCreate,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> LeadRead:
    lead = Lead(workspace_id=ctx.workspace_id, **payload.model_dump())
    db.add(lead)
    db.commit()
    db.refresh(lead)
    summary = _build_pipeline_summary_map(db, ctx.workspace_id, [lead]).get(lead.id)
    return _with_pipeline_summary(lead, summary)


@router.post("/imports", response_model=LeadImportResponse)
def import_leads(
    payload: LeadImportRequest,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> LeadImportResponse:
    candidates = [
        LeadImportCandidate(
            row_index=index,
            name=item.name,
            title=item.title,
            company=item.company,
            industry=item.industry,
            location=item.location,
            website_url=item.website_url,
            email=item.email,
            source=item.source,
            status=item.status,
        )
        for index, item in enumerate(payload.items)
    ]

    result = import_leads_for_workspace(
        db=db,
        workspace_id=ctx.workspace_id,
        candidates=candidates,
        default_source=payload.source,
        dedupe_by_website=payload.dedupe_by_website,
        dedupe_by_company_location=payload.dedupe_by_company_location,
    )

    return LeadImportResponse(
        source=payload.source,
        total_received=len(payload.items),
        imported_count=len(result.imported),
        duplicate_count=len(result.duplicates),
        error_count=len(result.errors),
        imported=result.imported,
        duplicates=[
            LeadImportDuplicate(
                row_index=item.row_index,
                reason=item.reason,
                company=item.company,
                location=item.location,
                website_url=item.website_url,
            )
            for item in result.duplicates
        ],
        errors=[
            LeadImportError(
                row_index=item.row_index,
                reason=item.reason,
                company=item.company,
                location=item.location,
                website_url=item.website_url,
            )
            for item in result.errors
        ],
    )


@router.get("", response_model=LeadListResponse)
def list_leads(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    query: str | None = Query(default=None, alias="q", min_length=1),
) -> LeadListResponse:
    filters = [Lead.workspace_id == ctx.workspace_id]

    if status_filter:
        filters.append(Lead.status == status_filter)
    if query:
        filters.append(Lead.company.ilike(f"%{query}%"))

    list_stmt = select(Lead).where(*filters).order_by(Lead.created_at.desc()).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(Lead).where(*filters)

    items = db.scalars(list_stmt).all()
    pipeline_map = _build_pipeline_summary_map(db, ctx.workspace_id, items)
    lead_items = [_with_pipeline_summary(item, pipeline_map.get(item.id)) for item in items]
    total = db.scalar(count_stmt) or 0
    return LeadListResponse(items=lead_items, total=total, offset=offset, limit=limit)


@router.get("/{lead_id}", response_model=LeadRead)
def get_lead(
    lead_id: UUID,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> LeadRead:
    lead = require_scoped_lead(db=db, lead_id=lead_id, workspace_id=ctx.workspace_id)
    summary = _build_pipeline_summary_map(db, ctx.workspace_id, [lead]).get(lead.id)
    return _with_pipeline_summary(lead, summary)


@router.patch("/{lead_id}", response_model=LeadRead)
def update_lead(
    lead_id: UUID,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> LeadRead:
    lead = require_scoped_lead(db=db, lead_id=lead_id, workspace_id=ctx.workspace_id)

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(lead, field, value)

    db.commit()
    db.refresh(lead)
    summary = _build_pipeline_summary_map(db, ctx.workspace_id, [lead]).get(lead.id)
    return _with_pipeline_summary(lead, summary)


@router.post(
    "/{lead_id}/ingest-website",
    response_model=WebsiteSnapshotIngestRead,
    status_code=status.HTTP_201_CREATED,
)
def ingest_website(
    lead_id: UUID,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> WebsiteSnapshotIngestRead:
    logger.info("Ingest website requested workspace_id=%s lead_id=%s", ctx.workspace_id, lead_id)
    lead = require_scoped_lead(db=db, lead_id=lead_id, workspace_id=ctx.workspace_id)

    if not lead.website_url or not lead.website_url.strip():
        logger.warning("Ingest website aborted workspace_id=%s lead_id=%s reason=missing_website_url", ctx.workspace_id, lead_id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lead website_url is missing")

    url = lead.website_url.strip()
    try:
        normalized_url = str(http_url_adapter.validate_python(url))
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid website_url") from exc

    try:
        ingestion = ingest_website_pages(normalized_url)
    except WebsiteFetchError as exc:
        logger.warning(
            "Ingest website failed workspace_id=%s lead_id=%s url=%s error=%s",
            ctx.workspace_id,
            lead_id,
            normalized_url,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Website fetch failed: {exc}",
        ) from exc

    db.execute(
        delete(WebsitePage).where(
            WebsitePage.lead_id == lead.id,
            WebsitePage.workspace_id == ctx.workspace_id,
        )
    )
    pages = [
        WebsitePage(
            workspace_id=ctx.workspace_id,
            lead_id=lead.id,
            url=page.url,
            page_type=page.page_type,
            raw_text=page.raw_text,
            extracted_emails=page.extracted_emails,
            extracted_phones=page.extracted_phones,
        )
        for page in ingestion.pages
    ]
    if pages:
        db.add_all(pages)

    raw_text = ingestion.combined_text or "[no readable text extracted]"
    logger.info(
        "Website text extracted lead_id=%s length=%s pages=%s emails=%s phones=%s",
        lead_id,
        len(raw_text),
        len(ingestion.pages),
        len(ingestion.unique_emails),
        len(ingestion.unique_phones),
    )

    snapshot = WebsiteSnapshot(
        workspace_id=ctx.workspace_id,
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
        pages_saved=len(ingestion.pages),
        emails_found=ingestion.unique_emails,
        phones_found=ingestion.unique_phones,
    )


@router.post(
    "/{lead_id}/run-agent1",
    response_model=Agent1RunResponse,
    status_code=status.HTTP_201_CREATED,
)
def run_agent1_for_lead(
    lead_id: UUID,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> Agent1RunResponse:
    logger.info("Agent1 run requested workspace_id=%s lead_id=%s", ctx.workspace_id, lead_id)
    lead = require_scoped_lead(db=db, lead_id=lead_id, workspace_id=ctx.workspace_id)

    latest_snapshot = db.scalar(
        select(WebsiteSnapshot)
        .where(WebsiteSnapshot.lead_id == lead_id, WebsiteSnapshot.workspace_id == ctx.workspace_id)
        .order_by(WebsiteSnapshot.fetched_at.desc(), WebsiteSnapshot.created_at.desc())
        .limit(1)
    )
    if latest_snapshot is None:
        logger.warning("Agent1 missing dependency workspace_id=%s lead_id=%s dependency=latest_snapshot", ctx.workspace_id, lead_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No website snapshots found for lead. Run /ingest-website first.",
        )

    openai_api_key, key_source = resolve_openai_api_key(db=db, workspace_id=ctx.workspace_id)
    logger.info(
        "Agent1 OpenAI key resolution workspace_id=%s lead_id=%s key_source=%s",
        ctx.workspace_id,
        lead_id,
        key_source,
    )

    logger.info("Agent1 run start lead_id=%s snapshot_id=%s", lead_id, latest_snapshot.id)
    try:
        agent1_output = run_agent1(latest_snapshot.raw_text, api_key=openai_api_key)
    except OpenAIConfigurationError as exc:
        logger.warning("Agent1 configuration error workspace_id=%s lead_id=%s error=%s", ctx.workspace_id, lead_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenAI API key is missing. Configure workspace settings at /api/v1/settings or set OPENAI_API_KEY.",
        ) from exc
    except OpenAIRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Agent1 failed: {exc}") from exc
    except OpenAIClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Agent1 failed: {exc}") from exc

    draft = EmailDraft(
        workspace_id=ctx.workspace_id,
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
def run_agent2_for_lead(
    lead_id: UUID,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> EmailDraft:
    logger.info("Agent2 run requested workspace_id=%s lead_id=%s", ctx.workspace_id, lead_id)
    lead = require_scoped_lead(db=db, lead_id=lead_id, workspace_id=ctx.workspace_id)

    latest_snapshot = db.scalar(
        select(WebsiteSnapshot)
        .where(WebsiteSnapshot.lead_id == lead_id, WebsiteSnapshot.workspace_id == ctx.workspace_id)
        .order_by(WebsiteSnapshot.fetched_at.desc(), WebsiteSnapshot.created_at.desc())
        .limit(1)
    )
    if latest_snapshot is None:
        logger.warning("Agent2 missing dependency workspace_id=%s lead_id=%s dependency=latest_snapshot", ctx.workspace_id, lead_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No website snapshots found for lead. Run /ingest-website and /run-agent1 first.",
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
        logger.warning("Agent2 missing dependency workspace_id=%s lead_id=%s dependency=agent1_output", ctx.workspace_id, lead_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No agent1 output found for lead. Run /run-agent1 first.",
        )
    logger.info(
        "Agent2 dependencies workspace_id=%s lead_id=%s snapshot_id=%s agent1_draft_id=%s",
        ctx.workspace_id,
        lead_id,
        latest_snapshot.id,
        latest_agent1_draft.id,
    )

    openai_api_key, key_source = resolve_openai_api_key(db=db, workspace_id=ctx.workspace_id)
    logger.info(
        "Agent2 OpenAI key resolution workspace_id=%s lead_id=%s key_source=%s",
        ctx.workspace_id,
        lead_id,
        key_source,
    )

    logger.info("Agent2 run start lead_id=%s snapshot_id=%s", lead_id, latest_snapshot.id)
    try:
        agent2_output = run_agent2(
            lead_name=lead.name,
            company=lead.company,
            website_url=lead.website_url,
            snapshot_text=latest_snapshot.raw_text,
            agent1_output=latest_agent1_draft.agent1_output,
            api_key=openai_api_key,
        )
    except OpenAIConfigurationError as exc:
        logger.warning("Agent2 configuration error workspace_id=%s lead_id=%s error=%s", ctx.workspace_id, lead_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenAI API key is missing. Configure workspace settings at /api/v1/settings or set OPENAI_API_KEY.",
        ) from exc
    except OpenAIRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Agent2 failed: {exc}") from exc
    except OpenAIClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Agent2 failed: {exc}") from exc

    draft = EmailDraft(
        workspace_id=ctx.workspace_id,
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
def get_latest_context(
    lead_id: UUID,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> LatestContextResponse:
    logger.info("Latest context requested workspace_id=%s lead_id=%s", ctx.workspace_id, lead_id)
    require_scoped_lead(db=db, lead_id=lead_id, workspace_id=ctx.workspace_id)

    latest_snapshot = db.scalar(
        select(WebsiteSnapshot)
        .where(WebsiteSnapshot.lead_id == lead_id, WebsiteSnapshot.workspace_id == ctx.workspace_id)
        .order_by(WebsiteSnapshot.fetched_at.desc(), WebsiteSnapshot.created_at.desc())
        .limit(1)
    )
    if latest_snapshot is None:
        logger.warning(
            "Latest context missing dependency workspace_id=%s lead_id=%s dependency=latest_snapshot",
            ctx.workspace_id,
            lead_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No website snapshots found for lead.",
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
    latest_agent3_draft = db.scalar(
        select(EmailDraft)
        .where(
            EmailDraft.lead_id == lead_id,
            EmailDraft.workspace_id == ctx.workspace_id,
            EmailDraft.agent3_verdict.is_not(None),
            EmailDraft.decision.in_(["send", "hold"]),
        )
        .order_by(EmailDraft.created_at.desc())
        .limit(1)
    )
    logger.info(
        "Latest context dependencies workspace_id=%s lead_id=%s snapshot=%s agent1_draft=%s agent3_draft=%s",
        ctx.workspace_id,
        lead_id,
        latest_snapshot.id,
        latest_agent1_draft.id if latest_agent1_draft else None,
        latest_agent3_draft.id if latest_agent3_draft else None,
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
        prepared_context=build_prepared_lead_context(db=db, workspace_id=ctx.workspace_id, lead_id=lead_id),
    )
