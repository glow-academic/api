"""Setting text sub-router."""

from fastapi import APIRouter

from app.routes.setting.text.download import router as download_router

router = APIRouter(prefix="/text", tags=["setting-text"])

router.include_router(download_router)
