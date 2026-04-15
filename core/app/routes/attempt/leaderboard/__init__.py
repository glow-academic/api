"""Leaderboard artifact router."""

from fastapi import APIRouter

from app.routes.attempt.leaderboard.context import router as context_router
from app.routes.attempt.leaderboard.export import router as export_router
from app.routes.attempt.leaderboard.generate import router as generate_router
from app.routes.attempt.leaderboard.generations import router as generations_router
from app.routes.attempt.leaderboard.get import router as get_router
from app.routes.attempt.leaderboard.group import router as group_router
from app.routes.attempt.leaderboard.problem import router as problem_router
from app.routes.attempt.leaderboard.refresh import router as refresh_router
from app.routes.attempt.leaderboard.search import router as search_router

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])
router.include_router(get_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(context_router)
router.include_router(group_router)
router.include_router(problem_router)
