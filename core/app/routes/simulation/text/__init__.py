"""Simulation text sub-router."""

from fastapi import APIRouter

from app.routes.simulation.text.download import router as download_router

router = APIRouter(prefix="/text", tags=["simulation-text"])

router.include_router(download_router)
