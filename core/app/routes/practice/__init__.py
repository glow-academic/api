"""Practice artifact router."""

from fastapi import APIRouter

from app.routes.practice.docs import router as docs_router
from app.routes.practice.export import router as export_router
from app.routes.practice.get import router as get_router
from app.routes.practice.group import router as group_router
from app.routes.practice.refresh import router as refresh_router
from app.routes.practice.search import router as search_router

router = APIRouter(prefix="/practice", tags=["practice"])

router.include_router(get_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(docs_router)
router.include_router(group_router)
