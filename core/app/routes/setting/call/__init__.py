"""Setting call sub-router."""

from fastapi import APIRouter

from app.routes.setting.call.download import router as download_router

router = APIRouter(prefix="/call", tags=["setting-call"])

router.include_router(download_router)
