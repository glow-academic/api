"""{artifact.title()} v4 router."""

from fastapi import APIRouter

from app.routes.parameter.context import router as context_router
from app.routes.parameter.create import router as create_router
from app.routes.parameter.csv import router as csv_router
from app.routes.parameter.delete import router as delete_router
from app.routes.parameter.docs import router as docs_router
from app.routes.parameter.draft import router as draft_router
from app.routes.parameter.drafts import router as drafts_router
from app.routes.parameter.duplicate import router as duplicate_router
from app.routes.parameter.export import router as export_router
from app.routes.parameter.generate import router as generate_router
from app.routes.parameter.generations import router as generations_router
from app.routes.parameter.get import router as get_router
from app.routes.parameter.group import router as group_router
from app.routes.parameter.problem import router as problem_router
from app.routes.parameter.refresh import router as refresh_router
from app.routes.parameter.search import router as search_router
from app.routes.parameter.update import router as update_router

router = APIRouter(prefix="/parameter", tags=["parameter"])

# Include all endpoint routers
router.include_router(get_router)
router.include_router(search_router)
router.include_router(create_router)
router.include_router(update_router)
router.include_router(duplicate_router)
router.include_router(context_router)
router.include_router(delete_router)
router.include_router(draft_router)
router.include_router(drafts_router)
router.include_router(docs_router)
router.include_router(export_router)
router.include_router(csv_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(group_router)
router.include_router(problem_router)
router.include_router(refresh_router)
