"""Group image sub-router."""

from fastapi import APIRouter

from app.routes.system.group.image.download import router as download_router

router = APIRouter(prefix="/image", tags=["group-image"])

router.include_router(download_router)
