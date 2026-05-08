"""Eval text sub-router."""

from fastapi import APIRouter

from app.routes.eval.text.download import router as download_router

router = APIRouter(prefix="/text", tags=["eval-text"])

router.include_router(download_router)
