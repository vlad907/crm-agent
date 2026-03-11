from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx

from app.core.config import settings
from app.models.workspace_ai_strategy import WorkspaceAIStrategy
from app.models.workspace_profile import WorkspaceProfile
from app.services.openai_client import (
    OpenAIClientError,
    OpenAIConfigurationError,
    OpenAIQuotaExceededError,
    OpenAIRateLimitError,
)

logger = logging.getLogger(__name__)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
REQUEST_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0)

GENERIC_STRATEGY_DRIFT_TERMS = {
    "online sales",
    "conversion rate",
    "email campaign automation",
    "low email response",
    "crm optimization",
    "growth hacking",
    "ecommerce funnel",
}

BUSINESS_MODEL_KEYWORDS: list[tuple[str, list[str]]] = [
    ("managed_it_services", ["managed it", "msp", "it support", "helpdesk", "network monitoring"]),
    ("onsite_it_services", ["onsite", "on-site", "field service", "site visit", "truck roll", "install"]),
    ("networking_and_pos_support", ["pos", "point of sale", "wifi", "wi-fi", "network", "switch", "router"]),
    ("structured_cabling_and_networking", ["structured cabling", "ethernet", "wiring", "cabling", "rack install"]),
    ("cybersecurity_consulting", ["security assessment", "cybersecurity", "compliance", "soc2", "threat"]),
    ("software_saas", ["saas", "software platform", "subscription software", "product analytics"]),
    ("marketing_agency", ["marketing agency", "paid ads", "seo", "creative campaign"]),
    ("crm_automation", ["crm automation", "sales automation", "outreach automation"]),
]

INDUSTRY_CATEGORY_LIBRARY: list[tuple[list[str], list[dict[str, str]]]] = [
    (
        ["restaurant", "dining", "food service"],
        [
            {"category": "restaurant", "display_name": "Restaurants"},
            {"category": "coffee_shop", "display_name": "Coffee Shops"},
            {"category": "bar_or_pub", "display_name": "Bars & Pubs"},
        ],
    ),
    (
        ["hospitality", "hotel", "lodging"],
        [
            {"category": "hotel", "display_name": "Hotels"},
            {"category": "boutique_hotel", "display_name": "Boutique Hotels"},
            {"category": "restaurant", "display_name": "Restaurant Groups"},
        ],
    ),
    (
        ["retail", "store", "shop"],
        [
            {"category": "retail_store", "display_name": "Retail Stores"},
            {"category": "franchise_retail", "display_name": "Franchise Retail"},
        ],
    ),
    (
        ["medical", "healthcare", "clinic", "dental"],
        [
            {"category": "medical_office", "display_name": "Medical Offices"},
            {"category": "dental_practice", "display_name": "Dental Practices"},
        ],
    ),
]

PAIN_POINT_LIBRARY: list[dict[str, Any]] = [
    {
        "key": "wifi_reliability_peak_hours",
        "label": "Wi-Fi reliability during peak customer traffic",
        "keywords": ["wifi", "wi-fi", "wireless"],
    },
    {
        "key": "pos_network_stability",
        "label": "POS network stability at checkout",
        "keywords": ["pos", "point of sale", "checkout", "terminal"],
    },
    {
        "key": "camera_system_uptime",
        "label": "Camera system uptime and remote access reliability",
        "keywords": ["camera", "surveillance", "cctv", "nvr"],
    },
    {
        "key": "network_uptime_for_daily_operations",
        "label": "Network uptime for daily operations",
        "keywords": ["network", "uptime", "reliability", "internet"],
    },
    {
        "key": "expansion_and_cabling_readiness",
        "label": "Cabling and infrastructure readiness for expansions",
        "keywords": ["cabling", "wiring", "install", "expansion"],
    },
    {
        "key": "onsite_issue_resolution_speed",
        "label": "Speed of onsite issue resolution",
        "keywords": ["onsite", "on-site", "field", "dispatch"],
    },
]

