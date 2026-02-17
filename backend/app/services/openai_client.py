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

AGENT1_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["website_summary", "rapport_hooks", "pain_points", "recommended_angle"],
    "properties": {
        "website_summary": {
            "type": "object",
            "additionalProperties": False,
            "required": ["one_liner", "services_offered"],
            "properties": {
                "one_liner": {"type": "string"},
                "services_offered": {"type": "array", "items": {"type": "string"}},
            },
        },
        "rapport_hooks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["type", "hook", "evidence_quote"],
                "properties": {
                    "type": {"type": "string"},
                    "hook": {"type": "string"},
                    "evidence_quote": {"type": "string"},
                },
            },
        },
        "pain_points": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["pain", "severity", "evidence_quote"],
                "properties": {
                    "pain": {"type": "string"},
                    "severity": {"type": "string"},
                    "evidence_quote": {"type": "string"},
                },
            },
        },
        "recommended_angle": {
            "type": "object",
            "additionalProperties": False,
            "required": ["primary_offer", "cta"],
            "properties": {
                "primary_offer": {"type": "string"},
                "cta": {"type": "string"},
            },
        },
    },
}

AGENT2_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["subject", "email_body", "used_signal"],
    "properties": {
        "subject": {"type": "string"},
        "email_body": {"type": "string"},
        "used_signal": {"type": "string"},
    },
}

SYSTEM_PROMPT = """You are Agent 1 in an outbound outreach system for an IT services business.

Your job is to analyze website text and extract factual signals that could justify IT-related outreach.

Return ONLY structured JSON matching the required schema.
Do not include explanations or extra text.

----------------------
OBJECTIVE
----------------------

1) Summarize what the business does.
2) Identify operational or technology-related signals that could indicate IT needs.
3) Extract conservative, evidence-backed pain points relevant to IT services.

----------------------
CATEGORIES TO EXTRACT
----------------------

1) business_summary
   - one_liner: Neutral factual summary of what the business does.

2) technology_signals
   - Explicit references to:
     - Wi-Fi
     - POS systems
     - online ordering
     - e-commerce
     - booking systems
     - digital menus
     - subscriptions
     - multiple locations
     - network usage
     - customer portals
     - software systems
   - Each must include:
     - signal
     - evidence_quote (verbatim)

3) operational_signals
   - Signals that imply scaling, growth, or infrastructure load.
   - Examples:
     - expansion
     - new locations
     - online store
     - high customer traffic
     - subscriptions
     - events
   - Each must include:
     - signal
     - evidence_quote

4) it_relevant_pain_points
   - ONLY explicit friction related to:
     - connectivity
     - reliability
     - high demand
     - scaling challenges
     - customer experience issues tied to tech
   - Each must include:
     - pain
     - severity ("low" | "medium" | "high")
     - evidence_quote

----------------------
STRICT RULES
----------------------

- Do NOT invent hidden IT problems.
- Do NOT assume internal systems.
- Do NOT speculate about cybersecurity, compliance, or infrastructure unless explicitly mentioned.
- All evidence_quote fields must be exact snippets from the text.
- If no IT-relevant pain is explicitly stated, return an empty array.
- Keep everything conservative and factual.
- Do not include sales language.
- Do not include strategic recommendations.

Return valid JSON only."""

AGENT2_SYSTEM_PROMPT = """You are Agent 2.
Write one concise outbound email draft using provided lead context.
Use a professional tone, stay factual, and do not invent claims.
Return JSON only matching the required schema."""


class OpenAIClientError(RuntimeError):
    pass


class OpenAIOutputValidationError(OpenAIClientError):
    pass


class OpenAIRateLimitError(OpenAIClientError):
    pass


class OpenAIQuotaExceededError(OpenAIRateLimitError):
    pass


def run_agent1(raw_text: str) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise OpenAIClientError("OPENAI_API_KEY is not configured")

    logger.info("Agent1 OpenAI request start text_length=%s", len(raw_text))
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = _build_payload(raw_text)
    retries = max(0, settings.openai_rate_limit_retries)
    base_backoff = max(0.1, settings.openai_rate_limit_backoff_seconds)

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
                        "OpenAI rate limited; retrying in %.2fs (attempt %s/%s)",
                        wait,
                        attempt + 1,
                        retries + 1,
                    )
                    time.sleep(wait)
                    continue
                raise OpenAIRateLimitError(error_message)

            if response.status_code >= 400:
                raise OpenAIClientError(_format_openai_error(response))

            try:
                parsed = _extract_output(response.json())
            except ValueError as exc:
                raise OpenAIClientError(f"OpenAI returned invalid JSON payload: {exc}") from exc

            _validate_agent1_output(parsed)
            logger.info("Agent1 OpenAI request end")
            return parsed

    raise OpenAIClientError("OpenAI request failed after retries")


