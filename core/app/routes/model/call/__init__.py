"""Model call sub-router."""

from fastapi import APIRouter

from app.routes.model.call.download import router as download_router

router = APIRouter(prefix="/call", tags=["model-call"])

router.include_router(download_router)
