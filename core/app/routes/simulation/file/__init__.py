"""Simulation file sub-router."""

from fastapi import APIRouter

from app.routes.simulation.file.download import router as download_router

router = APIRouter(prefix="/file", tags=["simulation-file"])

router.include_router(download_router)
