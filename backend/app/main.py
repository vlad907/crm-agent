from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.api import api_router
from app.core.config import settings
from app.services.dev_identity import DevIdentityError, initialize_default_identity_for_dev, resolve_request_identity

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def attach_request_identity(request: Request, call_next):
    if request.url.path == "/health":
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router, prefix=settings.api_prefix)
