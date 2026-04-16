from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps.request_context import RequestContext, get_request_context
from app.db.session import get_db
from app.models.email_message import EmailMessageRecord
from app.models.email_thread import EmailThread
from app.models.lead import Lead
from app.models.partner_candidate import PartnerCandidate
from app.schemas.inbox import (
    EmailMessageRead,
    EmailThreadListItem,
    EmailThreadListResponse,
    EmailThreadWithMessages,
    InboxReviewQueueItem,
    InboxReviewQueueResponse,
    InboxSyncResponse,
    ReclassifyRequest,
    SendReplyRequest,
)

router = APIRouter(prefix="/inbox", tags=["Inbox"])

NEXT_ACTION_MAP = {
    "meeting_request": "schedule_meeting",
    "pricing_request": "provide_quote",
    "interested": "follow_up",
    "question": "follow_up",
}


def _resolve_entity_name(db: Session, entity_type: str | None, entity_id: UUID | None) -> str | None:
    if not entity_type or not entity_id:
        return None
    if entity_type == "lead":
        lead = db.get(Lead, entity_id)
        return lead.company if lead else None
    if entity_type == "partner_candidate":
        partner = db.get(PartnerCandidate, entity_id)
        return partner.company_name if partner else None
    return None


@router.post("/sync", response_model=InboxSyncResponse)
def sync_inbox(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
    max_results: int = Query(default=20, ge=1, le=100),
):
    from app.services.inbox_service import sync_inbox as do_sync

    try:
        stats = do_sync(db, ctx.workspace_id, max_results=max_results)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return InboxSyncResponse(**stats)


@router.get("/threads", response_model=EmailThreadListResponse)
def list_threads(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    classification: str | None = Query(default=None),
    needs_reply: bool | None = Query(default=None),
):
    q = select(EmailThread).where(EmailThread.workspace_id == ctx.workspace_id)
    count_q = select(func.count()).select_from(EmailThread).where(EmailThread.workspace_id == ctx.workspace_id)

    if status_filter:
        q = q.where(EmailThread.status == status_filter)
        count_q = count_q.where(EmailThread.status == status_filter)

    total = db.scalar(count_q) or 0
    threads = db.scalars(q.order_by(EmailThread.last_message_at.desc().nullslast()).offset(offset).limit(limit)).all()

    items: list[EmailThreadListItem] = []
    for thread in threads:
        latest_msg = db.scalar(
            select(EmailMessageRecord)
            .where(EmailMessageRecord.thread_id == thread.id)
            .order_by(EmailMessageRecord.received_at.desc().nullslast())
            .limit(1)
        )
        latest_inbound = db.scalar(
            select(EmailMessageRecord)
            .where(
                EmailMessageRecord.thread_id == thread.id,
                EmailMessageRecord.direction == "inbound",
            )
            .order_by(EmailMessageRecord.received_at.desc().nullslast())
            .limit(1)
        )
        msg_classification = latest_inbound.classification if latest_inbound else None

        if classification and msg_classification != classification:
            continue
        if needs_reply and (not latest_inbound or latest_msg == latest_inbound):
            pass
        elif needs_reply is False:
            continue

        entity_name = _resolve_entity_name(db, thread.related_entity_type, thread.related_entity_id)

        items.append(EmailThreadListItem(
            **EmailThreadListItem.model_validate(thread).model_dump(
                exclude={"latest_message", "classification", "related_entity_name"}
            ),
            latest_message=EmailMessageRead.model_validate(latest_msg) if latest_msg else None,
            classification=msg_classification,
            related_entity_name=entity_name,
        ))

    return EmailThreadListResponse(items=items, total=total)


