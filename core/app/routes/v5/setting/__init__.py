"""Setting v4 router."""

from fastapi import APIRouter

from app.routes.v5.setting.create import router as create_router
from app.routes.v5.setting.csv import router as csv_router
from app.routes.v5.setting.decrypt import router as decrypt_router
from app.routes.v5.setting.delete import router as delete_router
from app.routes.v5.setting.docs import router as docs_router
from app.routes.v5.setting.draft import router as draft_router
from app.routes.v5.setting.drafts import router as drafts_router
from app.routes.v5.setting.duplicate import router as duplicate_router
from app.routes.v5.setting.export import router as export_router
from app.routes.v5.setting.get import router as get_router
from app.routes.v5.setting.refresh import router as refresh_router
from app.routes.v5.setting.search import router as search_router
from app.routes.v5.setting.update import router as update_router

router = APIRouter(prefix="/settings", tags=["settings"])

# Include all endpoint routers
router.include_router(search_router)
router.include_router(get_router)
router.include_router(create_router)
router.include_router(update_router)
router.include_router(duplicate_router)
router.include_router(delete_router)
router.include_router(draft_router)
router.include_router(drafts_router)
router.include_router(export_router)
router.include_router(csv_router)
router.include_router(docs_router)
router.include_router(refresh_router)
router.include_router(decrypt_router)
