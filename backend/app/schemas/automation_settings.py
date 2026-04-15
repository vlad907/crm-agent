from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

AutomationMode = Literal["manual", "semi_auto", "auto_draft", "auto_send"]


InboxReplyMode = Literal["suggest_only", "auto_draft", "manual_send_only"]


class WorkspaceAutomationSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workspace_id: UUID
    automation_mode: AutomationMode = "manual"
    require_manual_review_before_send: bool = True
    auto_create_gmail_draft: bool = False
    auto_send_approved_emails: bool = False
    pause_pipeline: bool = False
    inbox_reply_mode: InboxReplyMode = "suggest_only"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkspaceAutomationSettingsUpdate(BaseModel):
    automation_mode: AutomationMode | None = None
    require_manual_review_before_send: bool | None = None
    auto_create_gmail_draft: bool | None = None
    auto_send_approved_emails: bool | None = None
    pause_pipeline: bool | None = None
    inbox_reply_mode: InboxReplyMode | None = None
