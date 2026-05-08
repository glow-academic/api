"""Scenario call sub-router."""

from fastapi import APIRouter

from app.routes.scenario.call.download import router as download_router

router = APIRouter(prefix="/call", tags=["scenario-call"])

router.include_router(download_router)
