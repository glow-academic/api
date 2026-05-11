"""Dashboard artifact router."""

from fastapi import APIRouter

from app.routes.attempt.dashboard.get import router as get_router
from app.routes.attempt.dashboard.search import router as search_router

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
router.include_router(get_router)
router.include_router(search_router)
