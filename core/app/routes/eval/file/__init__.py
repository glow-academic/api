"""Eval file sub-router."""

from fastapi import APIRouter

from app.routes.eval.file.download import router as download_router

router = APIRouter(prefix="/file", tags=["eval-file"])

router.include_router(download_router)
