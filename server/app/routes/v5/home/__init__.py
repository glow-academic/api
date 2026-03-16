"""Home artifact router."""

from fastapi import APIRouter

from app.routes.v5.home.docs import router as docs_router
from app.routes.v5.home.export import router as export_router
from app.routes.v5.home.get import router as get_router
from app.routes.v5.home.refresh import router as refresh_router
from app.routes.v5.home.search import router as search_router

router = APIRouter(prefix="/home", tags=["home"])

router.include_router(get_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(docs_router)
