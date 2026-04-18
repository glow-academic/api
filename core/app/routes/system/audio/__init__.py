"""System audio sub-router."""

from fastapi import APIRouter

from app.routes.system.audio.download import router as download_router

router = APIRouter(prefix="/audio", tags=["system-audio"])

router.include_router(download_router)
