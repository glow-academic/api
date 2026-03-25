"""Leaderboard artifact router."""

from fastapi import APIRouter

from app.routes.leaderboard.docs import router as docs_router
from app.routes.leaderboard.export import router as export_router
from app.routes.leaderboard.get import router as get_router
from app.routes.leaderboard.refresh import router as refresh_router
from app.routes.leaderboard.search import router as search_router

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])
router.include_router(get_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(docs_router)
