from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.models.workspace_automation_setting import WorkspaceAutomationSetting

AUTOMATION_MODE_MANUAL = "manual"
AUTOMATION_MODE_SEMI_AUTO = "semi_auto"
AUTOMATION_MODE_AUTO_DRAFT = "auto_draft"
AUTOMATION_MODE_AUTO_SEND = "auto_send"

AUTOMATION_MODE_VALUES = {
    AUTOMATION_MODE_MANUAL,
    AUTOMATION_MODE_SEMI_AUTO,
    AUTOMATION_MODE_AUTO_DRAFT,
    AUTOMATION_MODE_AUTO_SEND,
}


@dataclass(frozen=True)
class AutomationPolicy:
    workspace_id: UUID
    automation_mode: str = AUTOMATION_MODE_MANUAL
    require_manual_review_before_send: bool = True
    auto_create_gmail_draft: bool = False
    auto_send_approved_emails: bool = False
    pause_pipeline: bool = False

    @property
    def allows_pipeline_progression(self) -> bool:
        return self.automation_mode in {
            AUTOMATION_MODE_SEMI_AUTO,
            AUTOMATION_MODE_AUTO_DRAFT,
            AUTOMATION_MODE_AUTO_SEND,
        }

    @property
    def effective_auto_create_gmail_draft(self) -> bool:
        return self.auto_create_gmail_draft or self.automation_mode in {
            AUTOMATION_MODE_AUTO_DRAFT,
            AUTOMATION_MODE_AUTO_SEND,
        }

    @property
    def effective_auto_send_approved_emails(self) -> bool:
        return self.auto_send_approved_emails or self.automation_mode == AUTOMATION_MODE_AUTO_SEND


def normalize_automation_mode(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in AUTOMATION_MODE_VALUES:
        return normalized
    return AUTOMATION_MODE_MANUAL


def get_or_create_automation_settings(db: Session, workspace_id: UUID) -> WorkspaceAutomationSetting:
    row = db.get(WorkspaceAutomationSetting, workspace_id)
    if row is None:
        row = WorkspaceAutomationSetting(workspace_id=workspace_id)
        db.add(row)
        db.flush()
    return row


def resolve_automation_policy(db: Session, workspace_id: UUID) -> AutomationPolicy:
    try:
        row = db.get(WorkspaceAutomationSetting, workspace_id)
    except (ProgrammingError, OperationalError):
        return AutomationPolicy(workspace_id=workspace_id)
    if row is None:
        return AutomationPolicy(workspace_id=workspace_id)
    return AutomationPolicy(
        workspace_id=workspace_id,
        automation_mode=normalize_automation_mode(row.automation_mode),
        require_manual_review_before_send=bool(row.require_manual_review_before_send),
        auto_create_gmail_draft=bool(row.auto_create_gmail_draft),
        auto_send_approved_emails=bool(row.auto_send_approved_emails),
        pause_pipeline=bool(row.pause_pipeline),
    )
