"""Simulation call sub-router."""

from fastapi import APIRouter

from app.routes.simulation.call.download import router as download_router

router = APIRouter(prefix="/call", tags=["simulation-call"])

router.include_router(download_router)
