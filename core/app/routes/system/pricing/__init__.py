"""Pricing artifact router."""

from fastapi import APIRouter

from app.routes.system.pricing.get import router as get_router
from app.routes.system.pricing.search import router as search_router

router = APIRouter(prefix="/pricing", tags=["pricing"])
router.include_router(get_router)
router.include_router(search_router)
