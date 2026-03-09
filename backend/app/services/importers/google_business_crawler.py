from __future__ import annotations

from dataclasses import dataclass

from app.services.lead_sources.google_places import GooglePlacesCrawler, GooglePlacesCrawlerError


@dataclass(frozen=True)
class GoogleBusinessProspect:
    source: str
    external_id: str
    company_name: str
    category: str | None
    address: str
    phone: str | None
    website_url: str | None
    rating: float | None
    review_count: int | None
    raw_source_payload: dict[str, object]


def discover_google_business_prospects(
    *,
    api_key: str,
    location: str,
    radius: int,
    categories: list[str],
    keyword: str = "business",
    missing_website_only: bool = False,
    limit: int = 300,
) -> list[GoogleBusinessProspect]:
    crawler = GooglePlacesCrawler(api_key=api_key)
    places = crawler.discover_businesses(
        location=location,
        radius=radius,
        business_types=categories,
        keyword=keyword,
        missing_website_only=missing_website_only,
    )

    normalized: list[GoogleBusinessProspect] = []
    for place in places[:limit]:
        normalized.append(
            GoogleBusinessProspect(
                source="google_business",
                external_id=place.place_id,
                company_name=place.company,
                category=place.business_type,
                address=place.location or "Unknown address",
                phone=place.phone,
                website_url=place.website_url,
                rating=place.rating,
                review_count=place.review_count,
                raw_source_payload={
                    "place_id": place.place_id,
                    "business_type": place.business_type,
                    "company": place.company,
                    "vicinity": place.location,
                    "phone": place.phone,
                    "website": place.website_url,
                    "rating": place.rating,
                    "review_count": place.review_count,
                },
            )
        )

    return normalized


__all__ = [
    "GoogleBusinessProspect",
    "GooglePlacesCrawlerError",
    "discover_google_business_prospects",
]
