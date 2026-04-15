"""Attempt chat sub-router — chat-level and voice operations."""

from fastapi import APIRouter

from app.routes.attempt.chat.end import router as end_router
from app.routes.attempt.chat.frame import router as frame_router
from app.routes.attempt.chat.grade import router as grade_router
from app.routes.attempt.chat.mute import router as mute_router
from app.routes.attempt.chat.response import router as response_router
from app.routes.attempt.chat.send import router as send_router
from app.routes.attempt.chat.silence import router as silence_router
from app.routes.attempt.chat.stop import router as stop_router
from app.routes.attempt.chat.voice import router as voice_router

router = APIRouter(prefix="/chat", tags=["attempt-chat"])

# Chat-level operations
router.include_router(end_router)
router.include_router(grade_router)
router.include_router(response_router)
router.include_router(send_router)
router.include_router(stop_router)

# Voice operations
router.include_router(voice_router)
router.include_router(frame_router)
router.include_router(mute_router)
router.include_router(silence_router)
