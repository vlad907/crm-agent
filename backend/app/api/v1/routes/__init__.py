from app.api.v1.routes.drafts import router as drafts_router
from app.api.v1.routes.leads import router as leads_router
from app.api.v1.routes.snapshots import router as snapshots_router
from app.api.v1.routes.verifier import router as verifier_router

__all__ = ["drafts_router", "leads_router", "snapshots_router", "verifier_router"]
