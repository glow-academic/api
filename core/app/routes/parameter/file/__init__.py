"""Parameter file sub-router."""

from fastapi import APIRouter

from app.routes.parameter.file.download import router as download_router

router = APIRouter(prefix="/file", tags=["parameter-file"])

router.include_router(download_router)
