"""{artifact.title()} v4 router."""

from fastapi import APIRouter

from app.routes.department.context import router as context_router
from app.routes.department.create import router as create_router
from app.routes.department.csv import router as csv_router
from app.routes.department.delete import router as delete_router
from app.routes.department.draft import router as draft_router
from app.routes.department.drafts import router as drafts_router
from app.routes.department.duplicate import router as duplicate_router
from app.routes.department.export import router as export_router
from app.routes.department.file_download import router as file_download_router
from app.routes.department.generate import router as generate_router
from app.routes.department.generations import router as generations_router
from app.routes.department.get import router as get_router
from app.routes.department.group import router as group_router
from app.routes.department.problem import router as problem_router
from app.routes.department.refresh import router as refresh_router
from app.routes.department.search import router as search_router
from app.routes.department.watch import router as watch_router
from app.routes.department.update import router as update_router
from app.routes.department.text_download import router as text_download_router
from app.routes.department.call_download import router as call_download_router
from app.routes.department.title import router as title_router

router = APIRouter(prefix="/department", tags=["department"])

# Include all endpoint routers
router.include_router(title_router)
router.include_router(get_router)
router.include_router(search_router)
router.include_router(create_router)
router.include_router(update_router)
router.include_router(duplicate_router)
router.include_router(delete_router)
router.include_router(draft_router)
router.include_router(drafts_router)
router.include_router(context_router)
router.include_router(export_router)
router.include_router(csv_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(group_router)
router.include_router(problem_router)
router.include_router(refresh_router)
router.include_router(watch_router)

# Typed media operations
router.include_router(text_download_router)
router.include_router(file_download_router)
router.include_router(call_download_router)
