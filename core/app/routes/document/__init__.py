"""Document v4 router."""

from fastapi import APIRouter

from app.routes.document.create import router as create_router
from app.routes.document.csv import router as csv_router
from app.routes.document.delete import router as delete_router
from app.routes.document.docs import router as docs_router
from app.routes.document.download import router as download_router
from app.routes.document.draft import router as draft_router
from app.routes.document.drafts import router as drafts_router
from app.routes.document.duplicate import router as duplicate_router
from app.routes.document.export import router as export_router
from app.routes.document.get import router as get_router
from app.routes.document.preview import router as preview_router
from app.routes.document.refresh import router as refresh_router
from app.routes.document.search import router as search_router
from app.routes.document.update import router as update_router
from app.routes.document.upload import router as upload_router

router = APIRouter(prefix="/documents", tags=["documents"])

# Include all endpoint routers (standard 6 endpoints)
router.include_router(search_router)
router.include_router(get_router)
router.include_router(create_router)
router.include_router(update_router)
router.include_router(duplicate_router)
router.include_router(delete_router)
router.include_router(draft_router)
router.include_router(drafts_router)
router.include_router(docs_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(csv_router)

# Unified upload / download / preview
router.include_router(upload_router)
router.include_router(download_router)
router.include_router(preview_router)
