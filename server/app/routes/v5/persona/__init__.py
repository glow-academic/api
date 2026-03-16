"""{artifact.title()} v4 router."""

from fastapi import APIRouter

from app.routes.v5.persona.create import router as create_router
from app.routes.v5.persona.csv import router as csv_router
from app.routes.v5.persona.delete import router as delete_router
from app.routes.v5.persona.docs import router as docs_router
from app.routes.v5.persona.draft import router as draft_router
from app.routes.v5.persona.drafts import router as drafts_router
from app.routes.v5.persona.duplicate import router as duplicate_router
from app.routes.v5.persona.export import router as export_router
from app.routes.v5.persona.get import router as get_router
from app.routes.v5.persona.refresh import router as refresh_router
from app.routes.v5.persona.search import router as search_router
from app.routes.v5.persona.update import router as update_router

router = APIRouter(prefix="/personas", tags=["personas"])

# Include all endpoint routers
router.include_router(get_router)
router.include_router(search_router)
router.include_router(create_router)
router.include_router(csv_router)
router.include_router(update_router)
router.include_router(duplicate_router)
router.include_router(delete_router)
router.include_router(draft_router)
router.include_router(drafts_router)
router.include_router(docs_router)
router.include_router(export_router)
router.include_router(refresh_router)
