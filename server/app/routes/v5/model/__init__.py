"""{artifact.title()} v4 router."""

from fastapi import APIRouter

from app.routes.v5.model.create import router as create_router
from app.routes.v5.model.delete import router as delete_router
from app.routes.v5.model.docs import router as docs_router
from app.routes.v5.model.draft import router as draft_router
from app.routes.v5.model.drafts import router as drafts_router
from app.routes.v5.model.duplicate import router as duplicate_router
from app.routes.v5.model.csv import router as csv_router
from app.routes.v5.model.export import router as export_router
from app.routes.v5.model.get import router as get_router
from app.routes.v5.model.refresh import router as refresh_router
from app.routes.v5.model.search import router as search_router
from app.routes.v5.model.update import router as update_router

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
