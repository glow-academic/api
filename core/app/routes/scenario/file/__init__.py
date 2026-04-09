"""Scenario file sub-router."""

from fastapi import APIRouter

from app.routes.scenario.file.download import router as download_router
from app.routes.scenario.file.preview import router as preview_router

router = APIRouter(prefix="/file", tags=["scenario-file"])

router.include_router(download_router)
router.include_router(preview_router)
