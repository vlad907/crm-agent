"""Response Draft Agent — generates contextual reply suggestions for inbound emails."""
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

RESPONSE_DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["subject", "reply_body"],
    "properties": {
        "subject": {"type": "string"},
        "reply_body": {"type": "string"},
    },
}

SYSTEM_PROMPT = """You are a Response Draft Agent for a CRM outreach system. Draft a professional reply to an inbound email.

INPUTS:
- The inbound message you are replying to
- Previous thread messages (conversation history)
- Workspace business profile (who we are)
- AI strategy (tone, CTA, guardrails)
- Email classification (what kind of reply this is)

RULES:
- Be contextual to the conversation — reference what they said
- Do NOT hallucinate claims about our services beyond what the workspace profile states
- Follow the workspace tone (formal, friendly, consultative, etc.)
- Move the conversation forward: suggest a meeting, call, or next step when appropriate
- For meeting_request classification: propose scheduling a call/meeting
- For question classification: answer directly and offer further discussion
- For interested classification: reinforce value and propose next step
- For objection classification: address the concern professionally
- Keep it concise (under 200 words for the reply body)
- Subject should be a natural reply subject (Re: original subject)

Return valid JSON only matching the schema."""


class ResponseDraftError(RuntimeError):
    pass


def generate_response_draft(
    *,
    inbound_body: str,
    inbound_subject: str | None = None,
    thread_history: str | None = None,
    classification: str | None = None,
    workspace_profile: dict[str, Any] | None = None,
    ai_strategy: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    resolved_key = (api_key or "").strip() or (settings.openai_api_key or "").strip()
    if not resolved_key:
        raise ResponseDraftError("OpenAI API key is not configured")

    user_content = ""
    if workspace_profile:
        parts = []
        if workspace_profile.get("business_name"):
            parts.append(f"Business: {workspace_profile['business_name']}")
        if workspace_profile.get("business_description"):
            parts.append(f"Description: {workspace_profile['business_description']}")
        if workspace_profile.get("preferred_tone"):
            parts.append(f"Tone: {workspace_profile['preferred_tone']}")
        if parts:
            user_content += f"Workspace profile:\n" + "\n".join(parts) + "\n\n"

    if ai_strategy:
        gen = ai_strategy.get("generated_strategy") or {}
        if isinstance(gen, dict):
            guardrails = gen.get("guardrails") or {}
            if isinstance(guardrails, dict) and guardrails.get("do_not_claim"):
                user_content += f"Guardrails — do not claim: {', '.join(guardrails['do_not_claim'])}\n\n"

    if classification:
        user_content += f"Email classification: {classification}\n\n"

    if thread_history:
        user_content += f"Previous messages in thread:\n{thread_history}\n\n---\n\n"

    if inbound_subject:
        user_content += f"Inbound subject: {inbound_subject}\n"
    user_content += f"Inbound message:\n{inbound_body[:8000]}"

    payload = {
        "model": settings.openai_model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": SYSTEM_PROMPT}]},
            {"role": "user", "content": [{"type": "input_text", "text": user_content}]},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "response_draft",
                "strict": True,
                "schema": RESPONSE_DRAFT_SCHEMA,
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
                raise ResponseDraftError(f"OpenAI request failed: {exc}") from exc

            if response.status_code == 429:
                if attempt < retries:
                    wait = base_backoff * (2 ** attempt)
                    logger.warning("Response draft agent rate limited, retrying in %.2fs", wait)
                    time.sleep(wait)
                    continue
                raise ResponseDraftError("OpenAI rate limited")

            if response.status_code >= 400:
                raise ResponseDraftError(f"OpenAI error {response.status_code}: {response.text[:500]}")

            data = response.json()
            text_output = _extract_output(data)
            parsed = json.loads(text_output)
            logger.info("Response draft generated, subject=%s", parsed.get("subject", "")[:50])
            return parsed

    raise ResponseDraftError("Response draft agent failed after retries")


def _extract_output(data: dict[str, Any]) -> str:
    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        return content["text"]
    raise ResponseDraftError("Could not extract output from OpenAI response")
