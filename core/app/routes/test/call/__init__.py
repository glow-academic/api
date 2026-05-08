"""Test call media routes."""

from fastapi import APIRouter

from . import download  # noqa: F401

router = APIRouter(prefix="/call")
router.include_router(download.router)
