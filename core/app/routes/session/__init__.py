"""Session artifact router."""

from fastapi import APIRouter

from app.routes.session.context import router as context_router
from app.routes.session.docs import router as docs_router
from app.routes.session.export import router as export_router
from app.routes.session.generate import router as generate_router
from app.routes.session.generations import router as generations_router
from app.routes.session.get import router as get_router
from app.routes.session.group import router as group_router
from app.routes.session.problem import router as problem_router
from app.routes.session.refresh import router as refresh_router

router = APIRouter(prefix="/session", tags=["session"])

router.include_router(get_router)
router.include_router(refresh_router)
router.include_router(docs_router)
router.include_router(context_router)
router.include_router(export_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(group_router)
router.include_router(problem_router)
