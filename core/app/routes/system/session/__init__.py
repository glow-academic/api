"""Session artifact router."""

from fastapi import APIRouter

from app.routes.system.session.export import router as export_router
from app.routes.system.session.get import router as get_router
from app.routes.system.session.refresh import router as refresh_router

router = APIRouter(prefix="/session", tags=["session"])

router.include_router(get_router)
router.include_router(refresh_router)
router.include_router(export_router)
