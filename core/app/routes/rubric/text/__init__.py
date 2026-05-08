"""Rubric text sub-router."""

from fastapi import APIRouter

from app.routes.rubric.text.download import router as download_router

router = APIRouter(prefix="/text", tags=["rubric-text"])

router.include_router(download_router)
