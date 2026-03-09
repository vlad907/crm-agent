from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.lead_sources.google_places import (
    GooglePlaceLead,
    GooglePlacesCrawler,
    GooglePlacesCrawlerError,
)

DEFAULT_LOCATION = "39.727132,-121.843275"
DEFAULT_RADIUS = 15_000
DEFAULT_BUSINESS_TYPES = [
    "plumber",
    "locksmith",
    "electrician",
    "car_repair",
    "painter",
    "hvac_contractor",
    "moving_company",
    "cleaning_service",
    "roofing_contractor",
    "furniture_store",
    "flooring_store",
    "home_goods_store",
    "landscaper",
    "hair_care",
    "nail_salon",
    "massage_therapist",
    "barber_shop",
    "spa",
    "accounting",
    "insurance_agency",
    "lawyer",
    "notary_public",
    "real_estate_agency",
    "tax_preparation_service",
    "pet_store",
    "dog_trainer",
    "pet_grooming",
    "veterinary_care",
    "gift_shop",
    "jewelry_store",
    "florist",
    "book_store",
    "antique_store",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Google Places crawler that produces payload for POST /api/v1/prospects/import",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY"),
        help="Google Places API key (or set GOOGLE_PLACES_API_KEY / GOOGLE_MAPS_API_KEY)",
    )
    parser.add_argument("--location", default=DEFAULT_LOCATION, help="lat,lng")
    parser.add_argument("--radius", type=int, default=DEFAULT_RADIUS, help="search radius in meters")
    parser.add_argument(
        "--types",
        default=",".join(DEFAULT_BUSINESS_TYPES),
        help="comma-separated Google Place types",
    )
    parser.add_argument("--keyword", default="business")
    parser.add_argument(
        "--missing-website-only",
        action="store_true",
        help="only include places that do not have a website",
    )
    parser.add_argument(
        "--output",
        default="crawler_output.json",
        help="output JSON file for /api/v1/prospects/import payload",
    )
    return parser.parse_args()


def build_import_payload(
    *,
    places: list[GooglePlaceLead],
    source: str = "google_business",
) -> dict[str, object]:
    items: list[dict[str, str | None]] = []
    for place in places:
        items.append(
            {
                "source": source,
                "external_id": place.place_id,
                "company_name": place.company,
                "category": place.business_type,
                "address": place.location or "Unknown address",
                "phone": place.phone,
                "website_url": place.website_url,
                "rating": place.rating,
                "review_count": place.review_count,
                "raw_source_payload": {
                    "place_id": place.place_id,
                    "business_type": place.business_type,
                    "company": place.company,
                    "vicinity": place.location,
                    "phone": place.phone,
                    "website": place.website_url,
                    "rating": place.rating,
                    "review_count": place.review_count,
                },
                "import_status": "new",
            }
        )

    return {
        "items": items,
    }


def main() -> int:
    args = parse_args()
    if not args.api_key:
        print("Missing API key. Use --api-key or set GOOGLE_PLACES_API_KEY (or GOOGLE_MAPS_API_KEY).")
        return 1

    business_types = [part.strip() for part in args.types.split(",") if part.strip()]
    if not business_types:
        print("No business types provided.")
        return 1

    crawler = GooglePlacesCrawler(api_key=args.api_key)
    try:
        leads = crawler.discover_businesses(
            location=args.location,
            radius=args.radius,
            business_types=business_types,
            keyword=args.keyword,
            missing_website_only=args.missing_website_only,
        )
    except GooglePlacesCrawlerError as exc:
        print(f"Crawler failed: {exc}")
        return 1

    payload = build_import_payload(places=leads)
    output_path = Path(args.output)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Crawled {len(leads)} candidate prospects.")
    print(f"Wrote import payload to {output_path}.")
    print("Next step: POST this JSON to /api/v1/prospects/import with workspace/user headers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
