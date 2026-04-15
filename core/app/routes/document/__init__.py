"""Document v4 router."""

from fastapi import APIRouter

from app.routes.document.context import router as context_router
from app.routes.document.create import router as create_router
from app.routes.document.csv import router as csv_router
from app.routes.document.delete import router as delete_router
from app.routes.document.docs import router as docs_router
from app.routes.document.draft import router as draft_router
from app.routes.document.drafts import router as drafts_router
from app.routes.document.duplicate import router as duplicate_router
from app.routes.document.export import router as export_router
from app.routes.document.file import router as file_router
from app.routes.document.generate import router as generate_router
from app.routes.document.generations import router as generations_router
from app.routes.document.get import router as get_router
from app.routes.document.group import router as group_router
from app.routes.document.problem import router as problem_router
from app.routes.document.refresh import router as refresh_router
from app.routes.document.search import router as search_router
from app.routes.document.text import router as text_router
from app.routes.document.update import router as update_router

router = APIRouter(prefix="/document", tags=["document"])

# Standard artifact operations
router.include_router(search_router)
router.include_router(get_router)
router.include_router(create_router)
router.include_router(update_router)
router.include_router(duplicate_router)
router.include_router(delete_router)
router.include_router(draft_router)
router.include_router(drafts_router)
router.include_router(context_router)
router.include_router(docs_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(group_router)
router.include_router(problem_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(csv_router)

# Typed media operations
router.include_router(text_router)
router.include_router(file_router)
