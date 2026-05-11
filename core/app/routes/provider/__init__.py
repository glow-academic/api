"""Provider v4 router."""

from fastapi import APIRouter

from app.routes.provider.context import router as context_router
from app.routes.provider.create import router as create_router
from app.routes.provider.csv import router as csv_router
from app.routes.provider.decrypt import router as decrypt_router
from app.routes.provider.delete import router as delete_router
from app.routes.provider.draft import router as draft_router
from app.routes.provider.drafts import router as drafts_router
from app.routes.provider.duplicate import router as duplicate_router
from app.routes.provider.export import router as export_router
from app.routes.provider.file import router as file_router
from app.routes.provider.generate import router as generate_router
from app.routes.provider.generations import router as generations_router
from app.routes.provider.get import router as get_router
from app.routes.provider.group import router as group_router
from app.routes.provider.problem import router as problem_router
from app.routes.provider.refresh import router as refresh_router
from app.routes.provider.search import router as search_router
from app.routes.provider.stream import router as stream_router
from app.routes.provider.update import router as update_router
from app.routes.provider.text import router as text_router
from app.routes.provider.call import router as call_router

router = APIRouter(prefix="/provider", tags=["provider"])

# Include all endpoint routers (standard 6 endpoints)
router.include_router(search_router)
router.include_router(get_router)
router.include_router(create_router)
router.include_router(update_router)
router.include_router(duplicate_router)
router.include_router(delete_router)
router.include_router(draft_router)
router.include_router(drafts_router)
router.include_router(context_router)
router.include_router(export_router)
router.include_router(csv_router)
router.include_router(refresh_router)
router.include_router(decrypt_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(group_router)
router.include_router(problem_router)
router.include_router(stream_router)

# Typed media operations
router.include_router(text_router)
router.include_router(file_router)
router.include_router(call_router)
