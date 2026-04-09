"""Group call sub-router."""

from fastapi import APIRouter

from app.routes.group.call.download import router as download_router

router = APIRouter(prefix="/call", tags=["group-call"])

router.include_router(download_router)
