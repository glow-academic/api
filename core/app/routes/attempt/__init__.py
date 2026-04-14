"""Attempt v4 router."""

from fastapi import APIRouter

from app.routes.attempt.archive import router as archive_router
from app.routes.attempt.audio import router as audio_router
from app.routes.attempt.docs import router as docs_router
from app.routes.attempt.end import router as end_router
from app.routes.attempt.expire import router as expire_router
from app.routes.attempt.export import router as export_router
from app.routes.attempt.file import router as file_router
from app.routes.attempt.generate import router as generate_router
from app.routes.attempt.generations import router as generations_router
from app.routes.attempt.get import router as get_router
from app.routes.attempt.grade import router as grade_router
from app.routes.attempt.group import router as group_router
from app.routes.attempt.image import router as image_router
from app.routes.attempt.join import router as join_router
from app.routes.attempt.leave import router as leave_router
from app.routes.attempt.message import router as message_router
from app.routes.attempt.next import router as next_router
from app.routes.attempt.previous import router as previous_router
from app.routes.attempt.problem import router as problem_router
from app.routes.attempt.refresh import router as refresh_router
from app.routes.attempt.response import router as response_router
from app.routes.attempt.search import router as search_router
from app.routes.attempt.start import router as start_router
from app.routes.attempt.stop import router as stop_router
from app.routes.attempt.text import router as text_router
from app.routes.attempt.video import router as video_router

router = APIRouter(prefix="/attempt", tags=["attempt"])

# Standard operations
router.include_router(get_router)
router.include_router(search_router)
router.include_router(archive_router)
router.include_router(refresh_router)
router.include_router(docs_router)
router.include_router(export_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(group_router)
router.include_router(problem_router)

# State machine operations
router.include_router(start_router)
router.include_router(next_router)
router.include_router(end_router)
router.include_router(expire_router)
router.include_router(message_router)
router.include_router(grade_router)
router.include_router(stop_router)
router.include_router(response_router)
router.include_router(previous_router)
router.include_router(join_router)
router.include_router(leave_router)

# Typed media operations
router.include_router(audio_router)
router.include_router(image_router)
router.include_router(video_router)
router.include_router(text_router)
router.include_router(file_router)
