from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.core.config import settings
from app.services.agent_outreach_mode import (
    attach_agent1_legacy_aliases,
    build_agent2_mode_instructions,
    compute_agent2_outreach_mode,
    ensure_agent1_canonical_fields,
)

logger = logging.getLogger(__name__)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
REQUEST_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0)

AGENT1_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "website_summary",
        "pain_points_detected",
        "signals_found",
        "recommended_angle",
        "confidence_score",
    ],
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
        "pain_points_detected": {
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
        "signals_found": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["type", "signal", "evidence_quote"],
                "properties": {
                    "type": {"type": "string"},
                    "signal": {"type": "string"},
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
        "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
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

SYSTEM_PROMPT = """You are Agent 1 in an outbound outreach system (often IT / commercial services).

Analyze ONLY the provided website text. Return ONLY JSON matching the schema — no markdown, no prose.

----------------------
OUTPUT FIELDS
----------------------

1) website_summary — one_liner + services_offered (factual).

2) signals_found — array of {type, signal, evidence_quote}:
   - Technology/ops cues visible on the site: Wi‑Fi, POS, online ordering, reservations, ecommerce, events, multiple locations, etc.
   - type: short label e.g. "technology" or "operational".
   - signal: one-line description of what you observed.
   - evidence_quote: VERBATIM snippet from the website text (must appear in the input).

3) pain_points_detected — array of {pain, severity, evidence_quote}:
   - ONLY issues clearly supported by the website (explicit or directly quoted frustration, downtime, peak demand, reliability, etc.).
   - severity: "low" | "medium" | "high".
   - If nothing is clearly evidenced, return [].

4) confidence_score — float 0.0–1.0:
   - How strong the combined evidence is for outreach (more concrete quotes + clearer signals → higher).
   - Use 0.0–0.4 when signals are thin or generic; 0.5+ only when pain_points_detected has solid quotes OR multiple strong signals.

5) recommended_angle — primary_offer + cta (conservative, for internal handoff).

----------------------
STRICT RULES
----------------------

- Do NOT invent problems, stack, or internal issues not in the text.
- Do NOT fill pain_points_detected from guesses. Empty array is correct when unclear.
- All evidence_quote values must be copied from the website text (short excerpts ok).
- No sales language in Agent 1 output.

Return valid JSON only."""

AGENT2_SYSTEM_PROMPT = """You are Agent 2. Write one concise outbound email (JSON: subject, email_body, used_signal).

SERVICE + CTA:
- Name what WE offer using core_positioning (solar vs IT vs other — match the business).
- Use the exact CTA label from strategy when provided. Do not swap unrelated CTAs (e.g. network assessment vs site assessment).
- Avoid filler: "enhance operations," "support your goals," "explore opportunities."

The user message gives MODE: SIGNAL, FALLBACK, or SOFT. Obey MODE rules before anything else.

SIGNATURE:
- If sender contact info is provided, use the real name, title, phone, and email in the sign-off.
- NEVER use placeholder brackets like [Your Name], [Your Position], [Your Phone Number], or [Your Email].
- If sender info is missing, end with a simple "Best regards" without placeholders.

Return JSON only matching the required schema."""


class OpenAIClientError(RuntimeError):
    pass


class OpenAIConfigurationError(OpenAIClientError):
    pass


class OpenAIOutputValidationError(OpenAIClientError):
    pass


class OpenAIRateLimitError(OpenAIClientError):
    pass


class OpenAIQuotaExceededError(OpenAIRateLimitError):
    pass


def run_agent1(raw_text: str, *, api_key: str | None = None) -> dict[str, Any]:
    resolved_api_key = (api_key or "").strip() or (settings.openai_api_key or "").strip()
    if not resolved_api_key:
        raise OpenAIConfigurationError("OpenAI API key is not configured")

    logger.info("Agent1 OpenAI request start text_length=%s", len(raw_text))
    headers = {
        "Authorization": f"Bearer {resolved_api_key}",
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
            parsed = attach_agent1_legacy_aliases(parsed)
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
    strategy_context: dict[str, Any] | None = None,
    sender_info: dict[str, str] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    resolved_api_key = (api_key or "").strip() or (settings.openai_api_key or "").strip()
    if not resolved_api_key:
        raise OpenAIConfigurationError("OpenAI API key is not configured")

    logger.info("Agent2 OpenAI request start text_length=%s", len(snapshot_text))
    headers = {
        "Authorization": f"Bearer {resolved_api_key}",
        "Content-Type": "application/json",
    }
    payload = _build_agent2_payload(
        lead_name=lead_name,
        company=company,
        website_url=website_url,
        snapshot_text=snapshot_text,
        agent1_output=agent1_output,
        strategy_context=strategy_context,
        sender_info=sender_info,
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


def augment_agent1_with_strategy_fallbacks(
    agent1_output: dict[str, Any],
    strategy_context: dict[str, Any],
) -> dict[str, Any]:
    """Deprecated: strategy fallbacks are applied in Agent 2 (fallback mode), not merged into Agent 1."""
    _ = strategy_context
    return dict(agent1_output)


def _build_agent2_payload(
    *,
    lead_name: str,
    company: str,
    website_url: str | None,
    snapshot_text: str,
    agent1_output: dict[str, Any],
    strategy_context: dict[str, Any] | None = None,
    sender_info: dict[str, str] | None = None,
) -> dict[str, Any]:
    strategy = dict(strategy_context or {})
    agent1_canon = ensure_agent1_canonical_fields(agent1_output)
    outreach_mode = compute_agent2_outreach_mode(agent1_canon, strategy)
    matched = strategy.get("matched_category") or strategy.get("matched_workspace_category")
    strategy["matched_category"] = matched
    strategy["agent2_outreach_mode"] = outreach_mode

    context = {
        "lead_name": lead_name,
        "company": company,
        "website_url": website_url,
        "agent1_output": agent1_canon,
        "strategy_context": strategy,
        "agent2_outreach_mode": outreach_mode,
        "matched_category": matched,
    }

    mode_instructions = build_agent2_mode_instructions(outreach_mode, agent1_canon, strategy)
    core_pos = strategy.get("core_positioning") or ""
    cta_detail = strategy.get("selected_cta_recommendation")
    if not cta_detail:
        gen = strategy.get("generated_strategy") or {}
        ctas = gen.get("cta_recommendations") if isinstance(gen, dict) else []
        cta_detail = ctas[0] if isinstance(ctas, list) and ctas else {}
    cta_label = cta_detail.get("label", "") if isinstance(cta_detail, dict) else ""
    service_angles = strategy.get("fallback_service_angles_for_category") or []
    service_angles_text = ", ".join(service_angles[:5]) if isinstance(service_angles, list) else ""

    strategy_instructions = (
        "Strategy rules:\n"
        "- If strategy_available is true, use core_positioning, ideal_customers, rapport_points, guardrails, preferred_tone, outreach_style.\n"
        f"- core_positioning (what we offer): {core_pos or '(use generated_strategy.core_positioning)'}\n"
    )
    if cta_label:
        strategy_instructions += f"- Use this CTA: {cta_label}\n"
    if service_angles_text:
        strategy_instructions += f"- Service angles for this lead category: {service_angles_text}\n"
    strategy_instructions += (
        "- Do NOT be vague about what we sell. Name the service and use the specific CTA.\n"
        f"{mode_instructions}\n"
        "- used_signal: briefly cite which evidence or angle you used (signal quote key, fallback topic, or website fact).\n"
    )

    sender_block = ""
    if sender_info:
        from app.services.sender_signature import get_sender_prompt_context
        ctx = get_sender_prompt_context(sender_info)
        if ctx:
            sender_block = f"\n{ctx}\n"

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
                            f"{strategy_instructions}\n"
                            f"{sender_block}"
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
    _require_keys(
        data,
        ["website_summary", "pain_points_detected", "signals_found", "recommended_angle", "confidence_score"],
        "root",
    )

    website_summary = _require_dict(data["website_summary"], "website_summary")
    _require_keys(website_summary, ["one_liner", "services_offered"], "website_summary")
    _require_string(website_summary["one_liner"], "website_summary.one_liner")
    services_offered = website_summary["services_offered"]
    if not isinstance(services_offered, list):
        raise OpenAIOutputValidationError("website_summary.services_offered must be a list")
    for index, service in enumerate(services_offered):
        _require_string(service, f"website_summary.services_offered[{index}]")

    signals_found = data["signals_found"]
    if not isinstance(signals_found, list):
        raise OpenAIOutputValidationError("signals_found must be a list")
    for index, sig_item in enumerate(signals_found):
        sig_obj = _require_dict(sig_item, f"signals_found[{index}]")
        _require_keys(sig_obj, ["type", "signal", "evidence_quote"], f"signals_found[{index}]")
        _require_string(sig_obj["type"], f"signals_found[{index}].type")
        _require_string(sig_obj["signal"], f"signals_found[{index}].signal")
        _require_string(sig_obj["evidence_quote"], f"signals_found[{index}].evidence_quote")

    pain_points_detected = data["pain_points_detected"]
    if not isinstance(pain_points_detected, list):
        raise OpenAIOutputValidationError("pain_points_detected must be a list")
    for index, pain_item in enumerate(pain_points_detected):
        pain_obj = _require_dict(pain_item, f"pain_points_detected[{index}]")
        _require_keys(pain_obj, ["pain", "severity", "evidence_quote"], f"pain_points_detected[{index}]")
        _require_string(pain_obj["pain"], f"pain_points_detected[{index}].pain")
        _require_string(pain_obj["severity"], f"pain_points_detected[{index}].severity")
        _require_string(pain_obj["evidence_quote"], f"pain_points_detected[{index}].evidence_quote")

    cs = data["confidence_score"]
    if not isinstance(cs, (int, float)):
        raise OpenAIOutputValidationError("confidence_score must be a number")
    if not (0.0 <= float(cs) <= 1.0):
        raise OpenAIOutputValidationError("confidence_score must be between 0 and 1")

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
