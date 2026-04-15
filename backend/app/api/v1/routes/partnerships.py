from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps.request_context import RequestContext, get_request_context
from app.db.session import get_db
from app.models.partner_candidate import PartnerCandidate
from app.schemas.partner_candidate import (
    PartnerCandidateCreate,
    PartnerCandidateListResponse,
    PartnerCandidateRead,
    PartnerCandidateUpdate,
    PartnerDiscoveryRequest,
    PartnerSearchRequest,
    PartnerSearchProgress,
    PartnerSearchResponse,
)

router = APIRouter(prefix="/partnerships", tags=["Partnerships"])


@router.get("", response_model=PartnerCandidateListResponse)
def list_candidates(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
):
    q = select(PartnerCandidate).where(PartnerCandidate.workspace_id == ctx.workspace_id)
    count_q = select(func.count()).select_from(PartnerCandidate).where(PartnerCandidate.workspace_id == ctx.workspace_id)

    if status_filter:
        q = q.where(PartnerCandidate.status == status_filter)
        count_q = count_q.where(PartnerCandidate.status == status_filter)

    total = db.scalar(count_q) or 0
    rows = db.scalars(q.order_by(PartnerCandidate.created_at.desc()).offset(offset).limit(limit)).all()
    return PartnerCandidateListResponse(items=[PartnerCandidateRead.model_validate(r) for r in rows], total=total)


@router.get("/{candidate_id}", response_model=PartnerCandidateRead)
def get_candidate(
    candidate_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    row = db.get(PartnerCandidate, candidate_id)
    if not row or row.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Partner candidate not found")
    return PartnerCandidateRead.model_validate(row)


@router.post("", response_model=PartnerCandidateRead, status_code=status.HTTP_201_CREATED)
def create_candidate(
    payload: PartnerCandidateCreate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    candidate = PartnerCandidate(
        workspace_id=ctx.workspace_id,
        company_name=payload.company_name,
        website=payload.website,
        industry=payload.industry,
        location=payload.location,
        partnership_type=payload.partnership_type,
        source=payload.source,
        status=payload.status,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return PartnerCandidateRead.model_validate(candidate)


@router.patch("/{candidate_id}", response_model=PartnerCandidateRead)
def update_candidate(
    candidate_id: UUID,
    payload: PartnerCandidateUpdate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    row = db.get(PartnerCandidate, candidate_id)
    if not row or row.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Partner candidate not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return PartnerCandidateRead.model_validate(row)


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(
    candidate_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    row = db.get(PartnerCandidate, candidate_id)
    if not row or row.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Partner candidate not found")
    db.delete(row)
    db.commit()


@router.post("/search", response_model=PartnerSearchResponse)
def search_partners(
    payload: PartnerSearchRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Automated partner search: web search → crawl → AI analysis → store candidates."""
    from app.services.partnership_discovery import search_and_discover

    try:
        result = search_and_discover(
            db,
            ctx.workspace_id,
            search_intent=payload.discovery_intent,
            max_results=payload.max_results,
            min_fit_score=payload.min_fit_score,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return PartnerSearchResponse(
        progress=PartnerSearchProgress(**result["stats"]),
        candidates=[PartnerCandidateRead.model_validate(c) for c in result["candidates"]],
    )


@router.post("/discover", response_model=PartnerCandidateRead)
def discover_partner(
    payload: PartnerDiscoveryRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    from app.services.partnership_discovery import discover_and_analyze

    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Discovery query is required")

    website_url = ""
    company_name = "Unknown"
    parts = payload.query.strip().split()
    for part in parts:
        if part.startswith("http://") or part.startswith("https://"):
            website_url = part
            break

    if not website_url:
        raise HTTPException(
            status_code=400,
            detail="Please include a website URL in your query (e.g. 'find IT vendors https://example.com')",
        )

    query_without_url = payload.query.replace(website_url, "").strip()
    from urllib.parse import urlparse
    parsed = urlparse(website_url)
    company_name = parsed.hostname or "Unknown"
    if company_name.startswith("www."):
        company_name = company_name[4:]

    try:
        candidate = discover_and_analyze(
            db,
            ctx.workspace_id,
            company_name=company_name,
            website_url=website_url,
            discovery_intent=query_without_url or payload.query,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return PartnerCandidateRead.model_validate(candidate)


@router.post("/{candidate_id}/re-analyze", response_model=PartnerCandidateRead)
def re_analyze_candidate(
    candidate_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
    discovery_intent: str = Query(default="general partnership fit"),
):
    from app.services.partnership_discovery import discover_and_analyze

    row = db.get(PartnerCandidate, candidate_id)
    if not row or row.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Partner candidate not found")

    if not row.website:
        raise HTTPException(status_code=400, detail="Candidate has no website URL")

    try:
        updated = discover_and_analyze(
            db,
            ctx.workspace_id,
            company_name=row.company_name,
            website_url=row.website,
            discovery_intent=discovery_intent,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return PartnerCandidateRead.model_validate(updated)


@router.post("/{candidate_id}/generate-outreach", response_model=PartnerCandidateRead)
def generate_partner_outreach(
    candidate_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    from app.services.response_draft_agent import generate_response_draft
    from app.services.workspace_credentials import resolve_openai_api_key
    from app.models.workspace_profile import WorkspaceProfile

    row = db.get(PartnerCandidate, candidate_id)
    if not row or row.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Partner candidate not found")

    profile = db.get(WorkspaceProfile, ctx.workspace_id)
    profile_dict = None
    if profile:
        profile_dict = {
            "business_name": profile.business_name,
            "business_description": profile.business_description,
            "preferred_tone": profile.preferred_tone,
        }

    signals = row.extracted_signals or {}
    context_text = f"Company: {row.company_name}\n"
    if signals.get("company_summary"):
        context_text += f"Summary: {signals['company_summary']}\n"
    if row.partnership_type:
        context_text += f"Partnership type: {row.partnership_type}\n"
    if row.recommended_outreach_angle:
        context_text += f"Recommended angle: {row.recommended_outreach_angle}\n"

    api_key = resolve_openai_api_key(db, ctx.workspace_id)
    result = generate_response_draft(
        inbound_body=context_text,
        inbound_subject=f"Partnership opportunity with {row.company_name}",
        classification="interested",
        workspace_profile=profile_dict,
        api_key=api_key,
    )

    row.outreach_subject = result.get("subject", "")
    row.outreach_body = result.get("reply_body", "")
    row.outreach_status = "draft"
    db.commit()
    db.refresh(row)
    return PartnerCandidateRead.model_validate(row)


@router.post("/{candidate_id}/send-outreach", response_model=PartnerCandidateRead)
def send_partner_outreach(
    candidate_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    from app.services.gmail_service import create_gmail_draft

    row = db.get(PartnerCandidate, candidate_id)
    if not row or row.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Partner candidate not found")

    if not row.outreach_subject or not row.outreach_body:
        raise HTTPException(status_code=400, detail="Generate an outreach draft first")

    if not row.contact_emails:
        raise HTTPException(status_code=400, detail="No contact email available")

    create_gmail_draft(
        db=db,
        workspace_id=ctx.workspace_id,
        to_email=row.contact_emails[0],
        subject=row.outreach_subject,
        body=row.outreach_body,
    )
    row.outreach_status = "gmail_draft_created"
    row.status = "contacted"
    db.commit()
    db.refresh(row)
    return PartnerCandidateRead.model_validate(row)
