"""Scenario v4 router."""

from fastapi import APIRouter

from app.routes.scenario.context import router as context_router
from app.routes.scenario.create import router as create_router
from app.routes.scenario.csv import router as csv_router
from app.routes.scenario.delete import router as delete_router
from app.routes.scenario.draft import router as draft_router
from app.routes.scenario.drafts import router as drafts_router
from app.routes.scenario.duplicate import router as duplicate_router
from app.routes.scenario.export import router as export_router
from app.routes.scenario.file_download import router as file_download_router
from app.routes.scenario.file_preview import router as file_preview_router
from app.routes.scenario.generate import router as generate_router
from app.routes.scenario.generations import router as generations_router
from app.routes.scenario.get import router as get_router
from app.routes.scenario.group import router as group_router
from app.routes.scenario.image_download import router as image_download_router
from app.routes.scenario.image_upload import router as image_upload_router
from app.routes.scenario.problem import router as problem_router
from app.routes.scenario.refresh import router as refresh_router
from app.routes.scenario.search import router as search_router
from app.routes.scenario.stream import router as stream_router
from app.routes.scenario.text_download import router as text_download_router
from app.routes.scenario.update import router as update_router
from app.routes.scenario.video_download import router as video_download_router
from app.routes.scenario.video_upload import router as video_upload_router
from app.routes.scenario.call_download import router as call_download_router
from app.routes.scenario.title import router as title_router

router = APIRouter(prefix="/scenario", tags=["scenario"])

# Standard artifact operations
router.include_router(title_router)
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
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(context_router)
router.include_router(group_router)
router.include_router(problem_router)
router.include_router(refresh_router)
router.include_router(stream_router)

# Typed media operations
router.include_router(image_download_router)
router.include_router(image_upload_router)
router.include_router(video_download_router)
router.include_router(video_upload_router)
router.include_router(text_download_router)
router.include_router(file_download_router)
router.include_router(file_preview_router)

# Typed media operations
router.include_router(call_download_router)
