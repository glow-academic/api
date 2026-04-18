"""Group sub-router — group detail operations under /system/group/."""

from fastapi import APIRouter

from app.routes.system.group.export import router as export_router
from app.routes.system.group.get import router as get_router
from app.routes.system.group.name import router as name_router
from app.routes.system.group.refresh import router as refresh_router
from app.routes.system.group.search import router as search_router

router = APIRouter(prefix="/group", tags=["group"])

router.include_router(get_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(name_router)
