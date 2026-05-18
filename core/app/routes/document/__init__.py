"""Document v4 router."""

from fastapi import APIRouter

from app.routes.document.context import router as context_router
from app.routes.document.create import router as create_router
from app.routes.document.csv import router as csv_router
from app.routes.document.delete import router as delete_router
from app.routes.document.draft import router as draft_router
from app.routes.document.drafts import router as drafts_router
from app.routes.document.duplicate import router as duplicate_router
from app.routes.document.export import router as export_router
from app.routes.document.file_download import router as file_download_router
from app.routes.document.file_preview import router as file_preview_router
from app.routes.document.file_upload import router as file_upload_router
from app.routes.document.generate import router as generate_router
from app.routes.document.generations import router as generations_router
from app.routes.document.get import router as get_router
from app.routes.document.group import router as group_router
from app.routes.document.problem import router as problem_router
from app.routes.document.refresh import router as refresh_router
from app.routes.document.search import router as search_router
from app.routes.document.watch import router as watch_router
from app.routes.document.text_download import router as text_download_router
from app.routes.document.text_upload import router as text_upload_router
from app.routes.document.update import router as update_router
from app.routes.document.call_download import router as call_download_router
from app.routes.document.title import router as title_router

router = APIRouter(prefix="/document", tags=["document"])

# Standard artifact operations
router.include_router(title_router)
router.include_router(search_router)
router.include_router(get_router)
router.include_router(create_router)
router.include_router(update_router)
router.include_router(duplicate_router)
router.include_router(delete_router)
router.include_router(draft_router)
router.include_router(drafts_router)
router.include_router(context_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(group_router)
router.include_router(problem_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(csv_router)
router.include_router(watch_router)

# Typed media operations
router.include_router(text_download_router)
router.include_router(text_upload_router)
router.include_router(file_download_router)
router.include_router(file_preview_router)
router.include_router(file_upload_router)

# Typed media operations
router.include_router(call_download_router)
