"""Benchmark artifact router."""

from fastapi import APIRouter

from app.routes.benchmark.docs import router as docs_router
from app.routes.benchmark.export import router as export_router
from app.routes.benchmark.get import router as get_router
from app.routes.benchmark.group import router as group_router
from app.routes.benchmark.refresh import router as refresh_router
from app.routes.benchmark.search import router as search_router

router = APIRouter(prefix="/benchmark", tags=["benchmark"])
router.include_router(get_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(docs_router)
router.include_router(group_router)
