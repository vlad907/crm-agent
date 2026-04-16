"""Partnership Discovery Service — orchestrates web search + website crawl + partnership fit analysis."""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.partner_candidate import PartnerCandidate
from app.models.workspace_profile import WorkspaceProfile
from app.services.partnership_agent import run_partnership_fit_agent
from app.services.website_ingestion import ingest_website_pages
from app.services.workspace_credentials import resolve_openai_api_key

logger = logging.getLogger(__name__)


def _get_workspace_profile(db: Session, workspace_id: UUID) -> dict[str, Any] | None:
    profile = db.get(WorkspaceProfile, workspace_id)
    if not profile:
        return None
    return {
        "business_name": profile.business_name,
        "business_description": profile.business_description,
        "service_specialties": profile.service_specialties,
        "service_area": profile.service_area,
    }


def discover_and_analyze(
    db: Session,
    workspace_id: UUID,
    *,
    company_name: str,
    website_url: str,
    discovery_intent: str,
) -> PartnerCandidate:
    profile_dict = _get_workspace_profile(db, workspace_id)

    ingestion = ingest_website_pages(website_url)
    combined_text = ingestion.combined_text
    if not combined_text.strip():
        combined_text = f"Company: {company_name}\nWebsite: {website_url}\n(No content could be extracted)"

    api_key, _src = resolve_openai_api_key(db, workspace_id)
    result = run_partnership_fit_agent(
        website_text=combined_text,
        discovery_intent=discovery_intent,
        workspace_profile=profile_dict,
        api_key=api_key,
    )

    contact_emails = result.get("contact_emails") or []
    if ingestion.unique_emails:
        for email in ingestion.unique_emails:
            if email not in contact_emails:
                contact_emails.append(email)

    candidate = PartnerCandidate(
        workspace_id=workspace_id,
        company_name=company_name,
        website=website_url,
        industry=result.get("industry"),
        partnership_type=result.get("partnership_type"),
        fit_score=result.get("fit_score"),
        extracted_signals={
            "company_summary": result.get("company_summary"),
            "reasons": result.get("reasons", []),
        },
        recommended_outreach_angle=result.get("recommended_outreach_angle"),
        contact_emails=contact_emails if contact_emails else None,
        contact_form_url=result.get("contact_form_url"),
        source="crawler",
        status="new",
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


def search_and_discover(
    db: Session,
    workspace_id: UUID,
    *,
    search_intent: str,
    max_results: int = 10,
    min_fit_score: float = 0.0,
) -> dict[str, Any]:
    """
    Automated pipeline: web search -> crawl each website -> run fit agent -> store candidates.
    Returns progress stats and the list of created candidates.
    """
    from app.services.partner_search_agent import search_for_partners

    api_key, _src = resolve_openai_api_key(db, workspace_id)
    profile_dict = _get_workspace_profile(db, workspace_id)

    companies = search_for_partners(
        search_intent=search_intent,
        api_key=api_key,
        max_results=max_results,
    )

    stats = {
        "total_found": len(companies),
        "analyzed": 0,
        "qualified": 0,
        "skipped_no_website": 0,
        "skipped_duplicate": 0,
        "errors": 0,
    }
    created: list[PartnerCandidate] = []

    for company in companies:
        website = company.get("website", "").strip()
        name = company.get("company_name", "Unknown").strip()

        if not website or not website.startswith(("http://", "https://")):
            stats["skipped_no_website"] += 1
            continue

        existing = db.scalar(
            select(PartnerCandidate).where(
                PartnerCandidate.workspace_id == workspace_id,
                PartnerCandidate.website == website,
            ).limit(1)
        )
        if existing:
            stats["skipped_duplicate"] += 1
            continue

        try:
            ingestion = ingest_website_pages(website)
            combined_text = ingestion.combined_text
            if not combined_text.strip():
                combined_text = (
                    f"Company: {name}\n"
                    f"Website: {website}\n"
                    f"Description: {company.get('description', '')}\n"
                    f"Relevance: {company.get('relevance_reason', '')}"
                )

            result = run_partnership_fit_agent(
                website_text=combined_text,
                discovery_intent=search_intent,
                workspace_profile=profile_dict,
                api_key=api_key,
            )
            stats["analyzed"] += 1

            fit_score = result.get("fit_score", 0)
            if fit_score < min_fit_score:
                continue

            contact_emails = result.get("contact_emails") or []
            if ingestion.unique_emails:
                for email in ingestion.unique_emails:
                    if email not in contact_emails:
                        contact_emails.append(email)

            candidate = PartnerCandidate(
                workspace_id=workspace_id,
                company_name=result.get("company_summary", name)[:255] if not name or name == "Unknown" else name,
                website=website,
                industry=result.get("industry"),
                location=None,
                partnership_type=result.get("partnership_type"),
                fit_score=fit_score,
                extracted_signals={
                    "company_summary": result.get("company_summary"),
                    "reasons": result.get("reasons", []),
                    "search_description": company.get("description"),
                    "search_relevance": company.get("relevance_reason"),
                },
                recommended_outreach_angle=result.get("recommended_outreach_angle"),
                contact_emails=contact_emails if contact_emails else None,
                contact_form_url=result.get("contact_form_url"),
                source="web_search",
                status="new",
            )
            db.add(candidate)
            db.flush()
            created.append(candidate)
            stats["qualified"] += 1

        except Exception:
            logger.exception("Failed to analyze partner: %s (%s)", name, website)
            stats["errors"] += 1

    db.commit()
    for c in created:
        db.refresh(c)

    return {"stats": stats, "candidates": created}
