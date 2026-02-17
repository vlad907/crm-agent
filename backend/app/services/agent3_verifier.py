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
AGENT3_TEMPERATURE = 0.1

AGENT3_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["send", "hold"],
        },
        "issues": {
            "type": "array",
            "items": {"type": "string"},
        },
        "final_email": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "subject": {"type": "string"},
                "email_body": {"type": "string"},
            },
            "required": ["subject", "email_body"],
        },
    },
    "required": ["decision", "issues", "final_email"],
}

AGENT3_SYSTEM_PROMPT = """You are Agent 3, an outbound email verifier.
Return JSON only. No markdown. No backticks.
Rules:
- Do not introduce facts not supported by website text or agent1 evidence.
- Keep tone professional, human, and non-spammy.
- Exactly one clear CTA.
- No aggressive language and no guarantees.
- If unsupported claims exist, decision must be "hold" and issues must explain why.
- You may make minor tone edits in final_email, but do not add new factual claims."""


class Agent3VerifierError(RuntimeError):
    pass


class Agent3RateLimitError(Agent3VerifierError):
    pass


def verify_email_with_agent3(
    *,
    lead_name: str,
    company: str,
    website_url: str | None,
    snapshot_text: str,
    agent1_output: dict[str, Any],
    draft_subject: str,
    draft_body: str,
) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise Agent3VerifierError("OPENAI_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = _build_payload(
        lead_name=lead_name,
        company=company,
        website_url=website_url,
        snapshot_text=snapshot_text,
        agent1_output=agent1_output,
        draft_subject=draft_subject,
        draft_body=draft_body,
    )
    retries = max(0, settings.openai_rate_limit_retries)
    base_backoff = max(0.1, settings.openai_rate_limit_backoff_seconds)

    logger.info("Agent3 verifier start company=%s", company)
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        for attempt in range(retries + 1):
            try:
                response = client.post(OPENAI_RESPONSES_URL, headers=headers, json=payload)
            except httpx.RequestError as exc:
                if attempt < retries:
                    wait = base_backoff * (2**attempt)
                    logger.warning("Agent3 network error retry in %.2fs attempt=%s", wait, attempt + 1)
                    time.sleep(wait)
                    continue
                raise Agent3VerifierError(f"OpenAI request failed: {exc}") from exc

            if response.status_code == 429:
                error_message = _format_openai_error(response)
                if attempt < retries:
                    retry_after = _retry_after_seconds(response)
                    wait = max(base_backoff * (2**attempt), retry_after or 0.0)
                    logger.warning("Agent3 rate limited retry in %.2fs attempt=%s", wait, attempt + 1)
                    time.sleep(wait)
                    continue
                raise Agent3RateLimitError(error_message)

            if 500 <= response.status_code <= 599 and attempt < retries:
                wait = base_backoff * (2**attempt)
                logger.warning("Agent3 server error retry in %.2fs attempt=%s", wait, attempt + 1)
                time.sleep(wait)
                continue

            if response.status_code >= 400:
                raise Agent3VerifierError(_format_openai_error(response))

            try:
                parsed = _extract_output(response.json())
            except ValueError as exc:
                raise Agent3VerifierError(f"OpenAI returned invalid JSON payload: {exc}") from exc

            verdict = _validate_verdict(parsed)
            logger.info("Agent3 verifier end decision=%s", verdict["decision"])
            return verdict

    raise Agent3VerifierError("OpenAI request failed after retries")


def _build_payload(
    *,
    lead_name: str,
    company: str,
    website_url: str | None,
    snapshot_text: str,
    agent1_output: dict[str, Any],
    draft_subject: str,
    draft_body: str,
) -> dict[str, Any]:
    context = {
        "lead_name": lead_name,
        "company": company,
        "website_url": website_url,
        "agent1_output": agent1_output,
        "draft_email": {
            "subject": draft_subject,
            "email_body": draft_body,
        },
    }
    return {
        "model": settings.openai_model,
        "temperature": AGENT3_TEMPERATURE,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": AGENT3_SYSTEM_PROMPT}]},
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Verify this outbound email.\n\n"
                            "Context (JSON):\n"
                            f"{json.dumps(context, ensure_ascii=True)}\n\n"
                            "Website snapshot text:\n"
                            f"{snapshot_text}"
                        ),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "agent3_verdict",
                "strict": True,
                "schema": AGENT3_SCHEMA,
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


def _validate_verdict(data: dict[str, Any]) -> dict[str, Any]:
    allowed_root_keys = {"decision", "issues", "final_email"}
    unknown_root = set(data.keys()) - allowed_root_keys
    if unknown_root:
        raise Agent3VerifierError(f"Unexpected keys in verdict: {', '.join(sorted(unknown_root))}")

    decision = data.get("decision")
    if decision not in {"send", "hold"}:
        raise Agent3VerifierError("decision must be one of: send, hold")

    final_email = data.get("final_email")
    if not isinstance(final_email, dict):
        raise Agent3VerifierError("final_email must be an object")

    allowed_email_keys = {"subject", "email_body"}
    unknown_email = set(final_email.keys()) - allowed_email_keys
    if unknown_email:
        raise Agent3VerifierError(f"Unexpected final_email keys: {', '.join(sorted(unknown_email))}")

    subject = final_email.get("subject")
    email_body = final_email.get("email_body")
    if not isinstance(subject, str) or not subject.strip():
        raise Agent3VerifierError("final_email.subject must be a non-empty string")
    if not isinstance(email_body, str) or not email_body.strip():
        raise Agent3VerifierError("final_email.email_body must be a non-empty string")
    if "```" in subject or "```" in email_body:
        raise Agent3VerifierError("final_email must not contain markdown fences")

    issues = data.get("issues", [])
    if not isinstance(issues, list):
        raise Agent3VerifierError("issues must be an array of strings")
    for issue in issues:
        if not isinstance(issue, str):
            raise Agent3VerifierError("issues must be an array of strings")

    return {
        "decision": decision,
        "issues": issues,
        "final_email": {"subject": subject.strip(), "email_body": email_body.strip()},
    }


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


def _retry_after_seconds(response: httpx.Response) -> float | None:
    retry_after = response.headers.get("retry-after")
    if retry_after is None:
        return None
    try:
        seconds = float(retry_after)
    except ValueError:
        return None
    return max(0.0, seconds)
