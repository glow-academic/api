"""Attempt text sub-router."""

from fastapi import APIRouter

from app.routes.attempt.text.download import router as download_router

router = APIRouter(prefix="/text", tags=["attempt-text"])

router.include_router(download_router)
