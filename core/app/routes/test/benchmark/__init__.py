"""Benchmark artifact router."""

from fastapi import APIRouter

from app.routes.test.benchmark.context import router as context_router
from app.routes.test.benchmark.export import router as export_router
from app.routes.test.benchmark.generate import router as generate_router
from app.routes.test.benchmark.generations import router as generations_router
from app.routes.test.benchmark.get import router as get_router
from app.routes.test.benchmark.group import router as group_router
from app.routes.test.benchmark.problem import router as problem_router
from app.routes.test.benchmark.refresh import router as refresh_router
from app.routes.test.benchmark.search import router as search_router

router = APIRouter(prefix="/benchmark", tags=["benchmark"])
router.include_router(get_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(context_router)
router.include_router(group_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(problem_router)
