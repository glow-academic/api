"""Tool call sub-router."""

from fastapi import APIRouter

from app.routes.tool.call.download import router as download_router

router = APIRouter(prefix="/call", tags=["tool-call"])

router.include_router(download_router)
