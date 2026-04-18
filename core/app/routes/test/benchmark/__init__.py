"""Benchmark artifact router."""

from fastapi import APIRouter

from app.routes.test.benchmark.export import router as export_router
from app.routes.test.benchmark.get import router as get_router
from app.routes.test.benchmark.refresh import router as refresh_router
from app.routes.test.benchmark.search import router as search_router

router = APIRouter(prefix="/benchmark", tags=["benchmark"])
router.include_router(get_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(export_router)
