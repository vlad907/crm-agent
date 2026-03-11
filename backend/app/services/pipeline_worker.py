from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.api.deps.request_context import RequestContext
from app.api.v1.routes.leads import ingest_website, run_agent1_for_lead, run_agent2_for_lead
from app.api.v1.routes.verifier import run_agent3_for_lead
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.lead import Lead
from app.models.lead_status import (
    LEAD_STATUS_APPROVED,
    LEAD_STATUS_DRAFT_READY,
    LEAD_STATUS_IMPORTED,
    LEAD_STATUS_NEEDS_REVIEW,
    LEAD_STATUS_RESEARCHED,
    LEAD_STATUS_RESEARCHING,
    normalize_lead_status,
)
from app.models.user import User
from app.services.automation_policy import resolve_automation_policy
from app.services.draft_delivery import (
    REVIEW_STATUS_REJECTED,
    ensure_gmail_draft_for_email_draft,
    get_latest_agent3_draft,
    send_email_draft_via_gmail,
)
from app.services.gmail_service import GmailApiError, set_gmail_integration_error

logger = logging.getLogger(__name__)

WORKER_STATUSES = (
    LEAD_STATUS_IMPORTED,
    LEAD_STATUS_RESEARCHING,
    LEAD_STATUS_RESEARCHED,
    LEAD_STATUS_DRAFT_READY,
    LEAD_STATUS_APPROVED,
)


