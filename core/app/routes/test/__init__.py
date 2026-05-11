"""Test operational router — test + absorbed benchmark/invocation artifacts."""

from fastapi import APIRouter

from app.routes.test.archive import router as archive_router
from app.routes.test.title import router as title_router

# Absorbed sub-routers (one-to-one nesting, each keeps its own prefix)
from app.routes.test.benchmark import router as benchmark_router
from app.routes.test.call_download import router as call_download_router
from app.routes.test.complete import router as complete_router
from app.routes.test.context import router as context_router
from app.routes.test.decrypt import router as decrypt_router
from app.routes.test.draft import router as draft_router
from app.routes.test.drafts import router as drafts_router
from app.routes.test.export import router as export_router
from app.routes.test.feedback import router as feedback_router
from app.routes.test.file_download import router as file_download_router
from app.routes.test.generate import router as generate_router
from app.routes.test.generations import router as generations_router
from app.routes.test.get import router as get_router
from app.routes.test.grade import router as grade_router
from app.routes.test.group import router as group_router
from app.routes.test.invocation_complete import router as invocation_complete_router
from app.routes.test.invocation_create import router as invocation_create_router
from app.routes.test.invocation_get import router as invocation_get_router
from app.routes.test.invocation_run import router as invocation_run_router
from app.routes.test.invocation_terminate import router as invocation_terminate_router
from app.routes.test.invocation_trace import router as invocation_trace_router
from app.routes.test.invocations import router as invocations_router
from app.routes.test.problem import router as problem_router
from app.routes.test.refresh import router as refresh_router
from app.routes.test.search import router as search_router
from app.routes.test.start import router as start_router
from app.routes.test.stop import router as stop_router
from app.routes.test.stream import router as stream_router
from app.routes.test.text_download import router as text_download_router

router = APIRouter(prefix="/test", tags=["test"])

router.include_router(title_router)
router.include_router(get_router)
router.include_router(archive_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(context_router)
# Canonical state-machine operations
router.include_router(start_router)
# trace moved under /test/invocation/trace (it requires test_invocation_id)
router.include_router(complete_router)  # POST /test/complete (whole test)
router.include_router(stop_router)
router.include_router(search_router)
router.include_router(invocations_router)  # POST /test/invocations
router.include_router(grade_router)
router.include_router(feedback_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(group_router)
router.include_router(stream_router)
router.include_router(problem_router)
# Promoted from /test/invocation/* to top-level (invocation was the only
# consumer of these; keeping them nested obscured shared use across
# benchmark/invocation flows).
router.include_router(draft_router)
router.include_router(drafts_router)
router.include_router(decrypt_router)
# Media operations
router.include_router(text_download_router)
router.include_router(call_download_router)
router.include_router(file_download_router)

# Absorbed sub-routers (one-to-one nesting)
router.include_router(benchmark_router)    # prefix="/benchmark"
router.include_router(invocation_complete_router)
router.include_router(invocation_create_router)
router.include_router(invocation_get_router)
router.include_router(invocation_run_router)
router.include_router(invocation_terminate_router)
router.include_router(invocation_trace_router)
