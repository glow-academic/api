"""Leaderboard artifact router."""

from fastapi import APIRouter

from app.routes.attempt.leaderboard.get import router as get_router
from app.routes.attempt.leaderboard.search import router as search_router

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])
router.include_router(get_router)
router.include_router(search_router)
