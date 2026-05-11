"""Test operational router — test + absorbed benchmark/invocation artifacts."""

from fastapi import APIRouter

from app.routes.test.archive import router as archive_router

# Absorbed sub-routers (one-to-one nesting, each keeps its own prefix)
from app.routes.test.benchmark import router as benchmark_router
from app.routes.test.call import router as call_router
from app.routes.test.complete import router as complete_router
from app.routes.test.context import router as context_router
from app.routes.test.export import router as export_router
from app.routes.test.feedback import router as feedback_router
from app.routes.test.file import router as file_router
from app.routes.test.generate import router as generate_router
from app.routes.test.generations import router as generations_router
from app.routes.test.get import router as get_router
from app.routes.test.grade import router as grade_router
from app.routes.test.group import router as group_router
from app.routes.test.invocation import router as invocation_router
from app.routes.test.problem import router as problem_router
from app.routes.test.refresh import router as refresh_router
from app.routes.test.run import router as run_router
from app.routes.test.search import router as search_router
from app.routes.test.start import router as start_router
from app.routes.test.stop import router as stop_router
from app.routes.test.stream import router as stream_router
from app.routes.test.text import router as text_router
from app.routes.test.trace import router as trace_router

router = APIRouter(prefix="/test", tags=["test"])

router.include_router(get_router)
router.include_router(archive_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(context_router)
# Canonical state-machine operations
router.include_router(start_router)
router.include_router(trace_router)
router.include_router(run_router)
router.include_router(complete_router)  # POST /test/complete (whole test)
router.include_router(stop_router)
router.include_router(search_router)
router.include_router(grade_router)
router.include_router(feedback_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(group_router)
router.include_router(stream_router)
router.include_router(problem_router)
# Media operations
router.include_router(text_router)
router.include_router(call_router)
router.include_router(file_router)

# Absorbed sub-routers (one-to-one nesting)
router.include_router(benchmark_router)    # prefix="/benchmark"
router.include_router(invocation_router)   # prefix="/invocation"
