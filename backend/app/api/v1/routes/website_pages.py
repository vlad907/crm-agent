from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.request_context import RequestContext, get_request_context
from app.api.deps.scoping import require_scoped_lead
from app.db.session import get_db
from app.models.website_page import WebsitePage
from app.schemas.website_page import WebsitePageRead

router = APIRouter(prefix="/leads/{lead_id}/website-pages", tags=["Website Pages"])


@router.get("", response_model=list[WebsitePageRead])
def list_website_pages(
    lead_id: UUID,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[WebsitePage]:
    require_scoped_lead(db=db, lead_id=lead_id, workspace_id=ctx.workspace_id)
    stmt = (
        select(WebsitePage)
        .where(WebsitePage.lead_id == lead_id, WebsitePage.workspace_id == ctx.workspace_id)
        .order_by(WebsitePage.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return db.scalars(stmt).all()
