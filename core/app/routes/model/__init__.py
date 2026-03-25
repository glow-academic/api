"""{artifact.title()} v4 router."""

from fastapi import APIRouter

from app.routes.model.create import router as create_router
from app.routes.model.delete import router as delete_router
from app.routes.model.docs import router as docs_router
from app.routes.model.draft import router as draft_router
from app.routes.model.drafts import router as drafts_router
from app.routes.model.duplicate import router as duplicate_router
from app.routes.model.csv import router as csv_router
from app.routes.model.export import router as export_router
from app.routes.model.get import router as get_router
from app.routes.model.refresh import router as refresh_router
from app.routes.model.search import router as search_router
from app.routes.model.update import router as update_router

router = APIRouter(prefix="/models", tags=["models"])

# Include all endpoint routers
router.include_router(get_router)
router.include_router(search_router)
router.include_router(create_router)
router.include_router(update_router)
router.include_router(duplicate_router)
router.include_router(delete_router)
router.include_router(draft_router)
router.include_router(drafts_router)
router.include_router(docs_router)
router.include_router(export_router)
router.include_router(csv_router)
router.include_router(refresh_router)