SERVICE_ANGLE_LIBRARY: list[dict[str, Any]] = [
    {
        "key": "guest_wifi_and_network_stability",
        "label": "Guest Wi-Fi and network stability support",
        "why_relevant": "Improves day-to-day reliability for front-of-house operations and customer experience.",
        "keywords": ["wifi", "network", "wireless"],
    },
    {
        "key": "pos_and_payment_network_hardening",
        "label": "POS and payment network hardening",
        "why_relevant": "Reduces checkout disruptions by stabilizing POS connectivity and segmentation.",
        "keywords": ["pos", "checkout", "payment", "terminal"],
    },
    {
        "key": "camera_and_backoffice_network_reliability",
        "label": "Camera and back-office network reliability",
        "why_relevant": "Keeps camera systems and operational back-office systems consistently reachable.",
        "keywords": ["camera", "surveillance", "backoffice", "nvr"],
    },
    {
        "key": "onsite_network_assessment_and_remediation",
        "label": "Onsite network assessment and remediation plan",
        "why_relevant": "Fits field-service business models where local infrastructure quality drives uptime.",
        "keywords": ["onsite", "install", "assessment", "field"],
    },
    {
        "key": "structured_cabling_and_location_expansion_support",
        "label": "Structured cabling and location expansion support",
        "why_relevant": "Supports growing businesses adding locations, terminals, or camera endpoints.",
        "keywords": ["cabling", "wiring", "expansion", "location"],
    },
]

CTA_LIBRARY_BY_MODEL: list[tuple[list[str], list[dict[str, str]]]] = [
    (
        ["onsite_it_services", "structured_cabling_and_networking", "networking_and_pos_support"],
        [
            {"key": "onsite_walkthrough", "label": "Offer a quick onsite walkthrough"},
            {"key": "network_assessment", "label": "Offer a short network reliability assessment"},
            {"key": "ops_call", "label": "Offer a short operations-focused call"},
        ],
    ),
    (
        ["managed_it_services"],
        [
            {"key": "health_check", "label": "Offer a simple infrastructure health check"},
            {"key": "ops_call", "label": "Offer a short operations-focused call"},
        ],
    ),
    (
        ["software_saas", "crm_automation", "marketing_agency"],
        [
            {"key": "discovery_call", "label": "Offer a short discovery call"},
            {"key": "demo", "label": "Offer a brief product/service walkthrough"},
        ],
    ),
]

