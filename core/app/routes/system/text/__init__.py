"""System text sub-router."""

from fastapi import APIRouter

from app.routes.system.text.download import router as download_router

router = APIRouter(prefix="/text", tags=["system-text"])

router.include_router(download_router)
