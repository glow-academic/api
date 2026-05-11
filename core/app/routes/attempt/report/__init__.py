"""Reports artifact router."""

from fastapi import APIRouter

from app.routes.attempt.report.search import router as search_router

router = APIRouter(prefix="/report", tags=["report"])
router.include_router(search_router)
