"""Rubric file sub-router."""

from fastapi import APIRouter

from app.routes.rubric.file.download import router as download_router

router = APIRouter(prefix="/file", tags=["rubric-file"])

router.include_router(download_router)
