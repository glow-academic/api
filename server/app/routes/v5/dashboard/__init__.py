"""Dashboard artifact router."""

from fastapi import APIRouter

from app.routes.v5.dashboard.docs import router as docs_router
from app.routes.v5.dashboard.export import router as export_router
from app.routes.v5.dashboard.get import router as get_router
from app.routes.v5.dashboard.refresh import router as refresh_router
from app.routes.v5.dashboard.search import router as search_router

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
router.include_router(get_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(docs_router)
