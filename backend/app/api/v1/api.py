from fastapi import APIRouter

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.drafts import router as drafts_router
from app.api.v1.routes.leads import router as leads_router
from app.api.v1.routes.me import router as me_router
from app.api.v1.routes.prospects import router as prospects_router
from app.api.v1.routes.settings import router as settings_router
from app.api.v1.routes.website_pages import router as website_pages_router
from app.api.v1.routes.snapshots import router as snapshots_router
from app.api.v1.routes.verifier import router as verifier_router
from app.api.v1.routes.workspaces import router as workspaces_router
from app.api.v1.routes.workspace_profile import router as workspace_profile_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(me_router)
api_router.include_router(settings_router)
api_router.include_router(workspace_profile_router)
api_router.include_router(workspaces_router)
api_router.include_router(leads_router)
api_router.include_router(prospects_router)
api_router.include_router(website_pages_router)
api_router.include_router(snapshots_router)
api_router.include_router(drafts_router)
api_router.include_router(verifier_router)
