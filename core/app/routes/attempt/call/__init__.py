"""Attempt call sub-router."""

from fastapi import APIRouter

from app.routes.attempt.call.download import router as download_router

router = APIRouter(prefix="/call", tags=["attempt-call"])

router.include_router(download_router)
