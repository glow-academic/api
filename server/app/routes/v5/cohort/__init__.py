"""Cohort v4 router."""

from fastapi import APIRouter

from app.routes.v5.cohort.create import router as create_router
from app.routes.v5.cohort.csv import router as csv_router
from app.routes.v5.cohort.delete import router as delete_router
from app.routes.v5.cohort.docs import router as docs_router
from app.routes.v5.cohort.draft import router as draft_router
from app.routes.v5.cohort.drafts import router as drafts_router
from app.routes.v5.cohort.duplicate import router as duplicate_router
from app.routes.v5.cohort.export import router as export_router
from app.routes.v5.cohort.get import router as get_router
from app.routes.v5.cohort.refresh import router as refresh_router
from app.routes.v5.cohort.search import router as search_router
from app.routes.v5.cohort.update import router as update_router

router = APIRouter(prefix="/cohorts", tags=["cohorts"])

# Include all endpoint routers (standard 6 endpoints)
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
