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
from app.models.lead_status import (
    DEFAULT_LEAD_STATUS,
    LEAD_STATUS_APPROVED,
    LEAD_STATUS_ARCHIVED,
    LEAD_STATUS_CONVERTED,
    LEAD_STATUS_DISCOVERED,
    LEAD_STATUS_DRAFT_READY,
    LEAD_STATUS_DRAFTING,
    LEAD_STATUS_IMPORTED,
    LEAD_STATUS_NEEDS_REVIEW,
    LEAD_STATUS_REPLIED,
    LEAD_STATUS_RESEARCHED,
    LEAD_STATUS_RESEARCHING,
    LEAD_STATUS_SENT,
    LEAD_STATUS_SET,
    normalize_lead_status,
)
from app.models.website_page import WebsitePage
from app.models.website_snapshot import WebsiteSnapshot
from app.schemas.agent1 import Agent1RunResponse, LatestContextResponse, LatestContextSnapshot
from app.schemas.agent3 import FinalEmailRead
from app.schemas.email_draft import EmailDraftRead
from app.schemas.lead import (
    LeadBulkDeleteRequest,
    LeadBulkDeleteResponse,
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
    run_agent2_with_claude,
)
from app.services.scrape import WebsiteFetchError
from app.services.website_ingestion import ingest_website_pages
from app.services.workspace_credentials import resolve_email_generation_provider, resolve_openai_api_key
from app.services.workspace_ai_strategy import build_strategy_context, ensure_workspace_strategy_generated

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
    status_norm = normalize_lead_status(lead_status, fallback=DEFAULT_LEAD_STATUS)
    if status_norm in {LEAD_STATUS_ARCHIVED, LEAD_STATUS_CONVERTED, LEAD_STATUS_REPLIED, LEAD_STATUS_SENT}:
        return status_norm
    if final_decision == "send":
        return LEAD_STATUS_APPROVED
    if final_decision == "hold":
        return LEAD_STATUS_NEEDS_REVIEW
    if has_agent3_verdict:
        return status_norm if status_norm in {LEAD_STATUS_APPROVED, LEAD_STATUS_NEEDS_REVIEW} else LEAD_STATUS_DRAFT_READY
    if has_draft:
        return status_norm if status_norm == LEAD_STATUS_DRAFTING else LEAD_STATUS_DRAFT_READY
    if has_agent1_output or has_snapshot:
        return status_norm if status_norm == LEAD_STATUS_RESEARCHING else LEAD_STATUS_RESEARCHED
    return status_norm if status_norm in {LEAD_STATUS_IMPORTED, LEAD_STATUS_DISCOVERED} else DEFAULT_LEAD_STATUS


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
            if status_norm in {"send", LEAD_STATUS_APPROVED}:
                final_decision = "send"
            elif status_norm in {"hold", LEAD_STATUS_NEEDS_REVIEW}:
                final_decision = "hold"

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
    lead_data = payload.model_dump()
    lead_data["status"] = DEFAULT_LEAD_STATUS
    lead = Lead(workspace_id=ctx.workspace_id, **lead_data)
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
    exclude_status: str | None = Query(default=None, alias="exclude_status"),
    lead_type_filter: str | None = Query(default=None, alias="lead_type"),
    query: str | None = Query(default=None, alias="q", min_length=1),
) -> LeadListResponse:
    filters = [Lead.workspace_id == ctx.workspace_id]

    if status_filter:
        normalized_status = normalize_lead_status(status_filter, fallback=None)
        if normalized_status is None or normalized_status not in LEAD_STATUS_SET:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter '{status_filter}'.",
            )
        filters.append(Lead.status == normalized_status)
    if exclude_status:
        normalized_exclude = normalize_lead_status(exclude_status, fallback=None)
        if normalized_exclude and normalized_exclude in LEAD_STATUS_SET:
            filters.append(Lead.status != normalized_exclude)
    if lead_type_filter and lead_type_filter in ("local_business", "partnership"):
        filters.append(Lead.lead_type == lead_type_filter)
    if query:
        filters.append(Lead.company.ilike(f"%{query}%"))

    list_stmt = select(Lead).where(*filters).order_by(Lead.created_at.desc()).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(Lead).where(*filters)

    items = db.scalars(list_stmt).all()
    pipeline_map = _build_pipeline_summary_map(db, ctx.workspace_id, items)
    lead_items = [_with_pipeline_summary(item, pipeline_map.get(item.id)) for item in items]
    total = db.scalar(count_stmt) or 0
    return LeadListResponse(items=lead_items, total=total, offset=offset, limit=limit)


