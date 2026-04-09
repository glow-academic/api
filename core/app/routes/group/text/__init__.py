"""Group text sub-router."""

from fastapi import APIRouter

from app.routes.group.text.download import router as download_router

router = APIRouter(prefix="/text", tags=["group-text"])

router.include_router(download_router)
