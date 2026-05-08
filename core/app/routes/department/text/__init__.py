"""Department text sub-router."""

from fastapi import APIRouter

from app.routes.department.text.download import router as download_router

router = APIRouter(prefix="/text", tags=["department-text"])

router.include_router(download_router)
