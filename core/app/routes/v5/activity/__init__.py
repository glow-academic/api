"""Activity artifact router."""

from fastapi import APIRouter

from app.routes.v5.activity.docs import router as docs_router
from app.routes.v5.activity.export import router as export_router
from app.routes.v5.activity.get import router as get_router
from app.routes.v5.activity.refresh import router as refresh_router
from app.routes.v5.activity.resolve import router as resolve_router
from app.routes.v5.activity.search import router as search_router

router = APIRouter(prefix="/activity", tags=["activity"])
router.include_router(get_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(resolve_router)
router.include_router(export_router)
router.include_router(docs_router)
