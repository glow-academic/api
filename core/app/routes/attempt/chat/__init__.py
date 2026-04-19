"""Attempt chat sub-router — chat-level, voice, and evaluation operations."""

from fastapi import APIRouter

from app.routes.attempt.chat.analyses import router as analyses_router
from app.routes.attempt.chat.complete import router as complete_router
from app.routes.attempt.chat.create import router as create_router
from app.routes.attempt.chat.feedback import router as feedback_router
from app.routes.attempt.chat.grade import router as grade_router
from app.routes.attempt.chat.hints import router as hints_router
from app.routes.attempt.chat.improvements import router as improvements_router
from app.routes.attempt.chat.response import router as response_router
from app.routes.attempt.chat.send import router as send_router
from app.routes.attempt.chat.silence import router as silence_router
from app.routes.attempt.chat.strengths import router as strengths_router
from app.routes.attempt.chat.voice import router as voice_router

# Chat artifact endpoints (get, refresh, export — context/group use parent)
from app.routes.chat.get import router as chat_get_router
from app.routes.chat.refresh import router as chat_refresh_router
from app.routes.chat.export import router as chat_export_router

router = APIRouter(prefix="/chat", tags=["attempt-chat"])

# Chat-level operations
router.include_router(create_router)
router.include_router(send_router)
router.include_router(grade_router)
router.include_router(response_router)

# Voice operations
router.include_router(voice_router)
router.include_router(silence_router)

# Completion
router.include_router(complete_router)

# Evaluation operations
router.include_router(feedback_router)
router.include_router(strengths_router)
router.include_router(improvements_router)
router.include_router(analyses_router)
router.include_router(hints_router)

# Chat artifact endpoints
router.include_router(chat_get_router)
router.include_router(chat_refresh_router)
router.include_router(chat_export_router)
