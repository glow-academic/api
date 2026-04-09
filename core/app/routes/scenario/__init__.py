"""Scenario v4 router."""

from fastapi import APIRouter

from app.routes.scenario.create import router as create_router
from app.routes.scenario.csv import router as csv_router
from app.routes.scenario.delete import router as delete_router
from app.routes.scenario.docs import router as docs_router
from app.routes.scenario.draft import router as draft_router
from app.routes.scenario.drafts import router as drafts_router
from app.routes.scenario.duplicate import router as duplicate_router
from app.routes.scenario.export import router as export_router
from app.routes.scenario.file import router as file_router
from app.routes.scenario.get import router as get_router
from app.routes.scenario.image import router as image_router
from app.routes.scenario.refresh import router as refresh_router
from app.routes.scenario.search import router as search_router
from app.routes.scenario.text import router as text_router
from app.routes.scenario.update import router as update_router
from app.routes.scenario.video import router as video_router

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

# Standard artifact operations
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

# Typed media operations
router.include_router(image_router)
router.include_router(video_router)
router.include_router(text_router)
router.include_router(file_router)
