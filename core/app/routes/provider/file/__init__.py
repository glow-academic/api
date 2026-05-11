"""Provider file sub-router."""

from fastapi import APIRouter

from app.routes.provider.file.download import router as download_router

router = APIRouter(prefix="/file", tags=["provider-file"])

router.include_router(download_router)
