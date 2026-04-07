from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.workspace_ai_strategy import WorkspaceAIStrategy
from app.models.website_page import WebsitePage
from app.models.workspace_profile import WorkspaceProfile
from app.services.workspace_ai_strategy import build_strategy_context


def build_prepared_lead_context(*, db: Session, workspace_id: UUID, lead_id: UUID) -> dict[str, object]:
    profile = db.get(WorkspaceProfile, workspace_id)
    workspace_ai_strategy = db.get(WorkspaceAIStrategy, workspace_id)
    pages = db.scalars(
        select(WebsitePage)
        .where(WebsitePage.workspace_id == workspace_id, WebsitePage.lead_id == lead_id)
        .order_by(WebsitePage.created_at.desc())
    ).all()

    pages_by_type: dict[str, list[dict[str, object]]] = {"home": [], "about": [], "contact": [], "other": []}
    emails: set[str] = set()
    phones: set[str] = set()

    for page in pages:
        page_type = page.page_type if page.page_type in pages_by_type else "other"
        pages_by_type[page_type].append(
            {
                "id": str(page.id),
                "url": page.url,
                "raw_text": page.raw_text,
                "created_at": page.created_at.isoformat(),
            }
        )
        emails.update(page.extracted_emails or [])
        phones.update(page.extracted_phones or [])

    return {
        "workspace_profile": {
            "business_name": profile.business_name if profile else None,
            "business_description": profile.business_description if profile else None,
            "industries_served": list(profile.industries_served) if profile else [],
            "service_specialties": list(profile.service_specialties) if profile else [],
            "service_area": profile.service_area if profile else None,
            "preferred_tone": profile.preferred_tone if profile else None,
            "outreach_style": profile.outreach_style if profile else None,
            "preferred_cta": profile.preferred_cta if profile else None,
            "do_not_mention": list(profile.do_not_mention) if profile else [],
        },
        "website_pages": pages_by_type,
        "contact_points": {
            "emails": sorted(emails),
            "phones": sorted(phones),
        },
        "workspace_ai_strategy": build_strategy_context(
            workspace_ai_strategy,
            lead_category=db.get(Lead, lead_id).industry if db.get(Lead, lead_id) else None,
        ),
    }
