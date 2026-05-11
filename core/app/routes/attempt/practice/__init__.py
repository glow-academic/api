"""Practice artifact router."""

from fastapi import APIRouter

from app.routes.attempt.practice.get import router as get_router
from app.routes.attempt.practice.search import router as search_router

router = APIRouter(prefix="/practice", tags=["practice"])

router.include_router(get_router)
router.include_router(search_router)
