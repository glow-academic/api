"""{artifact.title()} v4 router."""

from fastapi import APIRouter

from app.routes.persona.call_download import router as call_download_router
from app.routes.persona.context import router as context_router
from app.routes.persona.create import router as create_router
from app.routes.persona.csv import router as csv_router
from app.routes.persona.delete import router as delete_router
from app.routes.persona.draft import router as draft_router
from app.routes.persona.drafts import router as drafts_router
from app.routes.persona.duplicate import router as duplicate_router
from app.routes.persona.export import router as export_router
from app.routes.persona.file_download import router as file_download_router
from app.routes.persona.generate import router as generate_router
from app.routes.persona.generations import router as generations_router
from app.routes.persona.get import router as get_router
from app.routes.persona.group import router as group_router
from app.routes.persona.problem import router as problem_router
from app.routes.persona.refresh import router as refresh_router
from app.routes.persona.search import router as search_router
from app.routes.persona.watch import router as watch_router
from app.routes.persona.text_download import router as text_download_router
from app.routes.persona.update import router as update_router
from app.routes.persona.title import router as title_router

router = APIRouter(prefix="/persona", tags=["persona"])

# Include all endpoint routers
router.include_router(title_router)
router.include_router(get_router)
router.include_router(search_router)
router.include_router(create_router)
router.include_router(csv_router)
router.include_router(update_router)
router.include_router(duplicate_router)
router.include_router(delete_router)
router.include_router(draft_router)
router.include_router(drafts_router)
router.include_router(context_router)
router.include_router(export_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(group_router)
router.include_router(problem_router)
router.include_router(refresh_router)
router.include_router(watch_router)

# Typed media operations
router.include_router(text_download_router)
router.include_router(call_download_router)
router.include_router(file_download_router)
