"""Attempt video sub-router."""

from fastapi import APIRouter

from app.routes.attempt.video.download import router as download_router

router = APIRouter(prefix="/video", tags=["attempt-video"])

router.include_router(download_router)
