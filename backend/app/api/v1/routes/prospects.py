from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps.request_context import RequestContext, get_request_context
from app.db.session import get_db
from app.models.prospect import Prospect
from app.schemas.prospect import (
    ProspectConvertRequest,
    ProspectConvertResponse,
    ProspectConvertSkipped,
    ProspectImportError,
    ProspectImportRequest,
    ProspectImportResponse,
    ProspectImportSkipped,
    ProspectListResponse,
    ProspectRead,
    ProspectRunSearchRequest,
    ProspectRunSearchResponse,
)
from app.services.importers.google_business_crawler import (
    GooglePlacesCrawlerError,
    discover_google_business_prospects,
)
from app.services.prospect_service import (
    ProspectImportCandidate,
    ProspectImportResult,
    convert_prospects_to_leads,
    import_prospects_for_workspace,
)
from app.services.workspace_credentials import resolve_google_places_api_key

router = APIRouter(prefix="/prospects", tags=["Prospects"])


def _build_import_response(result: ProspectImportResult, total_received: int) -> ProspectImportResponse:
    return ProspectImportResponse(
        total_received=total_received,
        imported_count=len(result.imported),
        skipped_count=len(result.skipped),
        error_count=len(result.errors),
        imported=result.imported,
        skipped=[
            ProspectImportSkipped(
                row_index=item.row_index,
                reason=item.reason,
                source=item.source,
                external_id=item.external_id,
                company_name=item.company_name,
                address=item.address,
            )
            for item in result.skipped
        ],
        errors=[
            ProspectImportError(
                row_index=item.row_index,
                reason=item.reason,
                source=item.source,
                external_id=item.external_id,
                company_name=item.company_name,
                address=item.address,
            )
            for item in result.errors
        ],
    )


@router.get("", response_model=ProspectListResponse)
def list_prospects(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    category_filter: str | None = Query(default=None, alias="category"),
    query: str | None = Query(default=None, alias="q", min_length=1),
) -> ProspectListResponse:
    filters = [Prospect.workspace_id == ctx.workspace_id]
    if status_filter:
        filters.append(Prospect.import_status == status_filter)
    if category_filter:
        filters.append(Prospect.category.ilike(f"%{category_filter}%"))
    if query:
        filters.append(
            (Prospect.company_name.ilike(f"%{query}%")) | (Prospect.address.ilike(f"%{query}%"))
        )

    list_stmt = (
        select(Prospect)
        .where(*filters)
        .order_by(Prospect.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    count_stmt = select(func.count()).select_from(Prospect).where(*filters)

    items = db.scalars(list_stmt).all()
    total = db.scalar(count_stmt) or 0
    return ProspectListResponse(items=items, total=total, offset=offset, limit=limit)


@router.post("/import", response_model=ProspectImportResponse, status_code=status.HTTP_201_CREATED)
def import_prospects(
    payload: ProspectImportRequest,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> ProspectImportResponse:
    candidates = [
        ProspectImportCandidate(
            row_index=index,
            source=item.source,
            external_id=item.external_id,
            company_name=item.company_name,
            category=item.category,
            address=item.address,
            phone=item.phone,
            website_url=item.website_url,
            rating=item.rating,
            review_count=item.review_count,
            raw_source_payload=item.raw_source_payload,
            import_status=item.import_status,
        )
        for index, item in enumerate(payload.items)
    ]

    result = import_prospects_for_workspace(
        db=db,
        workspace_id=ctx.workspace_id,
        candidates=candidates,
    )
    return _build_import_response(result, total_received=len(payload.items))


@router.post("/search", response_model=ProspectRunSearchResponse, status_code=status.HTTP_201_CREATED)
def run_google_business_search(
    payload: ProspectRunSearchRequest,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> ProspectRunSearchResponse:
    google_api_key, _ = resolve_google_places_api_key(db=db, workspace_id=ctx.workspace_id)
    if not google_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Places API key is missing. Configure workspace settings at /api/v1/settings or set GOOGLE_PLACES_API_KEY.",
        )

    try:
        discovered = discover_google_business_prospects(
            api_key=google_api_key,
            location=payload.location,
            radius=payload.radius,
            categories=payload.categories,
            keyword=payload.keyword,
            missing_website_only=payload.missing_website_only,
            limit=payload.limit,
        )
    except GooglePlacesCrawlerError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Crawler failed: {exc}") from exc

    import_candidates = [
        ProspectImportCandidate(
            row_index=index,
            source=item.source,
            external_id=item.external_id,
            company_name=item.company_name,
            category=item.category,
            address=item.address,
            phone=item.phone,
            website_url=item.website_url,
            rating=item.rating,
            review_count=item.review_count,
            raw_source_payload=item.raw_source_payload,
            import_status="new",
        )
        for index, item in enumerate(discovered)
    ]
    import_result = import_prospects_for_workspace(
        db=db,
        workspace_id=ctx.workspace_id,
        candidates=import_candidates,
    )
    return ProspectRunSearchResponse(
        fetched_count=len(discovered),
        import_result=_build_import_response(import_result, total_received=len(discovered)),
    )


@router.post("/convert-to-leads", response_model=ProspectConvertResponse)
def convert_selected_prospects_to_leads(
    payload: ProspectConvertRequest,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> ProspectConvertResponse:
    result = convert_prospects_to_leads(
        db=db,
        workspace_id=ctx.workspace_id,
        prospect_ids=payload.prospect_ids,
        require_website=payload.require_website,
    )

    return ProspectConvertResponse(
        requested_count=result.requested_count,
        found_count=result.found_count,
        converted_count=len(result.converted_leads),
        skipped_count=len(result.skipped),
        converted_leads=result.converted_leads,
        skipped=[
            ProspectConvertSkipped(
                prospect_id=item.prospect_id,
                reason=item.reason,
                company_name=item.company_name,
                address=item.address,
                website_url=item.website_url,
            )
            for item in result.skipped
        ],
    )
