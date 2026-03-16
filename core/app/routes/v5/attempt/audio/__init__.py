"""Attempt audio sub-router — canonical HTTP adapters for audio session events.

Mirrors socket events: attempt_audio_start, attempt_audio_frame,
attempt_audio_stop, attempt_audio_mute.
"""

from fastapi import APIRouter

from app.routes.v5.attempt.audio.frame import router as frame_router
from app.routes.v5.attempt.audio.mute import router as mute_router
from app.routes.v5.attempt.audio.start import router as start_router
from app.routes.v5.attempt.audio.stop import router as stop_router

router = APIRouter(prefix="/audio", tags=["audio"])

router.include_router(start_router)
router.include_router(frame_router)
router.include_router(stop_router)
router.include_router(mute_router)
