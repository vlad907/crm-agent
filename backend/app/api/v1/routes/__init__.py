from app.api.v1.routes.automation_settings import router as automation_settings_router
from app.api.v1.routes.draft_actions import router as draft_actions_router
from app.api.v1.routes.drafts import router as drafts_router
from app.api.v1.routes.integrations import router as integrations_router
from app.api.v1.routes.leads import router as leads_router
from app.api.v1.routes.snapshots import router as snapshots_router
from app.api.v1.routes.verifier import router as verifier_router
from app.api.v1.routes.workspace_ai_strategy import router as workspace_ai_strategy_router

__all__ = [
    "automation_settings_router",
    "draft_actions_router",
    "drafts_router",
    "integrations_router",
    "leads_router",
    "snapshots_router",
    "verifier_router",
    "workspace_ai_strategy_router",
]
