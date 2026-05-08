"""{artifact.title()} v4 router."""

from fastapi import APIRouter

from app.routes.rubric.context import router as context_router
from app.routes.rubric.create import router as create_router
from app.routes.rubric.csv import router as csv_router
from app.routes.rubric.delete import router as delete_router
from app.routes.rubric.draft import router as draft_router
from app.routes.rubric.drafts import router as drafts_router
from app.routes.rubric.duplicate import router as duplicate_router
from app.routes.rubric.export import router as export_router
from app.routes.rubric.generate import router as generate_router
from app.routes.rubric.generations import router as generations_router
from app.routes.rubric.get import router as get_router
from app.routes.rubric.group import router as group_router
from app.routes.rubric.problem import router as problem_router
from app.routes.rubric.refresh import router as refresh_router
from app.routes.rubric.search import router as search_router
from app.routes.rubric.stream import router as stream_router
from app.routes.rubric.update import router as update_router
from app.routes.rubric.text import router as text_router
from app.routes.rubric.call import router as call_router

router = APIRouter(prefix="/rubric", tags=["rubric"])

# Include all endpoint routers
router.include_router(get_router)
router.include_router(search_router)
router.include_router(context_router)
router.include_router(create_router)
router.include_router(update_router)
router.include_router(duplicate_router)
router.include_router(delete_router)
router.include_router(draft_router)
router.include_router(drafts_router)
router.include_router(export_router)
router.include_router(csv_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(group_router)
router.include_router(problem_router)
router.include_router(refresh_router)
router.include_router(stream_router)

# Typed media operations
router.include_router(text_router)
router.include_router(call_router)
