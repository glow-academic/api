"""Scenario image sub-router."""

from fastapi import APIRouter

from app.routes.scenario.image.download import router as download_router
from app.routes.scenario.image.upload import router as upload_router

router = APIRouter(prefix="/image", tags=["scenario-image"])

router.include_router(upload_router)
router.include_router(download_router)
