from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lead import Lead


def get_scoped_lead(db: Session, lead_id: UUID, workspace_id: UUID) -> Lead | None:
    return db.scalar(select(Lead).where(Lead.id == lead_id, Lead.workspace_id == workspace_id).limit(1))


def require_scoped_lead(db: Session, lead_id: UUID, workspace_id: UUID) -> Lead:
    lead = get_scoped_lead(db=db, lead_id=lead_id, workspace_id=workspace_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead
