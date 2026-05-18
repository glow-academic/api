"""Attempt v4 router — operational parent for attempt + absorbed view artifacts."""

from fastapi import APIRouter

from app.routes.attempt.archive import router as archive_router
from app.routes.attempt.audio_download import router as audio_download_router
from app.routes.attempt.audio_upload import router as audio_upload_router
from app.routes.attempt.chat_analyses import router as chat_analyses_router
from app.routes.attempt.chat_audio import router as chat_audio_router
from app.routes.attempt.chat_complete import router as chat_complete_router
from app.routes.attempt.chat_create import router as chat_create_router
from app.routes.attempt.chat_feedback import router as chat_feedback_router
from app.routes.attempt.chat_get import router as chat_get_router
from app.routes.attempt.chat_grade import router as chat_grade_router
from app.routes.attempt.chat_hints import router as chat_hints_router
from app.routes.attempt.chat_improvements import router as chat_improvements_router
from app.routes.attempt.chat_message import router as chat_message_router
from app.routes.attempt.chat_response import router as chat_response_router
from app.routes.attempt.chat_silence import router as chat_silence_router
from app.routes.attempt.chat_speak import router as chat_speak_router
from app.routes.attempt.chat_strengths import router as chat_strengths_router
from app.routes.attempt.chat_voice import router as chat_voice_router
from app.routes.attempt.complete import router as complete_router
from app.routes.attempt.context import router as context_router
from app.routes.attempt.dashboard import router as dashboard_router
from app.routes.attempt.title import router as title_router

# Absorbed sub-routers (one-to-one nesting, each keeps its own prefix)
from app.routes.attempt.draft import router as draft_router
from app.routes.attempt.drafts import router as drafts_router
from app.routes.attempt.export import router as export_router
from app.routes.attempt.file_download import router as file_download_router
from app.routes.attempt.file_preview import router as file_preview_router
from app.routes.attempt.generate import router as generate_router
from app.routes.attempt.generations import router as generations_router
from app.routes.attempt.get import router as get_router
from app.routes.attempt.group import router as group_router
from app.routes.attempt.home import router as home_router
from app.routes.attempt.image_download import router as image_download_router
from app.routes.attempt.leaderboard import router as leaderboard_router
from app.routes.attempt.practice import router as practice_router
from app.routes.attempt.problem import router as problem_router
from app.routes.attempt.refresh import router as refresh_router
from app.routes.attempt.report import router as report_router
from app.routes.attempt.search import router as search_router
from app.routes.attempt.start import router as start_router
from app.routes.attempt.stop import router as stop_router
from app.routes.attempt.watch import router as watch_router
from app.routes.attempt.text_download import router as text_download_router
from app.routes.attempt.video_download import router as video_download_router
from app.routes.attempt.call_download import router as call_download_router

router = APIRouter(prefix="/attempt", tags=["attempt"])

# Standard operations
router.include_router(title_router)
router.include_router(get_router)
router.include_router(search_router)
router.include_router(archive_router)
router.include_router(refresh_router)
router.include_router(context_router)
router.include_router(export_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(group_router)
router.include_router(problem_router)

# Attempt-level state machine operations
router.include_router(start_router)
router.include_router(complete_router)
router.include_router(stop_router)
router.include_router(watch_router)

# Chat sub-router (chat-level + voice operations)
router.include_router(chat_analyses_router)
router.include_router(chat_audio_router)
router.include_router(chat_complete_router)
router.include_router(chat_create_router)
router.include_router(chat_feedback_router)
router.include_router(chat_get_router)
router.include_router(chat_grade_router)
router.include_router(chat_hints_router)
router.include_router(chat_improvements_router)
router.include_router(chat_message_router)
router.include_router(chat_response_router)
router.include_router(chat_silence_router)
router.include_router(chat_speak_router)
router.include_router(chat_strengths_router)
router.include_router(chat_voice_router)

# Chat draft/drafts (was /chat/draft → now /attempt/draft)
router.include_router(draft_router)
router.include_router(drafts_router)

# Absorbed sub-routers (one-to-one nesting)
# TODO: Future optimization — merge search endpoints, unify context, etc.
router.include_router(home_router)         # prefix="/home"
router.include_router(practice_router)     # prefix="/practice"
router.include_router(dashboard_router)    # prefix="/dashboard"
router.include_router(leaderboard_router)  # prefix="/leaderboard"
router.include_router(report_router)       # prefix="/report"

# Media transport
router.include_router(audio_download_router)
router.include_router(audio_upload_router)
router.include_router(image_download_router)
router.include_router(video_download_router)
router.include_router(text_download_router)
router.include_router(file_download_router)
router.include_router(file_preview_router)

# Typed media operations
router.include_router(call_download_router)
