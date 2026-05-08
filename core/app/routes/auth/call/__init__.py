"""Auth call sub-router."""

from fastapi import APIRouter

from app.routes.auth.call.download import router as download_router

router = APIRouter(prefix="/call", tags=["auth-call"])

router.include_router(download_router)
