"""Structured outreach modes (signal / fallback / soft) for Agent 2 and Agent 3."""

from __future__ import annotations

from typing import Any


def attach_agent1_legacy_aliases(data: dict[str, Any]) -> dict[str, Any]:
    """Mirror canonical Agent 1 fields for older UI/code expecting pain_points / rapport_hooks."""
    out = dict(data)
    pvd = out.get("pain_points_detected")
    if isinstance(pvd, list):
        out["pain_points"] = list(pvd)
    sfs = out.get("signals_found")
    if isinstance(sfs, list):
        out["rapport_hooks"] = [
            {
                "type": str(s.get("type") or "signal"),
                "hook": str(s.get("signal") or ""),
                "evidence_quote": str(s.get("evidence_quote") or ""),
            }
            for s in sfs
            if isinstance(s, dict)
        ]
    return out


def ensure_agent1_canonical_fields(agent1_output: dict[str, Any]) -> dict[str, Any]:
    """Normalize stored Agent 1 JSON (supports pre-migration drafts)."""
    out = dict(agent1_output)
    if "pain_points_detected" not in out and isinstance(out.get("pain_points"), list):
        out["pain_points_detected"] = list(out["pain_points"])
    if "signals_found" not in out and isinstance(out.get("rapport_hooks"), list):
        out["signals_found"] = []
        for h in out["rapport_hooks"]:
            if not isinstance(h, dict):
                continue
            out["signals_found"].append(
                {
                    "type": str(h.get("type") or "signal"),
                    "signal": str(h.get("hook") or h.get("signal") or ""),
                    "evidence_quote": str(h.get("evidence_quote") or ""),
                }
            )
    if "confidence_score" not in out:
        out["confidence_score"] = _heuristic_confidence_score(out)
    else:
        try:
            out["confidence_score"] = max(0.0, min(1.0, float(out["confidence_score"])))
        except (TypeError, ValueError):
            out["confidence_score"] = _heuristic_confidence_score(out)
    if "pain_points_detected" not in out:
        out["pain_points_detected"] = []
    if "signals_found" not in out:
        out["signals_found"] = []
    return out


def _heuristic_confidence_score(agent1: dict[str, Any]) -> float:
    pains = agent1.get("pain_points_detected") or agent1.get("pain_points") or []
    sigs = agent1.get("signals_found") or agent1.get("rapport_hooks") or []
    score = 0.12
    for p in pains:
        if not isinstance(p, dict):
            continue
        ev = (p.get("evidence_quote") or "").strip()
        if len(ev) >= 12 and "workspace" not in ev.lower():
            score += 0.22
    for s in sigs:
        if not isinstance(s, dict):
            continue
        ev = (s.get("evidence_quote") or s.get("signal") or "").strip()
        if len(ev) >= 10:
            score += 0.07
    return min(1.0, score)


def _nonempty_evidence_pains(agent1: dict[str, Any]) -> list[dict[str, Any]]:
    pains = agent1.get("pain_points_detected") or []
    out: list[dict[str, Any]] = []
    for p in pains:
        if not isinstance(p, dict):
            continue
        ev = (p.get("evidence_quote") or "").strip()
        if len(ev) < 12:
            continue
        low = ev.lower()
        if "workspace" in low and "strategy" in low:
            continue
        if "from workspace outreach strategy" in low:
            continue
        out.append(p)
    return out


def compute_agent2_outreach_mode(agent1: dict[str, Any], strategy: dict[str, Any]) -> str:
    """Return signal | fallback | soft."""
    conf = float(agent1.get("confidence_score") or 0.0)
    pains = _nonempty_evidence_pains(agent1)
    if pains and conf >= 0.5:
        return "signal"

    matched = strategy.get("matched_category") or strategy.get("matched_workspace_category")
    pbc = strategy.get("pain_points_by_category") or {}
    cat_entry = pbc.get(matched) if matched else None
    has_pbc = isinstance(cat_entry, list) and len(cat_entry) > 0
    fb = strategy.get("fallback_pain_points_for_category") or []
    has_fb = bool(matched) and len(fb) > 0
    if matched and (has_pbc or has_fb):
        return "fallback"
    return "soft"


def build_agent2_mode_instructions(mode: str, agent1: dict[str, Any], strategy: dict[str, Any]) -> str:
    if mode == "signal":
        pains = agent1.get("pain_points_detected") or []
        sigs = agent1.get("signals_found") or []
        return (
            "MODE: SIGNAL\n"
            "- Use ONLY agent1_output.pain_points_detected and agent1_output.signals_found.\n"
            "- Tie claims to evidence_quote / concrete website facts. Example: 'I noticed you offer online ordering...'\n"
            "- Do NOT invent pain points, ops issues, or goals beyond those arrays.\n"
            f"- Counts: pain_points_detected={len(pains)}, signals_found={len(sigs)}.\n"
        )
    if mode == "fallback":
        topics = _format_fallback_pain_topics(strategy)
        return (
            "MODE: FALLBACK\n"
            "- You must NOT state workspace topics as facts about this business.\n"
            "- ALLOWED: 'Many [type] we work with eventually look at...', "
            "'Some restaurants run into...', 'If this is something you're dealing with...'\n"
            "- NOT ALLOWED: 'You are struggling with...', 'Your business has issues with...', "
            "'You must be dealing with...'\n"
            f"- Hypothetical topics list (common scenarios only): {topics}\n"
        )
    return (
        "MODE: SOFT\n"
        "- No pain points, problems, struggles, or 'you may be facing...' language.\n"
        "- Compliment or one light factual observation from the site; name our service (core_positioning); modest CTA.\n"
    )


def _format_fallback_pain_topics(strategy: dict[str, Any]) -> str:
    items = strategy.get("fallback_pain_points_for_category") or []
    labels: list[str] = []
    for item in items[:8]:
        if isinstance(item, dict):
            lab = item.get("label") or item.get("pain") or item.get("key")
            if lab:
                labels.append(str(lab))
    return "; ".join(labels) if labels else "(none — lean on core_positioning only)"
