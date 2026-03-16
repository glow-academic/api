"""Unified attempt detail router (home + practice via practice: bool)."""

from fastapi import APIRouter

from app.routes.v5.attempt.archive import router as archive_router
from app.routes.v5.attempt.docs import router as docs_router
from app.routes.v5.attempt.download import router as download_router
from app.routes.v5.attempt.end import router as end_router
from app.routes.v5.attempt.end_all import router as end_all_router
from app.routes.v5.attempt.export import router as export_router
from app.routes.v5.attempt.get import router as get_router
from app.routes.v5.attempt.grade import router as grade_router
from app.routes.v5.attempt.join import router as join_router
from app.routes.v5.attempt.leave import router as leave_router
from app.routes.v5.attempt.message import router as message_router
from app.routes.v5.attempt.next import router as next_router
from app.routes.v5.attempt.refresh import router as refresh_router
from app.routes.v5.attempt.response import router as response_router
from app.routes.v5.attempt.search import router as search_router
from app.routes.v5.attempt.start import router as start_router
from app.routes.v5.attempt.stop import router as stop_router
from app.routes.v5.attempt.audio import router as audio_router
from app.routes.v5.attempt.use_previous import router as use_previous_router

router = APIRouter(prefix="/attempt", tags=["attempt"])

router.include_router(get_router)
router.include_router(join_router)
router.include_router(leave_router)
router.include_router(archive_router)
router.include_router(refresh_router)
router.include_router(docs_router)
router.include_router(export_router)
# Socket event API equivalents
router.include_router(start_router)
router.include_router(next_router)
router.include_router(end_router)
router.include_router(end_all_router)
router.include_router(message_router)
router.include_router(grade_router)
router.include_router(stop_router)
router.include_router(response_router)
router.include_router(use_previous_router)
router.include_router(audio_router)
router.include_router(search_router)

# Unified download
router.include_router(download_router)
