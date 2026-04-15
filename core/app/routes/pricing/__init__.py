"""Pricing artifact router."""

from fastapi import APIRouter

from app.routes.pricing.context import router as context_router
from app.routes.pricing.docs import router as docs_router
from app.routes.pricing.export import router as export_router
from app.routes.pricing.generate import router as generate_router
from app.routes.pricing.generations import router as generations_router
from app.routes.pricing.get import router as get_router
from app.routes.pricing.group import router as group_router
from app.routes.pricing.problem import router as problem_router
from app.routes.pricing.refresh import router as refresh_router
from app.routes.pricing.search import router as search_router

router = APIRouter(prefix="/pricing", tags=["pricing"])
router.include_router(get_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(docs_router)
router.include_router(context_router)
router.include_router(group_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(problem_router)
