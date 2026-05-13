from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.api import api_router
from app.core.config import settings
from app.services.dev_identity import DevIdentityError, initialize_default_identity_for_dev, resolve_request_identity
from app.services.pipeline_worker import pipeline_worker

app = FastAPI(title=settings.app_name)

# Desktop app may bind Next.js on any free port (3000, 3001, …). Allow any localhost origin.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def attach_request_identity(request: Request, call_next):
    bypass_paths = {
        "/health",
        f"{settings.api_prefix}/integrations/gmail/callback",
        f"{settings.api_prefix}/auth/login",
        f"{settings.api_prefix}/auth/google/connect-url",
        f"{settings.api_prefix}/auth/google/callback",
        f"{settings.api_prefix}/workspaces",
    }
    if request.url.path in bypass_paths:
        return await call_next(request)

    try:
        workspace_id, user_id = resolve_request_identity(
            request.headers.get("X-Workspace-Id"),
            request.headers.get("X-User-Id"),
        )
    except DevIdentityError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    request.state.workspace_id = workspace_id
    request.state.user_id = user_id
    return await call_next(request)


@app.on_event("startup")
def init_sqlite_schema() -> None:
    """Auto-create all tables when running with SQLite (bypasses Alembic)."""
    if settings.database_url.startswith("sqlite"):
        import app.models  # noqa: F401 — register all ORM models before create_all
        from app.db.base import Base
        from app.db.session import engine
        Base.metadata.create_all(bind=engine)
        _run_sqlite_column_migrations(engine)


def _run_sqlite_column_migrations(engine) -> None:  # type: ignore[type-arg]
    """Add any columns that exist in ORM models but are missing from the live SQLite schema.

    SQLite does not support ALTER TABLE … DROP COLUMN in older versions and
    create_all() never modifies existing tables, so we handle additive
    migrations here.  Each entry is (table, column, SQL type + default).
    """
    from sqlalchemy import text

    migrations: list[tuple[str, str, str]] = [
        # workspace_settings columns added in v2
        ("workspace_settings", "gmail_connected", "INTEGER NOT NULL DEFAULT 0"),
        ("workspace_settings", "gmail_send_as_email", "TEXT"),
        ("workspace_settings", "gmail_send_as_display_name", "TEXT"),
        # workspace_profile sender fields added in v2
        ("workspace_profile", "sender_name", "TEXT"),
        ("workspace_profile", "sender_title", "TEXT"),
        ("workspace_profile", "sender_phone", "TEXT"),
        ("workspace_profile", "sender_email", "TEXT"),
        # workspace_settings Anthropic key added in v3
        ("workspace_settings", "anthropic_api_key", "TEXT"),
        # leads lead_type and partnership_context added in v4
        ("leads", "lead_type", "TEXT NOT NULL DEFAULT 'local_business'"),
        ("leads", "partnership_context", "TEXT"),
        # workspace_settings preferred_ai_provider added in v5
        ("workspace_settings", "preferred_ai_provider", "TEXT DEFAULT 'auto'"),
    ]

    with engine.connect() as conn:
        for table, column, col_def in migrations:
            # Check existing columns via PRAGMA
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            existing = {row[1] for row in rows}  # column name is index 1
            if column not in existing:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))
                    conn.commit()
                except Exception:
                    pass  # already added by a concurrent process or table doesn't exist yet

        # Backfill: any lead with source='partnership_discovery' should be lead_type='partnership'
        try:
            conn.execute(text(
                "UPDATE leads SET lead_type = 'partnership' WHERE source = 'partnership_discovery' AND lead_type = 'local_business'"
            ))
            conn.commit()
        except Exception:
            pass


@app.on_event("startup")
def bootstrap_dev_identity_defaults() -> None:
    initialize_default_identity_for_dev()


@app.on_event("startup")
async def start_pipeline_worker() -> None:
    pipeline_worker.start()


@app.on_event("shutdown")
async def stop_pipeline_worker() -> None:
    await pipeline_worker.stop()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router, prefix=settings.api_prefix)
