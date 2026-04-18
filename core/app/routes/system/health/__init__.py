"""Health artifact router."""

from fastapi import APIRouter

from app.routes.system.health.export import router as export_router
from app.routes.system.health.get import router as get_router
from app.routes.system.health.refresh import router as refresh_router

router = APIRouter(prefix="/health", tags=["health"])
router.include_router(get_router)
router.include_router(refresh_router)
router.include_router(export_router)
