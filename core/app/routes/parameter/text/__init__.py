"""Parameter text sub-router."""

from fastapi import APIRouter

from app.routes.parameter.text.download import router as download_router

router = APIRouter(prefix="/text", tags=["parameter-text"])

router.include_router(download_router)
