"""Persona text sub-router."""

from fastapi import APIRouter

from app.routes.persona.text.download import router as download_router

router = APIRouter(prefix="/text", tags=["persona-text"])

router.include_router(download_router)
