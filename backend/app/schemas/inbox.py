from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

EmailDirection = Literal["inbound", "outbound"]

EmailClassification = Literal[
    "interested",
    "not_interested",
    "question",
    "objection",
    "pricing_request",
    "meeting_request",
    "referral",
    "unsubscribe",
    "unknown",
]


class EmailMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    thread_id: UUID
    direction: str
    subject: str | None
    body: str | None
    sender: str | None
    recipients: dict[str, Any] | None
    received_at: datetime | None
    classification: str | None
    suggested_response: dict[str, Any] | None
    gmail_message_id: str | None
    created_at: datetime


class EmailThreadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    gmail_thread_id: str
    related_entity_type: str | None
    related_entity_id: UUID | None
    last_message_at: datetime | None
    status: str
    next_action: str | None = None
    next_action_detail: dict[str, Any] | None = None
    reply_review_status: str | None = None
    created_at: datetime
    updated_at: datetime


class EmailThreadWithMessages(EmailThreadRead):
    messages: list[EmailMessageRead] = []


class EmailThreadListItem(EmailThreadRead):
    latest_message: EmailMessageRead | None = None
    classification: str | None = None
    related_entity_name: str | None = None


class EmailThreadListResponse(BaseModel):
    items: list[EmailThreadListItem]
    total: int


class InboxSyncResponse(BaseModel):
    threads_synced: int
    messages_synced: int
    new_inbound: int


class ReclassifyRequest(BaseModel):
    classification: EmailClassification


class SendReplyRequest(BaseModel):
    subject: str = Field(max_length=500)
    body: str = Field(min_length=1)


class InboxReviewQueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    thread_id: UUID
    gmail_thread_id: str
    related_entity_name: str | None = None
    classification: str | None = None
    next_action: str | None = None
    reply_review_status: str | None = None
    suggested_subject: str | None = None
    suggested_body: str | None = None
    last_message_at: datetime | None = None


class InboxReviewQueueResponse(BaseModel):
    items: list[InboxReviewQueueItem]
    total: int
