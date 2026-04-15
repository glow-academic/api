"""Reports artifact router."""

from fastapi import APIRouter

from app.routes.attempt.report.context import router as context_router
from app.routes.attempt.report.export import router as export_router
from app.routes.attempt.report.generate import router as generate_router
from app.routes.attempt.report.generations import router as generations_router
from app.routes.attempt.report.group import router as group_router
from app.routes.attempt.report.problem import router as problem_router
from app.routes.attempt.report.refresh import router as refresh_router
from app.routes.attempt.report.search import router as search_router

router = APIRouter(prefix="/report", tags=["report"])
router.include_router(export_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(group_router)
router.include_router(problem_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(context_router)
