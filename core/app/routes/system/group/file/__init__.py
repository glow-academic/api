"""Group file sub-router."""

from fastapi import APIRouter

from app.routes.system.group.file.download import router as download_router
from app.routes.system.group.file.preview import router as preview_router

router = APIRouter(prefix="/file", tags=["group-file"])

router.include_router(download_router)
router.include_router(preview_router)
