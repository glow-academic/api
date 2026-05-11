"""Activity artifact router."""

from fastapi import APIRouter

from app.routes.system.activity.get import router as get_router
from app.routes.system.activity.resolve import router as resolve_router
from app.routes.system.activity.search import router as search_router

router = APIRouter(prefix="/activity", tags=["activity"])
router.include_router(get_router)
router.include_router(search_router)
router.include_router(resolve_router)
