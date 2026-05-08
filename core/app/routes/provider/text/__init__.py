"""Provider text sub-router."""

from fastapi import APIRouter

from app.routes.provider.text.download import router as download_router

router = APIRouter(prefix="/text", tags=["provider-text"])

router.include_router(download_router)
