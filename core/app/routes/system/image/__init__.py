"""System image sub-router."""

from fastapi import APIRouter

from app.routes.system.image.download import router as download_router

router = APIRouter(prefix="/image", tags=["system-image"])

router.include_router(download_router)