STRATEGY_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "business_model_classification",
        "core_positioning",
        "ideal_customers",
        "priority_pain_points",
        "service_angles",
        "cta_recommendations",
        "guardrails",
    ],
    "properties": {
        "business_model_classification": {"type": "array", "items": {"type": "string"}},
        "core_positioning": {"type": "string"},
        "ideal_customers": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["category", "display_name", "why_fit", "priority"],
                "properties": {
                    "category": {"type": "string"},
                    "display_name": {"type": "string"},
                    "why_fit": {"type": "string"},
                    "priority": {"type": "integer"},
                },
            },
        },
        "priority_pain_points": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["key", "label", "why_relevant"],
                "properties": {
                    "key": {"type": "string"},
                    "label": {"type": "string"},
                    "why_relevant": {"type": "string"},
                },
            },
        },
        "service_angles": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["key", "label", "best_for_categories", "why_relevant"],
                "properties": {
                    "key": {"type": "string"},
                    "label": {"type": "string"},
                    "best_for_categories": {"type": "array", "items": {"type": "string"}},
                    "why_relevant": {"type": "string"},
                },
            },
        },
        "cta_recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["key", "label"],
                "properties": {
                    "key": {"type": "string"},
                    "label": {"type": "string"},
                },
            },
        },
        "guardrails": {
            "type": "object",
            "additionalProperties": False,
            "required": ["avoid_claims", "avoid_tone", "notes"],
            "properties": {
                "avoid_claims": {"type": "array", "items": {"type": "string"}},
                "avoid_tone": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}

STRATEGY_SYSTEM_PROMPT = """You are an AI Outreach Strategist for B2B outbound.
Generate a practical strategy strictly grounded in the workspace profile.
Return JSON only matching the required schema.

Strict constraints:
- Ground ideal_customers in industries_served; do not invent unrelated verticals.
- Ground priority_pain_points in service_specialties; avoid generic sales/CRM pain unless profile explicitly provides it.
- Ground service_angles in actual deliverables this business can provide.
- Match CTA style to the business model (onsite assessment, walkthrough, consultation, review).
- Do not suggest ecommerce growth or email automation strategies unless explicitly present in the profile.
- Keep recommendations concrete, operational, and profile-specific.
"""


def normalize_string_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        if not isinstance(raw, str):
            continue
        value = raw.strip()
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def generate_workspace_outreach_strategy(
    *,
    workspace_profile: WorkspaceProfile | None,
    api_key: str | None = None,
) -> dict[str, Any]:
    resolved_api_key = (api_key or "").strip() or (settings.openai_api_key or "").strip()
    if not resolved_api_key:
        raise OpenAIConfigurationError("OpenAI API key is not configured")

    profile_payload = _workspace_profile_payload(workspace_profile)
    preclassified_models = _classify_business_model(profile_payload)
    profile_payload["business_model_classification"] = preclassified_models
    payload = _build_strategy_payload(profile_payload, preclassified_models)

    retries = max(0, settings.openai_rate_limit_retries)
    base_backoff = max(0.1, settings.openai_rate_limit_backoff_seconds)
    headers = {"Authorization": f"Bearer {resolved_api_key}", "Content-Type": "application/json"}

    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        for attempt in range(retries + 1):
            try:
                response = client.post(OPENAI_RESPONSES_URL, headers=headers, json=payload)
            except httpx.RequestError as exc:
                raise OpenAIClientError(f"OpenAI request failed: {exc}") from exc

            if response.status_code == 429:
                error_message, error_code = _openai_error_details(response)
                if error_code == "insufficient_quota":
                    raise OpenAIQuotaExceededError(error_message)
                if attempt < retries:
                    retry_after = _retry_after_seconds(response)
                    wait = max(base_backoff * (2**attempt), retry_after or 0.0)
                    logger.warning(
                        "Workspace strategy generation rate-limited; retry in %.2fs attempt=%s",
                        wait,
                        attempt + 1,
                    )
                    time.sleep(wait)
                    continue
                raise OpenAIRateLimitError(error_message)

            if response.status_code >= 400:
                raise OpenAIClientError(_format_openai_error(response))

            try:
                raw = _extract_output(response.json())
            except ValueError as exc:
                raise OpenAIClientError(f"OpenAI returned invalid strategy JSON: {exc}") from exc

            sanitized = _sanitize_generated_strategy(raw)
            return _ground_strategy_to_profile(sanitized, profile_payload, preclassified_models)

    raise OpenAIClientError("OpenAI request failed after retries")


def build_strategy_context(strategy: WorkspaceAIStrategy | None) -> dict[str, Any]:
    if strategy is None:
        return {
            "generated_strategy": None,
            "selected_target_categories": [],
            "selected_priority_pain_points": [],
            "selected_service_angles": [],
            "selected_cta_style": None,
            "selected_target_category_details": [],
            "selected_priority_pain_point_details": [],
            "selected_service_angle_details": [],
            "selected_cta_recommendation": None,
            "strategy_available": False,
            "selection_mode": "open",
        }

    generated = strategy.generated_strategy if isinstance(strategy.generated_strategy, dict) else None
    ideal_customers = _safe_object_list(generated, "ideal_customers")
    pain_points = _safe_object_list(generated, "priority_pain_points")
    service_angles = _safe_object_list(generated, "service_angles")
    ctas = _safe_object_list(generated, "cta_recommendations")

    selected_categories = normalize_string_list(strategy.selected_target_categories)
    selected_pains = normalize_string_list(strategy.selected_priority_pain_points)
    selected_angles = normalize_string_list(strategy.selected_service_angles)
    selected_cta = (strategy.selected_cta_style or "").strip() or None

    selected_category_details = _match_selected(ideal_customers, "category", selected_categories)
    selected_pain_details = _match_selected(pain_points, "key", selected_pains)
    selected_angle_details = _match_selected(service_angles, "key", selected_angles)
    selected_cta_detail = _first_matching(ctas, "key", selected_cta)

    return {
        "generated_strategy": generated,
        "selected_target_categories": selected_categories,
        "selected_priority_pain_points": selected_pains,
        "selected_service_angles": selected_angles,
        "selected_cta_style": selected_cta,
        "selected_target_category_details": selected_category_details,
        "selected_priority_pain_point_details": selected_pain_details,
        "selected_service_angle_details": selected_angle_details,
        "selected_cta_recommendation": selected_cta_detail,
        "strategy_available": generated is not None,
        "selection_mode": "selected_only" if (selected_categories or selected_pains or selected_angles or selected_cta) else "open",
    }


def _workspace_profile_payload(workspace_profile: WorkspaceProfile | None) -> dict[str, Any]:
    if workspace_profile is None:
        return {
            "business_name": None,
            "business_description": None,
            "industries_served": [],
            "service_specialties": [],
            "service_area": None,
            "preferred_tone": None,
            "outreach_style": None,
            "preferred_cta": None,
            "do_not_mention": [],
        }

    return {
        "business_name": workspace_profile.business_name,
        "business_description": workspace_profile.business_description,
        "industries_served": list(workspace_profile.industries_served or []),
        "service_specialties": list(workspace_profile.service_specialties or []),
        "service_area": workspace_profile.service_area,
        "preferred_tone": workspace_profile.preferred_tone,
        "outreach_style": workspace_profile.outreach_style,
        "preferred_cta": workspace_profile.preferred_cta,
        "do_not_mention": list(workspace_profile.do_not_mention or []),
    }


def _profile_signal_text(profile_payload: dict[str, Any]) -> str:
    fragments: list[str] = []
    for field in ("business_name", "business_description", "service_area"):
        value = profile_payload.get(field)
        if isinstance(value, str) and value.strip():
            fragments.append(value.strip().lower())
    fragments.extend(value.lower() for value in normalize_string_list(profile_payload.get("industries_served")))
    fragments.extend(value.lower() for value in normalize_string_list(profile_payload.get("service_specialties")))
    return " ".join(fragments)


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _normalize_identifier(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.lower())).strip("_")