class LeadPipelineWorker:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._cycle_lock = asyncio.Lock()

    def start(self) -> None:
        if not settings.pipeline_worker_enabled:
            logger.info("Lead pipeline worker is disabled by configuration")
            return
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="lead-pipeline-worker")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _run_loop(self) -> None:
        logger.info(
            "Lead pipeline worker started interval=%ss batch_size=%s",
            settings.pipeline_worker_interval_seconds,
            settings.pipeline_worker_batch_size,
        )
        while not self._stop_event.is_set():
            try:
                await self.run_once()
            except Exception:
                logger.exception("Lead pipeline worker cycle failed")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=float(settings.pipeline_worker_interval_seconds),
                )
            except asyncio.TimeoutError:
                continue
        logger.info("Lead pipeline worker stopped")

    async def run_once(self) -> None:
        if self._cycle_lock.locked():
            return
        async with self._cycle_lock:
            await asyncio.to_thread(self._run_once_sync)

    def _run_once_sync(self) -> None:
        with SessionLocal() as db:
            candidate_ids = db.scalars(
                select(Lead.id)
                .where(Lead.status.in_(WORKER_STATUSES))
                .order_by(Lead.updated_at.asc(), Lead.created_at.asc())
                .limit(settings.pipeline_worker_batch_size)
            ).all()

        if not candidate_ids:
            return

        for lead_id in candidate_ids:
            self._process_lead(lead_id)

    def _process_lead(self, lead_id: UUID) -> None:
        with SessionLocal() as db:
            lead = db.get(Lead, lead_id)
            if lead is None:
                return

            lead_status = normalize_lead_status(lead.status, fallback=None)
            if lead_status not in WORKER_STATUSES:
                return

            policy = resolve_automation_policy(db, lead.workspace_id)
            if policy.pause_pipeline:
                logger.debug(
                    "Pipeline worker skipped lead_id=%s workspace_id=%s reason=pipeline_paused",
                    lead.id,
                    lead.workspace_id,
                )
                return

            user_id = self._resolve_workspace_user_id(db, lead.workspace_id)
            if user_id is None:
                logger.warning(
                    "Pipeline worker skipped lead_id=%s workspace_id=%s reason=no_workspace_user",
                    lead.id,
                    lead.workspace_id,
                )
                return

            ctx = RequestContext(workspace_id=lead.workspace_id, user_id=user_id)

            try:
                if lead_status == LEAD_STATUS_IMPORTED:
                    if not policy.allows_pipeline_progression:
                        logger.debug(
                            "Pipeline worker skipped lead_id=%s workspace_id=%s status=%s mode=%s",
                            lead.id,
                            lead.workspace_id,
                            lead_status,
                            policy.automation_mode,
                        )
                        return
                    if not lead.website_url or not lead.website_url.strip():
                        lead.status = LEAD_STATUS_NEEDS_REVIEW
                        db.commit()
                        logger.warning(
                            "Pipeline worker marked needs_review lead_id=%s workspace_id=%s reason=missing_website_url",
                            lead.id,
                            lead.workspace_id,
                        )
                        return
                    logger.info("Pipeline worker step=ingest lead_id=%s workspace_id=%s", lead.id, lead.workspace_id)
                    ingest_website(lead_id=lead.id, db=db, ctx=ctx)
                    logger.info("Pipeline worker step=ingest_done lead_id=%s workspace_id=%s", lead.id, lead.workspace_id)
                    return

                if lead_status == LEAD_STATUS_RESEARCHING:
                    if not policy.allows_pipeline_progression:
                        return
                    logger.info("Pipeline worker step=agent1 lead_id=%s workspace_id=%s", lead.id, lead.workspace_id)
                    run_agent1_for_lead(lead_id=lead.id, db=db, ctx=ctx)
                    logger.info("Pipeline worker step=agent1_done lead_id=%s workspace_id=%s", lead.id, lead.workspace_id)
                    return

                if lead_status == LEAD_STATUS_RESEARCHED:
                    if not policy.allows_pipeline_progression:
                        return
                    logger.info("Pipeline worker step=agent2 lead_id=%s workspace_id=%s", lead.id, lead.workspace_id)
                    run_agent2_for_lead(lead_id=lead.id, db=db, ctx=ctx)
                    logger.info("Pipeline worker step=agent2_done lead_id=%s workspace_id=%s", lead.id, lead.workspace_id)
                    return

                if lead_status == LEAD_STATUS_DRAFT_READY:
                    if not policy.allows_pipeline_progression:
                        return
                    logger.info("Pipeline worker step=agent3 lead_id=%s workspace_id=%s", lead.id, lead.workspace_id)
                    result = run_agent3_for_lead(lead_id=lead.id, db=db, ctx=ctx)
                    logger.info(
                        "Pipeline worker step=agent3_done lead_id=%s workspace_id=%s decision=%s",
                        lead.id,
                        lead.workspace_id,
                        result.decision,
                    )
                    db.refresh(lead)
                    self._maybe_process_approved_delivery(db=db, lead=lead)
                    return

                if lead_status == LEAD_STATUS_APPROVED:
                    self._maybe_process_approved_delivery(db=db, lead=lead)
                    return
            except HTTPException as exc:
                db.rollback()
                if self._should_mark_needs_review(lead_status=lead_status, exc=exc):
                    lead.status = LEAD_STATUS_NEEDS_REVIEW
                    db.commit()
                    logger.warning(
                        "Pipeline worker marked needs_review lead_id=%s workspace_id=%s from_status=%s reason=http_%s",
                        lead.id,
                        lead.workspace_id,
                        lead_status,
                        exc.status_code,
                    )
                logger.warning(
                    "Pipeline worker step_failed lead_id=%s workspace_id=%s status=%s http_status=%s detail=%s",
                    lead.id,
                    lead.workspace_id,
                    lead_status,
                    exc.status_code,
                    exc.detail,
                )
            except GmailApiError as exc:
                db.rollback()
                set_gmail_integration_error(
                    db,
                    workspace_id=lead.workspace_id,
                    error_message=str(exc),
                )
                db.commit()
                logger.warning(
                    "Pipeline worker delivery_failed lead_id=%s workspace_id=%s status=%s detail=%s",
                    lead.id,
                    lead.workspace_id,
                    lead_status,
                    exc,
                )
            except ValueError as exc:
                db.rollback()
                logger.warning(
                    "Pipeline worker delivery_skipped lead_id=%s workspace_id=%s status=%s detail=%s",
                    lead.id,
                    lead.workspace_id,
                    lead_status,
                    exc,
                )
            except Exception:
                db.rollback()
                logger.exception(
                    "Pipeline worker unexpected failure lead_id=%s workspace_id=%s status=%s",
                    lead.id,
                    lead.workspace_id,
                    lead_status,
                )

    def _maybe_process_approved_delivery(self, *, db, lead: Lead) -> None:
        policy = resolve_automation_policy(db, lead.workspace_id)
        if lead.status != LEAD_STATUS_APPROVED:
            return
        if policy.pause_pipeline:
            return
        if not policy.effective_auto_create_gmail_draft and not policy.effective_auto_send_approved_emails:
            return

        latest_draft = get_latest_agent3_draft(
            db,
            workspace_id=lead.workspace_id,
            lead_id=lead.id,
        )
        if latest_draft is None:
            logger.warning(
                "Pipeline worker approved lead missing draft lead_id=%s workspace_id=%s",
                lead.id,
                lead.workspace_id,
            )
            return
        if latest_draft.review_status == REVIEW_STATUS_REJECTED:
            return

        if policy.effective_auto_create_gmail_draft:
            ensure_gmail_draft_for_email_draft(db=db, draft=latest_draft, lead=lead)
            logger.info(
                "Pipeline worker step=gmail_draft_ready lead_id=%s workspace_id=%s draft_id=%s gmail_draft_id=%s",
                lead.id,
                lead.workspace_id,
                latest_draft.id,
                latest_draft.gmail_draft_id,
            )

        if policy.effective_auto_send_approved_emails:
            if policy.require_manual_review_before_send and latest_draft.review_status != REVIEW_STATUS_APPROVED:
                logger.info(
                    "Pipeline worker auto_send_waiting_review lead_id=%s workspace_id=%s draft_id=%s",
                    lead.id,
                    lead.workspace_id,
                    latest_draft.id,
                )
                db.commit()
                return
            send_email_draft_via_gmail(db=db, draft=latest_draft, lead=lead)
            logger.info(
                "Pipeline worker step=gmail_sent lead_id=%s workspace_id=%s draft_id=%s message_id=%s",
                lead.id,
                lead.workspace_id,
                latest_draft.id,
                latest_draft.gmail_message_id,
            )

        db.commit()

    @staticmethod
    def _resolve_workspace_user_id(db, workspace_id: UUID) -> UUID | None:
        return db.scalar(
            select(User.id)
            .where(User.workspace_id == workspace_id)
            .order_by(User.created_at.asc())
            .limit(1)
        )

    @staticmethod
    def _should_mark_needs_review(*, lead_status: str, exc: HTTPException) -> bool:
        if lead_status == LEAD_STATUS_IMPORTED:
            return True
        return exc.status_code in {400, 404, 422}


pipeline_worker = LeadPipelineWorker()
