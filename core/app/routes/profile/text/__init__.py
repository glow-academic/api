"""Profile text sub-router."""

from fastapi import APIRouter

from app.routes.profile.text.download import router as download_router

router = APIRouter(prefix="/text", tags=["profile-text"])

router.include_router(download_router)
