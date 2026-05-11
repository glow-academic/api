"""Test file router."""

from fastapi import APIRouter

from app.routes.test.file.download import router as download_router

router = APIRouter(prefix="/file")
router.include_router(download_router)
