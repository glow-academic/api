"""Field text sub-router."""

from fastapi import APIRouter

from app.routes.field.text.download import router as download_router

router = APIRouter(prefix="/text", tags=["field-text"])

router.include_router(download_router)
