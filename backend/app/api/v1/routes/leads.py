from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.lead import Lead
from app.schemas.lead import LeadCreate, LeadListResponse, LeadRead, LeadUpdate

router = APIRouter(prefix="/leads", tags=["Leads"])


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def create_lead(payload: LeadCreate, db: Session = Depends(get_db)) -> Lead:
    lead = Lead(**payload.model_dump())
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


@router.get("", response_model=LeadListResponse)
def list_leads(
    db: Session = Depends(get_db),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    query: str | None = Query(default=None, alias="q", min_length=1),
) -> LeadListResponse:
    filters = []

    if status_filter:
        filters.append(Lead.status == status_filter)
    if query:
        filters.append(Lead.company.ilike(f"%{query}%"))

    list_stmt = select(Lead).order_by(Lead.created_at.desc()).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(Lead)

    if filters:
        list_stmt = list_stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    items = db.scalars(list_stmt).all()
    total = db.scalar(count_stmt) or 0
    return LeadListResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/{lead_id}", response_model=LeadRead)
def get_lead(lead_id: UUID, db: Session = Depends(get_db)) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


@router.patch("/{lead_id}", response_model=LeadRead)
def update_lead(lead_id: UUID, payload: LeadUpdate, db: Session = Depends(get_db)) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(lead, field, value)

    db.commit()
    db.refresh(lead)
    return lead

