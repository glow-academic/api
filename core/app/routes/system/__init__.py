"""System operational router — context, generate, generations, group, problem + child sub-routers + media."""

from fastapi import APIRouter

# Child sub-routers (VIEW artifacts absorbed into system)
from app.routes.system.activity import router as activity_router
from app.routes.system.title import router as title_router

# Media operations (promoted from group to system level)
from app.routes.system.audio_download import router as audio_download_router
from app.routes.system.call_download import router as call_download_router

# Top-level system operations
from app.routes.system.context import router as context_router
from app.routes.system.export import router as export_router
from app.routes.system.file_download import router as file_download_router
from app.routes.system.file_preview import router as file_preview_router
from app.routes.system.generate import router as generate_router
from app.routes.system.generations import router as generations_router
from app.routes.system.group import router as group_router
from app.routes.system.groups import router as groups_router
from app.routes.system.health import router as health_router
from app.routes.system.image_download import router as image_download_router
from app.routes.system.pricing import router as pricing_router
from app.routes.system.problem import router as problem_router
from app.routes.system.refresh import router as refresh_router
from app.routes.system.resolve import router as resolve_router
from app.routes.system.session import router as session_router
from app.routes.system.sessions import router as sessions_router
from app.routes.system.watch import router as watch_router
from app.routes.system.text_download import router as text_download_router
from app.routes.system.video_download import router as video_download_router

router = APIRouter(prefix="/system", tags=["system"])

# Top-level system operations
router.include_router(title_router)
router.include_router(context_router)
router.include_router(export_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(groups_router)      # paginated groups list (was /pricing/search)
router.include_router(sessions_router)    # paginated sessions list (was /activity/search)
router.include_router(resolve_router)     # problem resolve (was /activity/resolve)
router.include_router(problem_router)
router.include_router(refresh_router)
router.include_router(watch_router)

# Child sub-routers
router.include_router(group_router)      # prefix="/group"
router.include_router(session_router)    # prefix="/session"
router.include_router(health_router)     # prefix="/health"
router.include_router(activity_router)   # prefix="/activity"
router.include_router(pricing_router)    # prefix="/pricing"

# Media operations (system-level, not nested under group)
router.include_router(audio_download_router)
router.include_router(call_download_router)
router.include_router(file_download_router)
router.include_router(file_preview_router)
router.include_router(image_download_router)
router.include_router(text_download_router)
router.include_router(video_download_router)
