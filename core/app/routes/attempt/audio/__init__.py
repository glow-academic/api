"""Attempt audio sub-router."""

from fastapi import APIRouter

from app.routes.attempt.audio.download import router as download_router
from app.routes.attempt.audio.frame import router as frame_router
from app.routes.attempt.audio.mute import router as mute_router
from app.routes.attempt.audio.start import router as start_router
from app.routes.attempt.audio.stop import router as stop_router
from app.routes.attempt.audio.upload import router as upload_router

router = APIRouter(prefix="/audio", tags=["attempt-audio"])

router.include_router(start_router)
router.include_router(frame_router)
router.include_router(stop_router)
router.include_router(mute_router)
router.include_router(upload_router)
router.include_router(download_router)
