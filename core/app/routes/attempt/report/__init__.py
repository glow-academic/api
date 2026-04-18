"""Reports artifact router."""

from fastapi import APIRouter

from app.routes.attempt.report.export import router as export_router
from app.routes.attempt.report.refresh import router as refresh_router
from app.routes.attempt.report.search import router as search_router

router = APIRouter(prefix="/report", tags=["report"])
router.include_router(export_router)
router.include_router(search_router)
router.include_router(refresh_router)
