"""Model file sub-router."""

from fastapi import APIRouter

from app.routes.model.file.download import router as download_router

router = APIRouter(prefix="/file", tags=["model-file"])

router.include_router(download_router)
