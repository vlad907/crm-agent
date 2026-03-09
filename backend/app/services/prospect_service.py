from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.prospect import Prospect
from app.services.lead_import import normalize_website_url


@dataclass(frozen=True)
class ProspectImportCandidate:
    row_index: int
    source: str | None
    external_id: str | None
    company_name: str | None
    category: str | None
    address: str | None
    phone: str | None
    website_url: str | None
    rating: float | None
    review_count: int | None
    raw_source_payload: dict[str, object] | None
    import_status: str | None


@dataclass(frozen=True)
class ProspectImportSkipped:
    row_index: int
    reason: str
    source: str | None
    external_id: str | None
    company_name: str | None
    address: str | None


@dataclass(frozen=True)
class ProspectImportError:
    row_index: int
    reason: str
    source: str | None
    external_id: str | None
    company_name: str | None
    address: str | None


@dataclass
class ProspectImportResult:
    imported: list[Prospect]
    skipped: list[ProspectImportSkipped]
    errors: list[ProspectImportError]


@dataclass(frozen=True)
class ProspectConvertSkipped:
    prospect_id: UUID
    reason: str
    company_name: str
    address: str
    website_url: str | None


@dataclass
class ProspectConvertResult:
    requested_count: int
    found_count: int
    converted_leads: list[Lead]
    skipped: list[ProspectConvertSkipped]


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _company_address_key(company_name: str | None, address: str | None) -> str | None:
    company = _clean_text(company_name)
    address_clean = _clean_text(address)
    if company is None or address_clean is None:
        return None
    return f"{company.casefold()}::{address_clean.casefold()}"


def _website_variants(normalized_url: str) -> set[str]:
    parsed = urlparse(normalized_url)
    scheme = parsed.scheme.casefold()
    host = parsed.netloc.casefold()
    path = parsed.path.rstrip("/").casefold()
    canonical = f"{scheme}://{host}{path}"

    variants = {canonical, canonical.rstrip("/") or canonical}
    no_path = f"{scheme}://{host}"
    variants.add(no_path)
    variants.add(f"{no_path}/")

    if canonical.startswith("https://"):
        alt = "http://" + canonical.removeprefix("https://")
        variants.add(alt)
        variants.add(alt.rstrip("/") or alt)
    elif canonical.startswith("http://"):
        alt = "https://" + canonical.removeprefix("http://")
        variants.add(alt)
        variants.add(alt.rstrip("/") or alt)

    return {variant for variant in variants if variant}


