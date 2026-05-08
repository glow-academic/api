"""Agent call sub-router."""

from fastapi import APIRouter

from app.routes.agent.call.download import router as download_router

router = APIRouter(prefix="/call", tags=["agent-call"])

router.include_router(download_router)
