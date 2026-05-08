"""Field call sub-router."""

from fastapi import APIRouter

from app.routes.field.call.download import router as download_router

router = APIRouter(prefix="/call", tags=["field-call"])

router.include_router(download_router)