def import_prospects_for_workspace(
    *,
    db: Session,
    workspace_id: UUID,
    candidates: list[ProspectImportCandidate],
) -> ProspectImportResult:
    source_external_keys = {
        (source, external_id)
        for candidate in candidates
        for source in [_clean_text(candidate.source)]
        for external_id in [_clean_text(candidate.external_id)]
        if source and external_id
    }
    source_company_address_keys = {
        (source, company_address)
        for candidate in candidates
        for source in [_clean_text(candidate.source)]
        for company_address in [_company_address_key(candidate.company_name, candidate.address)]
        if source and company_address
    }

    existing_source_external: set[tuple[str, str]] = set()
    if source_external_keys:
        candidate_sources = {source.casefold() for source, _ in source_external_keys}
        candidate_external_ids = {external_id for _, external_id in source_external_keys}
        rows = db.execute(
            select(Prospect.source, Prospect.external_id).where(
                Prospect.workspace_id == workspace_id,
                Prospect.external_id.is_not(None),
                func.lower(Prospect.source).in_(candidate_sources),
                Prospect.external_id.in_(candidate_external_ids),
            )
        ).all()
        existing_source_external = {
            (source.casefold(), external_id.casefold())
            for source, external_id in rows
            if source and external_id
        }

    existing_source_company_address: set[tuple[str, str]] = set()
    if source_company_address_keys:
        candidate_sources = {source.casefold() for source, _ in source_company_address_keys}
        candidate_companies = {
            company.casefold()
            for _, company_address in source_company_address_keys
            for company in [company_address.split("::", 1)[0]]
            if company
        }
        rows = db.execute(
            select(Prospect.source, Prospect.company_name, Prospect.address).where(
                Prospect.workspace_id == workspace_id,
                func.lower(Prospect.source).in_(candidate_sources),
                func.lower(Prospect.company_name).in_(candidate_companies),
            )
        ).all()
        existing_source_company_address = {
            (source.casefold(), company_address)
            for source, company_name, address in rows
            for company_address in [_company_address_key(company_name, address)]
            if source and company_address
        }

    imported: list[Prospect] = []
    skipped: list[ProspectImportSkipped] = []
    errors: list[ProspectImportError] = []

    seen_source_external: set[tuple[str, str]] = set()
    seen_source_company_address: set[tuple[str, str]] = set()

    for candidate in candidates:
        source = _clean_text(candidate.source)
        external_id = _clean_text(candidate.external_id)
        company_name = _clean_text(candidate.company_name)
        category = _clean_text(candidate.category)
        address = _clean_text(candidate.address)
        phone = _clean_text(candidate.phone)
        website_url = normalize_website_url(candidate.website_url)

        if source is None:
            errors.append(
                ProspectImportError(
                    row_index=candidate.row_index,
                    reason="source is required",
                    source=None,
                    external_id=external_id,
                    company_name=company_name,
                    address=address,
                )
            )
            continue
        if company_name is None:
            errors.append(
                ProspectImportError(
                    row_index=candidate.row_index,
                    reason="company_name is required",
                    source=source,
                    external_id=external_id,
                    company_name=None,
                    address=address,
                )
            )
            continue
        if address is None:
            errors.append(
                ProspectImportError(
                    row_index=candidate.row_index,
                    reason="address is required",
                    source=source,
                    external_id=external_id,
                    company_name=company_name,
                    address=None,
                )
            )
            continue
        if candidate.website_url and website_url is None:
            errors.append(
                ProspectImportError(
                    row_index=candidate.row_index,
                    reason="website_url is invalid",
                    source=source,
                    external_id=external_id,
                    company_name=company_name,
                    address=address,
                )
            )
            continue

        if external_id:
            source_external_key = (source.casefold(), external_id.casefold())
            if source_external_key in existing_source_external or source_external_key in seen_source_external:
                skipped.append(
                    ProspectImportSkipped(
                        row_index=candidate.row_index,
                        reason="duplicate_external_id",
                        source=source,
                        external_id=external_id,
                        company_name=company_name,
                        address=address,
                    )
                )
                continue
        else:
            source_external_key = None

        company_address_key = _company_address_key(company_name, address)
        if company_address_key:
            source_company_address_key = (source.casefold(), company_address_key)
            if (
                source_company_address_key in existing_source_company_address
                or source_company_address_key in seen_source_company_address
            ):
                skipped.append(
                    ProspectImportSkipped(
                        row_index=candidate.row_index,
                        reason="duplicate_company_address",
                        source=source,
                        external_id=external_id,
                        company_name=company_name,
                        address=address,
                    )
                )
                continue
        else:
            source_company_address_key = None

        prospect = Prospect(
            workspace_id=workspace_id,
            source=source,
            external_id=external_id,
            company_name=company_name,
            category=category,
            address=address,
            phone=phone,
            website_url=website_url,
            rating=candidate.rating,
            review_count=candidate.review_count,
            raw_source_payload=candidate.raw_source_payload or {},
            import_status=_clean_text(candidate.import_status) or "new",
        )
        imported.append(prospect)

        if source_external_key:
            seen_source_external.add(source_external_key)
        if source_company_address_key:
            seen_source_company_address.add(source_company_address_key)

    if imported:
        db.add_all(imported)
        db.commit()
        for prospect in imported:
            db.refresh(prospect)

    return ProspectImportResult(imported=imported, skipped=skipped, errors=errors)


