"""Response Draft Agent — generates contextual reply suggestions for inbound emails.

Supports both OpenAI and Anthropic (Claude) as generation backends.
Claude is preferred for partner/vendor inquiry emails due to better instruction-following.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
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

SYSTEM_PROMPT = """You are a Response Draft Agent for a CRM outreach system. You draft professional emails.

INPUTS:
- Context about the email to write (could be a reply OR cold outreach)
- Previous thread messages (conversation history, if any)
- Workspace business profile (who we are)
- AI strategy (tone, CTA, guardrails)
- Email classification (what kind of email this is)

RULES:
- Be contextual — reference what you know about the recipient/company
- Do NOT hallucinate claims about our services beyond what the workspace profile states
- Follow the workspace tone (formal, friendly, consultative, etc.)
- Move the conversation forward: suggest a meeting, call, or next step when appropriate
- For meeting_request classification: propose scheduling a call/meeting
- For question classification: answer directly and offer further discussion
- For interested classification: reinforce value and propose next step
- For objection classification: address the concern professionally
- For cold_outreach classification: write a COLD OUTREACH email (NOT a reply). Address the recipient company by name. Pitch our services/partnership value. Do NOT say "thank you for reaching out" — we are reaching out to them.

- Keep it concise (under 200 words for the reply body)
- Subject should be compelling and specific to the recipient
- If sender contact info is provided, use the real name, title, phone, and email in the signature
- NEVER use placeholder brackets like [Your Name], [Your Position], [Recipient's Name] — use actual values or omit

Return valid JSON only matching the schema: {"subject": "...", "reply_body": "..."}"""

def _build_vendor_inquiry_prompt(
    workspace_profile: dict[str, Any] | None,
    sender_info: dict[str, str] | None,
) -> str:
    """Build the vendor inquiry system prompt dynamically from the user's actual profile.

    The EXAMPLE section uses their real business name, service area, and specialties so
    the AI sees a concrete pattern that matches what should actually be in the output.
    """
    profile = workspace_profile or {}
    business_name = (profile.get("business_name") or "our company").strip()
    service_area = (profile.get("service_area") or "our service area").strip()
    specs = [s.strip() for s in (profile.get("service_specialties") or []) if s and s.strip()]

    if len(specs) >= 3:
        spec_str = ", ".join(specs[:-1]) + f", and {specs[-1]}"
    elif len(specs) == 2:
        spec_str = f"{specs[0]} and {specs[1]}"
    elif specs:
        spec_str = specs[0]
    else:
        spec_str = "IT and low-voltage services"

    example_subject = f"Subcontractor Inquiry — Field Coverage in {service_area}"
    example_body = (
        f"Noticed you handle commercial on-site installs in the region.  "
        f"We're {business_name}, a licensed contractor in {service_area} covering {spec_str}.  "
        f"When you have on-site work in our area, would it make sense to add us to your subcontractor list?"
    )

    return f"""You are writing a SHORT vendor/subcontractor inquiry email. Goal: get added to the recipient's subcontractor or vendor network so THEY send on-site jobs TO US. We are NOT selling anything to them.

FORMAT — exactly 3 sentences, under 90 words total body:

  Sentence 1 — PERSONALIZED OBSERVATION about the recipient:
    A casual, factual statement about what they do, their specialty, or their coverage area.
    Use openers like "Noticed you", "Saw you", "Came across you".
    This shows we looked them up and makes the email feel personal.
    MUST NOT be a compliment. Do not use: "impressive", "great work", "I was impressed",
    "commitment to", "standing out", "love what you do", "truly stands out".

  Sentence 2 — WHO WE ARE:
    Introduce our company ({business_name}), our service area ({service_area}), and the specific on-site work we cover ({spec_str}).

  Sentence 3 — THE ASK:
    One direct question asking to be added to their subcontractor or vendor list.

PROHIBITED — any of these = output is wrong:
- Compliment words: "impressive", "I was impressed", "I admire", "great work", "commitment to", "stands out"
- Selling to them: "we can help your business", "complement your offerings", "enhance your operations", "our services would be perfect for you"
- "Free Health Check", "audit", "consultation", or "assessment"
- Filler closings: "Looking forward to connecting", "hope this finds you well", "I'd love to explore how we can collaborate"

CORRECT EXAMPLE (using the sender's actual values — yours should match this pattern):
  Subject: {example_subject}
  Body: {example_body}

Return valid JSON only: {{"subject": "...", "reply_body": "..."}}"""


class ResponseDraftError(RuntimeError):
    pass


def _build_vendor_inquiry_content(
    *,
    context_body: str,
    workspace_profile: dict[str, Any] | None,
    sender_info: dict[str, str] | None,
) -> str:
    """Build a structured user message for the VENDOR_INQUIRY_PROMPT.

    The context_body already contains the curated recipient info built in partnerships.py.
    We add our sender info separately so the AI can clearly distinguish recipient vs sender.
    business_description is intentionally omitted — it triggers sales-pitch mode.
    """
    lines: list[str] = []

    # --- Recipient section (what we know about the company we're writing to) ---
    lines.append("=== RECIPIENT (who we're writing to) ===")
    lines.append(context_body[:2000])
    lines.append("")

    # --- Our info (minimal — only what's needed for sentence 2 and the signature) ---
    lines.append("=== OUR BUSINESS (the sender) ===")
    if workspace_profile:
        if workspace_profile.get("business_name"):
            lines.append(f"Company: {workspace_profile['business_name']}")
        if workspace_profile.get("service_area"):
            lines.append(f"Service area: {workspace_profile['service_area']}")
        if workspace_profile.get("service_specialties"):
            lines.append(f"Services we cover: {', '.join(workspace_profile['service_specialties'])}")
    if sender_info:
        if sender_info.get("name"):
            lines.append(f"Sender name: {sender_info['name']}")
        if sender_info.get("title"):
            lines.append(f"Sender title: {sender_info['title']}")
        if sender_info.get("phone"):
            lines.append(f"Sender phone: {sender_info['phone']}")
        if sender_info.get("email"):
            lines.append(f"Sender email: {sender_info['email']}")
    lines.append("")
    lines.append(
        "Write the 3-sentence vendor inquiry email. "
        "Sentence 1: casual observation about what THEY do (no compliments). "
        "Sentence 2: who WE are + our service area + what we cover. "
        "Sentence 3: ask to be added to their subcontractor list."
    )

    return "\n".join(lines)


def _build_user_content(
    *,
    inbound_body: str,
    inbound_subject: str | None,
    thread_history: str | None,
    classification: str | None,
    workspace_profile: dict[str, Any] | None,
    ai_strategy: dict[str, Any] | None,
    sender_info: dict[str, str] | None,
) -> str:
    # Partner vendor inquiry uses its own structured format — completely separate path
    if classification == "partner_vendor_inquiry":
        return _build_vendor_inquiry_content(
            context_body=inbound_body,
            workspace_profile=workspace_profile,
            sender_info=sender_info,
        )

    user_content = ""

    if workspace_profile:
        parts = []
        if workspace_profile.get("business_name"):
            parts.append(f"Business: {workspace_profile['business_name']}")
        if workspace_profile.get("business_description"):
            parts.append(f"Description: {workspace_profile['business_description']}")
        if workspace_profile.get("preferred_tone"):
            parts.append(f"Tone: {workspace_profile['preferred_tone']}")
        if workspace_profile.get("service_area"):
            parts.append(f"Service area: {workspace_profile['service_area']}")
        if workspace_profile.get("service_specialties"):
            parts.append(f"Specialties: {', '.join(workspace_profile['service_specialties'])}")
        if parts:
            user_content += "Workspace profile:\n" + "\n".join(parts) + "\n\n"

    if ai_strategy:
        gen = ai_strategy.get("generated_strategy") or {}
        if isinstance(gen, dict):
            guardrails = gen.get("guardrails") or {}
            if isinstance(guardrails, dict) and guardrails.get("do_not_claim"):
                user_content += f"Guardrails — do not claim: {', '.join(guardrails['do_not_claim'])}\n\n"

    if sender_info:
        from app.services.sender_signature import get_sender_prompt_context
        ctx = get_sender_prompt_context(sender_info)
        if ctx:
            user_content += ctx + "\n\n"

    if classification:
        user_content += f"Email classification: {classification}\n\n"

    if thread_history:
        user_content += f"Previous messages in thread:\n{thread_history}\n\n---\n\n"

    if inbound_subject:
        user_content += f"Inbound subject: {inbound_subject}\n"
    user_content += f"Inbound message:\n{inbound_body[:8000]}"

    return user_content


def _generate_with_openai(user_content: str, api_key: str, *, system_prompt: str = SYSTEM_PROMPT) -> dict[str, Any]:
    payload = {
        "model": settings.openai_model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
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
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
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
                    time.sleep(base_backoff * (2 ** attempt))
                    continue
                raise ResponseDraftError("OpenAI rate limited")

            if response.status_code >= 400:
                raise ResponseDraftError(f"OpenAI error {response.status_code}: {response.text[:500]}")

            data = response.json()
            output = data.get("output")
            if isinstance(output, list):
                for item in output:
                    if item.get("type") == "message":
                        for content in item.get("content", []):
                            if content.get("type") == "output_text":
                                return json.loads(content["text"])
            raise ResponseDraftError("Could not extract output from OpenAI response")

    raise ResponseDraftError("OpenAI response draft failed after retries")


def _generate_with_anthropic(user_content: str, api_key: str, *, system_prompt: str = SYSTEM_PROMPT) -> dict[str, Any]:
    model = settings.anthropic_model or "claude-sonnet-4-5"
    payload = {
        "model": model,
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_content}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        for attempt in range(3):
            try:
                response = client.post(ANTHROPIC_MESSAGES_URL, headers=headers, json=payload)
            except httpx.RequestError as exc:
                raise ResponseDraftError(f"Anthropic request failed: {exc}") from exc

            if response.status_code == 529 or response.status_code == 429:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise ResponseDraftError("Anthropic API overloaded or rate limited")

            if response.status_code >= 400:
                raise ResponseDraftError(f"Anthropic error {response.status_code}: {response.text[:500]}")

            data = response.json()
            # Extract text from Anthropic's response format
            content_blocks = data.get("content", [])
            for block in content_blocks:
                if block.get("type") == "text":
                    text = block["text"].strip()
                    # Strip markdown code fences if present
                    if text.startswith("```"):
                        text = text.split("```")[1]
                        if text.startswith("json"):
                            text = text[4:]
                    return json.loads(text.strip())

            raise ResponseDraftError("Could not extract text from Anthropic response")

    raise ResponseDraftError("Anthropic response draft failed after retries")


def generate_response_draft(
    *,
    inbound_body: str,
    inbound_subject: str | None = None,
    thread_history: str | None = None,
    classification: str | None = None,
    workspace_profile: dict[str, Any] | None = None,
    ai_strategy: dict[str, Any] | None = None,
    sender_info: dict[str, str] | None = None,
    api_key: str | None = None,
    anthropic_api_key: str | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    """Generate an email draft using the configured AI provider.

    Provider resolution order:
    1. Explicit `provider` + matching key if both provided
    2. Anthropic if `anthropic_api_key` is set (preferred — better instruction-following)
    3. OpenAI via `api_key` or env fallback
    """
    user_content = _build_user_content(
        inbound_body=inbound_body,
        inbound_subject=inbound_subject,
        thread_history=thread_history,
        classification=classification,
        workspace_profile=workspace_profile,
        ai_strategy=ai_strategy,
        sender_info=sender_info,
    )

    # Vendor inquiry emails use a dedicated system prompt built from the user's actual profile
    if classification == "partner_vendor_inquiry":
        system_prompt = _build_vendor_inquiry_prompt(workspace_profile, sender_info)
    else:
        system_prompt = SYSTEM_PROMPT

    resolved_anthropic = (anthropic_api_key or "").strip() or (settings.anthropic_api_key or "").strip()
    resolved_openai = (api_key or "").strip() or (settings.openai_api_key or "").strip()

    # Determine provider
    use_anthropic = (
        (provider == "anthropic" and resolved_anthropic)
        or (not provider and resolved_anthropic)
    )

    if use_anthropic and resolved_anthropic:
        logger.info("Generating email draft with Anthropic (%s) [classification=%s]", settings.anthropic_model, classification)
        result = _generate_with_anthropic(user_content, resolved_anthropic, system_prompt=system_prompt)
        logger.info("Anthropic draft generated, subject=%s", result.get("subject", "")[:50])
        return result

    if resolved_openai:
        logger.info("Generating email draft with OpenAI (%s) [classification=%s]", settings.openai_model, classification)
        result = _generate_with_openai(user_content, resolved_openai, system_prompt=system_prompt)
        logger.info("OpenAI draft generated, subject=%s", result.get("subject", "")[:50])
        return result

    raise ResponseDraftError(
        "No AI API key configured. Add an Anthropic or OpenAI API key in Settings."
    )
