from __future__ import annotations

from typing import Final

LEAD_STATUS_DISCOVERED: Final[str] = "discovered"
LEAD_STATUS_IMPORTED: Final[str] = "imported"
LEAD_STATUS_RESEARCHING: Final[str] = "researching"
LEAD_STATUS_RESEARCHED: Final[str] = "researched"
LEAD_STATUS_DRAFTING: Final[str] = "drafting"
LEAD_STATUS_DRAFT_READY: Final[str] = "draft_ready"
LEAD_STATUS_NEEDS_REVIEW: Final[str] = "needs_review"
LEAD_STATUS_APPROVED: Final[str] = "approved"
LEAD_STATUS_SENT: Final[str] = "sent"
LEAD_STATUS_REPLIED: Final[str] = "replied"
LEAD_STATUS_CONVERTED: Final[str] = "converted"
LEAD_STATUS_ARCHIVED: Final[str] = "archived"

LEAD_STATUS_VALUES: Final[tuple[str, ...]] = (
    LEAD_STATUS_DISCOVERED,
    LEAD_STATUS_IMPORTED,
    LEAD_STATUS_RESEARCHING,
    LEAD_STATUS_RESEARCHED,
    LEAD_STATUS_DRAFTING,
    LEAD_STATUS_DRAFT_READY,
    LEAD_STATUS_NEEDS_REVIEW,
    LEAD_STATUS_APPROVED,
    LEAD_STATUS_SENT,
    LEAD_STATUS_REPLIED,
    LEAD_STATUS_CONVERTED,
    LEAD_STATUS_ARCHIVED,
)
LEAD_STATUS_SET: Final[set[str]] = set(LEAD_STATUS_VALUES)
DEFAULT_LEAD_STATUS: Final[str] = LEAD_STATUS_IMPORTED

LEAD_STATUS_LEGACY_MAP: Final[dict[str, str]] = {
    "new": LEAD_STATUS_IMPORTED,
    "ingested": LEAD_STATUS_RESEARCHED,
    "enriched": LEAD_STATUS_RESEARCHED,
    "agent1": LEAD_STATUS_RESEARCHED,
    "agent2": LEAD_STATUS_DRAFT_READY,
    "agent3": LEAD_STATUS_DRAFT_READY,
    "verified": LEAD_STATUS_DRAFT_READY,
    "draft": LEAD_STATUS_DRAFT_READY,
    "drafted": LEAD_STATUS_DRAFT_READY,
    "ready": LEAD_STATUS_APPROVED,
    "ready_to_send": LEAD_STATUS_APPROVED,
    "send": LEAD_STATUS_APPROVED,
    "hold": LEAD_STATUS_NEEDS_REVIEW,
}


def normalize_lead_status(value: str | None, *, fallback: str | None = DEFAULT_LEAD_STATUS) -> str | None:
    if value is None:
        return fallback
    normalized = value.strip().lower()
    if not normalized:
        return fallback
    normalized = LEAD_STATUS_LEGACY_MAP.get(normalized, normalized)
    if normalized in LEAD_STATUS_SET:
        return normalized
    return fallback
