"""Persona call sub-router."""

from fastapi import APIRouter

from app.routes.persona.call.download import router as download_router

router = APIRouter(prefix="/call", tags=["persona-call"])

router.include_router(download_router)
