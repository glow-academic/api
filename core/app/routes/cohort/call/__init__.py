"""Cohort call sub-router."""

from fastapi import APIRouter

from app.routes.cohort.call.download import router as download_router

router = APIRouter(prefix="/call", tags=["cohort-call"])

router.include_router(download_router)
