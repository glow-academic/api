"""Test text media routes."""

from . import download  # noqa: F401

from fastapi import APIRouter

router = APIRouter(prefix="/text")
router.include_router(download.router)
