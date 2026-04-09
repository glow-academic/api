"""Document text sub-router."""

from fastapi import APIRouter

from app.routes.document.text.download import router as download_router
from app.routes.document.text.upload import router as upload_router

router = APIRouter(prefix="/text", tags=["document-text"])

router.include_router(upload_router)
router.include_router(download_router)
