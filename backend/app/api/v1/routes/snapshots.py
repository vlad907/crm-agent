from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.lead import Lead
from app.models.website_snapshot import WebsiteSnapshot
from app.schemas.website_snapshot import WebsiteSnapshotCreate, WebsiteSnapshotRead

router = APIRouter(prefix="/leads/{lead_id}/snapshots", tags=["Website Snapshots"])


@router.post("", response_model=WebsiteSnapshotRead, status_code=status.HTTP_201_CREATED)
def create_snapshot(
    lead_id: UUID,
    payload: WebsiteSnapshotCreate,
    db: Session = Depends(get_db),
) -> WebsiteSnapshot:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    data = payload.model_dump(exclude_none=True)
    snapshot = WebsiteSnapshot(lead_id=lead_id, **data)
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


@router.get("", response_model=list[WebsiteSnapshotRead])
def list_snapshots(
    lead_id: UUID,
    db: Session = Depends(get_db),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[WebsiteSnapshot]:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    stmt = (
        select(WebsiteSnapshot)
        .where(WebsiteSnapshot.lead_id == lead_id)
        .order_by(WebsiteSnapshot.fetched_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return db.scalars(stmt).all()
