"""Attempt v4 router — operational parent for attempt + absorbed view artifacts."""

from fastapi import APIRouter

from app.routes.attempt.archive import router as archive_router
from app.routes.attempt.audio import router as audio_router
from app.routes.attempt.chat import router as chat_router
from app.routes.attempt.complete import router as complete_router
from app.routes.attempt.context import router as context_router
from app.routes.attempt.expire import router as expire_router
from app.routes.attempt.export import router as export_router
from app.routes.attempt.file import router as file_router
from app.routes.attempt.generate import router as generate_router
from app.routes.attempt.generations import router as generations_router
from app.routes.attempt.get import router as get_router
from app.routes.attempt.group import router as group_router
from app.routes.attempt.image import router as image_router
from app.routes.attempt.join import router as join_router
from app.routes.attempt.leave import router as leave_router
from app.routes.attempt.problem import router as problem_router
from app.routes.attempt.refresh import router as refresh_router
from app.routes.attempt.search import router as search_router
from app.routes.attempt.speak import router as speak_router
from app.routes.attempt.start import router as start_router
from app.routes.attempt.stream import router as stream_router
from app.routes.attempt.stop import router as stop_router
from app.routes.attempt.text import router as text_router
from app.routes.attempt.video import router as video_router

# Absorbed sub-routers (one-to-one nesting, each keeps its own prefix)
from app.routes.attempt.draft import router as draft_router
from app.routes.attempt.drafts import router as drafts_router
from app.routes.attempt.dashboard import router as dashboard_router
from app.routes.attempt.home import router as home_router
from app.routes.attempt.leaderboard import router as leaderboard_router
from app.routes.attempt.practice import router as practice_router
from app.routes.attempt.record import router as record_router
from app.routes.attempt.report import router as report_router

router = APIRouter(prefix="/attempt", tags=["attempt"])

# Standard operations
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
router.include_router(speak_router)
router.include_router(stop_router)
router.include_router(stream_router)
router.include_router(expire_router)
router.include_router(join_router)
router.include_router(leave_router)

# Chat sub-router (chat-level + voice operations)
router.include_router(chat_router)

# Chat draft/drafts (was /chat/draft → now /attempt/draft)
router.include_router(draft_router)
router.include_router(drafts_router)

# Absorbed sub-routers (one-to-one nesting)
# TODO: Future optimization — merge search endpoints, unify context, etc.
router.include_router(home_router)         # prefix="/home"
router.include_router(practice_router)     # prefix="/practice"
router.include_router(dashboard_router)    # prefix="/dashboard"
router.include_router(leaderboard_router)  # prefix="/leaderboard"
router.include_router(record_router)       # prefix="/record"
router.include_router(report_router)       # prefix="/report"

# Media transport
router.include_router(audio_router)
router.include_router(image_router)
router.include_router(video_router)
router.include_router(text_router)
router.include_router(file_router)
