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

SYSTEM_PROMPT = """You are a Partnership Fit Agent. You analyze a company's website content to determine if they are a good partnership candidate.

Given:
- Website text content
- The workspace's business profile (who WE are)
- The discovery intent (what kind of partner the user is looking for)

Your job:
1. Summarize what the company does (company_summary)
2. Classify the partnership_type (subcontractor, vendor, integrator, reseller, referral_partner, field_service_partner, or other descriptive type)
3. Determine fit_score (0.0 to 1.0) based on alignment with the workspace business and discovery intent
4. List concrete reasons for the fit (evidence from website text)
5. Suggest a recommended_outreach_angle (how to approach them)
6. Extract any contact emails found in the website text
7. Extract contact form URL if found
8. Identify the company's industry

RULES:
- Only use information from the provided website text
- Do NOT invent facts or capabilities not evidenced in the text
- fit_score should be 0.0-0.3 for poor fit, 0.4-0.6 for moderate, 0.7-1.0 for strong fit
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