@router.post("/bulk-delete", response_model=LeadBulkDeleteResponse)
def bulk_delete_leads(
    payload: LeadBulkDeleteRequest,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> LeadBulkDeleteResponse:
    # Look up the leads being deleted *first* so we can release their source
    # prospects / partner candidates back to a re-importable state. Without
    # this, a lead that was originally converted from a prospect stays linked
    # in Prospect.import_status='imported' forever — meaning even after the
    # lead is gone, the user can't re-convert that prospect.
    leads_to_delete = db.scalars(
        select(Lead).where(
            Lead.workspace_id == ctx.workspace_id,
            Lead.id.in_(payload.lead_ids),
        )
    ).all()

    _release_source_records_for_deleted_leads(db, ctx.workspace_id, leads_to_delete)

    stmt = delete(Lead).where(
        Lead.workspace_id == ctx.workspace_id,
        Lead.id.in_(payload.lead_ids),
    )
    result = db.execute(stmt)
    db.commit()
    return LeadBulkDeleteResponse(deleted_count=result.rowcount or 0)


def _release_source_records_for_deleted_leads(
    db: Session,
    workspace_id: UUID,
    leads: list[Lead],
) -> None:
    """Reset `import_status` / `status` on prospects and partner candidates that
    were the source of the leads being deleted.

    There is no FK between Lead and Prospect/PartnerCandidate, so we match
    heuristically by normalized website_url first, then by lower-cased
    company name. This mirrors the dedupe logic used during conversion.
    """
    if not leads:
        return

    from app.models.partner_candidate import PartnerCandidate
    from app.models.prospect import Prospect
    from app.services.lead_import import normalize_website_url

    websites: set[str] = set()
    companies: set[str] = set()
    for lead in leads:
        normalized = normalize_website_url(lead.website_url) if lead.website_url else None
        if normalized:
            websites.add(normalized.lower())
        if lead.company:
            companies.add(lead.company.strip().lower())

    if websites:
        prospects_by_url = db.scalars(
            select(Prospect).where(
                Prospect.workspace_id == workspace_id,
                Prospect.import_status == "imported",
                func.lower(Prospect.website_url).in_(websites),
            )
        ).all()
        for prospect in prospects_by_url:
            prospect.import_status = "selected"

        partners_by_url = db.scalars(
            select(PartnerCandidate).where(
                PartnerCandidate.workspace_id == workspace_id,
                PartnerCandidate.status == "converted",
                func.lower(PartnerCandidate.website).in_(websites),
            )
        ).all()
        for partner in partners_by_url:
            partner.status = "discovered"

    if companies:
        prospects_by_company = db.scalars(
            select(Prospect).where(
                Prospect.workspace_id == workspace_id,
                Prospect.import_status == "imported",
                func.lower(Prospect.company_name).in_(companies),
            )
        ).all()
        for prospect in prospects_by_company:
            prospect.import_status = "selected"

        partners_by_company = db.scalars(
            select(PartnerCandidate).where(
                PartnerCandidate.workspace_id == workspace_id,
                PartnerCandidate.status == "converted",
                func.lower(PartnerCandidate.company_name).in_(companies),
            )
        ).all()
        for partner in partners_by_company:
            partner.status = "discovered"


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
    lead.status = LEAD_STATUS_RESEARCHING
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
    lead.status = LEAD_STATUS_RESEARCHED
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

    email_provider, email_api_key = resolve_email_generation_provider(db=db, workspace_id=ctx.workspace_id)
    if not email_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No AI API key configured. Add an Anthropic or OpenAI key in Settings.",
        )
    logger.info(
        "Agent2 provider resolution workspace_id=%s lead_id=%s provider=%s",
        ctx.workspace_id,
        lead_id,
        email_provider,
    )

    logger.info("Agent2 run start lead_id=%s snapshot_id=%s provider=%s", lead_id, latest_snapshot.id, email_provider)
    lead.status = LEAD_STATUS_DRAFTING
    db.commit()
    db.refresh(lead)

    openai_api_key_for_strategy, _ = resolve_openai_api_key(db=db, workspace_id=ctx.workspace_id)
    strategy = ensure_workspace_strategy_generated(
        db=db,
        workspace_id=ctx.workspace_id,
        api_key=openai_api_key_for_strategy,
    )
    strategy_context = build_strategy_context(strategy, lead_category=lead.industry)
    from app.services.sender_signature import get_sender_info, replace_placeholders
    sender_info = get_sender_info(db, ctx.workspace_id)

    try:
        if email_provider == "anthropic":
            agent2_output = run_agent2_with_claude(
                lead_name=lead.name,
                company=lead.company,
                website_url=lead.website_url,
                snapshot_text=latest_snapshot.raw_text,
                agent1_output=latest_agent1_draft.agent1_output,
                strategy_context=strategy_context,
                sender_info=sender_info,
                api_key=email_api_key,
                lead_type=lead.lead_type or "local_business",
                partnership_context=lead.partnership_context,
            )
        else:
            agent2_output = run_agent2(
                lead_name=lead.name,
                company=lead.company,
                website_url=lead.website_url,
                snapshot_text=latest_snapshot.raw_text,
                agent1_output=latest_agent1_draft.agent1_output,
                strategy_context=strategy_context,
                sender_info=sender_info,
                api_key=email_api_key,
                lead_type=lead.lead_type or "local_business",
                partnership_context=lead.partnership_context,
            )
    except OpenAIConfigurationError as exc:
        logger.warning("Agent2 configuration error workspace_id=%s lead_id=%s error=%s", ctx.workspace_id, lead_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI API key is missing or invalid. Configure workspace settings.",
        ) from exc
    except OpenAIRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Agent2 failed: {exc}") from exc
    except OpenAIClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Agent2 failed: {exc}") from exc

    final_subject = replace_placeholders(agent2_output["subject"], sender_info)
    final_body = replace_placeholders(agent2_output["email_body"], sender_info)

    draft = EmailDraft(
        workspace_id=ctx.workspace_id,
        lead_id=lead_id,
        subject=final_subject[:255],
        body=final_body,
        agent1_output=latest_agent1_draft.agent1_output,
        agent3_verdict={"used_signal": agent2_output["used_signal"], "source": "agent2"},
        decision="draft",
    )
    lead.status = LEAD_STATUS_DRAFT_READY
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
