"""Group artifact router."""

from fastapi import APIRouter

from app.routes.v5.group.docs import router as docs_router
from app.routes.v5.group.download import router as download_router
from app.routes.v5.group.export import router as export_router
from app.routes.v5.group.get import router as get_router
from app.routes.v5.group.refresh import router as refresh_router

router = APIRouter(prefix="/group", tags=["group"])

router.include_router(get_router)
router.include_router(refresh_router)
router.include_router(docs_router)
router.include_router(export_router)

# Unified download
router.include_router(download_router)
