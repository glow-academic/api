"""Cohort v4 router."""

from fastapi import APIRouter

from app.routes.cohort.create import router as create_router
from app.routes.cohort.csv import router as csv_router
from app.routes.cohort.delete import router as delete_router
from app.routes.cohort.docs import router as docs_router
from app.routes.cohort.draft import router as draft_router
from app.routes.cohort.drafts import router as drafts_router
from app.routes.cohort.duplicate import router as duplicate_router
from app.routes.cohort.export import router as export_router
from app.routes.cohort.get import router as get_router
from app.routes.cohort.group import router as group_router
from app.routes.cohort.refresh import router as refresh_router
from app.routes.cohort.search import router as search_router
from app.routes.cohort.update import router as update_router

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
router.include_router(group_router)
router.include_router(refresh_router)
