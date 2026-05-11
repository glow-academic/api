"""Persona file sub-router."""

from fastapi import APIRouter

from app.routes.persona.file.download import router as download_router

router = APIRouter(prefix="/file", tags=["persona-file"])

router.include_router(download_router)
