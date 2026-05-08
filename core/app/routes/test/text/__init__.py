"""Test text media routes."""

from fastapi import APIRouter

from . import download  # noqa: F401

router = APIRouter(prefix="/text")
router.include_router(download.router)
