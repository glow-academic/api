"""Record artifact router — profile report (dashboard for one profile)."""

from fastapi import APIRouter

from app.routes.attempt.record.get import router as get_router
from app.routes.attempt.record.search import router as search_router

router = APIRouter(prefix="/record", tags=["record"])
router.include_router(get_router)
router.include_router(search_router)
