"""Partnership Fit Agent — analyzes website content to assess partnership potential."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
REQUEST_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0)

PARTNERSHIP_FIT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "company_summary",
        "partnership_type",
        "fit_score",
        "reasons",
        "recommended_outreach_angle",
        "contact_emails",
        "contact_form_url",
        "industry",
    ],
    "properties": {
        "company_summary": {"type": "string"},
        "partnership_type": {
            "type": "string",
            "description": "e.g. subcontractor, vendor, integrator, reseller, referral_partner",
        },
        "fit_score": {"type": "number", "minimum": 0, "maximum": 1},
        "reasons": {
            "type": "array",
            "items": {"type": "string"},
        },
        "recommended_outreach_angle": {"type": "string"},
        "contact_emails": {
            "type": "array",
            "items": {"type": "string"},
        },
        "contact_form_url": {
            "type": ["string", "null"],
        },
        "industry": {
            "type": ["string", "null"],
        },
    },
}

SYSTEM_PROMPT = """You are a Partnership Fit Agent. You analyze a company's website to assess whether they are a good candidate for a SUBCONTRACTOR / VENDOR NETWORK partnership.

CONTEXT — what "partnership" means here:
The workspace owner is a local field service or IT contractor. They are NOT trying to sell services TO this company. They want to JOIN this company's vendor/subcontractor network so that when the company has field service work in the workspace's service area, they send that work to the workspace owner. This is a referral-in / subcontracting arrangement.

Given:
- Website text content
- The workspace's business profile (who WE are — our services, specialties, service area)
- The discovery intent (what kind of subcontracting or referral relationship we're looking for)

Your job:
1. Summarize what the target company does (company_summary) — focus on whether they dispatch or subcontract field work
2. Classify partnership_type: use "subcontractor", "vendor_network", "referral_partner", or "field_service_partner" as appropriate
3. Determine fit_score (0.0–1.0):
   - High (0.7–1.0): Company clearly uses subcontractors or has a vendor network in our service type and area
   - Medium (0.4–0.6): Company likely has occasional needs for our type of services but no explicit vendor program
   - Low (0.0–0.3): No overlap with our services or geography
4. List concrete reasons for the fit — quote specific evidence from the website (e.g. "has a vendor sign-up page", "operates nationwide and needs local contractors", "lists plumbers and IT vendors as partner types")
5. recommended_outreach_angle: Write 1–2 sentences describing how to ask to JOIN their network. Be specific. E.g. "They dispatch on-site technicians across NorCal — ask to be added as their local IT/low-voltage subcontractor for jobs in our service area." STRICT RULES: (a) NEVER suggest offering or selling services TO the company. (b) NEVER suggest a "Free Health Check," audit, or consultation. (c) If the company is an IT provider or MSP, they need LOCAL FIELD TECHNICIANS dispatched — not managed IT sold to them. The angle is always: "we want to do on-site work FOR them in our area."
6. Extract contact emails from the website text
7. Extract contact form URL if present (especially vendor/partner sign-up forms)
8. Identify the company's industry

RULES:
- Only use information from the provided website text — do NOT invent facts
- fit_score 0.0–0.3 = poor fit, 0.4–0.6 = moderate, 0.7–1.0 = strong
- NEVER use placeholder brackets like [Your Name] — use actual values or omit
- Return valid JSON only matching the schema"""


class PartnershipAgentError(RuntimeError):
    pass


def run_partnership_fit_agent(
    *,
    website_text: str,
    discovery_intent: str,
    workspace_profile: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    resolved_key = (api_key or "").strip() or (settings.openai_api_key or "").strip()
    if not resolved_key:
        raise PartnershipAgentError("OpenAI API key is not configured")

    profile_text = ""
    if workspace_profile:
        parts = []
        if workspace_profile.get("business_name"):
            parts.append(f"Business: {workspace_profile['business_name']}")
        if workspace_profile.get("business_description"):
            parts.append(f"Description: {workspace_profile['business_description']}")
        if workspace_profile.get("service_specialties"):
            parts.append(f"Specialties: {', '.join(workspace_profile['service_specialties'])}")
        if workspace_profile.get("service_area"):
            parts.append(f"Service area: {workspace_profile['service_area']}")
        profile_text = "\n".join(parts)

    user_content = f"Discovery intent: {discovery_intent}\n\n"
    if profile_text:
        user_content += f"Our business profile:\n{profile_text}\n\n"
    user_content += f"Website text to analyze:\n\n{website_text[:15000]}"

    payload = {
        "model": settings.openai_model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": SYSTEM_PROMPT}]},
            {"role": "user", "content": [{"type": "input_text", "text": user_content}]},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "partnership_fit_output",
                "strict": True,
                "schema": PARTNERSHIP_FIT_SCHEMA,
            }
        },
    }

    headers = {
        "Authorization": f"Bearer {resolved_key}",
        "Content-Type": "application/json",
    }
    retries = max(0, settings.openai_rate_limit_retries)
    base_backoff = max(0.1, settings.openai_rate_limit_backoff_seconds)

    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        for attempt in range(retries + 1):
            try:
                response = client.post(OPENAI_RESPONSES_URL, headers=headers, json=payload)
            except httpx.RequestError as exc:
                raise PartnershipAgentError(f"OpenAI request failed: {exc}") from exc

            if response.status_code == 429:
                if attempt < retries:
                    wait = base_backoff * (2 ** attempt)
                    logger.warning("Partnership agent rate limited, retrying in %.2fs", wait)
                    time.sleep(wait)
                    continue
                raise PartnershipAgentError("OpenAI rate limited")

            if response.status_code >= 400:
                raise PartnershipAgentError(f"OpenAI error {response.status_code}: {response.text[:500]}")

            data = response.json()
            text_output = _extract_output(data)
            parsed = json.loads(text_output)
            logger.info("Partnership Fit Agent completed, fit_score=%.2f", parsed.get("fit_score", 0))
            return parsed

    raise PartnershipAgentError("Partnership agent failed after retries")


def _extract_output(data: dict[str, Any]) -> str:
    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        return content["text"]
    raise PartnershipAgentError("Could not extract output from OpenAI response")
