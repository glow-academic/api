"""Session artifact router."""

from fastapi import APIRouter

from app.routes.system.session.get import router as get_router

router = APIRouter(prefix="/session", tags=["session"])

router.include_router(get_router)
