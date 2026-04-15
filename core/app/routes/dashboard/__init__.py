"""Dashboard artifact router."""

from fastapi import APIRouter

from app.routes.dashboard.context import router as context_router
from app.routes.dashboard.docs import router as docs_router
from app.routes.dashboard.export import router as export_router
from app.routes.dashboard.get import router as get_router
from app.routes.dashboard.group import router as group_router
from app.routes.dashboard.refresh import router as refresh_router
from app.routes.dashboard.search import router as search_router

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
router.include_router(get_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(context_router)
router.include_router(docs_router)
router.include_router(group_router)
