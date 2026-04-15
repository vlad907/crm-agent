"""Partner Search Agent — uses OpenAI web search to find potential vendor/MSP partners."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
REQUEST_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)

SEARCH_RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["companies"],
    "properties": {
        "companies": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["company_name", "website", "description", "relevance_reason"],
                "properties": {
                    "company_name": {"type": "string"},
                    "website": {"type": "string"},
                    "description": {"type": "string"},
                    "relevance_reason": {"type": "string"},
                },
            },
        },
    },
}

SYSTEM_PROMPT = """You are a business development researcher. Your job is to find real companies that match a specific partnership opportunity.

The user will describe what kind of partner/vendor/MSP they are looking for. Use web search to find REAL companies that match.

Focus on finding:
- National or regional vendors/MSPs who subcontract work to local providers
- Companies that manage large-scale deployments and need field service partners
- Managed service providers that need local technical talent
- Large contractors who farm out installation, maintenance, or service work

For each company found, provide:
- company_name: the actual company name
- website: their real website URL (must start with http:// or https://)
- description: what they do (1-2 sentences)
- relevance_reason: why they match the search intent

RULES:
- Only return REAL companies you found via web search
- Every website URL must be a real, working URL
- Return between 5-15 companies
- Prioritize companies that are known to use subcontractors or local partners
- Do NOT invent companies or URLs

Return valid JSON matching the schema."""


class PartnerSearchError(RuntimeError):
    pass


def search_for_partners(
    *,
    search_intent: str,
    api_key: str | None = None,
    max_results: int = 15,
) -> list[dict[str, str]]:
    resolved_key = (api_key or "").strip() or (settings.openai_api_key or "").strip()
    if not resolved_key:
        raise PartnerSearchError("OpenAI API key is not configured")

    user_content = (
        f"Find up to {max_results} real companies matching this partnership opportunity:\n\n"
        f"{search_intent}\n\n"
        f"Search the web thoroughly. Return real company names and their actual website URLs."
    )

    payload = {
        "model": "gpt-4o",
        "tools": [{"type": "web_search_preview"}],
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": SYSTEM_PROMPT}]},
            {"role": "user", "content": [{"type": "input_text", "text": user_content}]},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "partner_search_results",
                "strict": True,
                "schema": SEARCH_RESULT_SCHEMA,
            }
        },
    }

    headers = {
        "Authorization": f"Bearer {resolved_key}",
        "Content-Type": "application/json",
    }
    retries = 2
    base_backoff = 2.0

    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        for attempt in range(retries + 1):
            try:
                response = client.post(OPENAI_RESPONSES_URL, headers=headers, json=payload)
            except httpx.RequestError as exc:
                raise PartnerSearchError(f"OpenAI request failed: {exc}") from exc

            if response.status_code == 429:
                if attempt < retries:
                    wait = base_backoff * (2 ** attempt)
                    logger.warning("Partner search rate limited, retrying in %.2fs", wait)
                    time.sleep(wait)
                    continue
                raise PartnerSearchError("OpenAI rate limited")

            if response.status_code >= 400:
                raise PartnerSearchError(f"OpenAI error {response.status_code}: {response.text[:500]}")

            data = response.json()
            text_output = _extract_output(data)
            parsed = json.loads(text_output)
            companies = parsed.get("companies", [])
            valid = [
                c for c in companies
                if c.get("website", "").startswith(("http://", "https://"))
            ]
            logger.info("Partner search found %d companies (%d valid)", len(companies), len(valid))
            return valid[:max_results]

    raise PartnerSearchError("Partner search failed after retries")


def _extract_output(data: dict[str, Any]) -> str:
    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        return content["text"]
    raise PartnerSearchError("Could not extract output from OpenAI response")
