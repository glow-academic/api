"""Tool file sub-router."""

from fastapi import APIRouter

from app.routes.tool.file.download import router as download_router

router = APIRouter(prefix="/file", tags=["tool-file"])

router.include_router(download_router)
