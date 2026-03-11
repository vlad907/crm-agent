from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps.request_context import RequestContext, get_request_context
from app.db.session import get_db
from app.models.email_draft import EmailDraft
from app.models.lead import Lead
from app.models.lead_status import LEAD_STATUS_APPROVED, LEAD_STATUS_NEEDS_REVIEW
from app.schemas.email_draft import (
    DraftReviewQueueItem,
    DraftReviewQueueSummary,
    DraftReviewUpdateResponse,
    GmailDraftActionResponse,
    GmailSendResponse,
)
from app.services.draft_delivery import (
    REVIEW_STATUS_APPROVED,
    REVIEW_STATUS_PENDING,
    REVIEW_STATUS_REJECTED,
    ensure_gmail_draft_for_email_draft,
    send_email_draft_via_gmail,
)
from app.services.gmail_service import GmailApiError

router = APIRouter(prefix="/drafts", tags=["Draft Actions"])


def _require_scoped_draft(db: Session, draft_id: UUID, workspace_id: UUID) -> tuple[EmailDraft, Lead]:
    row = db.execute(
        select(EmailDraft, Lead)
        .join(Lead, Lead.id == EmailDraft.lead_id)
        .where(
            EmailDraft.id == draft_id,
            EmailDraft.workspace_id == workspace_id,
            Lead.workspace_id == workspace_id,
        )
        .limit(1)
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return row[0], row[1]


@router.get("/review-queue", response_model=list[DraftReviewQueueItem])
def list_review_queue(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=200),
    include_approved: bool = Query(default=False),
) -> list[DraftReviewQueueItem]:
    statuses = [REVIEW_STATUS_PENDING]
    if include_approved:
        statuses.append(REVIEW_STATUS_APPROVED)
    rows = db.execute(
        select(EmailDraft, Lead)
        .join(Lead, Lead.id == EmailDraft.lead_id)
        .where(
            EmailDraft.workspace_id == ctx.workspace_id,
            Lead.workspace_id == ctx.workspace_id,
            EmailDraft.review_status.in_(statuses),
        )
        .order_by(EmailDraft.updated_at.asc(), EmailDraft.created_at.asc())
        .offset(offset)
        .limit(limit)
    ).all()

    items: list[DraftReviewQueueItem] = []
    for draft, lead in rows:
        verdict = draft.agent3_verdict if isinstance(draft.agent3_verdict, dict) else {}
        issues = verdict.get("issues") if isinstance(verdict, dict) else None
        final_email = verdict.get("final_email") if isinstance(verdict, dict) else None
        item = DraftReviewQueueItem(
            draft_id=draft.id,
            lead_id=lead.id,
            lead_company=lead.company,
            lead_email=lead.email,
            lead_status=lead.status,
            subject=draft.subject,
            body=draft.body,
            decision=draft.decision,
            review_status=draft.review_status,
            issues=[entry for entry in issues if isinstance(entry, str)] if isinstance(issues, list) else [],
            final_email=final_email if isinstance(final_email, dict) else None,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
        )
        items.append(item)
    return items


@router.get("/review-queue-summary", response_model=DraftReviewQueueSummary)
def review_queue_summary(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> DraftReviewQueueSummary:
    filters = [EmailDraft.workspace_id == ctx.workspace_id]
    needs_review = db.scalar(
        select(func.count())
        .select_from(EmailDraft)
        .where(
            *filters,
            EmailDraft.review_status == REVIEW_STATUS_PENDING,
        )
    ) or 0
    approved = db.scalar(
        select(func.count())
        .select_from(EmailDraft)
        .where(*filters, EmailDraft.review_status == REVIEW_STATUS_APPROVED)
    ) or 0
    queued_to_send = db.scalar(
        select(func.count())
        .select_from(EmailDraft)
        .where(
            *filters,
            EmailDraft.review_status == REVIEW_STATUS_APPROVED,
            EmailDraft.sent_at.is_(None),
        )
    ) or 0
    sent = db.scalar(
        select(func.count())
        .select_from(EmailDraft)
        .where(
            *filters,
            or_(EmailDraft.review_status == "sent", EmailDraft.sent_at.is_not(None)),
        )
    ) or 0
    return DraftReviewQueueSummary(
        needs_review=int(needs_review),
        approved=int(approved),
        queued_to_send=int(queued_to_send),
        sent=int(sent),
    )


@router.post("/{draft_id}/approve", response_model=DraftReviewUpdateResponse)
def approve_draft(
    draft_id: UUID,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> DraftReviewUpdateResponse:
    draft, lead = _require_scoped_draft(db, draft_id=draft_id, workspace_id=ctx.workspace_id)
    draft.review_status = REVIEW_STATUS_APPROVED
    draft.approved_at = datetime.now(timezone.utc)
    draft.rejected_at = None
    if draft.decision == "hold":
        draft.decision = "send"
    lead.status = LEAD_STATUS_APPROVED

    db.commit()
    return DraftReviewUpdateResponse(
        draft_id=draft.id,
        lead_id=lead.id,
        review_status=draft.review_status,
        decision=draft.decision,
        lead_status=lead.status,
    )


@router.post("/{draft_id}/reject", response_model=DraftReviewUpdateResponse)
def reject_draft(
    draft_id: UUID,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> DraftReviewUpdateResponse:
    draft, lead = _require_scoped_draft(db, draft_id=draft_id, workspace_id=ctx.workspace_id)
    draft.review_status = REVIEW_STATUS_REJECTED
    draft.rejected_at = datetime.now(timezone.utc)
    draft.decision = "hold"
    lead.status = LEAD_STATUS_NEEDS_REVIEW

    db.commit()
    return DraftReviewUpdateResponse(
        draft_id=draft.id,
        lead_id=lead.id,
        review_status=draft.review_status,
        decision=draft.decision,
        lead_status=lead.status,
    )


@router.post("/{draft_id}/create-gmail-draft", response_model=GmailDraftActionResponse)
def create_gmail_draft_for_draft(
    draft_id: UUID,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> GmailDraftActionResponse:
    draft, lead = _require_scoped_draft(db, draft_id=draft_id, workspace_id=ctx.workspace_id)
    try:
        ensure_gmail_draft_for_email_draft(db=db, draft=draft, lead=lead)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except GmailApiError as exc:
        db.commit()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    db.commit()
    return GmailDraftActionResponse(
        draft_id=draft.id,
        lead_id=lead.id,
        gmail_draft_id=draft.gmail_draft_id or "",
        gmail_message_id=draft.gmail_message_id,
        gmail_thread_id=draft.gmail_thread_id,
        review_status=draft.review_status,
        lead_status=lead.status,
    )


@router.post("/{draft_id}/send", response_model=GmailSendResponse)
def send_draft(
    draft_id: UUID,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> GmailSendResponse:
    draft, lead = _require_scoped_draft(db, draft_id=draft_id, workspace_id=ctx.workspace_id)
    try:
        send_email_draft_via_gmail(db=db, draft=draft, lead=lead)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except GmailApiError as exc:
        db.commit()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    db.commit()
    return GmailSendResponse(
        draft_id=draft.id,
        lead_id=lead.id,
        gmail_message_id=draft.gmail_message_id,
        gmail_thread_id=draft.gmail_thread_id,
        sent_at=draft.sent_at,
        review_status=draft.review_status,
        lead_status=lead.status,
    )
