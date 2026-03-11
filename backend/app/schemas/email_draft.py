from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmailDraftBase(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    agent1_output: dict[str, Any] | None = None
    agent3_verdict: dict[str, Any] | None = None
    decision: str = Field(default="draft", min_length=1, max_length=20)


class EmailDraftCreate(EmailDraftBase):
    pass


class EmailDraftRead(EmailDraftBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    workspace_id: UUID
    review_status: str = "draft"
    review_notes: str | None = None
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    gmail_draft_id: str | None = None
    gmail_message_id: str | None = None
    gmail_thread_id: str | None = None
    sent_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DraftReviewUpdateResponse(BaseModel):
    draft_id: UUID
    lead_id: UUID
    review_status: str
    decision: str
    lead_status: str


class GmailDraftActionResponse(BaseModel):
    draft_id: UUID
    lead_id: UUID
    gmail_draft_id: str
    gmail_message_id: str | None = None
    gmail_thread_id: str | None = None
    review_status: str
    lead_status: str


class GmailSendResponse(BaseModel):
    draft_id: UUID
    lead_id: UUID
    gmail_message_id: str | None = None
    gmail_thread_id: str | None = None
    sent_at: datetime
    review_status: str
    lead_status: str


class DraftReviewQueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    draft_id: UUID
    lead_id: UUID
    lead_company: str
    lead_email: str | None = None
    lead_status: str
    subject: str
    body: str
    decision: str
    review_status: str
    issues: list[str] = Field(default_factory=list)
    final_email: dict[str, str] | None = None
    created_at: datetime
    updated_at: datetime


class DraftReviewQueueSummary(BaseModel):
    needs_review: int = 0
    approved: int = 0
    queued_to_send: int = 0
    sent: int = 0
