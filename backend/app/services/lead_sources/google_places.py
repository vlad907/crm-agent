from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any
import httpx

logger = logging.getLogger(__name__)

NEARBY_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

# Maps user-friendly category names → valid Google Places API type strings.
# When a category isn't in this map, it falls back to type=establishment with the
# category as the keyword so Google still filters by relevance.
CATEGORY_TO_PLACES_TYPE: dict[str, str] = {
    # Medical / dental
    "dental": "dentist",
    "dentist": "dentist",
    "dental office": "dentist",
    "dentistry": "dentist",
    "orthodontist": "dentist",
    "doctor": "doctor",
    "physician": "doctor",
    "medical": "doctor",
    "clinic": "doctor",
    "hospital": "hospital",
    "pharmacy": "pharmacy",
    "drugstore": "pharmacy",
    "optometrist": "doctor",
    "chiropractor": "physiotherapist",
    "physical therapy": "physiotherapist",
    "physiotherapy": "physiotherapist",
    "veterinarian": "veterinary_care",
    "vet": "veterinary_care",
    "veterinary": "veterinary_care",
    # Food & drink
    "restaurant": "restaurant",
    "restaurants": "restaurant",
    "food": "restaurant",
    "bar": "bar",
    "cafe": "cafe",
    "coffee": "cafe",
    "coffee shop": "cafe",
    "bakery": "bakery",
    "meal takeaway": "meal_takeaway",
    "fast food": "meal_takeaway",
    # Lodging
    "hotel": "lodging",
    "hotels": "lodging",
    "lodging": "lodging",
    "motel": "lodging",
    "inn": "lodging",
    # Home services / trades
    "plumber": "plumber",
    "plumbing": "plumber",
    "electrician": "electrician",
    "electrical": "electrician",
    "roofing": "roofing_contractor",
    "roofer": "roofing_contractor",
    "contractor": "general_contractor",
    "general contractor": "general_contractor",
    "painter": "painter",
    "painting": "painter",
    "locksmith": "locksmith",
    "moving": "moving_company",
    "mover": "moving_company",
    "storage": "storage",
    "hvac": "general_contractor",
    "landscaping": "general_contractor",
    "landscaper": "general_contractor",
    "pest control": "general_contractor",
    "cleaning": "general_contractor",
    "janitorial": "general_contractor",
    # Auto
    "auto repair": "car_repair",
    "mechanic": "car_repair",
    "car repair": "car_repair",
    "car wash": "car_wash",
    "auto dealer": "car_dealer",
    "car dealer": "car_dealer",
    # Retail
    "store": "store",
    "retail": "store",
    "grocery": "grocery_or_supermarket",
    "supermarket": "grocery_or_supermarket",
    "pet store": "pet_store",
    "florist": "florist",
    "clothing": "clothing_store",
    "electronics": "electronics_store",
    "furniture": "furniture_store",
    "hardware": "hardware_store",
    "jewelry": "jewelry_store",
    "book store": "book_store",
    "bookstore": "book_store",
    # Health / beauty
    "gym": "gym",
    "fitness": "gym",
    "salon": "beauty_salon",
    "hair salon": "hair_care",
    "barbershop": "hair_care",
    "barber": "hair_care",
    "spa": "spa",
    "nail salon": "beauty_salon",
    # Finance / professional
    "bank": "bank",
    "atm": "atm",
    "accounting": "accounting",
    "accountant": "accounting",
    "lawyer": "lawyer",
    "attorney": "lawyer",
    "law firm": "lawyer",
    "insurance": "insurance_agency",
    "real estate": "real_estate_agency",
    "realtor": "real_estate_agency",
    # Education / care
    "school": "school",
    "university": "university",
    "daycare": "school",
    "child care": "school",
    # Other
    "laundry": "laundry",
    "dry cleaner": "laundry",
    "gas station": "gas_station",
    "parking": "parking",
    "post office": "post_office",
    "church": "church",
    "funeral home": "funeral_home",
}


