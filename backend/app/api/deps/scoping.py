from __future__ import annotations

import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lead import Lead

logger = logging.getLogger(__name__)


def get_scoped_lead(db: Session, lead_id: UUID, workspace_id: UUID) -> Lead | None:
    lead = db.scalar(select(Lead).where(Lead.id == lead_id, Lead.workspace_id == workspace_id).limit(1))
    logger.info(
        "Scoped lead lookup workspace_id=%s lead_id=%s found=%s",
        workspace_id,
        lead_id,
        bool(lead),
    )
    return lead


def require_scoped_lead(db: Session, lead_id: UUID, workspace_id: UUID) -> Lead:
    lead = get_scoped_lead(db=db, lead_id=lead_id, workspace_id=workspace_id)
    if lead is None:
        logger.warning("Scoped lead missing workspace_id=%s lead_id=%s", workspace_id, lead_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead
