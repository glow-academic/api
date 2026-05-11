"""Health artifact router."""

from fastapi import APIRouter

from app.routes.system.health.get import router as get_router

router = APIRouter(prefix="/health", tags=["health"])
router.include_router(get_router)
