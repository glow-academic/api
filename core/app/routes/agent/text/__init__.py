"""Agent text sub-router."""

from fastapi import APIRouter

from app.routes.agent.text.download import router as download_router

router = APIRouter(prefix="/text", tags=["agent-text"])

router.include_router(download_router)
