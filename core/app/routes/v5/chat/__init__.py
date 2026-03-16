"""Unified chat analytics router (home + practice via practice: bool)."""

from fastapi import APIRouter

from app.routes.v5.chat.docs import router as docs_router
from app.routes.v5.chat.draft import router as draft_router
from app.routes.v5.chat.drafts import router as drafts_router
from app.routes.v5.chat.export import router as export_router
from app.routes.v5.chat.get import router as get_router
from app.routes.v5.chat.refresh import router as refresh_router

router = APIRouter(prefix="/chat", tags=["chat"])

router.include_router(get_router)
router.include_router(draft_router)
router.include_router(drafts_router)
router.include_router(export_router)
router.include_router(refresh_router)
router.include_router(docs_router)