def resolve_places_type(category: str) -> tuple[str, str]:
    """Return (places_api_type, keyword) for a user category string.

    Uses CATEGORY_TO_PLACES_TYPE for known mappings. Falls back to
    type='establishment' with the raw category as keyword so Google still
    filters results by relevance rather than returning random businesses.
    """
    normalized = category.strip().lower()
    places_type = CATEGORY_TO_PLACES_TYPE.get(normalized)
    if places_type:
        return places_type, category
    # Unknown category: use as keyword with broad type
    return "establishment", category
PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
AUTOCOMPLETE_URL = "https://maps.googleapis.com/maps/api/place/autocomplete/json"

_LAT_LNG_PATTERN = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")
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

    @staticmethod
    def _format_lat_lng(lat: float, lng: float) -> str:
        return f"{lat:.7f},{lng:.7f}"

    def resolve_location_for_nearby_search(self, location: str) -> str:
        """
        Nearby Search requires \"lat,lng\". Accepts that format or geocodes a free-text address.
        """
        raw = (location or "").strip()
        if not raw:
            raise GooglePlacesCrawlerError("Location is empty.")

        match = _LAT_LNG_PATTERN.match(raw)
        if match:
            lat_s, lng_s = match.group(1), match.group(2)
            return f"{float(lat_s):.7f},{float(lng_s):.7f}"

        params = {"key": self.api_key, "address": raw}
        payload = self._request_json(GEOCODE_URL, params)
        results = payload.get("results")
        if not isinstance(results, list) or not results:
            raise GooglePlacesCrawlerError(f"No geocoding results for: {raw!r}")

        first = results[0]
        if not isinstance(first, dict):
            raise GooglePlacesCrawlerError("Geocoding response was invalid.")

        geometry = first.get("geometry")
        if not isinstance(geometry, dict):
            raise GooglePlacesCrawlerError("Geocoding result missing geometry.")

        loc = geometry.get("location")
        if not isinstance(loc, dict):
            raise GooglePlacesCrawlerError("Geocoding result missing coordinates.")

        lat = loc.get("lat")
        lng = loc.get("lng")
        if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
            raise GooglePlacesCrawlerError("Geocoding returned invalid lat/lng.")

        formatted = self._format_lat_lng(float(lat), float(lng))
        logger.info("Geocoded %r -> %s", raw, formatted)
        return formatted

    def place_autocomplete(self, *, input_text: str, max_results: int = 8) -> list[dict[str, str]]:
        """Returns Place Autocomplete predictions (description + place_id)."""
        raw = (input_text or "").strip()
        if len(raw) < 2:
            return []

        payload = self._request_json(AUTOCOMPLETE_URL, {"input": raw, "key": self.api_key})
        predictions = payload.get("predictions")
        if not isinstance(predictions, list):
            return []

        out: list[dict[str, str]] = []
        for item in predictions[:max_results]:
            if not isinstance(item, dict):
                continue
            desc = item.get("description")
            pid = item.get("place_id")
            if isinstance(desc, str) and desc.strip() and isinstance(pid, str) and pid.strip():
                out.append({"description": desc.strip(), "place_id": pid.strip()})
        return out

    def get_places(self, *, location: str, radius: int, business_type: str, keyword: str = "business") -> list[str]:
        places_type, resolved_keyword = resolve_places_type(business_type)
        # Prefer the category-derived keyword over the generic "business" default
        effective_keyword = resolved_keyword if resolved_keyword != business_type or keyword == "business" else keyword
        params: dict[str, Any] = {
            "key": self.api_key,
            "location": location,
            "radius": radius,
            "type": places_type,
            "keyword": effective_keyword,
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

        logger.info("Google Places fetched category=%s type=%s keyword=%s count=%s", business_type, places_type, effective_keyword, len(place_ids))
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
        resolved = self.resolve_location_for_nearby_search(location)
        seen_place_ids: set[str] = set()
        businesses: list[GooglePlaceLead] = []

        for business_type in business_types:
            place_ids = self.get_places(
                location=resolved,
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
