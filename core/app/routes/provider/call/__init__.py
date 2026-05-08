"""Provider call sub-router."""

from fastapi import APIRouter

from app.routes.provider.call.download import router as download_router

router = APIRouter(prefix="/call", tags=["provider-call"])

router.include_router(download_router)
