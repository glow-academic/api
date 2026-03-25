"""{artifact.title()} v4 router."""

from fastapi import APIRouter

from app.routes.simulation.create import router as create_router
from app.routes.simulation.csv import router as csv_router
from app.routes.simulation.delete import router as delete_router
from app.routes.simulation.docs import router as docs_router
from app.routes.simulation.draft import router as draft_router
from app.routes.simulation.drafts import router as drafts_router
from app.routes.simulation.duplicate import router as duplicate_router
from app.routes.simulation.export import router as export_router
from app.routes.simulation.get import router as get_router
from app.routes.simulation.refresh import router as refresh_router
from app.routes.simulation.search import router as search_router
from app.routes.simulation.update import router as update_router

router = APIRouter(prefix="/simulations", tags=["simulations"])

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
router.include_router(export_router)
router.include_router(docs_router)
router.include_router(refresh_router)