def _classify_business_model(profile_payload: dict[str, Any]) -> list[str]:
    signal_text = _profile_signal_text(profile_payload)
    classifications: list[str] = []
    for key, keywords in BUSINESS_MODEL_KEYWORDS:
        if _contains_any(signal_text, keywords):
            classifications.append(key)

    if not classifications:
        if _contains_any(signal_text, ["it", "network", "wifi", "pos", "camera", "cabling"]):
            classifications.extend(["managed_it_services", "networking_and_pos_support"])
        elif _contains_any(signal_text, ["saas", "software"]):
            classifications.append("software_saas")

    if not classifications:
        classifications.append("general_b2b_services")

    return normalize_string_list(classifications)


def _build_strategy_payload(profile_payload: dict[str, Any], preclassified_models: list[str]) -> dict[str, Any]:
    return {
        "model": settings.openai_model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": STRATEGY_SYSTEM_PROMPT}]},
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Workspace profile (JSON):\n"
                            f"{json.dumps(profile_payload, ensure_ascii=True)}\n\n"
                            "Derived business model classification from profile:\n"
                            f"{json.dumps(preclassified_models, ensure_ascii=True)}\n\n"
                            "Use this classification and profile fields to keep strategy recommendations tightly grounded."
                        ),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "workspace_ai_strategy",
                "strict": True,
                "schema": STRATEGY_JSON_SCHEMA,
            }
        },
    }


