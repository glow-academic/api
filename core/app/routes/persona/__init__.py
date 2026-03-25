"""{artifact.title()} v4 router."""

from fastapi import APIRouter

from app.routes.persona.create import router as create_router
from app.routes.persona.csv import router as csv_router
from app.routes.persona.delete import router as delete_router
from app.routes.persona.docs import router as docs_router
from app.routes.persona.draft import router as draft_router
from app.routes.persona.drafts import router as drafts_router
from app.routes.persona.duplicate import router as duplicate_router
from app.routes.persona.export import router as export_router
from app.routes.persona.get import router as get_router
from app.routes.persona.refresh import router as refresh_router
from app.routes.persona.search import router as search_router
from app.routes.persona.update import router as update_router

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
