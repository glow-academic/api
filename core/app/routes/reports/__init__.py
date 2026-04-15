"""Reports artifact router."""

from fastapi import APIRouter

from app.routes.reports.context import router as context_router
from app.routes.reports.docs import router as docs_router
from app.routes.reports.export import router as export_router
from app.routes.reports.generate import router as generate_router
from app.routes.reports.generations import router as generations_router
from app.routes.reports.group import router as group_router
from app.routes.reports.problem import router as problem_router
from app.routes.reports.refresh import router as refresh_router
from app.routes.reports.search import router as search_router

router = APIRouter(prefix="/reports", tags=["reports"])
router.include_router(export_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(group_router)
router.include_router(problem_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(docs_router)
router.include_router(context_router)
