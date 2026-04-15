from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps.request_context import RequestContext, get_request_context
from app.db.session import get_db
from app.models.job import Job
from app.schemas.job import JobCreate, JobListResponse, JobRead, JobUpdate

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("", response_model=JobListResponse)
def list_jobs(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
):
    q = select(Job).where(Job.workspace_id == ctx.workspace_id)
    count_q = select(func.count()).select_from(Job).where(Job.workspace_id == ctx.workspace_id)

    if status_filter:
        q = q.where(Job.status == status_filter)
        count_q = count_q.where(Job.status == status_filter)

    total = db.scalar(count_q) or 0
    rows = db.scalars(q.order_by(Job.created_at.desc()).offset(offset).limit(limit)).all()
    return JobListResponse(items=[JobRead.model_validate(r) for r in rows], total=total)


@router.get("/{job_id}", response_model=JobRead)
def get_job(
    job_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    row = db.get(Job, job_id)
    if not row or row.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobRead.model_validate(row)


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    job = Job(
        workspace_id=ctx.workspace_id,
        title=payload.title,
        description=payload.description,
        job_type=payload.job_type,
        source_thread_id=payload.source_thread_id,
        source_entity_type=payload.source_entity_type,
        source_entity_id=payload.source_entity_id,
        scheduled_at=payload.scheduled_at,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return JobRead.model_validate(job)


@router.patch("/{job_id}", response_model=JobRead)
def update_job(
    job_id: UUID,
    payload: JobUpdate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    row = db.get(Job, job_id)
    if not row or row.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Job not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return JobRead.model_validate(row)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    row = db.get(Job, job_id)
    if not row or row.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(row)
    db.commit()
