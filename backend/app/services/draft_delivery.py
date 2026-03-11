from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.email_draft import EmailDraft
from app.models.lead import Lead
from app.models.lead_status import LEAD_STATUS_SENT
from app.models.workspace_setting import WorkspaceSetting
from app.services.gmail_service import create_gmail_draft, send_gmail_draft

REVIEW_STATUS_DRAFT = "draft"
REVIEW_STATUS_PENDING = "pending_review"
REVIEW_STATUS_APPROVED = "approved"
REVIEW_STATUS_REJECTED = "rejected"
REVIEW_STATUS_SENT = "sent"


def get_latest_agent3_draft(db: Session, *, workspace_id, lead_id) -> EmailDraft | None:
    return db.scalar(
        select(EmailDraft)
        .where(
            EmailDraft.workspace_id == workspace_id,
            EmailDraft.lead_id == lead_id,
            EmailDraft.agent3_verdict.is_not(None),
            EmailDraft.decision.in_(["send", "hold"]),
        )
        .order_by(EmailDraft.updated_at.desc(), EmailDraft.created_at.desc())
        .limit(1)
    )


def resolve_final_email(draft: EmailDraft) -> tuple[str, str]:
    verdict = draft.agent3_verdict if isinstance(draft.agent3_verdict, dict) else None
    if isinstance(verdict, dict):
        final_email = verdict.get("final_email")
        if isinstance(final_email, dict):
            subject = final_email.get("subject")
            body = final_email.get("email_body")
            if isinstance(subject, str) and subject.strip() and isinstance(body, str) and body.strip():
                return subject.strip(), body.strip()
    return draft.subject.strip(), draft.body.strip()


def _mark_workspace_gmail_connected(db: Session, workspace_id) -> None:
    workspace_settings = db.get(WorkspaceSetting, workspace_id)
    if workspace_settings is None:
        workspace_settings = WorkspaceSetting(workspace_id=workspace_id)
        db.add(workspace_settings)
    workspace_settings.gmail_connected = True


def ensure_gmail_draft_for_email_draft(*, db: Session, draft: EmailDraft, lead: Lead) -> EmailDraft:
    if not lead.email or not lead.email.strip():
        raise ValueError("Lead email is required before creating a Gmail draft.")

    if draft.gmail_draft_id and draft.gmail_draft_id.strip():
        return draft

    subject, body = resolve_final_email(draft)
    gmail_result = create_gmail_draft(
        db=db,
        workspace_id=draft.workspace_id,
        to_email=lead.email.strip(),
        subject=subject,
        body=body,
    )
    _apply_created_gmail_draft_payload(draft=draft, payload=gmail_result)
    _mark_workspace_gmail_connected(db, draft.workspace_id)
    return draft


def send_email_draft_via_gmail(*, db: Session, draft: EmailDraft, lead: Lead) -> EmailDraft:
    if draft.review_status == REVIEW_STATUS_REJECTED:
        raise ValueError("Draft is rejected and cannot be sent.")
    if not lead.email or not lead.email.strip():
        raise ValueError("Lead email is required before sending.")

    ensure_gmail_draft_for_email_draft(db=db, draft=draft, lead=lead)
    if not draft.gmail_draft_id:
        raise ValueError("Gmail draft creation did not return a draft id.")

    send_result = send_gmail_draft(
        db=db,
        workspace_id=draft.workspace_id,
        gmail_draft_id=draft.gmail_draft_id,
    )
    _apply_sent_message_payload(draft=draft, payload=send_result)
    draft.sent_at = datetime.now(timezone.utc)
    draft.review_status = REVIEW_STATUS_SENT
    draft.decision = "send"
    lead.status = LEAD_STATUS_SENT
    _mark_workspace_gmail_connected(db, draft.workspace_id)
    return draft


def _apply_created_gmail_draft_payload(*, draft: EmailDraft, payload: dict[str, Any]) -> None:
    draft_id = payload.get("id")
    if draft_id:
        draft.gmail_draft_id = str(draft_id)
    message = payload.get("message")
    if isinstance(message, dict):
        if message.get("id"):
            draft.gmail_message_id = str(message.get("id"))
        if message.get("threadId"):
            draft.gmail_thread_id = str(message.get("threadId"))


def _apply_sent_message_payload(*, draft: EmailDraft, payload: dict[str, Any]) -> None:
    if payload.get("id"):
        draft.gmail_message_id = str(payload.get("id"))
    if payload.get("threadId"):
        draft.gmail_thread_id = str(payload.get("threadId"))
