"""Field file sub-router."""

from fastapi import APIRouter

from app.routes.field.file.download import router as download_router

router = APIRouter(prefix="/file", tags=["field-file"])

router.include_router(download_router)
