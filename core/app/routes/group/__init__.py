"""Group v4 router."""

from fastapi import APIRouter

from app.routes.group.generate import router as generate_router
from app.routes.group.group import router as group_group_router
from app.routes.group.search import router as search_router
from app.routes.group.audio import router as audio_router
from app.routes.group.call import router as call_router
from app.routes.group.docs import router as docs_router
from app.routes.group.export import router as export_router
from app.routes.group.file import router as file_router
from app.routes.group.get import router as get_router
from app.routes.group.image import router as image_router
from app.routes.group.name import router as name_router
from app.routes.group.refresh import router as refresh_router
from app.routes.group.text import router as text_router
from app.routes.group.video import router as video_router

router = APIRouter(prefix="/group", tags=["group"])

# Standard operations
router.include_router(get_router)
router.include_router(search_router)
router.include_router(refresh_router)
router.include_router(docs_router)
router.include_router(export_router)

# Group-specific operations
router.include_router(generate_router)
router.include_router(group_group_router)
router.include_router(name_router)

# Typed media operations
router.include_router(image_router)
router.include_router(video_router)
router.include_router(text_router)
router.include_router(file_router)
router.include_router(audio_router)
router.include_router(call_router)