def _sanitize_generated_strategy(raw: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {
        "business_model_classification": normalize_string_list(
            raw.get("business_model_classification") if isinstance(raw.get("business_model_classification"), list) else []
        ),
        "core_positioning": str(raw.get("core_positioning") or "").strip(),
        "ideal_customers": [],
        "priority_pain_points": [],
        "service_angles": [],
        "cta_recommendations": [],
        "guardrails": {"avoid_claims": [], "avoid_tone": [], "notes": []},
    }

    for item in _safe_object_list(raw, "ideal_customers"):
        category = _normalize_identifier(str(item.get("category") or ""))
        display_name = str(item.get("display_name") or "").strip()
        why_fit = str(item.get("why_fit") or "").strip()
        if not category:
            continue
        if not display_name:
            display_name = category.replace("_", " ").title()
        priority_raw = item.get("priority")
        priority = priority_raw if isinstance(priority_raw, int) and priority_raw > 0 else 999
        sanitized["ideal_customers"].append(
            {
                "category": category,
                "display_name": display_name,
                "why_fit": why_fit,
                "priority": priority,
            }
        )

    for item in _safe_object_list(raw, "priority_pain_points"):
        key = _normalize_identifier(str(item.get("key") or ""))
        label = str(item.get("label") or "").strip()
        why_relevant = str(item.get("why_relevant") or "").strip()
        if not key or not label:
            continue
        sanitized["priority_pain_points"].append({"key": key, "label": label, "why_relevant": why_relevant})

    for item in _safe_object_list(raw, "service_angles"):
        key = _normalize_identifier(str(item.get("key") or ""))
        label = str(item.get("label") or "").strip()
        why_relevant = str(item.get("why_relevant") or "").strip()
        best_for = normalize_string_list(
            [_normalize_identifier(v) for v in item.get("best_for_categories")]
            if isinstance(item.get("best_for_categories"), list)
            else []
        )
        if not key or not label:
            continue
        sanitized["service_angles"].append(
            {
                "key": key,
                "label": label,
                "best_for_categories": best_for,
                "why_relevant": why_relevant,
            }
        )

    for item in _safe_object_list(raw, "cta_recommendations"):
        key = _normalize_identifier(str(item.get("key") or ""))
        label = str(item.get("label") or "").strip()
        if not key or not label:
            continue
        sanitized["cta_recommendations"].append({"key": key, "label": label})

    guardrails = raw.get("guardrails")
    if isinstance(guardrails, dict):
        sanitized["guardrails"] = {
            "avoid_claims": normalize_string_list(
                guardrails.get("avoid_claims") if isinstance(guardrails.get("avoid_claims"), list) else []
            ),
            "avoid_tone": normalize_string_list(
                guardrails.get("avoid_tone") if isinstance(guardrails.get("avoid_tone"), list) else []
            ),
            "notes": normalize_string_list(guardrails.get("notes") if isinstance(guardrails.get("notes"), list) else []),
        }

    return sanitized


def _ground_strategy_to_profile(
    sanitized: dict[str, Any],
    profile_payload: dict[str, Any],
    preclassified_models: list[str],
) -> dict[str, Any]:
    fallback_categories = _derive_categories_from_profile(profile_payload, preclassified_models)
    fallback_pains = _derive_pain_points_from_profile(profile_payload, preclassified_models)
    fallback_angles = _derive_service_angles_from_profile(profile_payload, preclassified_models, fallback_categories)
    fallback_ctas = _derive_cta_from_profile(preclassified_models)

    allowed_category_keys = {item["category"] for item in fallback_categories}
    allowed_pain_keys = {item["key"] for item in fallback_pains}
    allowed_angle_keys = {item["key"] for item in fallback_angles}
    allowed_cta_keys = {item["key"] for item in fallback_ctas}

    ai_categories = [item for item in sanitized["ideal_customers"] if item["category"] in allowed_category_keys]
    ideal_customers = _merge_unique(ai_categories, fallback_categories, key="category", max_items=8)
    if not ideal_customers:
        ideal_customers = fallback_categories

    ai_pains = [item for item in sanitized["priority_pain_points"] if item["key"] in allowed_pain_keys]
    priority_pain_points = _merge_unique(ai_pains, fallback_pains, key="key", max_items=8)
    if not priority_pain_points:
        priority_pain_points = fallback_pains

    ai_angles = [item for item in sanitized["service_angles"] if item["key"] in allowed_angle_keys]
    service_angles = _merge_unique(ai_angles, fallback_angles, key="key", max_items=8)
    if not service_angles:
        service_angles = fallback_angles

    for angle in service_angles:
        if not angle.get("best_for_categories"):
            angle["best_for_categories"] = [item["category"] for item in ideal_customers[:3]]

    ai_ctas = [item for item in sanitized["cta_recommendations"] if item["key"] in allowed_cta_keys]
    cta_recommendations = _merge_unique(ai_ctas, fallback_ctas, key="key", max_items=4)
    if not cta_recommendations:
        cta_recommendations = fallback_ctas

    core_positioning = sanitized["core_positioning"]
    if not core_positioning or _is_generic_core_positioning(core_positioning, profile_payload):
        core_positioning = _fallback_core_positioning(profile_payload, preclassified_models)

    classification = preclassified_models or sanitized["business_model_classification"]
    if not classification:
        classification = ["general_b2b_services"]

    guardrails = sanitized["guardrails"]
    avoid_claims = _merge_string_lists(
        guardrails.get("avoid_claims", []),
        [
            "Do not claim ecommerce conversion outcomes unless ecommerce services are explicitly listed.",
            "Do not claim email campaign automation outcomes unless outreach/automation is explicitly listed.",
            "Do not position services outside listed specialties.",
        ],
    )
    avoid_tone = _merge_string_lists(
        guardrails.get("avoid_tone", []),
        ["Generic SaaS growth language", "Overpromising guarantees", "Aggressive marketing hype"],
    )
    notes = _merge_string_lists(
        guardrails.get("notes", []),
        [
            "Ground recommendations in business_description, industries_served, and service_specialties.",
            "Prioritize local operational pain points for onsite/networking service models.",
            "Keep suggestions relevant to what this workspace can actually deliver.",
        ],
    )

    return {
        "business_model_classification": classification,
        "core_positioning": core_positioning,
        "ideal_customers": ideal_customers,
        "priority_pain_points": priority_pain_points,
        "service_angles": service_angles,
        "cta_recommendations": cta_recommendations,
        "guardrails": {"avoid_claims": avoid_claims, "avoid_tone": avoid_tone, "notes": notes},
    }


def _derive_categories_from_profile(profile_payload: dict[str, Any], classification: list[str]) -> list[dict[str, Any]]:
    signal_text = _profile_signal_text(profile_payload)
    categories: list[dict[str, Any]] = []
    for keywords, templates in INDUSTRY_CATEGORY_LIBRARY:
        if _contains_any(signal_text, keywords):
            for template in templates:
                categories.append(
                    {
                        "category": template["category"],
                        "display_name": template["display_name"],
                        "why_fit": "Matches industries explicitly listed in this workspace profile.",
                        "priority": len(categories) + 1,
                    }
                )

    if not categories and "networking_and_pos_support" in classification:
        categories = [
            {"category": "restaurant", "display_name": "Restaurants", "why_fit": "Strong fit for Wi-Fi and POS reliability work.", "priority": 1},
            {"category": "coffee_shop", "display_name": "Coffee Shops", "why_fit": "High dependency on stable guest Wi-Fi and POS uptime.", "priority": 2},
            {"category": "retail_store", "display_name": "Retail Stores", "why_fit": "Retail checkout and camera systems depend on reliable networking.", "priority": 3},
        ]

    if not categories:
        categories = [
            {
                "category": "local_smb_business",
                "display_name": "Local SMB Businesses",
                "why_fit": "Fallback target when profile industries are broad or unspecified.",
                "priority": 1,
            }
        ]

    deduped = _merge_unique(categories, [], key="category", max_items=8)
    for index, item in enumerate(deduped, start=1):
        item["priority"] = index
    return deduped


def _derive_pain_points_from_profile(profile_payload: dict[str, Any], classification: list[str]) -> list[dict[str, Any]]:
    signal_text = _profile_signal_text(profile_payload)
    pains: list[dict[str, Any]] = []
    for template in PAIN_POINT_LIBRARY:
        if _contains_any(signal_text, template["keywords"]):
            pains.append(
                {
                    "key": template["key"],
                    "label": template["label"],
                    "why_relevant": "Directly aligned to listed specialties and service deliverables.",
                }
            )

    if not pains and any(model in classification for model in {"managed_it_services", "networking_and_pos_support"}):
        pains = [
            {
                "key": "network_uptime_for_daily_operations",
                "label": "Network uptime for daily operations",
                "why_relevant": "Managed IT and network support workflows depend on reliable connectivity.",
            }
        ]

    return _merge_unique(pains, [], key="key", max_items=8)


def _derive_service_angles_from_profile(
    profile_payload: dict[str, Any],
    classification: list[str],
    categories: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    signal_text = _profile_signal_text(profile_payload)
    category_keys = [item["category"] for item in categories[:4]]

    angles: list[dict[str, Any]] = []
    for template in SERVICE_ANGLE_LIBRARY:
        if _contains_any(signal_text, template["keywords"]):
            angles.append(
                {
                    "key": template["key"],
                    "label": template["label"],
                    "best_for_categories": category_keys,
                    "why_relevant": template["why_relevant"],
                }
            )

    if not angles and "managed_it_services" in classification:
        angles = [
            {
                "key": "onsite_network_assessment_and_remediation",
                "label": "Onsite network assessment and remediation plan",
                "best_for_categories": category_keys,
                "why_relevant": "Managed IT positioning supports practical reliability assessments and fixes.",
            }
        ]

    return _merge_unique(angles, [], key="key", max_items=8)


def _derive_cta_from_profile(classification: list[str]) -> list[dict[str, str]]:
    ctas: list[dict[str, str]] = []
    for models, templates in CTA_LIBRARY_BY_MODEL:
        if any(model in classification for model in models):
            ctas.extend(templates)

    if not ctas:
        ctas = [{"key": "discovery_call", "label": "Offer a short discovery call"}]

    return _merge_unique(ctas, [], key="key", max_items=4)


def _is_generic_core_positioning(core_positioning: str, profile_payload: dict[str, Any]) -> bool:
    lowered = core_positioning.lower()
    profile_text = _profile_signal_text(profile_payload)
    drift_detected = any(term in lowered for term in GENERIC_STRATEGY_DRIFT_TERMS)
    if not drift_detected:
        return False
    return not any(term in profile_text for term in GENERIC_STRATEGY_DRIFT_TERMS)


def _fallback_core_positioning(profile_payload: dict[str, Any], classification: list[str]) -> str:
    business_name = (profile_payload.get("business_name") or "").strip() or "This workspace"
    industries = normalize_string_list(profile_payload.get("industries_served"))
    specialties = normalize_string_list(profile_payload.get("service_specialties"))
    service_area = (profile_payload.get("service_area") or "").strip()

    industries_text = ", ".join(industries[:3]) if industries else "local service-heavy businesses"
    specialties_text = ", ".join(specialties[:3]) if specialties else "reliability-focused IT operations"

    area_suffix = f" in {service_area}" if service_area else ""
    model_hint = " and ".join(classification[:2]) if classification else "profile-aligned service delivery"

    return (
        f"{business_name} provides {specialties_text} for {industries_text}{area_suffix}, "
        f"with outreach focused on practical operational reliability tied to {model_hint}."
    )


def _merge_unique(primary: list[dict[str, Any]], fallback: list[dict[str, Any]], *, key: str, max_items: int) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in (primary, fallback):
        for item in source:
            raw_key = item.get(key)
            if not isinstance(raw_key, str):
                continue
            normalized_key = raw_key.strip()
            if not normalized_key or normalized_key in seen:
                continue
            seen.add(normalized_key)
            merged.append(item)
            if len(merged) >= max_items:
                return merged
    return merged


def _merge_string_lists(*lists: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for values in lists:
        for value in values:
            if not isinstance(value, str):
                continue
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
    return merged


def _safe_object_list(container: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    if not isinstance(container, dict):
        return []
    value = container.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _match_selected(items: list[dict[str, Any]], key_field: str, selected_keys: list[str]) -> list[dict[str, Any]]:
    index = {
        str(item.get(key_field)).strip(): item
        for item in items
        if isinstance(item.get(key_field), str) and str(item.get(key_field)).strip()
    }
    matched: list[dict[str, Any]] = []
    for key in selected_keys:
        item = index.get(key)
        if item is not None:
            matched.append(item)
    return matched


def _first_matching(items: list[dict[str, Any]], key_field: str, key: str | None) -> dict[str, Any] | None:
    if not key:
        return None
    for item in items:
        value = item.get(key_field)
        if isinstance(value, str) and value.strip() == key:
            return item
    return None


def _extract_output(response_json: dict[str, Any]) -> dict[str, Any]:
    if isinstance(response_json.get("output_json"), dict):
        return response_json["output_json"]

    if isinstance(response_json.get("output_parsed"), dict):
        return response_json["output_parsed"]

    output_text = response_json.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        parsed = json.loads(output_text)
        if isinstance(parsed, dict):
            return parsed
        raise ValueError("output_text is not a JSON object")
    if isinstance(output_text, list):
        joined = "".join(part for part in output_text if isinstance(part, str)).strip()
        if joined:
            parsed = json.loads(joined)
            if isinstance(parsed, dict):
                return parsed
            raise ValueError("output_text is not a JSON object")

    output = response_json.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if isinstance(block.get("json"), dict):
                    return block["json"]
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        return parsed
                    raise ValueError("content text is not a JSON object")

    raise ValueError("Could not extract structured JSON output")


def _format_openai_error(response: httpx.Response) -> str:
    fallback = f"OpenAI API error: HTTP {response.status_code}"
    try:
        payload = response.json()
    except ValueError:
        return fallback

    error = payload.get("error")
    if not isinstance(error, dict):
        return fallback
    message = error.get("message")
    if isinstance(message, str) and message.strip():
        return f"OpenAI API error: {message}"
    return fallback


def _openai_error_details(response: httpx.Response) -> tuple[str, str | None]:
    fallback = f"OpenAI API error: HTTP {response.status_code}"
    try:
        payload = response.json()
    except ValueError:
        return fallback, None

    error = payload.get("error")
    if not isinstance(error, dict):
        return fallback, None
    message = error.get("message")
    code = error.get("code")
    if isinstance(message, str) and message.strip():
        return f"OpenAI API error: {message}", code if isinstance(code, str) else None
    return fallback, code if isinstance(code, str) else None


def _retry_after_seconds(response: httpx.Response) -> float | None:
    retry_after = response.headers.get("retry-after")
    if retry_after is None:
        return None
    try:
        seconds = float(retry_after)
    except ValueError:
        return None
    return max(0.0, seconds)