def convert_prospects_to_leads(
    *,
    db: Session,
    workspace_id: UUID,
    prospect_ids: list[UUID],
    require_website: bool = False,
) -> ProspectConvertResult:
    requested_count = len(prospect_ids)
    if requested_count == 0:
        return ProspectConvertResult(
            requested_count=0,
            found_count=0,
            converted_leads=[],
            skipped=[],
        )

    rows = db.scalars(
        select(Prospect).where(Prospect.workspace_id == workspace_id, Prospect.id.in_(prospect_ids))
    ).all()
    by_id = {prospect.id: prospect for prospect in rows}
    prospects = [by_id[prospect_id] for prospect_id in prospect_ids if prospect_id in by_id]

    candidate_websites = {
        normalized
        for prospect in prospects
        for normalized in [normalize_website_url(prospect.website_url)]
        if normalized
    }
    website_match_candidates = {
        variant
        for website in candidate_websites
        for variant in _website_variants(website)
    }
    candidate_companies = {
        company_name.casefold()
        for prospect in prospects
        for company_name in [_clean_text(prospect.company_name)]
        if company_name
    }

    existing_websites: set[str] = set()
    if website_match_candidates:
        existing_websites = {
            website.casefold()
            for website in db.scalars(
                select(Lead.website_url).where(
                    Lead.workspace_id == workspace_id,
                    Lead.website_url.is_not(None),
                    func.lower(Lead.website_url).in_(website_match_candidates),
                )
            ).all()
            if website
        }

    existing_company_addresses: set[str] = set()
    if candidate_companies:
        rows = db.execute(
            select(Lead.company, Lead.location).where(
                Lead.workspace_id == workspace_id,
                func.lower(Lead.company).in_(candidate_companies),
            )
        ).all()
        existing_company_addresses = {
            key
            for company, address in rows
            for key in [_company_address_key(company, address)]
            if key
        }

    converted_leads: list[Lead] = []
    skipped: list[ProspectConvertSkipped] = []
    seen_websites: set[str] = set()
    seen_company_addresses: set[str] = set()

    for prospect in prospects:
        previous_status = (prospect.import_status or "").strip().lower()
        if previous_status == "imported":
            skipped.append(
                ProspectConvertSkipped(
                    prospect_id=prospect.id,
                    reason="already_imported",
                    company_name=prospect.company_name,
                    address=prospect.address,
                    website_url=prospect.website_url,
                )
            )
            continue
        prospect.import_status = "selected"

        website_url = normalize_website_url(prospect.website_url)
        company_address_key = _company_address_key(prospect.company_name, prospect.address)

        if require_website and not website_url:
            prospect.import_status = "skipped"
            skipped.append(
                ProspectConvertSkipped(
                    prospect_id=prospect.id,
                    reason="missing_website_url",
                    company_name=prospect.company_name,
                    address=prospect.address,
                    website_url=None,
                )
            )
            continue

        duplicate_reason: str | None = None
        if website_url:
            variants = _website_variants(website_url)
            if variants & existing_websites or variants & seen_websites:
                duplicate_reason = "duplicate_website_url"
        if duplicate_reason is None and company_address_key:
            if company_address_key in existing_company_addresses or company_address_key in seen_company_addresses:
                duplicate_reason = "duplicate_company_address"

        if duplicate_reason:
            prospect.import_status = "skipped"
            skipped.append(
                ProspectConvertSkipped(
                    prospect_id=prospect.id,
                    reason=duplicate_reason,
                    company_name=prospect.company_name,
                    address=prospect.address,
                    website_url=website_url,
                )
            )
            continue

        lead = Lead(
            workspace_id=workspace_id,
            name=prospect.company_name,
            company=prospect.company_name,
            location=prospect.address,
            phone=_clean_text(prospect.phone),
            website_url=website_url,
            source=prospect.source,
            status="new",
        )
        converted_leads.append(lead)
        prospect.import_status = "imported"

        if website_url:
            seen_websites.update(_website_variants(website_url))
        if company_address_key:
            seen_company_addresses.add(company_address_key)

    if converted_leads:
        db.add_all(converted_leads)
    db.commit()
    for lead in converted_leads:
        db.refresh(lead)

    return ProspectConvertResult(
        requested_count=requested_count,
        found_count=len(prospects),
        converted_leads=converted_leads,
        skipped=skipped,
    )
