from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import httpx

from app.core.config import settings
from app.models.workspace_ai_strategy import WorkspaceAIStrategy
from app.models.workspace_profile import WorkspaceProfile

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
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

# When profile indicates non-IT business (solar, HVAC, legal, etc.), reject AI output that defaults to IT
IT_DRIFT_TERMS = {"it solutions", "it support", "pos support", "pos systems", "network infrastructure", "managed it"}
NON_IT_PROFILE_SIGNALS = ["solar", "photovoltaic", "hvac", "plumbing", "electrical", "roofing", "legal", "law firm", "attorney"]

BUSINESS_MODEL_KEYWORDS: list[tuple[str, list[str]]] = [
    ("managed_it_services", ["managed it", "msp", "it support", "helpdesk", "network monitoring"]),
    ("onsite_it_services", ["onsite", "on-site", "field service", "site visit", "truck roll", "install"]),
    ("networking_and_pos_support", ["pos", "point of sale", "wifi", "wi-fi", "network", "switch", "router"]),
    ("structured_cabling_and_networking", ["structured cabling", "ethernet", "wiring", "cabling", "rack install"]),
    ("cybersecurity_consulting", ["security assessment", "cybersecurity", "compliance", "soc2", "threat"]),
    ("software_saas", ["saas", "software platform", "subscription software", "product analytics"]),
    ("marketing_agency", ["marketing agency", "paid ads", "seo", "creative campaign"]),
    ("crm_automation", ["crm automation", "sales automation", "outreach automation"]),
    ("solar_installation", ["solar", "pv", "photovoltaic", "rooftop solar", "solar panel"]),
    ("home_services", ["hvac", "plumbing", "electrical", "roofing", "contractor"]),
    ("legal_services", ["legal", "law firm", "attorney", "litigation", "compliance"]),
    ("professional_services", ["consulting", "advisory", "professional services"]),
    ("real_estate", ["real estate", "property management", "commercial real estate"]),
    ("healthcare_services", ["healthcare", "medical", "dental", "clinic", "practice"]),
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
    (
        ["solar_installation", "home_services"],
        [
            {"key": "site_assessment", "label": "Offer a free site assessment"},
            {"key": "consultation", "label": "Offer a consultation call"},
            {"key": "quote", "label": "Offer a no-obligation quote"},
        ],
    ),
    (
        ["legal_services", "professional_services", "real_estate", "healthcare_services"],
        [
            {"key": "consultation", "label": "Offer a consultation call"},
            {"key": "discovery_call", "label": "Offer a short discovery call"},
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
        "rapport_points",
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
        "rapport_points": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["category", "display_name", "hooks"],
                "properties": {
                    "category": {"type": "string"},
                    "display_name": {"type": "string"},
                    "hooks": {"type": "array", "items": {"type": "string"}},
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

CRITICAL — BUSINESS TYPE: The business_name and service_specialties define the PRIMARY business type.
- If the profile says solar, photovoltaic, solar panels, or solar installation → generate SOLAR-specific strategy:
  target categories (e.g. commercial property owners, restaurants, retail), pain points (high utility costs, roof suitability,
  energy savings, ROI on solar), CTAs (site assessment, energy audit, quote).
- If HVAC, plumbing, electrical, roofing → generate HOME SERVICES strategy.
- If IT, MSP, networking, POS → generate IT strategy.
- If legal, law firm → generate LEGAL strategy.
- NEVER default to IT/restaurant when the profile clearly indicates a different business (e.g. solar, HVAC, legal).
  Match the business type exactly.

- ideal_customers: From industries_served and business_description. Each category = real target segment for THIS business type.
- priority_pain_points: From service_specialties. Each pain = concrete challenge this business solves (solar: utility rates,
  roof condition; HVAC: comfort, equipment age; IT: uptime, POS; legal: case load, compliance).
- core_positioning: One sentence describing what THIS business does for THESE industries. Must match business_name and specialties.
- rapport_points: 4-8 hooks per category, tailored to the business type and target industries.
- cta_recommendations: Match business model (solar/home services: site assessment, quote; IT: walkthrough, health check; etc.).

Honor preferred_tone, outreach_style, preferred_cta, do_not_mention. Keep everything concrete and profile-specific.
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


def ensure_workspace_strategy_generated(
    *,
    db: "Session",
    workspace_id: Any,
    api_key: str | None = None,
) -> WorkspaceAIStrategy | None:
    """Auto-generate outreach strategy from workspace profile if missing. Used before agent 2 runs."""
    profile = db.get(WorkspaceProfile, workspace_id)
    strategy = db.get(WorkspaceAIStrategy, workspace_id)

    if not _profile_has_content(profile):
        return strategy

    if strategy is not None and strategy.generated_strategy is not None:
        return strategy

    try:
        generated = generate_workspace_outreach_strategy(
            workspace_profile=profile,
            api_key=api_key,
        )
    except (OpenAIConfigurationError, OpenAIRateLimitError, OpenAIClientError) as exc:
        logger.warning(
            "Auto-generate strategy failed workspace_id=%s error=%s; agent 2 will run with empty strategy",
            workspace_id,
            exc,
        )
        return strategy

    if strategy is None:
        strategy = WorkspaceAIStrategy(workspace_id=workspace_id)
        db.add(strategy)

    strategy.generated_strategy = generated
    strategy.last_generated_at = datetime.now(timezone.utc)
    strategy.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(strategy)
    logger.info("Auto-generated workspace strategy workspace_id=%s", workspace_id)
    return strategy


def _profile_has_content(profile: WorkspaceProfile | None) -> bool:
    if profile is None:
        return False
    if profile.business_name and profile.business_name.strip():
        return True
    if profile.business_description and profile.business_description.strip():
        return True
    if profile.industries_served and len(profile.industries_served) > 0:
        return True
    if profile.service_specialties and len(profile.service_specialties) > 0:
        return True
    return False


def _normalize_category_for_match(value: str | None) -> str:
    """Normalize category string for matching (e.g. 'Coffee Shop' -> 'coffee_shop')."""
    if not value or not isinstance(value, str):
        return ""
    return _normalize_identifier(value.strip())


# Lead industries that map to target categories (brewery/brewing → restaurants, etc.)
_CATEGORY_ALIASES: dict[str, list[str]] = {
    "brewing": ["restaurant", "hospitality", "food_beverage"],
    "brewery": ["restaurant", "hospitality", "food_beverage"],
    "beverage": ["restaurant", "hospitality", "food_beverage"],
    "bar": ["restaurant", "hospitality"],
    "pub": ["restaurant", "hospitality"],
    "food": ["restaurant", "hospitality"],
}


def _resolve_matched_workspace_category(
    lead_category: str | None,
    target_categories: list[str],
) -> str | None:
    """Map lead/prospect category to a workspace target category if possible."""
    if not lead_category or not target_categories:
        return None
    normalized_lead = _normalize_category_for_match(lead_category)
    if not normalized_lead:
        return None
    target_norms = {_normalize_identifier(tc): tc for tc in target_categories}
    for tc in target_categories:
        tc_norm = _normalize_identifier(tc)
        if tc_norm == normalized_lead:
            return tc
        if normalized_lead in tc_norm or tc_norm in normalized_lead:
            return tc
    for alias, candidates in _CATEGORY_ALIASES.items():
        if alias in normalized_lead:
            for cand in candidates:
                c_norm = _normalize_identifier(cand)
                if c_norm in target_norms:
                    return target_norms[c_norm]
                for tn, t in target_norms.items():
                    if c_norm in tn or cand in tn or tn in c_norm:
                        return t
            return target_categories[0]
    return None


def build_strategy_context(
    strategy: WorkspaceAIStrategy | None,
    *,
    lead_category: str | None = None,
) -> dict[str, Any]:
    if strategy is None:
        return {
            "generated_strategy": None,
            "selected_target_categories": [],
            "selected_priority_pain_points": [],
            "selected_cta_style": None,
            "selected_target_category_details": [],
            "selected_priority_pain_point_details": [],
            "selected_cta_recommendation": None,
            "rapport_points": [],
            "strategy_available": False,
            "selection_mode": "open",
            "target_categories": [],
            "matched_workspace_category": None,
            "matched_category": None,
            "pain_points_by_category": {},
            "fallback_pain_points_for_category": [],
            "fallback_service_angles_for_category": [],
            "fallback_rapport_hooks_for_category": [],
        }

    generated = strategy.generated_strategy if isinstance(strategy.generated_strategy, dict) else None
    ideal_customers = _safe_object_list(generated, "ideal_customers")
    pain_points = _safe_object_list(generated, "priority_pain_points")
    rapport_points = _safe_object_list(generated, "rapport_points")
    ctas = _safe_object_list(generated, "cta_recommendations")
    raw_target = (generated or {}).get("target_categories")
    target_categories = [str(c) for c in (raw_target or []) if isinstance(c, str)]
    if not target_categories:
        target_categories = [item.get("category") for item in ideal_customers if item.get("category")]

    pain_points_by_cat = (generated or {}).get("pain_points_by_category") or {}
    service_angles_by_cat = (generated or {}).get("service_angles_by_category") or {}
    rapport_hooks_by_cat = (generated or {}).get("rapport_hooks_by_category") or {}

    selected_categories = normalize_string_list(strategy.selected_target_categories)
    selected_pains = normalize_string_list(strategy.selected_priority_pain_points)
    selected_cta = (strategy.selected_cta_style or "").strip() or None

    selected_category_details = _match_selected(ideal_customers, "category", selected_categories)
    selected_pain_details = _match_selected(pain_points, "key", selected_pains)
    selected_cta_detail = _first_matching(ctas, "key", selected_cta)

    matched_category = _resolve_matched_workspace_category(lead_category, target_categories)
    fallback_pain_points: list[dict[str, Any]] = []
    fallback_service_angles: list[str] = []
    fallback_rapport_hooks: list[str] = []
    if matched_category:
        fallback_pain_points = pain_points_by_cat.get(matched_category, pain_points)
        fallback_service_angles = service_angles_by_cat.get(matched_category, [])
        fallback_rapport_hooks = rapport_hooks_by_cat.get(matched_category, [])
        if not fallback_rapport_hooks:
            rp = next((r for r in rapport_points if r.get("category") == matched_category), None)
            if rp and rp.get("hooks"):
                fallback_rapport_hooks = rp["hooks"]
    if not fallback_pain_points and pain_points:
        fallback_pain_points = pain_points
    if not fallback_rapport_hooks and rapport_points:
        for rp in rapport_points:
            if isinstance(rp, dict) and rp.get("hooks"):
                fallback_rapport_hooks.extend(rp["hooks"])
        fallback_rapport_hooks = list(dict.fromkeys(fallback_rapport_hooks))

    core_positioning = (generated or {}).get("core_positioning") if isinstance(generated, dict) else None
    core_positioning = str(core_positioning).strip() if core_positioning else None

    pbc_dict: dict[str, Any] = {}
    if isinstance(pain_points_by_cat, dict):
        pbc_dict = {str(k): v for k, v in pain_points_by_cat.items()}

    return {
        "generated_strategy": generated,
        "core_positioning": core_positioning,
        "selected_target_categories": selected_categories,
        "selected_priority_pain_points": selected_pains,
        "selected_cta_style": selected_cta,
        "selected_target_category_details": selected_category_details,
        "selected_priority_pain_point_details": selected_pain_details,
        "selected_cta_recommendation": selected_cta_detail,
        "rapport_points": rapport_points,
        "strategy_available": generated is not None,
        "selection_mode": "selected_only" if (selected_categories or selected_pains or selected_cta) else "open",
        "target_categories": target_categories,
        "matched_workspace_category": matched_category,
        "matched_category": matched_category,
        "pain_points_by_category": pbc_dict,
        "fallback_pain_points_for_category": fallback_pain_points,
        "fallback_service_angles_for_category": fallback_service_angles,
        "fallback_rapport_hooks_for_category": fallback_rapport_hooks,
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

    if not classifications and signal_text:
        if _contains_any(signal_text, ["it", "network", "wifi", "pos", "camera", "cabling"]):
            classifications.extend(["managed_it_services", "networking_and_pos_support"])
        elif _contains_any(signal_text, ["saas", "software"]):
            classifications.append("software_saas")
        elif _contains_any(signal_text, ["solar", "pv", "photovoltaic"]):
            classifications.append("solar_installation")
        elif _contains_any(signal_text, ["legal", "law", "attorney"]):
            classifications.append("legal_services")
        elif _contains_any(signal_text, ["consulting", "advisory"]):
            classifications.append("professional_services")
        elif _contains_any(signal_text, ["real estate", "property"]):
            classifications.append("real_estate")
        elif _contains_any(signal_text, ["healthcare", "medical", "dental"]):
            classifications.append("healthcare_services")

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
        "rapport_points": [],
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

    for item in _safe_object_list(raw, "rapport_points"):
        category = _normalize_identifier(str(item.get("category") or ""))
        display_name = str(item.get("display_name") or "").strip()
        hooks_raw = item.get("hooks")
        hooks = (
            [str(h).strip() for h in hooks_raw if isinstance(h, str) and str(h).strip()]
            if isinstance(hooks_raw, list)
            else []
        )
        if not category or not hooks:
            continue
        if not display_name:
            display_name = category.replace("_", " ").title()
        sanitized["rapport_points"].append(
            {"category": category, "display_name": display_name, "hooks": hooks[:12]}
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


def _build_pain_points_by_category(
    ideal_customers: list[dict[str, Any]],
    priority_pain_points: list[dict[str, Any]],
    profile_payload: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Build category-keyed pain points. Each category gets the full list (workspace-approved)."""
    categories = [item["category"] for item in ideal_customers]
    result: dict[str, list[dict[str, Any]]] = {}
    for cat in categories:
        result[cat] = list(priority_pain_points)
    return result


def _build_service_angles_by_category(
    ideal_customers: list[dict[str, Any]],
    profile_payload: dict[str, Any],
) -> dict[str, list[str]]:
    """Build category-keyed service angles from specialties and category context."""
    specialties = normalize_string_list(profile_payload.get("service_specialties"))
    result: dict[str, list[str]] = {}
    for item in ideal_customers:
        cat = item.get("category", "")
        display_name = (item.get("display_name") or cat.replace("_", " ")).lower()
        if not cat:
            continue
        angles: list[str] = []
        for spec in specialties[:6]:
            angles.append(f"{spec} for {display_name}")
        if not angles:
            angles = [f"Service delivery for {display_name}"]
        result[cat] = angles
    return result


def _ground_strategy_to_profile(
    sanitized: dict[str, Any],
    profile_payload: dict[str, Any],
    preclassified_models: list[str],
) -> dict[str, Any]:
    fallback_categories = _derive_categories_from_profile(profile_payload, preclassified_models)
    fallback_pains = _derive_pain_points_from_profile(profile_payload, preclassified_models)
    fallback_ctas = _derive_cta_from_profile(preclassified_models)

    profile_has_content = bool(_profile_signal_text(profile_payload))
    allowed_category_keys = {item["category"] for item in fallback_categories}
    allowed_pain_keys = {item["key"] for item in fallback_pains}
    allowed_cta_keys = {item["key"] for item in fallback_ctas}
    if profile_has_content:
        for item in _safe_object_list(sanitized, "ideal_customers"):
            cat = item.get("category")
            if isinstance(cat, str) and cat.strip():
                allowed_category_keys.add(_normalize_identifier(cat))
        for item in _safe_object_list(sanitized, "priority_pain_points"):
            key = item.get("key")
            if isinstance(key, str) and key.strip():
                allowed_pain_keys.add(_normalize_identifier(key))
        for item in _safe_object_list(sanitized, "cta_recommendations"):
            key = item.get("key")
            if isinstance(key, str) and key.strip():
                allowed_cta_keys.add(_normalize_identifier(key))

    ai_categories = [item for item in sanitized["ideal_customers"] if item["category"] in allowed_category_keys]
    ideal_customers = _merge_unique(ai_categories, fallback_categories, key="category", max_items=8)
    if not ideal_customers:
        ideal_customers = fallback_categories

    ai_pains = [item for item in sanitized["priority_pain_points"] if item["key"] in allowed_pain_keys]
    priority_pain_points = _merge_unique(ai_pains, fallback_pains, key="key", max_items=8)
    if not priority_pain_points:
        priority_pain_points = fallback_pains

    allowed_rapport_categories = {item["category"] for item in ideal_customers}
    if profile_has_content:
        for item in _safe_object_list(sanitized, "rapport_points"):
            cat = item.get("category")
            if isinstance(cat, str) and cat.strip():
                allowed_rapport_categories.add(_normalize_identifier(cat))
    ai_rapport = [item for item in _safe_object_list(sanitized, "rapport_points") if item["category"] in allowed_rapport_categories]
    fallback_rapport = _derive_rapport_from_ideal_customers(ideal_customers)
    rapport_points = _merge_unique(ai_rapport, fallback_rapport, key="category", max_items=16)
    if not rapport_points:
        rapport_points = fallback_rapport

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

    target_categories = [item["category"] for item in ideal_customers]
    pain_points_by_category = _build_pain_points_by_category(
        ideal_customers, priority_pain_points, profile_payload
    )
    service_angles_by_category = _build_service_angles_by_category(
        ideal_customers, profile_payload
    )
    rapport_hooks_by_category: dict[str, list[str]] = {}
    for item in rapport_points:
        if item.get("category") and item.get("hooks"):
            rapport_hooks_by_category[item["category"]] = item["hooks"]
    for cat in target_categories:
        if cat not in rapport_hooks_by_category:
            fallback = _derive_rapport_from_ideal_customers(
                [c for c in ideal_customers if c["category"] == cat]
            )
            rapport_hooks_by_category[cat] = fallback[0]["hooks"] if fallback else []

    return {
        "business_model_classification": classification,
        "core_positioning": core_positioning,
        "target_categories": target_categories,
        "ideal_customers": ideal_customers,
        "priority_pain_points": priority_pain_points,
        "pain_points_by_category": pain_points_by_category,
        "service_angles_by_category": service_angles_by_category,
        "rapport_points": rapport_points,
        "rapport_hooks_by_category": rapport_hooks_by_category,
        "cta_recommendations": cta_recommendations,
        "guardrails": {"avoid_claims": avoid_claims, "avoid_tone": avoid_tone, "notes": notes},
    }


def _derive_rapport_from_ideal_customers(categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate generic rapport hooks for any category — used when AI does not produce them. Works for all service angles."""
    result: list[dict[str, Any]] = []
    for item in categories:
        cat = item.get("category", "")
        display_name = item.get("display_name", cat.replace("_", " ").title())
        result.append({
            "category": cat,
            "display_name": display_name,
            "hooks": [
                "daily operations",
                "growth and expansion",
                "customer experience",
                "efficiency",
                "seasonal demand",
                "staff and team",
            ],
        })
    return result


def _derive_categories_from_profile(profile_payload: dict[str, Any], classification: list[str]) -> list[dict[str, Any]]:
    """Derive categories dynamically from industries_served. No static library — fully profile-driven fallback."""
    industries = normalize_string_list(profile_payload.get("industries_served"))
    specialties = normalize_string_list(profile_payload.get("service_specialties"))
    categories: list[dict[str, Any]] = []

    for idx, industry in enumerate(industries[:8], start=1):
        if not industry or not industry.strip():
            continue
        cat = _normalize_identifier(industry)
        if not cat:
            continue
        display = industry.strip()
        if len(display) > 60:
            display = display[:57] + "..."
        categories.append({
            "category": cat,
            "display_name": display,
            "why_fit": "From industries_served in workspace profile.",
            "priority": idx,
        })

    if not categories and specialties:
        for idx, spec in enumerate(specialties[:8], start=1):
            if not spec or not spec.strip():
                continue
            cat = _normalize_identifier(spec)
            if not cat:
                continue
            display = spec.strip()
            if len(display) > 60:
                display = display[:57] + "..."
            categories.append({
                "category": cat,
                "display_name": display,
                "why_fit": "From service_specialties in workspace profile.",
                "priority": idx,
            })

    if not categories:
        categories = [{
            "category": "profile_aligned_businesses",
            "display_name": "Profile-aligned businesses",
            "why_fit": "Add industries_served or service_specialties to your workspace profile for tailored categories.",
            "priority": 1,
        }]

    deduped = _merge_unique(categories, [], key="category", max_items=8)
    for index, item in enumerate(deduped, start=1):
        item["priority"] = index
    return deduped


def _derive_pain_points_from_profile(profile_payload: dict[str, Any], classification: list[str]) -> list[dict[str, Any]]:
    """Derive pain points dynamically from service_specialties. No static library — fully profile-driven fallback."""
    specialties = normalize_string_list(profile_payload.get("service_specialties"))
    description = (profile_payload.get("business_description") or "").strip()
    pains: list[dict[str, Any]] = []

    for idx, spec in enumerate(specialties[:6], start=1):
        if not spec or not spec.strip():
            continue
        key = _normalize_identifier(spec)
        if not key:
            continue
        label = spec.strip()
        if len(label) > 80:
            label = label[:77] + "..."
        pains.append({
            "key": key,
            "label": f"Challenges related to {label}",
            "why_relevant": "Aligned to service_specialties in workspace profile.",
        })

    if not pains and description:
        key = _normalize_identifier(description[:40])
        if key:
            pains.append({
                "key": key[:50],
                "label": "Operational challenges relevant to your services",
                "why_relevant": "Derived from business_description.",
            })

    return _merge_unique(pains, [], key="key", max_items=8)


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
    # Reject marketing/ecommerce drift
    drift_detected = any(term in lowered for term in GENERIC_STRATEGY_DRIFT_TERMS)
    if drift_detected and not any(term in profile_text for term in GENERIC_STRATEGY_DRIFT_TERMS):
        return True
    # Reject IT drift when profile clearly indicates non-IT business (solar, HVAC, legal, etc.)
    profile_is_non_it = any(sig in profile_text for sig in NON_IT_PROFILE_SIGNALS)
    has_it_drift = any(term in lowered for term in IT_DRIFT_TERMS)
    if profile_is_non_it and has_it_drift:
        return True
    return False


def _fallback_core_positioning(profile_payload: dict[str, Any], classification: list[str]) -> str:
    business_name = (profile_payload.get("business_name") or "").strip() or "This workspace"
    description = (profile_payload.get("business_description") or "").strip()
    industries = normalize_string_list(profile_payload.get("industries_served"))
    specialties = normalize_string_list(profile_payload.get("service_specialties"))
    service_area = (profile_payload.get("service_area") or "").strip()

    industries_text = ", ".join(industries[:3]) if industries else "local businesses"
    if specialties:
        specialties_text = ", ".join(specialties[:3])
    elif description:
        specialties_text = description[:80] + ("..." if len(description) > 80 else "")
    else:
        specialties_text = "profile-aligned services"

    area_suffix = f" in {service_area}" if service_area else ""
    model_hint = " and ".join(classification[:2]) if classification else "service delivery"

    return (
        f"{business_name} provides {specialties_text} for {industries_text}{area_suffix}, "
        f"with outreach focused on practical value tied to {model_hint}."
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
