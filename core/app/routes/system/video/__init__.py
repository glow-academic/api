"""System video sub-router."""

from fastapi import APIRouter

from app.routes.system.video.download import router as download_router

router = APIRouter(prefix="/video", tags=["system-video"])

router.include_router(download_router)
