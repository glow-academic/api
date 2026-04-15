"""Attempt audio sub-router — media transport only (upload/download)."""

from fastapi import APIRouter

from app.routes.attempt.audio.download import router as download_router
from app.routes.attempt.audio.upload import router as upload_router

router = APIRouter(prefix="/audio", tags=["attempt-audio"])

router.include_router(upload_router)
router.include_router(download_router)
