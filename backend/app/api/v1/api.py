from fastapi import APIRouter

from app.api.v1.routes.admin import router as admin_router
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.automation_settings import router as automation_settings_router
from app.api.v1.routes.draft_actions import router as draft_actions_router
from app.api.v1.routes.drafts import router as drafts_router
from app.api.v1.routes.inbox import router as inbox_router
from app.api.v1.routes.integrations import router as integrations_router
from app.api.v1.routes.jobs import router as jobs_router
from app.api.v1.routes.leads import router as leads_router
from app.api.v1.routes.me import router as me_router
from app.api.v1.routes.partnerships import router as partnerships_router
from app.api.v1.routes.prospects import router as prospects_router
from app.api.v1.routes.settings import router as settings_router
from app.api.v1.routes.website_pages import router as website_pages_router
from app.api.v1.routes.snapshots import router as snapshots_router
from app.api.v1.routes.verifier import router as verifier_router
from app.api.v1.routes.workspaces import router as workspaces_router
from app.api.v1.routes.workspace_ai_strategy import router as workspace_ai_strategy_router
from app.api.v1.routes.workspace_profile import router as workspace_profile_router

api_router = APIRouter()
api_router.include_router(admin_router)
api_router.include_router(auth_router)
api_router.include_router(me_router)
api_router.include_router(settings_router)
api_router.include_router(automation_settings_router)
api_router.include_router(workspace_profile_router)
api_router.include_router(workspace_ai_strategy_router)
api_router.include_router(integrations_router)
api_router.include_router(workspaces_router)
api_router.include_router(leads_router)
api_router.include_router(prospects_router)
api_router.include_router(partnerships_router)
api_router.include_router(inbox_router)
api_router.include_router(jobs_router)
api_router.include_router(website_pages_router)
api_router.include_router(snapshots_router)
api_router.include_router(drafts_router)
api_router.include_router(draft_actions_router)
api_router.include_router(verifier_router)
