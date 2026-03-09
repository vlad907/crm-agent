from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.request_context import RequestContext, get_request_context
from app.api.deps.scoping import require_scoped_lead
from app.db.session import get_db
from app.models.email_draft import EmailDraft
from app.schemas.email_draft import EmailDraftCreate, EmailDraftRead

router = APIRouter(prefix="/leads/{lead_id}/drafts", tags=["Email Drafts"])


@router.post("", response_model=EmailDraftRead, status_code=status.HTTP_201_CREATED)
def create_draft(
    lead_id: UUID,
    payload: EmailDraftCreate,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> EmailDraft:
    require_scoped_lead(db=db, lead_id=lead_id, workspace_id=ctx.workspace_id)

    data = payload.model_dump(exclude_none=True)
    draft = EmailDraft(lead_id=lead_id, workspace_id=ctx.workspace_id, **data)
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


@router.get("", response_model=list[EmailDraftRead])
def list_drafts(
    lead_id: UUID,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[EmailDraft]:
    require_scoped_lead(db=db, lead_id=lead_id, workspace_id=ctx.workspace_id)

    stmt = (
        select(EmailDraft)
        .where(EmailDraft.lead_id == lead_id, EmailDraft.workspace_id == ctx.workspace_id)
        .order_by(EmailDraft.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return db.scalars(stmt).all()
