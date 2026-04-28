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
