"""Group audio sub-router."""

from fastapi import APIRouter

from app.routes.system.group.audio.download import router as download_router

router = APIRouter(prefix="/audio", tags=["group-audio"])

router.include_router(download_router)
