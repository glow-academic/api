"""Home artifact router."""

from fastapi import APIRouter

from app.routes.attempt.home.start import router as start_router
from app.routes.attempt.home.export import router as export_router
from app.routes.attempt.home.get import router as get_router
from app.routes.attempt.home.refresh import router as refresh_router
from app.routes.attempt.home.search import router as search_router

router = APIRouter(prefix="/home", tags=["home"])

router.include_router(start_router)
router.include_router(get_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(export_router)
