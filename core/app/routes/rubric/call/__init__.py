"""Rubric call sub-router."""

from fastapi import APIRouter

from app.routes.rubric.call.download import router as download_router

router = APIRouter(prefix="/call", tags=["rubric-call"])

router.include_router(download_router)
