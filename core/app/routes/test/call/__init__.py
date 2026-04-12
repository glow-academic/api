"""Test call media routes."""

from . import download  # noqa: F401

from fastapi import APIRouter

router = APIRouter(prefix="/call")
router.include_router(download.router)
