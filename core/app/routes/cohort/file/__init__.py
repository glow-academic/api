"""Cohort file sub-router."""

from fastapi import APIRouter

from app.routes.cohort.file.download import router as download_router

router = APIRouter(prefix="/file", tags=["cohort-file"])

router.include_router(download_router)
