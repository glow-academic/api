"""Tool v4 router."""

from fastapi import APIRouter

from app.routes.v5.tool.create import router as create_router
from app.routes.v5.tool.csv import router as csv_router
from app.routes.v5.tool.delete import router as delete_router
from app.routes.v5.tool.docs import router as docs_router
from app.routes.v5.tool.draft import router as draft_router
from app.routes.v5.tool.drafts import router as drafts_router
from app.routes.v5.tool.duplicate import router as duplicate_router
from app.routes.v5.tool.export import router as export_router
from app.routes.v5.tool.get import router as get_router
from app.routes.v5.tool.refresh import router as refresh_router
from app.routes.v5.tool.search import router as search_router
from app.routes.v5.tool.update import router as update_router

router = APIRouter(prefix="/tools", tags=["tools"])

# Include all endpoint routers
router.include_router(search_router)
router.include_router(get_router)
router.include_router(create_router)
router.include_router(update_router)
router.include_router(duplicate_router)
router.include_router(delete_router)
router.include_router(draft_router)
router.include_router(drafts_router)
router.include_router(export_router)
router.include_router(csv_router)
router.include_router(docs_router)
router.include_router(refresh_router)