def run_agent2(
    *,
    lead_name: str,
    company: str,
    website_url: str | None,
    snapshot_text: str,
    agent1_output: dict[str, Any],
) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise OpenAIClientError("OPENAI_API_KEY is not configured")

    logger.info("Agent2 OpenAI request start text_length=%s", len(snapshot_text))
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = _build_agent2_payload(
        lead_name=lead_name,
        company=company,
        website_url=website_url,
        snapshot_text=snapshot_text,
        agent1_output=agent1_output,
    )
    retries = max(0, settings.openai_rate_limit_retries)
    base_backoff = max(0.1, settings.openai_rate_limit_backoff_seconds)

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
                        "OpenAI rate limited; retrying in %.2fs (attempt %s/%s)",
                        wait,
                        attempt + 1,
                        retries + 1,
                    )
                    time.sleep(wait)
                    continue
                raise OpenAIRateLimitError(error_message)

            if response.status_code >= 400:
                raise OpenAIClientError(_format_openai_error(response))

            try:
                parsed = _extract_output(response.json())
            except ValueError as exc:
                raise OpenAIClientError(f"OpenAI returned invalid JSON payload: {exc}") from exc

            _validate_agent2_output(parsed)
            logger.info("Agent2 OpenAI request end")
            return parsed

    raise OpenAIClientError("OpenAI request failed after retries")


def _build_payload(raw_text: str) -> dict[str, Any]:
    return {
        "model": settings.openai_model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": SYSTEM_PROMPT}]},
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Website text to analyze:\n\n{raw_text}",
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "agent1_output",
                "strict": True,
                "schema": AGENT1_SCHEMA,
            }
        },
    }


def _build_agent2_payload(
    *,
    lead_name: str,
    company: str,
    website_url: str | None,
    snapshot_text: str,
    agent1_output: dict[str, Any],
) -> dict[str, Any]:
    context = {
        "lead_name": lead_name,
        "company": company,
        "website_url": website_url,
        "agent1_output": agent1_output,
    }
    return {
        "model": settings.openai_model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": AGENT2_SYSTEM_PROMPT}]},
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Lead context (JSON):\n"
                            f"{json.dumps(context, ensure_ascii=True)}\n\n"
                            "Website snapshot text:\n"
                            f"{snapshot_text}\n\n"
                            "Return subject, email_body, and used_signal."
                        ),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "agent2_output",
                "strict": True,
                "schema": AGENT2_SCHEMA,
            }
        },
    }


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
    message, _ = _openai_error_details(response)
    return message


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


def _validate_agent1_output(data: dict[str, Any]) -> None:
    _require_keys(data, ["website_summary", "rapport_hooks", "pain_points", "recommended_angle"], "root")

    website_summary = _require_dict(data["website_summary"], "website_summary")
    _require_keys(website_summary, ["one_liner", "services_offered"], "website_summary")
    _require_string(website_summary["one_liner"], "website_summary.one_liner")
    services_offered = website_summary["services_offered"]
    if not isinstance(services_offered, list):
        raise OpenAIOutputValidationError("website_summary.services_offered must be a list")
    for index, service in enumerate(services_offered):
        _require_string(service, f"website_summary.services_offered[{index}]")

    rapport_hooks = data["rapport_hooks"]
    if not isinstance(rapport_hooks, list):
        raise OpenAIOutputValidationError("rapport_hooks must be a list")
    for index, hook_item in enumerate(rapport_hooks):
        hook_obj = _require_dict(hook_item, f"rapport_hooks[{index}]")
        _require_keys(hook_obj, ["type", "hook", "evidence_quote"], f"rapport_hooks[{index}]")
        _require_string(hook_obj["type"], f"rapport_hooks[{index}].type")
        _require_string(hook_obj["hook"], f"rapport_hooks[{index}].hook")
        _require_string(hook_obj["evidence_quote"], f"rapport_hooks[{index}].evidence_quote")

    pain_points = data["pain_points"]
    if not isinstance(pain_points, list):
        raise OpenAIOutputValidationError("pain_points must be a list")
    for index, pain_item in enumerate(pain_points):
        pain_obj = _require_dict(pain_item, f"pain_points[{index}]")
        _require_keys(pain_obj, ["pain", "severity", "evidence_quote"], f"pain_points[{index}]")
        _require_string(pain_obj["pain"], f"pain_points[{index}].pain")
        _require_string(pain_obj["severity"], f"pain_points[{index}].severity")
        _require_string(pain_obj["evidence_quote"], f"pain_points[{index}].evidence_quote")

    recommended_angle = _require_dict(data["recommended_angle"], "recommended_angle")
    _require_keys(recommended_angle, ["primary_offer", "cta"], "recommended_angle")
    _require_string(recommended_angle["primary_offer"], "recommended_angle.primary_offer")
    _require_string(recommended_angle["cta"], "recommended_angle.cta")


def _validate_agent2_output(data: dict[str, Any]) -> None:
    _require_keys(data, ["subject", "email_body", "used_signal"], "root")
    _require_non_empty_string(data["subject"], "subject")
    _require_non_empty_string(data["email_body"], "email_body")
    _require_non_empty_string(data["used_signal"], "used_signal")


def _require_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OpenAIOutputValidationError(f"{path} must be an object")
    return value


def _require_string(value: Any, path: str) -> None:
    if not isinstance(value, str):
        raise OpenAIOutputValidationError(f"{path} must be a string")


def _require_non_empty_string(value: Any, path: str) -> None:
    _require_string(value, path)
    if not value.strip():
        raise OpenAIOutputValidationError(f"{path} must be a non-empty string")


def _require_keys(value: dict[str, Any], keys: list[str], path: str) -> None:
    missing = [key for key in keys if key not in value]
    if missing:
        raise OpenAIOutputValidationError(f"{path} missing required keys: {', '.join(missing)}")
