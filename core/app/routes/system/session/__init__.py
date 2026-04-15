"""Session artifact router."""

from fastapi import APIRouter

from app.routes.system.session.context import router as context_router
from app.routes.system.session.export import router as export_router
from app.routes.system.session.generate import router as generate_router
from app.routes.system.session.generations import router as generations_router
from app.routes.system.session.get import router as get_router
from app.routes.system.session.group import router as group_router
from app.routes.system.session.problem import router as problem_router
from app.routes.system.session.refresh import router as refresh_router

router = APIRouter(prefix="/session", tags=["session"])

router.include_router(get_router)
router.include_router(refresh_router)
router.include_router(context_router)
router.include_router(export_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(group_router)
router.include_router(problem_router)
