from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import UUID

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.lead import Lead

email_adapter = TypeAdapter(EmailStr)


@dataclass(frozen=True)
class LeadImportCandidate:
    row_index: int
    name: str | None
    title: str | None
    company: str | None
    industry: str | None
    location: str | None
    website_url: str | None
    email: str | None
    source: str | None
    status: str | None


@dataclass(frozen=True)
class LeadImportDuplicate:
    row_index: int
    reason: str
    company: str | None
    location: str | None
    website_url: str | None


@dataclass(frozen=True)
class LeadImportError:
    row_index: int
    reason: str
    company: str | None
    location: str | None
    website_url: str | None


@dataclass
class LeadImportResult:
    imported: list[Lead]
    duplicates: list[LeadImportDuplicate]
    errors: list[LeadImportError]


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def normalize_website_url(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None

    candidate = cleaned if "://" in cleaned else f"https://{cleaned}"
    parsed = urlparse(candidate)
    if not parsed.netloc:
        return None

    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return None

    path = parsed.path.rstrip("/")
    return f"{scheme}://{host}{path}"


def _company_location_key(company: str | None, location: str | None) -> str | None:
    company_clean = _clean_text(company)
    if company_clean is None:
        return None
    location_clean = _clean_text(location) or ""
    return f"{company_clean.casefold()}::{location_clean.casefold()}"


def _website_variants(normalized_url: str) -> set[str]:
    base = normalized_url.casefold()
    variants = {base}
    if base.endswith("/"):
        variants.add(base.rstrip("/"))
    else:
        variants.add(f"{base}/")

    if base.startswith("https://"):
        http_base = "http://" + base.removeprefix("https://")
        variants.add(http_base)
        variants.add(http_base.rstrip("/") if http_base.endswith("/") else f"{http_base}/")
    elif base.startswith("http://"):
        https_base = "https://" + base.removeprefix("http://")
        variants.add(https_base)
        variants.add(https_base.rstrip("/") if https_base.endswith("/") else f"{https_base}/")

    return variants


def import_leads_for_workspace(
    *,
    db: Session,
    workspace_id: UUID,
    candidates: list[LeadImportCandidate],
    default_source: str,
    dedupe_by_website: bool = True,
    dedupe_by_company_location: bool = True,
) -> LeadImportResult:
    candidate_websites = {
        normalized
        for candidate in candidates
        for normalized in [normalize_website_url(candidate.website_url)]
        if normalized
    }
    candidate_companies = {
        company.casefold()
        for candidate in candidates
        for company in [_clean_text(candidate.company)]
        if company
    }
    website_match_candidates = {
        variant
        for website in candidate_websites
        for variant in _website_variants(website)
    }

    existing_websites: set[str] = set()
    if dedupe_by_website and website_match_candidates:
        rows = db.scalars(
            select(Lead.website_url).where(
                Lead.workspace_id == workspace_id,
                Lead.website_url.is_not(None),
                func.lower(Lead.website_url).in_(website_match_candidates),
            )
        )
        existing_websites = {row.casefold() for row in rows if row}

    existing_company_locations: set[str] = set()
    if dedupe_by_company_location and candidate_companies:
        rows = db.execute(
            select(Lead.company, Lead.location).where(
                Lead.workspace_id == workspace_id,
                func.lower(Lead.company).in_(candidate_companies),
            )
        ).all()
        existing_company_locations = {
            key
            for company, location in rows
            for key in [_company_location_key(company, location)]
            if key
        }

    imported: list[Lead] = []
    duplicates: list[LeadImportDuplicate] = []
    errors: list[LeadImportError] = []

    seen_websites: set[str] = set()
    seen_company_locations: set[str] = set()

    for candidate in candidates:
        company = _clean_text(candidate.company)
        location = _clean_text(candidate.location)
        website_url = normalize_website_url(candidate.website_url)
        email = _clean_text(candidate.email)

        if company is None:
            errors.append(
                LeadImportError(
                    row_index=candidate.row_index,
                    reason="company is required",
                    company=None,
                    location=location,
                    website_url=website_url,
                )
            )
            continue

        if candidate.website_url and website_url is None:
            errors.append(
                LeadImportError(
                    row_index=candidate.row_index,
                    reason="website_url is invalid",
                    company=company,
                    location=location,
                    website_url=None,
                )
            )
            continue

        if email is not None:
            try:
                email = str(email_adapter.validate_python(email))
            except ValidationError:
                errors.append(
                    LeadImportError(
                        row_index=candidate.row_index,
                        reason="email is invalid",
                        company=company,
                        location=location,
                        website_url=website_url,
                    )
                )
                continue

        company_location_key = _company_location_key(company, location)
        duplicate_reason: str | None = None
        if dedupe_by_website and website_url:
            website_variants = _website_variants(website_url)
            if website_variants & existing_websites or website_variants & seen_websites:
                duplicate_reason = "website_url"

        if duplicate_reason is None and dedupe_by_company_location and company_location_key:
            if company_location_key in existing_company_locations or company_location_key in seen_company_locations:
                duplicate_reason = "company+location"

        if duplicate_reason is not None:
            duplicates.append(
                LeadImportDuplicate(
                    row_index=candidate.row_index,
                    reason=duplicate_reason,
                    company=company,
                    location=location,
                    website_url=website_url,
                )
            )
            continue

        lead = Lead(
            workspace_id=workspace_id,
            name=_clean_text(candidate.name) or company,
            title=_clean_text(candidate.title),
            company=company,
            industry=_clean_text(candidate.industry),
            location=location,
            website_url=website_url,
            email=email,
            source=_clean_text(candidate.source) or default_source,
            status=_clean_text(candidate.status) or "new",
        )
        imported.append(lead)
        if dedupe_by_website and website_url:
            seen_websites.update(_website_variants(website_url))
        if dedupe_by_company_location and company_location_key:
            seen_company_locations.add(company_location_key)

    if imported:
        db.add_all(imported)
        db.commit()
        for lead in imported:
            db.refresh(lead)

    return LeadImportResult(
        imported=imported,
        duplicates=duplicates,
        errors=errors,
    )
