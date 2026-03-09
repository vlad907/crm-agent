from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from app.services.scrape import WebsiteFetchError, extract_text, fetch_html

logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b")
PHONE_PATTERN = re.compile(
    r"(?:(?:\+?1[\s.\-]?)?(?:\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})|\+\d{1,3}[\s.\-]?\d{6,14})"
)
MAX_EXTRA_PAGES = 6
ABOUT_KEYWORDS = ("about", "team", "company")
CONTACT_KEYWORDS = ("contact",)


@dataclass(frozen=True)
class IngestedPage:
    url: str
    page_type: str
    raw_text: str
    extracted_emails: list[str]
    extracted_phones: list[str]


@dataclass(frozen=True)
class WebsiteIngestionResult:
    pages: list[IngestedPage]
    combined_text: str
    unique_emails: list[str]
    unique_phones: list[str]


def ingest_website_pages(root_url: str) -> WebsiteIngestionResult:
    homepage_html = fetch_html(root_url)
    homepage_raw_text = extract_text(homepage_html) or "[no readable text extracted]"
    homepage_emails = _extract_emails(homepage_html, homepage_raw_text)
    homepage_phones = _extract_phones(homepage_html, homepage_raw_text)

    pages: list[IngestedPage] = [
        IngestedPage(
            url=root_url,
            page_type="home",
            raw_text=homepage_raw_text,
            extracted_emails=homepage_emails,
            extracted_phones=homepage_phones,
        )
    ]

    candidate_urls = _discover_candidate_links(base_url=root_url, html=homepage_html)
    for url, page_type in candidate_urls[:MAX_EXTRA_PAGES]:
        try:
            html = fetch_html(url)
        except WebsiteFetchError as exc:
            logger.warning("Secondary page fetch failed url=%s error=%s", url, exc)
            continue

        raw_text = extract_text(html) or "[no readable text extracted]"
        pages.append(
            IngestedPage(
                url=url,
                page_type=page_type,
                raw_text=raw_text,
                extracted_emails=_extract_emails(html, raw_text),
                extracted_phones=_extract_phones(html, raw_text),
            )
        )

    combined_text = _build_combined_text(pages)
    unique_emails = sorted({email for page in pages for email in page.extracted_emails})
    unique_phones = sorted({phone for page in pages for phone in page.extracted_phones})
    return WebsiteIngestionResult(
        pages=pages,
        combined_text=combined_text,
        unique_emails=unique_emails,
        unique_phones=unique_phones,
    )


def _build_combined_text(pages: list[IngestedPage]) -> str:
    sections: list[str] = []
    for page in pages:
        header = f"[{page.page_type.upper()} PAGE] {page.url}"
        sections.append(f"{header}\n{page.raw_text}")
    return "\n\n".join(sections).strip()


def _discover_candidate_links(*, base_url: str, html: str) -> list[tuple[str, str]]:
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        logger.exception("Failed to parse homepage HTML while discovering links")
        return []

    base = urlparse(base_url)
    seen: set[str] = set()
    candidates: list[tuple[str, str]] = []

    for anchor in soup.find_all("a", href=True):
        href = (anchor.get("href") or "").strip()
        if not href or href.startswith("#"):
            continue
        lower_href = href.lower()
        if lower_href.startswith(("mailto:", "tel:", "javascript:")):
            continue

        absolute = _normalize_url(urljoin(base_url, href))
        if not absolute:
            continue

        parsed = urlparse(absolute)
        if parsed.netloc and parsed.netloc != base.netloc:
            continue

        page_type = _classify_page_type(parsed.path)
        if page_type is None:
            continue

        if absolute in seen or absolute == base_url:
            continue
        seen.add(absolute)
        candidates.append((absolute, page_type))

    return candidates


def _classify_page_type(path: str) -> str | None:
    normalized = (path or "/").strip("/").casefold()
    if not normalized:
        return None

    segments = [part for part in normalized.split("/") if part]
    if any(_contains_keyword(segment, CONTACT_KEYWORDS) for segment in segments):
        return "contact"
    if any(_contains_keyword(segment, ABOUT_KEYWORDS) for segment in segments):
        return "about"
    return None


def _contains_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _normalize_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    cleaned_path = parsed.path or "/"
    if cleaned_path != "/":
        cleaned_path = cleaned_path.rstrip("/") or "/"
    return urlunparse((parsed.scheme, parsed.netloc, cleaned_path, "", "", ""))


def _extract_emails(html: str, raw_text: str) -> list[str]:
    found = set(EMAIL_PATTERN.findall(html))
    found.update(EMAIL_PATTERN.findall(raw_text))
    return sorted({email.strip().lower() for email in found if email.strip()})


def _extract_phones(html: str, raw_text: str) -> list[str]:
    candidates = list(PHONE_PATTERN.findall(html))
    candidates.extend(PHONE_PATTERN.findall(raw_text))
    normalized = {_normalize_phone(phone) for phone in candidates}
    return sorted({phone for phone in normalized if phone})


def _normalize_phone(phone: str) -> str | None:
    digits = re.sub(r"\D+", "", phone or "")
    if len(digits) < 10:
        return None
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"+1-{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"
    return f"+{digits}"
