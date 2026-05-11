"""Agent file sub-router."""

from fastapi import APIRouter

from app.routes.agent.file.download import router as download_router

router = APIRouter(prefix="/file", tags=["agent-file"])

router.include_router(download_router)
