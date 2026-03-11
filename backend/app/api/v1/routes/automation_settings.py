from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps.request_context import RequestContext, get_request_context
from app.db.session import get_db
from app.models.workspace_automation_setting import WorkspaceAutomationSetting
from app.schemas.automation_settings import (
    WorkspaceAutomationSettingsRead,
    WorkspaceAutomationSettingsUpdate,
)
from app.services.automation_policy import (
    AUTOMATION_MODE_AUTO_DRAFT,
    AUTOMATION_MODE_AUTO_SEND,
    get_or_create_automation_settings,
    normalize_automation_mode,
)

router = APIRouter(prefix="/automation-settings", tags=["Automation Settings"])


@router.get("", response_model=WorkspaceAutomationSettingsRead)
def get_automation_settings(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> WorkspaceAutomationSettingsRead:
    row = db.get(WorkspaceAutomationSetting, ctx.workspace_id)
    if row is None:
        return WorkspaceAutomationSettingsRead(
            workspace_id=ctx.workspace_id,
            automation_mode="manual",
            require_manual_review_before_send=True,
            auto_create_gmail_draft=False,
            auto_send_approved_emails=False,
            pause_pipeline=False,
            created_at=None,
            updated_at=None,
        )
    return WorkspaceAutomationSettingsRead.model_validate(row)


@router.patch("", response_model=WorkspaceAutomationSettingsRead)
def patch_automation_settings(
    payload: WorkspaceAutomationSettingsUpdate,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> WorkspaceAutomationSettingsRead:
    row = get_or_create_automation_settings(db, ctx.workspace_id)

    updates = payload.model_dump(exclude_unset=True)
    if "automation_mode" in updates:
        row.automation_mode = normalize_automation_mode(updates["automation_mode"])

    if "require_manual_review_before_send" in updates and updates["require_manual_review_before_send"] is not None:
        row.require_manual_review_before_send = bool(updates["require_manual_review_before_send"])
    if "auto_create_gmail_draft" in updates and updates["auto_create_gmail_draft"] is not None:
        row.auto_create_gmail_draft = bool(updates["auto_create_gmail_draft"])
    if "auto_send_approved_emails" in updates and updates["auto_send_approved_emails"] is not None:
        row.auto_send_approved_emails = bool(updates["auto_send_approved_emails"])
    if "pause_pipeline" in updates and updates["pause_pipeline"] is not None:
        row.pause_pipeline = bool(updates["pause_pipeline"])

    mode = normalize_automation_mode(row.automation_mode)
    if mode == AUTOMATION_MODE_AUTO_DRAFT:
        row.auto_create_gmail_draft = True
    elif mode == AUTOMATION_MODE_AUTO_SEND:
        row.auto_create_gmail_draft = True
        row.auto_send_approved_emails = True

    db.commit()
    db.refresh(row)
    return WorkspaceAutomationSettingsRead.model_validate(row)
