"""Home artifact router."""

from fastapi import APIRouter

from app.routes.attempt.home.get import router as get_router
from app.routes.attempt.home.search import router as search_router

router = APIRouter(prefix="/home", tags=["home"])

router.include_router(get_router)
router.include_router(search_router)
