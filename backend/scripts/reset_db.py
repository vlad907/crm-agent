#!/usr/bin/env python3
"""
Drop all tables and run migrations from scratch. Use for a clean slate.

Run from backend dir:
  python scripts/reset_db.py

With Docker:
  docker compose exec backend python scripts/reset_db.py
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine


def main() -> None:
    print("Dropping all objects in public schema...")
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
        conn.commit()
    print("Schema dropped.")

    print("Running alembic upgrade head...")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env={**os.environ, "DATABASE_URL": str(settings.database_url or "")},
    )
    if result.returncode != 0:
        sys.exit(result.returncode)
    print("Database reset complete. Restart the backend to bootstrap dev identity.")


if __name__ == "__main__":
    main()
