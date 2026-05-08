"""Department call sub-router."""

from fastapi import APIRouter

from app.routes.department.call.download import router as download_router

router = APIRouter(prefix="/call", tags=["department-call"])

router.include_router(download_router)
