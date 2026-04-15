"""Chat analytics helpers — get, group, refresh, export, context.

NOTE: draft.py and drafts.py moved to routes/attempt/.
This module is NOT route-mounted but infra still imports individual files.
"""

from fastapi import APIRouter

from app.routes.chat.context import router as context_router
from app.routes.chat.export import router as export_router
from app.routes.chat.get import router as get_router
from app.routes.chat.group import router as group_router
from app.routes.chat.refresh import router as refresh_router

router = APIRouter(prefix="/chat", tags=["chat"])

router.include_router(get_router)
router.include_router(group_router)
router.include_router(export_router)
router.include_router(refresh_router)
router.include_router(context_router)
