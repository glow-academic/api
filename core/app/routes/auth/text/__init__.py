"""Auth text sub-router."""

from fastapi import APIRouter

from app.routes.auth.text.download import router as download_router

router = APIRouter(prefix="/text", tags=["auth-text"])

router.include_router(download_router)
