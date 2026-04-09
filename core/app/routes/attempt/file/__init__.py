"""Attempt file sub-router."""

from fastapi import APIRouter

from app.routes.attempt.file.download import router as download_router
from app.routes.attempt.file.preview import router as preview_router

router = APIRouter(prefix="/file", tags=["attempt-file"])

router.include_router(download_router)
router.include_router(preview_router)
