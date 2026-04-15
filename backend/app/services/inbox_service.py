"""Inbox service — syncs Gmail threads/messages, maps to entities, processes inbound."""
from __future__ import annotations

import base64
import logging
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.email_draft import EmailDraft
from app.models.email_message import EmailMessageRecord
from app.models.email_thread import EmailThread
from app.models.lead import Lead
from app.models.partner_candidate import PartnerCandidate
from app.services.gmail_service import get_active_token, GMAIL_API_ROOT, GmailApiError

logger = logging.getLogger(__name__)


def _gmail_api_get(
    *,
    db: Session,
    workspace_id: UUID,
    path: str,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    account, token = get_active_token(db, workspace_id)
    url = f"{GMAIL_API_ROOT}{path}"
    headers = {"Authorization": f"Bearer {token.access_token}"}
    with httpx.Client(timeout=25.0) as client:
        response = client.get(url, headers=headers, params=params or {})
    if response.status_code >= 400:
        detail = response.text.strip() or "unknown Gmail API error"
        raise GmailApiError(f"Gmail API GET failed: {detail}", status_code=502)
    return response.json()


def fetch_recent_threads(
    db: Session,
    workspace_id: UUID,
    *,
    max_results: int = 20,
    query: str = "in:inbox",
) -> list[dict[str, Any]]:
    data = _gmail_api_get(
        db=db,
        workspace_id=workspace_id,
        path="/threads",
        params={"maxResults": str(max_results), "q": query},
    )
    return data.get("threads", [])


def fetch_thread_detail(db: Session, workspace_id: UUID, gmail_thread_id: str) -> dict[str, Any]:
    return _gmail_api_get(
        db=db,
        workspace_id=workspace_id,
        path=f"/threads/{gmail_thread_id}",
        params={"format": "full"},
    )


def _extract_header(headers: list[dict[str, str]], name: str) -> str | None:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value")
    return None


def _decode_body(payload: dict[str, Any]) -> str:
    body_data = payload.get("body", {}).get("data")
    if body_data:
        try:
            return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
        except Exception:
            return ""

    parts = payload.get("parts", [])
    for part in parts:
        mime = part.get("mimeType", "")
        if mime == "text/plain":
            data = part.get("body", {}).get("data")
            if data:
                try:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                except Exception:
                    pass
    for part in parts:
        mime = part.get("mimeType", "")
        if mime == "text/html":
            data = part.get("body", {}).get("data")
            if data:
                try:
                    html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                    return re.sub(r"<[^>]+>", " ", html).strip()
                except Exception:
                    pass
    return ""


def _parse_timestamp(internal_date: str | None) -> datetime | None:
    if not internal_date:
        return None
    try:
        return datetime.fromtimestamp(int(internal_date) / 1000, tz=timezone.utc)
    except (ValueError, OSError):
        return None


def _find_related_entity(
    db: Session,
    workspace_id: UUID,
    sender: str | None,
    recipients_str: str | None,
) -> tuple[str | None, UUID | None]:
    emails_to_check = set()
    for val in [sender, recipients_str]:
        if val:
            found = re.findall(r"[\w.+-]+@[\w.-]+", val)
            emails_to_check.update(e.lower() for e in found)

    if not emails_to_check:
        return None, None

    for email in emails_to_check:
        lead = db.scalar(
            select(Lead).where(
                Lead.workspace_id == workspace_id,
                func.lower(Lead.email) == email,
            ).limit(1)
        )
        if lead:
            return "lead", lead.id

    for email in emails_to_check:
        partner = db.scalar(
            select(PartnerCandidate).where(
                PartnerCandidate.workspace_id == workspace_id,
                PartnerCandidate.contact_emails.any(email),
            ).limit(1)
        )
        if partner:
            return "partner_candidate", partner.id

    thread_with_entity = db.scalar(
        select(EmailThread).where(
            EmailThread.workspace_id == workspace_id,
            EmailThread.related_entity_id.is_not(None),
        ).order_by(EmailThread.updated_at.desc()).limit(1)
    )
    if thread_with_entity:
        gmail_thread = db.scalar(
            select(EmailDraft.gmail_thread_id).where(
                EmailDraft.workspace_id == workspace_id,
                EmailDraft.gmail_thread_id.is_not(None),
            ).limit(1)
        )
        if gmail_thread:
            return None, None

    return None, None


def sync_inbox(db: Session, workspace_id: UUID, *, max_results: int = 20) -> dict[str, int]:
    thread_refs = fetch_recent_threads(db, workspace_id, max_results=max_results)
    stats = {"threads_synced": 0, "messages_synced": 0, "new_inbound": 0}

    account, token = get_active_token(db, workspace_id)
    our_email = (account.display_name or account.external_account_id or "").lower()

    for ref in thread_refs:
        gmail_tid = ref.get("id")
        if not gmail_tid:
            continue

        try:
            detail = fetch_thread_detail(db, workspace_id, gmail_tid)
        except GmailApiError:
            logger.warning("Failed to fetch thread %s", gmail_tid)
            continue

        existing = db.scalar(
            select(EmailThread).where(
                EmailThread.workspace_id == workspace_id,
                EmailThread.gmail_thread_id == gmail_tid,
            )
        )
        if existing is None:
            existing = EmailThread(
                workspace_id=workspace_id,
                gmail_thread_id=gmail_tid,
                status="active",
            )
            db.add(existing)
            db.flush()

        messages = detail.get("messages", [])
        for msg in messages:
            msg_id = msg.get("id")
            if not msg_id:
                continue

            already = db.scalar(
                select(EmailMessageRecord.id).where(
                    EmailMessageRecord.gmail_message_id == msg_id,
                    EmailMessageRecord.thread_id == existing.id,
                ).limit(1)
            )
            if already:
                continue

            headers = msg.get("payload", {}).get("headers", [])
            sender = _extract_header(headers, "From")
            to = _extract_header(headers, "To")
            subject = _extract_header(headers, "Subject")
            body = _decode_body(msg.get("payload", {}))
            received_at = _parse_timestamp(msg.get("internalDate"))

            sender_email = ""
            if sender:
                found = re.findall(r"[\w.+-]+@[\w.-]+", sender)
                sender_email = found[0].lower() if found else ""

            direction = "outbound" if sender_email == our_email else "inbound"

            record = EmailMessageRecord(
                thread_id=existing.id,
                direction=direction,
                subject=subject,
                body=body[:50000] if body else None,
                sender=sender,
                recipients={"to": to} if to else None,
                received_at=received_at,
                gmail_message_id=msg_id,
            )
            db.add(record)
            stats["messages_synced"] += 1
            if direction == "inbound":
                stats["new_inbound"] += 1

        if messages:
            last_msg = messages[-1]
            last_date = _parse_timestamp(last_msg.get("internalDate"))
            if last_date:
                existing.last_message_at = last_date

        if not existing.related_entity_type:
            first_msg_headers = messages[0].get("payload", {}).get("headers", []) if messages else []
            sender = _extract_header(first_msg_headers, "From")
            to = _extract_header(first_msg_headers, "To")
            entity_type, entity_id = _find_related_entity(db, workspace_id, sender, to)
            if entity_type:
                existing.related_entity_type = entity_type
                existing.related_entity_id = entity_id

        stats["threads_synced"] += 1

    db.commit()
    return stats


def send_reply(
    db: Session,
    workspace_id: UUID,
    *,
    thread_id: UUID,
    subject: str,
    body: str,
) -> EmailMessageRecord:
    from app.services.gmail_service import _gmail_api_post, _build_raw_message

    thread = db.get(EmailThread, thread_id)
    if not thread or thread.workspace_id != workspace_id:
        raise ValueError("Thread not found")

    last_inbound = db.scalar(
        select(EmailMessageRecord).where(
            EmailMessageRecord.thread_id == thread_id,
            EmailMessageRecord.direction == "inbound",
        ).order_by(EmailMessageRecord.received_at.desc()).limit(1)
    )
    if not last_inbound or not last_inbound.sender:
        raise ValueError("No inbound message to reply to")

    to_emails = re.findall(r"[\w.+-]+@[\w.-]+", last_inbound.sender)
    if not to_emails:
        raise ValueError("Could not extract recipient email")

    raw = _build_raw_message(to_email=to_emails[0], subject=subject, body=body)
    payload = {
        "message": {"raw": raw, "threadId": thread.gmail_thread_id},
    }
    result = _gmail_api_post(db=db, workspace_id=workspace_id, path="/messages/send", payload=payload)

    record = EmailMessageRecord(
        thread_id=thread_id,
        direction="outbound",
        subject=subject,
        body=body,
        sender="me",
        recipients={"to": to_emails[0]},
        received_at=datetime.now(timezone.utc),
        gmail_message_id=result.get("id"),
    )
    db.add(record)
    thread.last_message_at = datetime.now(timezone.utc)
    db.commit()
    return record
