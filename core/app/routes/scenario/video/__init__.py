"""Scenario video sub-router."""

from fastapi import APIRouter

from app.routes.scenario.video.download import router as download_router
from app.routes.scenario.video.upload import router as upload_router

router = APIRouter(prefix="/video", tags=["scenario-video"])

router.include_router(upload_router)
router.include_router(download_router)
