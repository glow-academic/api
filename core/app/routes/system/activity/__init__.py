"""Activity artifact router."""

from fastapi import APIRouter

from app.routes.system.activity.context import router as context_router
from app.routes.system.activity.export import router as export_router
from app.routes.system.activity.generate import router as generate_router
from app.routes.system.activity.generations import router as generations_router
from app.routes.system.activity.get import router as get_router
from app.routes.system.activity.group import router as group_router
from app.routes.system.activity.problem import router as problem_router
from app.routes.system.activity.refresh import router as refresh_router
from app.routes.system.activity.resolve import router as resolve_router
from app.routes.system.activity.search import router as search_router

router = APIRouter(prefix="/activity", tags=["activity"])
router.include_router(get_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(resolve_router)
router.include_router(export_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(context_router)
router.include_router(group_router)
router.include_router(problem_router)
