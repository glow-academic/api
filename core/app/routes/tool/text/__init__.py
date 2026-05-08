"""Tool text sub-router."""

from fastapi import APIRouter

from app.routes.tool.text.download import router as download_router

router = APIRouter(prefix="/text", tags=["tool-text"])

router.include_router(download_router)
