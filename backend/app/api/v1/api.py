from fastapi import APIRouter

from app.api.v1.routes.drafts import router as drafts_router
from app.api.v1.routes.leads import router as leads_router
from app.api.v1.routes.snapshots import router as snapshots_router
from app.api.v1.routes.verifier import router as verifier_router

api_router = APIRouter()
api_router.include_router(leads_router)
api_router.include_router(snapshots_router)
api_router.include_router(drafts_router)
api_router.include_router(verifier_router)
