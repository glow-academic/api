"""Group video sub-router."""

from fastapi import APIRouter

from app.routes.system.group.video.download import router as download_router

router = APIRouter(prefix="/video", tags=["group-video"])

router.include_router(download_router)
