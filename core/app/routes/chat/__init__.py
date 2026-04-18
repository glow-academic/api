"""Chat analytics helpers — get, refresh, export.

NOTE: draft.py and drafts.py moved to routes/attempt/.
context.py and group.py removed — use parent /attempt/context and /attempt/group.
"""

from fastapi import APIRouter

from app.routes.chat.export import router as export_router
from app.routes.chat.get import router as get_router
from app.routes.chat.refresh import router as refresh_router

router = APIRouter(prefix="/chat", tags=["chat"])

router.include_router(get_router)
router.include_router(export_router)
router.include_router(refresh_router)
