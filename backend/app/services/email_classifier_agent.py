"""Email Classifier Agent — classifies inbound emails by intent."""
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

CLASSIFICATION_VALUES = [
    "interested",
    "not_interested",
    "question",
    "objection",
    "pricing_request",
    "meeting_request",
    "referral",
    "unsubscribe",
    "unknown",
]

CLASSIFIER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["classification", "confidence", "reasoning", "meeting_intent"],
    "properties": {
        "classification": {
            "type": "string",
            "enum": CLASSIFICATION_VALUES,
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reasoning": {"type": "string"},
        "meeting_intent": {"type": "boolean"},
    },
}

SYSTEM_PROMPT = """You are an Email Classifier Agent for a CRM outreach system.

Classify the inbound email into exactly one category:
- interested: positive response, wants to learn more
- not_interested: decline, not a fit
- question: asks for more information
- objection: raises concerns or objections
- pricing_request: asks about cost/pricing
- meeting_request: wants to schedule a call/meeting
- referral: refers to someone else
- unsubscribe: wants to opt out
- unknown: cannot determine intent

Also determine:
- confidence (0.0 to 1.0)
- reasoning: one sentence explaining the classification
- meeting_intent: true if the email indicates desire for a meeting/call, even if not the primary classification

Return valid JSON only matching the schema."""


class EmailClassifierError(RuntimeError):
    pass


def classify_email(
    *,
    email_body: str,
    email_subject: str | None = None,
    thread_context: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    resolved_key = (api_key or "").strip() or (settings.openai_api_key or "").strip()
    if not resolved_key:
        raise EmailClassifierError("OpenAI API key is not configured")

    user_content = ""
    if thread_context:
        user_content += f"Previous thread context:\n{thread_context}\n\n---\n\n"
    if email_subject:
        user_content += f"Subject: {email_subject}\n\n"
    user_content += f"Email body:\n{email_body[:8000]}"

    payload = {
        "model": settings.openai_model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": SYSTEM_PROMPT}]},
            {"role": "user", "content": [{"type": "input_text", "text": user_content}]},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "email_classification",
                "strict": True,
                "schema": CLASSIFIER_SCHEMA,
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
                raise EmailClassifierError(f"OpenAI request failed: {exc}") from exc

            if response.status_code == 429:
                if attempt < retries:
                    wait = base_backoff * (2 ** attempt)
                    logger.warning("Email classifier rate limited, retrying in %.2fs", wait)
                    time.sleep(wait)
                    continue
                raise EmailClassifierError("OpenAI rate limited")

            if response.status_code >= 400:
                raise EmailClassifierError(f"OpenAI error {response.status_code}: {response.text[:500]}")

            data = response.json()
            text_output = _extract_output(data)
            parsed = json.loads(text_output)
            logger.info("Email classified as %s (confidence=%.2f)", parsed.get("classification"), parsed.get("confidence", 0))
            return parsed

    raise EmailClassifierError("Email classifier failed after retries")


def _extract_output(data: dict[str, Any]) -> str:
    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        return content["text"]
    raise EmailClassifierError("Could not extract output from OpenAI response")
