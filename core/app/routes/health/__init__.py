"""Health artifact router."""

from fastapi import APIRouter

from app.routes.health.docs import router as docs_router
from app.routes.health.export import router as export_router
from app.routes.health.get import router as get_router
from app.routes.health.group import router as group_router
from app.routes.health.refresh import router as refresh_router

router = APIRouter(prefix="/health", tags=["health"])
router.include_router(get_router)
router.include_router(group_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(docs_router)
