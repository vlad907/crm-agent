from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

NEARBY_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
NEXT_PAGE_TOKEN_DELAY_SECONDS = 2.0


class GooglePlacesCrawlerError(RuntimeError):
    pass


@dataclass(frozen=True)
class GooglePlaceLead:
    place_id: str
    company: str
    location: str | None
    phone: str | None
    website_url: str | None
    rating: float | None
    review_count: int | None
    business_type: str


class GooglePlacesCrawler:
    def __init__(self, *, api_key: str, timeout_seconds: float = 20.0) -> None:
        api_key_clean = api_key.strip()
        if not api_key_clean:
            raise GooglePlacesCrawlerError("Google Places API key is missing")
        self.api_key = api_key_clean
        self.timeout = httpx.Timeout(timeout_seconds)

    def _request_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, params=params)
        if response.status_code != 200:
            raise GooglePlacesCrawlerError(f"Google Places HTTP error {response.status_code}: {response.text[:200]}")

        payload = response.json()
        status = payload.get("status")
        if status in {"OK", "ZERO_RESULTS"}:
            return payload

        error_message = payload.get("error_message") or "Google Places request failed"
        raise GooglePlacesCrawlerError(f"{status}: {error_message}")

    def get_places(self, *, location: str, radius: int, business_type: str, keyword: str = "business") -> list[str]:
        params: dict[str, Any] = {
            "key": self.api_key,
            "location": location,
            "radius": radius,
            "type": business_type,
            "keyword": keyword,
        }

        place_ids: list[str] = []
        while True:
            payload = self._request_json(NEARBY_SEARCH_URL, params)
            for place in payload.get("results", []):
                place_id = place.get("place_id")
                if isinstance(place_id, str):
                    place_ids.append(place_id)

            next_page_token = payload.get("next_page_token")
            if not next_page_token:
                break

            time.sleep(NEXT_PAGE_TOKEN_DELAY_SECONDS)
            params = {
                "key": self.api_key,
                "pagetoken": next_page_token,
            }

        logger.info("Google Places fetched type=%s count=%s", business_type, len(place_ids))
        return place_ids

    def get_place_details(self, place_id: str) -> GooglePlaceLead | None:
        payload = self._request_json(
            PLACE_DETAILS_URL,
            {
                "key": self.api_key,
                "place_id": place_id,
                "fields": "name,vicinity,formatted_phone_number,website,rating,user_ratings_total",
            },
        )
        details = payload.get("result")
        if not isinstance(details, dict):
            return None

        company = details.get("name")
        if not isinstance(company, str) or not company.strip():
            return None

        location = details.get("vicinity") if isinstance(details.get("vicinity"), str) else None
        phone = details.get("formatted_phone_number") if isinstance(details.get("formatted_phone_number"), str) else None
        website_url = details.get("website") if isinstance(details.get("website"), str) else None
        raw_rating = details.get("rating")
        rating = None
        if isinstance(raw_rating, (int, float)):
            rating = float(raw_rating)
        raw_review_count = details.get("user_ratings_total")
        review_count = raw_review_count if isinstance(raw_review_count, int) else None

        return GooglePlaceLead(
            place_id=place_id,
            company=company.strip(),
            location=location.strip() if location else None,
            phone=phone.strip() if phone else None,
            website_url=website_url.strip() if website_url else None,
            rating=rating,
            review_count=review_count,
            business_type="",
        )

    def discover_businesses(
        self,
        *,
        location: str,
        radius: int,
        business_types: list[str],
        keyword: str = "business",
        missing_website_only: bool = False,
    ) -> list[GooglePlaceLead]:
        seen_place_ids: set[str] = set()
        businesses: list[GooglePlaceLead] = []

        for business_type in business_types:
            place_ids = self.get_places(
                location=location,
                radius=radius,
                business_type=business_type,
                keyword=keyword,
            )
            for place_id in place_ids:
                if place_id in seen_place_ids:
                    continue
                seen_place_ids.add(place_id)

                details = self.get_place_details(place_id)
                if details is None:
                    continue
                if missing_website_only and details.website_url:
                    continue

                businesses.append(
                    GooglePlaceLead(
                        place_id=details.place_id,
                        company=details.company,
                        location=details.location,
                        phone=details.phone,
                        website_url=details.website_url,
                        rating=details.rating,
                        review_count=details.review_count,
                        business_type=business_type,
                    )
                )

        return businesses
