"""Model text sub-router."""

from fastapi import APIRouter

from app.routes.model.text.download import router as download_router

router = APIRouter(prefix="/text", tags=["model-text"])

router.include_router(download_router)
