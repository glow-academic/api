"""Department file sub-router."""

from fastapi import APIRouter

from app.routes.department.file.download import router as download_router

router = APIRouter(prefix="/file", tags=["department-file"])

router.include_router(download_router)
