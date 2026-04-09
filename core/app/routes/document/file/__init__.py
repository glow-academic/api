"""Document file sub-router."""

from fastapi import APIRouter

from app.routes.document.file.download import router as download_router
from app.routes.document.file.preview import router as preview_router
from app.routes.document.file.upload import router as upload_router

router = APIRouter(prefix="/file", tags=["document-file"])

router.include_router(upload_router)
router.include_router(download_router)
router.include_router(preview_router)
