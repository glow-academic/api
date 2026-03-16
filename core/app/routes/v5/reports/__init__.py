"""Reports artifact router."""

from fastapi import APIRouter

from app.routes.v5.reports.docs import router as docs_router
from app.routes.v5.reports.export import router as export_router
from app.routes.v5.reports.refresh import router as refresh_router
from app.routes.v5.reports.search import router as search_router

router = APIRouter(prefix="/reports", tags=["reports"])
router.include_router(export_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(docs_router)
