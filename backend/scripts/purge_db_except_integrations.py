#!/usr/bin/env python3
"""
Purge database except for integration data (integration_accounts, oauth_tokens).

Keeps: workspaces, integration_accounts, oauth_tokens, workspace_settings (API keys)
Deletes: users, workspace_profile, workspace_automation_settings, workspace_ai_strategy,
         leads, prospects, email_drafts, website_snapshots, website_pages

After purge: Restart backend so dev identity creates a user. Add leads to run ingestion/agents.

Run from backend dir:
  python scripts/purge_db_except_integrations.py

With Docker:
  docker compose exec backend python scripts/purge_db_except_integrations.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.db.session import SessionLocal


def purge(db) -> dict[str, int]:
    """Delete all rows from non-integration tables."""
    counts: dict[str, int] = {}
    tables = [
        "email_drafts",
        "website_snapshots",
        "website_pages",
        "leads",
        "prospects",
        "workspace_ai_strategy",
        "workspace_automation_settings",
        "workspace_profile",
        "users",
    ]
    for table in tables:
        result = db.execute(text(f"DELETE FROM {table}"))
        counts[table] = result.rowcount or 0
    db.commit()
    return counts


def main() -> None:
    db = SessionLocal()
    try:
        counts = purge(db)
        total = sum(counts.values())
        print("Purged (kept workspaces, integration_accounts, oauth_tokens, workspace_settings):")
        for table, n in counts.items():
            if n:
                print(f"  {table}: {n} rows")
        print(f"  Total: {total} rows")
    finally:
        db.close()


if __name__ == "__main__":
    main()
