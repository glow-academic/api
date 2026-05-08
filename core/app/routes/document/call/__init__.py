"""Document call sub-router."""

from fastapi import APIRouter

from app.routes.document.call.download import router as download_router

router = APIRouter(prefix="/call", tags=["document-call"])

router.include_router(download_router)
