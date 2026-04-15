"""Practice artifact router."""

from fastapi import APIRouter

from app.routes.attempt.practice.context import router as context_router
from app.routes.attempt.practice.export import router as export_router
from app.routes.attempt.practice.generate import router as generate_router
from app.routes.attempt.practice.generations import router as generations_router
from app.routes.attempt.practice.get import router as get_router
from app.routes.attempt.practice.group import router as group_router
from app.routes.attempt.practice.problem import router as problem_router
from app.routes.attempt.practice.refresh import router as refresh_router
from app.routes.attempt.practice.search import router as search_router

router = APIRouter(prefix="/practice", tags=["practice"])

router.include_router(get_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(context_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(group_router)
router.include_router(problem_router)