@router.get("/threads/{thread_id}", response_model=EmailThreadWithMessages)
def get_thread(
    thread_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    thread = db.get(EmailThread, thread_id)
    if not thread or thread.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Thread not found")

    messages = db.scalars(
        select(EmailMessageRecord)
        .where(EmailMessageRecord.thread_id == thread_id)
        .order_by(EmailMessageRecord.received_at.asc().nullslast())
    ).all()

    return EmailThreadWithMessages(
        **EmailThreadWithMessages.model_validate(thread).model_dump(exclude={"messages"}),
        messages=[EmailMessageRead.model_validate(m) for m in messages],
    )


@router.post("/threads/{thread_id}/classify")
def classify_thread(
    thread_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    from app.services.email_classifier_agent import classify_email
    from app.services.workspace_credentials import resolve_openai_api_key

    thread = db.get(EmailThread, thread_id)
    if not thread or thread.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Thread not found")

    messages = db.scalars(
        select(EmailMessageRecord)
        .where(EmailMessageRecord.thread_id == thread_id)
        .order_by(EmailMessageRecord.received_at.asc().nullslast())
    ).all()

    inbound_msgs = [m for m in messages if m.direction == "inbound"]
    if not inbound_msgs:
        raise HTTPException(status_code=400, detail="No inbound messages to classify")

    latest = inbound_msgs[-1]
    thread_context = "\n---\n".join(
        f"[{m.direction}] {m.subject or ''}\n{(m.body or '')[:1000]}"
        for m in messages[:-1]
    ) if len(messages) > 1 else None

    api_key, _src = resolve_openai_api_key(db, ctx.workspace_id)
    result = classify_email(
        email_body=latest.body or "",
        email_subject=latest.subject,
        thread_context=thread_context,
        api_key=api_key,
    )

    latest.classification = result.get("classification", "unknown")
    cls = latest.classification

    if result.get("meeting_intent"):
        thread.status = "meeting_requested"
    if cls in NEXT_ACTION_MAP:
        thread.next_action = NEXT_ACTION_MAP[cls]

    thread.reply_review_status = "needs_review"
    db.commit()

    return {"classification": result, "message_id": str(latest.id)}


@router.post("/threads/{thread_id}/suggest-reply")
def suggest_reply(
    thread_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    from app.services.response_draft_agent import generate_response_draft
    from app.services.workspace_credentials import resolve_openai_api_key
    from app.models.workspace_profile import WorkspaceProfile
    from app.models.workspace_ai_strategy import WorkspaceAIStrategy
    from app.services.sender_signature import get_sender_info, replace_placeholders

    thread = db.get(EmailThread, thread_id)
    if not thread or thread.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Thread not found")

    messages = db.scalars(
        select(EmailMessageRecord)
        .where(EmailMessageRecord.thread_id == thread_id)
        .order_by(EmailMessageRecord.received_at.asc().nullslast())
    ).all()

    inbound_msgs = [m for m in messages if m.direction == "inbound"]
    if not inbound_msgs:
        raise HTTPException(status_code=400, detail="No inbound messages to reply to")

    latest = inbound_msgs[-1]
    thread_history = "\n---\n".join(
        f"[{m.direction}] {m.subject or ''}\n{(m.body or '')[:1000]}"
        for m in messages[:-1]
    ) if len(messages) > 1 else None

    profile = db.get(WorkspaceProfile, ctx.workspace_id)
    profile_dict = None
    if profile:
        profile_dict = {
            "business_name": profile.business_name,
            "business_description": profile.business_description,
            "preferred_tone": profile.preferred_tone,
        }

    sender_info = get_sender_info(db, ctx.workspace_id)

    strategy = db.get(WorkspaceAIStrategy, ctx.workspace_id)
    strategy_dict = None
    if strategy and strategy.generated_strategy:
        strategy_dict = {"generated_strategy": strategy.generated_strategy}

    api_key, _src = resolve_openai_api_key(db, ctx.workspace_id)
    result = generate_response_draft(
        inbound_body=latest.body or "",
        inbound_subject=latest.subject,
        thread_history=thread_history,
        classification=latest.classification,
        workspace_profile=profile_dict,
        ai_strategy=strategy_dict,
        sender_info=sender_info,
        api_key=api_key,
    )

    if result.get("subject"):
        result["subject"] = replace_placeholders(result["subject"], sender_info)
    if result.get("reply_body"):
        result["reply_body"] = replace_placeholders(result["reply_body"], sender_info)

    latest.suggested_response = result
    thread.reply_review_status = "suggested"
    db.commit()

    return {"suggested_response": result, "message_id": str(latest.id)}


@router.post("/threads/{thread_id}/approve-reply")
def approve_reply(
    thread_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    thread = db.get(EmailThread, thread_id)
    if not thread or thread.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread.reply_review_status = "approved"
    db.commit()
    return {"status": "approved"}


@router.post("/threads/{thread_id}/reject-reply")
def reject_reply(
    thread_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    thread = db.get(EmailThread, thread_id)
    if not thread or thread.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread.reply_review_status = "rejected"
    db.commit()
    return {"status": "rejected"}


@router.post("/threads/{thread_id}/create-gmail-draft")
def create_gmail_draft_for_thread(
    thread_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    from app.services.gmail_service import create_gmail_draft
    import re as _re

    thread = db.get(EmailThread, thread_id)
    if not thread or thread.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Thread not found")

    latest_inbound = db.scalar(
        select(EmailMessageRecord)
        .where(
            EmailMessageRecord.thread_id == thread_id,
            EmailMessageRecord.direction == "inbound",
        )
        .order_by(EmailMessageRecord.received_at.desc().nullslast())
        .limit(1)
    )
    if not latest_inbound or not latest_inbound.suggested_response:
        raise HTTPException(status_code=400, detail="No suggested response to draft")

    to_emails = _re.findall(r"[\w.+-]+@[\w.-]+", latest_inbound.sender or "")
    if not to_emails:
        raise HTTPException(status_code=400, detail="Cannot determine recipient email")

    suggested = latest_inbound.suggested_response
    result = create_gmail_draft(
        db=db,
        workspace_id=ctx.workspace_id,
        to_email=to_emails[0],
        subject=suggested.get("subject", ""),
        body=suggested.get("reply_body", ""),
    )
    thread.reply_review_status = "gmail_draft_created"
    db.commit()

    return {"gmail_draft_id": result.get("id"), "status": "draft_created"}


@router.get("/review-queue", response_model=InboxReviewQueueResponse)
def get_review_queue(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
):
    threads = db.scalars(
        select(EmailThread)
        .where(
            EmailThread.workspace_id == ctx.workspace_id,
            EmailThread.reply_review_status.in_(["needs_review", "suggested"]),
        )
        .order_by(EmailThread.last_message_at.desc().nullslast())
        .limit(limit)
    ).all()

    items: list[InboxReviewQueueItem] = []
    for thread in threads:
        latest_inbound = db.scalar(
            select(EmailMessageRecord)
            .where(
                EmailMessageRecord.thread_id == thread.id,
                EmailMessageRecord.direction == "inbound",
            )
            .order_by(EmailMessageRecord.received_at.desc().nullslast())
            .limit(1)
        )
        suggested = latest_inbound.suggested_response if latest_inbound else None
        entity_name = _resolve_entity_name(db, thread.related_entity_type, thread.related_entity_id)

        items.append(InboxReviewQueueItem(
            thread_id=thread.id,
            gmail_thread_id=thread.gmail_thread_id,
            related_entity_name=entity_name,
            classification=latest_inbound.classification if latest_inbound else None,
            next_action=thread.next_action,
            reply_review_status=thread.reply_review_status,
            suggested_subject=suggested.get("subject") if isinstance(suggested, dict) else None,
            suggested_body=suggested.get("reply_body") if isinstance(suggested, dict) else None,
            last_message_at=thread.last_message_at,
        ))

    return InboxReviewQueueResponse(items=items, total=len(items))


@router.post("/messages/{message_id}/reclassify", response_model=EmailMessageRead)
def reclassify_message(
    message_id: UUID,
    payload: ReclassifyRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    msg = db.get(EmailMessageRecord, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    thread = db.get(EmailThread, msg.thread_id)
    if not thread or thread.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Message not found")

    msg.classification = payload.classification
    cls = payload.classification
    if cls == "meeting_request":
        thread.status = "meeting_requested"
    if cls in NEXT_ACTION_MAP:
        thread.next_action = NEXT_ACTION_MAP[cls]
    db.commit()
    db.refresh(msg)
    return EmailMessageRead.model_validate(msg)


@router.post("/threads/{thread_id}/send-reply", response_model=EmailMessageRead)
def send_thread_reply(
    thread_id: UUID,
    payload: SendReplyRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    from app.services.inbox_service import send_reply

    try:
        record = send_reply(
            db,
            ctx.workspace_id,
            thread_id=thread_id,
            subject=payload.subject,
            body=payload.body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    thread = db.get(EmailThread, thread_id)
    if thread:
        thread.reply_review_status = "sent"
        thread.next_action = None
        db.commit()

    return EmailMessageRead.model_validate(record)


@router.patch("/threads/{thread_id}/status")
def update_thread_status(
    thread_id: UUID,
    new_status: str = Query(...),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    thread = db.get(EmailThread, thread_id)
    if not thread or thread.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Thread not found")

    thread.status = new_status
    db.commit()
    return {"status": new_status}
