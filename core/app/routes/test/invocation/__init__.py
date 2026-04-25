"""Invocation artifact router."""

from fastapi import APIRouter

from app.routes.test.invocation.create import router as create_router
from app.routes.test.invocation.decrypt import router as decrypt_router
from app.routes.test.invocation.draft import router as draft_router
from app.routes.test.invocation.drafts import router as drafts_router
from app.routes.test.invocation.export import router as export_router
from app.routes.test.invocation.get import router as get_router
from app.routes.test.invocation.refresh import router as refresh_router

router = APIRouter(prefix="/invocation", tags=["invocation"])
router.include_router(get_router)
router.include_router(create_router)
router.include_router(draft_router)
router.include_router(drafts_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(decrypt_router)
