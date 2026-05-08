"""Cohort text sub-router."""

from fastapi import APIRouter

from app.routes.cohort.text.download import router as download_router

router = APIRouter(prefix="/text", tags=["cohort-text"])

router.include_router(download_router)
