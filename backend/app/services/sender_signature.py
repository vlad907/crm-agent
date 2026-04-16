"""Builds sender signature and replaces placeholder tokens in AI-generated emails."""
from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.workspace_profile import WorkspaceProfile


def get_sender_info(db: Session, workspace_id: UUID) -> dict[str, str]:
    profile = db.get(WorkspaceProfile, workspace_id)
    if not profile:
        return {}
    return {
        "sender_name": (profile.sender_name or "").strip(),
        "sender_title": (profile.sender_title or "").strip(),
        "sender_phone": (profile.sender_phone or "").strip(),
        "sender_email": (profile.sender_email or "").strip(),
        "business_name": (profile.business_name or "").strip(),
    }


def build_signature_block(info: dict[str, str]) -> str:
    lines: list[str] = []
    if info.get("sender_name"):
        lines.append(info["sender_name"])
    if info.get("sender_title"):
        lines.append(info["sender_title"])
    if info.get("business_name"):
        lines.append(info["business_name"])
    if info.get("sender_phone"):
        lines.append(info["sender_phone"])
    if info.get("sender_email"):
        lines.append(info["sender_email"])
    return "\n".join(lines)


_PLACEHOLDER_MAP = {
    r"\[Your Name\]": "sender_name",
    r"\[Your Position\]": "sender_title",
    r"\[Your Title\]": "sender_title",
    r"\[Your Role\]": "sender_title",
    r"\[Your Phone Number\]": "sender_phone",
    r"\[Your Phone\]": "sender_phone",
    r"\[Your Email\]": "sender_email",
    r"\[Your Email Address\]": "sender_email",
    r"\[Your Company\]": "business_name",
    r"\[Company Name\]": "business_name",
}


def replace_placeholders(text: str, info: dict[str, str]) -> str:
    for pattern, key in _PLACEHOLDER_MAP.items():
        value = info.get(key, "")
        text = re.sub(pattern, value, text, flags=re.IGNORECASE)
    return text


def finalize_email(
    db: Session,
    workspace_id: UUID,
    *,
    subject: str,
    body: str,
) -> tuple[str, str]:
    info = get_sender_info(db, workspace_id)
    subject = replace_placeholders(subject, info)
    body = replace_placeholders(body, info)
    return subject, body


def get_sender_prompt_context(info: dict[str, str]) -> str:
    parts: list[str] = []
    if info.get("sender_name"):
        parts.append(f"Sender name: {info['sender_name']}")
    if info.get("sender_title"):
        parts.append(f"Sender title/position: {info['sender_title']}")
    if info.get("sender_phone"):
        parts.append(f"Sender phone: {info['sender_phone']}")
    if info.get("sender_email"):
        parts.append(f"Sender email: {info['sender_email']}")
    if info.get("business_name"):
        parts.append(f"Company: {info['business_name']}")
    if not parts:
        return ""
    return "Sender contact info (use in signature, do NOT use placeholders like [Your Name]):\n" + "\n".join(parts)
