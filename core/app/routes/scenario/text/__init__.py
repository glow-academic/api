"""Scenario text sub-router."""

from fastapi import APIRouter

from app.routes.scenario.text.download import router as download_router

router = APIRouter(prefix="/text", tags=["scenario-text"])

router.include_router(download_router)
