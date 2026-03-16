"""Eval v4 router."""

from fastapi import APIRouter

from app.routes.v5.eval.create import router as create_router
from app.routes.v5.eval.delete import router as delete_router
from app.routes.v5.eval.docs import router as docs_router
from app.routes.v5.eval.draft import router as draft_router
from app.routes.v5.eval.drafts import router as drafts_router
from app.routes.v5.eval.duplicate import router as duplicate_router
from app.routes.v5.eval.csv import router as csv_router
from app.routes.v5.eval.export import router as export_router
from app.routes.v5.eval.get import router as get_router
from app.routes.v5.eval.refresh import router as refresh_router
from app.routes.v5.eval.search import router as search_router
from app.routes.v5.eval.update import router as update_router

router = APIRouter(prefix="/evals", tags=["evals"])

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
