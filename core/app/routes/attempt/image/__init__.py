"""Attempt image sub-router."""

from fastapi import APIRouter

from app.routes.attempt.image.download import router as download_router

router = APIRouter(prefix="/image", tags=["attempt-image"])

router.include_router(download_router)
