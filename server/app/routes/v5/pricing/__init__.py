"""Pricing artifact router."""

from fastapi import APIRouter

from app.routes.v5.pricing.docs import router as docs_router
from app.routes.v5.pricing.export import router as export_router
from app.routes.v5.pricing.get import router as get_router
from app.routes.v5.pricing.refresh import router as refresh_router
from app.routes.v5.pricing.search import router as search_router

router = APIRouter(prefix="/pricing", tags=["pricing"])
router.include_router(get_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(docs_router)
