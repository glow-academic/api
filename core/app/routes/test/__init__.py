"""Benchmark test artifact router."""

from fastapi import APIRouter

from app.routes.test.archive import router as archive_router
from app.routes.test.context import router as context_router
from app.routes.test.docs import router as docs_router
from app.routes.test.end import router as end_router
from app.routes.test.export import router as export_router
from app.routes.test.call import router as call_router
from app.routes.test.feedback import router as feedback_router
from app.routes.test.generate import router as generate_router
from app.routes.test.generations import router as generations_router
from app.routes.test.get import router as get_router
from app.routes.test.group import router as group_router
from app.routes.test.grade import router as grade_router
from app.routes.test.join import router as join_router
from app.routes.test.leave import router as leave_router
from app.routes.test.next import router as next_router
from app.routes.test.problem import router as problem_router
from app.routes.test.refresh import router as refresh_router
from app.routes.test.run import router as run_router
from app.routes.test.search import router as search_router
from app.routes.test.start import router as start_router
from app.routes.test.stop import router as stop_router
from app.routes.test.text import router as text_router

router = APIRouter(prefix="/test", tags=["test"])

router.include_router(get_router)
router.include_router(join_router)
router.include_router(leave_router)
router.include_router(archive_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(docs_router)
router.include_router(context_router)
# Socket event API equivalents
router.include_router(start_router)
router.include_router(next_router)
router.include_router(run_router)
router.include_router(end_router)
router.include_router(stop_router)
router.include_router(search_router)
router.include_router(grade_router)
router.include_router(feedback_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(group_router)
router.include_router(problem_router)
# Media operations
router.include_router(text_router)
router.include_router(call_router)
